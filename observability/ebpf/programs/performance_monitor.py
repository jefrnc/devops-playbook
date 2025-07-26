#!/usr/bin/env python3
"""
eBPF-based Performance Monitor
Collects low-level performance metrics for DORA platform
"""

import time
import json
from datetime import datetime
from collections import defaultdict
from bcc import BPF
from prometheus_client import Histogram, Gauge, Counter, start_http_server

# eBPF program for performance monitoring
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/runqueue.h>

// Performance event structure
struct perf_event_t {
    u64 timestamp;
    u32 cpu;
    u32 pid;
    u32 tid;
    char comm[TASK_COMM_LEN];
    u64 runtime_ns;
    u64 wait_time_ns;
    u64 io_time_ns;
    u32 ctx_switches;
    u64 cache_misses;
    u64 page_faults;
};

// CPU utilization tracking
struct cpu_stat_t {
    u64 idle_ns;
    u64 busy_ns;
    u64 iowait_ns;
    u64 irq_ns;
};

// Maps
BPF_HASH(cpu_stats, u32, struct cpu_stat_t);
BPF_HASH(task_stats, u32, struct perf_event_t);
BPF_PERF_OUTPUT(perf_events);
BPF_HISTOGRAM(sched_latency);
BPF_HISTOGRAM(io_latency);

// Track CPU scheduling latency
TRACEPOINT_PROBE(sched, sched_wakeup) {
    u64 ts = bpf_ktime_get_ns();
    u32 pid = args->pid;
    
    struct perf_event_t *task = task_stats.lookup(&pid);
    if (!task) {
        struct perf_event_t new_task = {};
        new_task.timestamp = ts;
        new_task.pid = pid;
        task_stats.update(&pid, &new_task);
    } else {
        task->wait_time_ns = ts;
    }
    
    return 0;
}

// Track context switches
TRACEPOINT_PROBE(sched, sched_switch) {
    u64 ts = bpf_ktime_get_ns();
    u32 prev_pid = args->prev_pid;
    u32 next_pid = args->next_pid;
    
    // Update previous task runtime
    struct perf_event_t *prev_task = task_stats.lookup(&prev_pid);
    if (prev_task && prev_task->timestamp > 0) {
        u64 runtime = ts - prev_task->timestamp;
        prev_task->runtime_ns += runtime;
        prev_task->ctx_switches++;
        
        // Update scheduling latency histogram
        if (prev_task->wait_time_ns > 0) {
            u64 wait_time = ts - prev_task->wait_time_ns;
            sched_latency.increment(bpf_log2l(wait_time / 1000));  // Convert to microseconds
            prev_task->wait_time_ns = 0;
        }
    }
    
    // Start tracking next task
    struct perf_event_t *next_task = task_stats.lookup(&next_pid);
    if (!next_task) {
        struct perf_event_t new_task = {};
        new_task.pid = next_pid;
        bpf_probe_read_kernel_str(&new_task.comm, sizeof(new_task.comm), args->next_comm);
        task_stats.update(&next_pid, &new_task);
        next_task = task_stats.lookup(&next_pid);
    }
    if (next_task) {
        next_task->timestamp = ts;
    }
    
    // Update CPU stats
    u32 cpu = bpf_get_smp_processor_id();
    struct cpu_stat_t *cpu_stat = cpu_stats.lookup(&cpu);
    if (!cpu_stat) {
        struct cpu_stat_t new_stat = {};
        cpu_stats.update(&cpu, &new_stat);
        cpu_stat = cpu_stats.lookup(&cpu);
    }
    
    if (cpu_stat) {
        if (prev_pid == 0) {  // Idle task
            cpu_stat->idle_ns += runtime;
        } else {
            cpu_stat->busy_ns += runtime;
        }
    }
    
    return 0;
}

// Track block I/O latency
TRACEPOINT_PROBE(block, block_rq_complete) {
    u64 latency = args->__data_loc_cmd_len;  // Simplified - get actual latency
    io_latency.increment(bpf_log2l(latency / 1000));
    
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct perf_event_t *task = task_stats.lookup(&pid);
    if (task) {
        task->io_time_ns += latency;
    }
    
    return 0;
}

// Track page faults
TRACEPOINT_PROBE(exceptions, page_fault_user) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct perf_event_t *task = task_stats.lookup(&pid);
    if (task) {
        task->page_faults++;
    }
    return 0;
}

// Periodic performance snapshot
KPROBE(finish_task_switch) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    struct perf_event_t *task = task_stats.lookup(&pid);
    
    if (task && task->runtime_ns > 1000000000) {  // Every 1 second of runtime
        struct perf_event_t event = *task;
        event.cpu = bpf_get_smp_processor_id();
        event.timestamp = bpf_ktime_get_ns();
        
        perf_events.perf_submit(ctx, &event, sizeof(event));
        
        // Reset counters
        task->runtime_ns = 0;
        task->ctx_switches = 0;
        task->page_faults = 0;
    }
    
    return 0;
}
"""

class PerformanceMonitor:
    def __init__(self):
        # Load eBPF program
        self.bpf = BPF(text=bpf_program)
        
        # Metrics
        self.cpu_usage = Gauge(
            'dora_cpu_usage_percent',
            'CPU usage percentage',
            ['cpu', 'mode']
        )
        
        self.sched_latency = Histogram(
            'dora_scheduling_latency_microseconds',
            'Task scheduling latency',
            ['cpu'],
            buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
        )
        
        self.io_latency = Histogram(
            'dora_io_latency_microseconds',
            'I/O operation latency',
            ['device'],
            buckets=(1, 10, 100, 1000, 10000, 100000)
        )
        
        self.context_switches = Counter(
            'dora_context_switches_total',
            'Total context switches',
            ['cpu']
        )
        
        self.page_faults = Counter(
            'dora_page_faults_total',
            'Total page faults',
            ['type']
        )
        
        self.task_runtime = Histogram(
            'dora_task_runtime_seconds',
            'Task runtime distribution',
            ['comm'],
            buckets=(0.001, 0.01, 0.1, 1.0, 10.0)
        )
        
        # State tracking
        self.cpu_count = self.get_cpu_count()
        self.last_cpu_stats = {}
        
    def get_cpu_count(self):
        """Get number of CPUs"""
        import multiprocessing
        return multiprocessing.cpu_count()
    
    def process_perf_event(self, cpu, data, size):
        """Process performance event from eBPF"""
        event = self.bpf["perf_events"].event(data)
        
        comm = event.comm.decode('utf-8', 'replace')
        runtime_s = event.runtime_ns / 1e9
        
        # Update task runtime metric
        if runtime_s > 0:
            self.task_runtime.labels(comm=comm).observe(runtime_s)
        
        # Update context switches
        if event.ctx_switches > 0:
            self.context_switches.labels(cpu=str(event.cpu)).inc(event.ctx_switches)
        
        # Update page faults
        if event.page_faults > 0:
            self.page_faults.labels(type='minor').inc(event.page_faults)
        
        print(f"[PERF] {comm} (PID: {event.pid}) - CPU: {event.cpu}, "
              f"Runtime: {runtime_s:.3f}s, Context switches: {event.ctx_switches}, "
              f"Page faults: {event.page_faults}")
    
    def update_cpu_metrics(self):
        """Update CPU utilization metrics"""
        cpu_stats = self.bpf["cpu_stats"]
        
        for cpu in range(self.cpu_count):
            stats = cpu_stats.get(cpu)
            if not stats:
                continue
            
            # Calculate deltas
            last = self.last_cpu_stats.get(cpu, {
                'idle_ns': 0, 'busy_ns': 0, 'iowait_ns': 0
            })
            
            idle_delta = stats.idle_ns - last['idle_ns']
            busy_delta = stats.busy_ns - last['busy_ns']
            iowait_delta = stats.iowait_ns - last['iowait_ns']
            
            total_delta = idle_delta + busy_delta + iowait_delta
            
            if total_delta > 0:
                idle_pct = (idle_delta / total_delta) * 100
                busy_pct = (busy_delta / total_delta) * 100
                iowait_pct = (iowait_delta / total_delta) * 100
                
                self.cpu_usage.labels(cpu=str(cpu), mode='idle').set(idle_pct)
                self.cpu_usage.labels(cpu=str(cpu), mode='busy').set(busy_pct)
                self.cpu_usage.labels(cpu=str(cpu), mode='iowait').set(iowait_pct)
            
            # Save current stats
            self.last_cpu_stats[cpu] = {
                'idle_ns': stats.idle_ns,
                'busy_ns': stats.busy_ns,
                'iowait_ns': stats.iowait_ns
            }
    
    def update_latency_metrics(self):
        """Update latency histograms"""
        # Scheduling latency
        sched_hist = self.bpf["sched_latency"]
        for k, v in sched_hist.items():
            if v.value > 0:
                latency_us = 2 ** k.value  # Convert from log2
                for _ in range(v.value):
                    self.sched_latency.labels(cpu='all').observe(latency_us)
        sched_hist.clear()
        
        # I/O latency
        io_hist = self.bpf["io_latency"]
        for k, v in io_hist.items():
            if v.value > 0:
                latency_us = 2 ** k.value
                for _ in range(v.value):
                    self.io_latency.labels(device='all').observe(latency_us)
        io_hist.clear()
    
    def print_summary(self):
        """Print performance summary"""
        print("\n=== Performance Summary ===")
        
        # CPU usage
        print("\nCPU Usage:")
        for cpu in range(self.cpu_count):
            if cpu in self.last_cpu_stats:
                print(f"  CPU {cpu}: Busy: {self.cpu_usage._metrics.get(('busy', str(cpu)), 0):.1f}%")
        
        # Top processes by runtime
        print("\nTop Processes by Runtime:")
        task_stats = self.bpf["task_stats"]
        top_tasks = sorted(
            [(k.value, v) for k, v in task_stats.items()],
            key=lambda x: x[1].runtime_ns,
            reverse=True
        )[:10]
        
        for pid, stats in top_tasks:
            if stats.runtime_ns > 0:
                runtime_s = stats.runtime_ns / 1e9
                comm = stats.comm.decode('utf-8', 'replace')
                print(f"  {comm} (PID: {pid}): {runtime_s:.2f}s runtime, "
                      f"{stats.ctx_switches} context switches")
        
        print("==========================\n")
    
    def run(self):
        """Main loop"""
        # Start Prometheus metrics server
        start_http_server(9093)
        print("Prometheus metrics available at :9093/metrics")
        
        # Attach event processor
        self.bpf["perf_events"].open_perf_buffer(self.process_perf_event)
        
        print("eBPF Performance Monitor started...")
        print(f"Monitoring {self.cpu_count} CPUs")
        print("Press Ctrl+C to stop\n")
        
        # Main loop
        try:
            last_update = time.time()
            
            while True:
                self.bpf.perf_buffer_poll(timeout=100)
                
                # Update metrics every 5 seconds
                if time.time() - last_update > 5:
                    self.update_cpu_metrics()
                    self.update_latency_metrics()
                    last_update = time.time()
                
                # Print summary every 30 seconds
                if int(time.time()) % 30 == 0:
                    self.print_summary()
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.print_summary()


def main():
    import os
    if os.geteuid() != 0:
        print("This program requires root privileges or CAP_BPF capability")
        print("Run with: sudo python3 performance_monitor.py")
        return
    
    monitor = PerformanceMonitor()
    monitor.run()


if __name__ == "__main__":
    main()