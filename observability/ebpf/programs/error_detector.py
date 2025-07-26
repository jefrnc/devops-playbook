#!/usr/bin/env python3
"""
eBPF-based Error Detector for MTTR and Change Failure Rate
Detects application errors, crashes, and failures at kernel level
"""

import time
import json
import signal
import sys
from datetime import datetime
from collections import defaultdict
from bcc import BPF
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# eBPF program for error detection
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

// Error types
#define ERROR_SEGFAULT 1
#define ERROR_OOM 2
#define ERROR_PANIC 3
#define ERROR_HTTP_5XX 4
#define ERROR_CONNECTION_REFUSED 5
#define ERROR_TIMEOUT 6
#define ERROR_EXCEPTION 7

// Error event structure
struct error_event_t {
    u64 timestamp;
    u32 pid;
    u32 tgid;
    u32 uid;
    u8 error_type;
    u16 error_code;
    char comm[TASK_COMM_LEN];
    char container_id[64];
    char error_msg[128];
};

// Incident tracking
struct incident_t {
    u64 start_time;
    u64 end_time;
    u32 error_count;
    u8 severity;  // 1=low, 2=medium, 3=high, 4=critical
    u8 resolved;
};

// Maps
BPF_HASH(incidents, char[64], struct incident_t);  // Track incidents by service
BPF_PERF_OUTPUT(error_events);  // Send events to userspace
BPF_HASH(error_counts, u32, u64);  // Count errors by type

// Trace segmentation faults
TRACEPOINT_PROBE(signal, signal_generate) {
    if (args->sig != 11) return 0;  // SIGSEGV
    
    struct error_event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.pid = bpf_get_current_pid_tgid() & 0xFFFFFFFF;
    event.tgid = bpf_get_current_pid_tgid() >> 32;
    event.uid = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    event.error_type = ERROR_SEGFAULT;
    event.error_code = 11;
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    __builtin_memcpy(event.error_msg, "Segmentation fault", 19);
    
    // Track incident
    struct incident_t *incident = incidents.lookup(&event.comm);
    if (!incident) {
        struct incident_t new_incident = {};
        new_incident.start_time = event.timestamp;
        new_incident.error_count = 1;
        new_incident.severity = 3;  // High
        incidents.update(&event.comm, &new_incident);
    } else {
        incident->error_count++;
        if (incident->error_count > 5) {
            incident->severity = 4;  // Critical
        }
    }
    
    error_events.perf_submit(args, &event, sizeof(event));
    return 0;
}

// Trace OOM kills
TRACEPOINT_PROBE(oom, oom_score_adj_update) {
    struct error_event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.pid = args->pid;
    event.error_type = ERROR_OOM;
    event.error_code = 137;  // OOM kill exit code
    
    bpf_probe_read_kernel_str(&event.comm, sizeof(event.comm), args->comm);
    __builtin_memcpy(event.error_msg, "Out of memory kill", 19);
    
    error_events.perf_submit(args, &event, sizeof(event));
    return 0;
}

// Trace kernel panics
KPROBE(panic) {
    struct error_event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.error_type = ERROR_PANIC;
    event.error_code = 255;
    
    __builtin_memcpy(event.comm, "kernel", 7);
    __builtin_memcpy(event.error_msg, "Kernel panic", 13);
    
    error_events.perf_submit(ctx, &event, sizeof(event));
    return 0;
}

// Trace HTTP errors (via return codes)
KRETRPROBE(tcp_sendmsg) {
    int ret = PT_REGS_RC(ctx);
    if (ret >= 0) return 0;  // Success
    
    struct error_event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.pid = bpf_get_current_pid_tgid() & 0xFFFFFFFF;
    event.tgid = bpf_get_current_pid_tgid() >> 32;
    
    if (ret == -ECONNREFUSED) {
        event.error_type = ERROR_CONNECTION_REFUSED;
        event.error_code = 111;
        __builtin_memcpy(event.error_msg, "Connection refused", 19);
    } else if (ret == -ETIMEDOUT) {
        event.error_type = ERROR_TIMEOUT;
        event.error_code = 110;
        __builtin_memcpy(event.error_msg, "Connection timeout", 19);
    } else {
        return 0;
    }
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    error_events.perf_submit(ctx, &event, sizeof(event));
    
    // Update error count
    u64 *count = error_counts.lookup(&event.error_type);
    if (count) {
        (*count)++;
    } else {
        u64 initial = 1;
        error_counts.update(&event.error_type, &initial);
    }
    
    return 0;
}

// Trace process crashes (abnormal exits)
TRACEPOINT_PROBE(sched, sched_process_exit) {
    struct task_struct *task = (struct task_struct *)args->task;
    if (!task) return 0;
    
    // Check exit code for crashes
    if (task->exit_code == 0) return 0;  // Normal exit
    
    struct error_event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.pid = task->pid;
    event.tgid = task->tgid;
    event.error_type = ERROR_EXCEPTION;
    event.error_code = task->exit_code;
    
    bpf_probe_read_kernel_str(&event.comm, sizeof(event.comm), task->comm);
    
    if (task->exit_code == 139) {
        __builtin_memcpy(event.error_msg, "Segmentation fault (core dumped)", 33);
    } else if (task->exit_code == 134) {
        __builtin_memcpy(event.error_msg, "Aborted (core dumped)", 22);
    } else {
        __builtin_memcpy(event.error_msg, "Abnormal termination", 21);
    }
    
    error_events.perf_submit(args, &event, sizeof(event));
    return 0;
}
"""

class ErrorDetector:
    def __init__(self):
        # Load eBPF program
        self.bpf = BPF(text=bpf_program)
        
        # Metrics
        self.error_counter = Counter(
            'dora_errors_total',
            'Total number of errors detected',
            ['service', 'error_type', 'severity']
        )
        
        self.mttr_histogram = Histogram(
            'dora_mttr_seconds',
            'Mean time to recovery',
            ['service', 'severity'],
            buckets=(60, 300, 600, 1800, 3600, 7200, 14400)
        )
        
        self.incident_gauge = Gauge(
            'dora_active_incidents',
            'Currently active incidents',
            ['service', 'severity']
        )
        
        self.failure_rate = Gauge(
            'dora_change_failure_rate',
            'Change failure rate percentage',
            ['service', 'environment']
        )
        
        # State tracking
        self.incidents = {}
        self.deployment_count = defaultdict(int)
        self.failure_count = defaultdict(int)
        
    def get_severity_label(self, severity):
        """Convert severity number to label"""
        return {1: 'low', 2: 'medium', 3: 'high', 4: 'critical'}.get(severity, 'unknown')
    
    def get_error_type_label(self, error_type):
        """Convert error type to label"""
        return {
            1: 'segfault',
            2: 'oom_kill',
            3: 'kernel_panic',
            4: 'http_5xx',
            5: 'connection_refused',
            6: 'timeout',
            7: 'exception'
        }.get(error_type, 'unknown')
    
    def process_error_event(self, cpu, data, size):
        """Process error event from eBPF"""
        event = self.bpf["error_events"].event(data)
        
        timestamp = datetime.fromtimestamp(event.timestamp / 1e9)
        service = event.comm.decode('utf-8', 'replace')
        error_type = self.get_error_type_label(event.error_type)
        error_msg = event.error_msg.decode('utf-8', 'replace')
        
        # Determine severity based on error type
        severity = 'high' if event.error_type in [1, 2, 3] else 'medium'
        
        print(f"[{timestamp}] ERROR: {service} - {error_type}: {error_msg} "
              f"(PID: {event.pid}, Code: {event.error_code})")
        
        # Update metrics
        self.error_counter.labels(
            service=service,
            error_type=error_type,
            severity=severity
        ).inc()
        
        # Track incident
        incident_key = f"{service}-{error_type}"
        if incident_key not in self.incidents:
            self.incidents[incident_key] = {
                'service': service,
                'error_type': error_type,
                'severity': severity,
                'start_time': event.timestamp,
                'error_count': 1,
                'resolved': False
            }
            
            self.incident_gauge.labels(
                service=service,
                severity=severity
            ).inc()
        else:
            self.incidents[incident_key]['error_count'] += 1
        
        # Update failure rate
        self.update_failure_rate(service)
    
    def update_failure_rate(self, service):
        """Calculate and update change failure rate"""
        # Track as failure
        self.failure_count[service] += 1
        
        # Calculate rate (simplified - in production would track deployments)
        total_changes = self.deployment_count[service] or 100  # Default for demo
        failure_rate = (self.failure_count[service] / total_changes) * 100
        
        self.failure_rate.labels(
            service=service,
            environment='production'
        ).set(failure_rate)
    
    def check_incident_recovery(self):
        """Check for recovered incidents and calculate MTTR"""
        current_time = time.time() * 1e9  # Convert to nanoseconds
        
        for incident_key, incident in list(self.incidents.items()):
            if incident['resolved']:
                continue
            
            # Simple recovery detection: no new errors for 5 minutes
            time_since_start = (current_time - incident['start_time']) / 1e9
            
            if time_since_start > 300:  # 5 minutes
                # Mark as recovered
                incident['resolved'] = True
                recovery_time = time_since_start
                
                print(f"\nIncident RESOLVED: {incident['service']} - "
                      f"{incident['error_type']} (MTTR: {recovery_time:.2f}s)\n")
                
                # Update MTTR metric
                self.mttr_histogram.labels(
                    service=incident['service'],
                    severity=incident['severity']
                ).observe(recovery_time)
                
                # Update incident gauge
                self.incident_gauge.labels(
                    service=incident['service'],
                    severity=incident['severity']
                ).dec()
                
                # Remove from active incidents
                del self.incidents[incident_key]
    
    def print_statistics(self):
        """Print error statistics"""
        print("\n=== Error Statistics ===")
        
        # Get error counts from eBPF
        counts = self.bpf["error_counts"]
        total_errors = 0
        
        for k, v in counts.items():
            error_type = self.get_error_type_label(k.value)
            count = v.value
            total_errors += count
            print(f"{error_type}: {count} errors")
        
        print(f"\nTotal errors detected: {total_errors}")
        print(f"Active incidents: {len([i for i in self.incidents.values() if not i['resolved']])}")
        
        # Print active incidents
        for incident in self.incidents.values():
            if not incident['resolved']:
                duration = (time.time() * 1e9 - incident['start_time']) / 1e9
                print(f"  - {incident['service']}: {incident['error_type']} "
                      f"({incident['error_count']} errors, {duration:.0f}s)")
        
        print("========================\n")
    
    def run(self):
        """Main loop"""
        # Start Prometheus metrics server
        start_http_server(9092)
        print("Prometheus metrics available at :9092/metrics")
        
        # Attach event processor
        self.bpf["error_events"].open_perf_buffer(self.process_error_event)
        
        print("eBPF Error Detector started...")
        print("Detecting crashes, errors, and failures")
        print("Press Ctrl+C to stop\n")
        
        # Main loop
        try:
            last_check = time.time()
            
            while True:
                self.bpf.perf_buffer_poll(timeout=1000)
                
                # Check for incident recovery every 30 seconds
                if time.time() - last_check > 30:
                    self.check_incident_recovery()
                    last_check = time.time()
                
                # Print stats every 60 seconds
                if int(time.time()) % 60 == 0:
                    self.print_statistics()
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.print_statistics()


def main():
    import os
    if os.geteuid() != 0:
        print("This program requires root privileges or CAP_BPF capability")
        print("Run with: sudo python3 error_detector.py")
        return
    
    detector = ErrorDetector()
    detector.run()


if __name__ == "__main__":
    main()