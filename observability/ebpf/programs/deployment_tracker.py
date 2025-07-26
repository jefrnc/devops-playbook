#!/usr/bin/env python3
"""
eBPF-based Deployment Tracker for DORA Metrics
Tracks container lifecycle events to measure deployment frequency
"""

import time
import json
import socket
from datetime import datetime
from collections import defaultdict
from bcc import BPF
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# eBPF program
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <linux/fs.h>

// Event types
#define EVENT_EXEC 1
#define EVENT_EXIT 2
#define EVENT_CONTAINER_START 3
#define EVENT_CONTAINER_STOP 4

// Data structure for events
struct event_t {
    u32 pid;
    u32 ppid;
    u32 uid;
    u64 timestamp;
    u8 event_type;
    char comm[TASK_COMM_LEN];
    char container_id[64];
};

// Maps
BPF_HASH(container_pids, u32, u64);  // Track container PIDs
BPF_PERF_OUTPUT(events);             // Send events to userspace
BPF_HASH(deployment_count, char[64], u64);  // Count deployments by container

// Trace process execution
TRACEPOINT_PROBE(sched, sched_process_exec) {
    struct event_t event = {};
    
    event.pid = bpf_get_current_pid_tgid() >> 32;
    event.ppid = bpf_get_current_task()->real_parent->tgid;
    event.uid = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    event.timestamp = bpf_ktime_get_ns();
    event.event_type = EVENT_EXEC;
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    
    // Check if this is a container process
    if (event.comm[0] == 'd' && event.comm[1] == 'o' && 
        event.comm[2] == 'c' && event.comm[3] == 'k') {
        event.event_type = EVENT_CONTAINER_START;
        
        // Track container PID
        u64 start_time = event.timestamp;
        container_pids.update(&event.pid, &start_time);
        
        // Increment deployment counter
        u64 *count = deployment_count.lookup(event.container_id);
        if (count) {
            (*count)++;
        } else {
            u64 initial = 1;
            deployment_count.update(event.container_id, &initial);
        }
    }
    
    events.perf_submit(args, &event, sizeof(event));
    return 0;
}

// Trace process exit
TRACEPOINT_PROBE(sched, sched_process_exit) {
    struct event_t event = {};
    
    event.pid = bpf_get_current_pid_tgid() >> 32;
    event.timestamp = bpf_ktime_get_ns();
    event.event_type = EVENT_EXIT;
    
    // Check if this was a tracked container
    u64 *start_time = container_pids.lookup(&event.pid);
    if (start_time) {
        event.event_type = EVENT_CONTAINER_STOP;
        container_pids.delete(&event.pid);
        
        bpf_get_current_comm(&event.comm, sizeof(event.comm));
        events.perf_submit(args, &event, sizeof(event));
    }
    
    return 0;
}

// Trace container operations via cgroup events
TRACEPOINT_PROBE(cgroup, cgroup_mkdir) {
    // Track new container cgroups
    char path[256];
    bpf_probe_read_str(&path, sizeof(path), args->path);
    
    // Check if this is a container cgroup
    if (path[0] == '/' && path[1] == 'd' && path[2] == 'o' && 
        path[3] == 'c' && path[4] == 'k' && path[5] == 'e' && path[6] == 'r') {
        struct event_t event = {};
        event.timestamp = bpf_ktime_get_ns();
        event.event_type = EVENT_CONTAINER_START;
        
        // Extract container ID from path
        bpf_probe_read_str(&event.container_id, sizeof(event.container_id), 
                          args->path + 8);  // Skip "/docker/"
        
        events.perf_submit(args, &event, sizeof(event));
    }
    
    return 0;
}
"""

class DeploymentTracker:
    def __init__(self):
        # Load eBPF program
        self.bpf = BPF(text=bpf_program)
        
        # Metrics
        self.deployment_counter = Counter(
            'dora_deployments_total',
            'Total number of deployments',
            ['service', 'environment', 'status']
        )
        
        self.deployment_duration = Histogram(
            'dora_deployment_duration_seconds',
            'Deployment duration in seconds',
            ['service', 'environment'],
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600)
        )
        
        self.active_deployments = Gauge(
            'dora_active_deployments',
            'Currently active deployments',
            ['service', 'environment']
        )
        
        # State tracking
        self.deployments = {}
        self.container_to_service = {}
        
    def process_event(self, cpu, data, size):
        """Process eBPF event"""
        event = self.bpf["events"].event(data)
        
        timestamp = datetime.fromtimestamp(event.timestamp / 1e9)
        container_id = event.container_id.decode('utf-8', 'replace')[:12]
        
        # Determine service from container
        service = self.get_service_from_container(container_id)
        environment = self.get_environment()
        
        if event.event_type == 3:  # Container start
            print(f"[{timestamp}] Deployment started: {service} ({container_id})")
            
            self.deployments[container_id] = {
                'service': service,
                'start_time': event.timestamp,
                'environment': environment
            }
            
            self.deployment_counter.labels(
                service=service,
                environment=environment,
                status='started'
            ).inc()
            
            self.active_deployments.labels(
                service=service,
                environment=environment
            ).inc()
            
        elif event.event_type == 4:  # Container stop
            if container_id in self.deployments:
                deployment = self.deployments[container_id]
                duration = (event.timestamp - deployment['start_time']) / 1e9
                
                print(f"[{timestamp}] Deployment completed: {service} "
                      f"({container_id}) - Duration: {duration:.2f}s")
                
                self.deployment_duration.labels(
                    service=service,
                    environment=environment
                ).observe(duration)
                
                self.deployment_counter.labels(
                    service=service,
                    environment=environment,
                    status='completed'
                ).inc()
                
                self.active_deployments.labels(
                    service=service,
                    environment=environment
                ).dec()
                
                del self.deployments[container_id]
    
    def get_service_from_container(self, container_id):
        """Map container ID to service name"""
        # In production, this would query k8s API or container labels
        # For demo, use simple mapping
        if container_id in self.container_to_service:
            return self.container_to_service[container_id]
        
        # Default mapping based on container ID prefix
        if container_id.startswith('api-'):
            return 'api-service'
        elif container_id.startswith('web-'):
            return 'web-frontend'
        elif container_id.startswith('db-'):
            return 'database'
        else:
            return 'unknown'
    
    def get_environment(self):
        """Determine current environment"""
        # In production, this would read from node labels or config
        hostname = socket.gethostname()
        if 'prod' in hostname:
            return 'production'
        elif 'staging' in hostname:
            return 'staging'
        else:
            return 'development'
    
    def print_stats(self):
        """Print deployment statistics"""
        print("\n=== Deployment Statistics ===")
        print(f"Active deployments: {len(self.deployments)}")
        
        # Get deployment counts from eBPF map
        counts = self.bpf["deployment_count"]
        total_deployments = 0
        
        for k, v in counts.items():
            container_id = k.value.decode('utf-8', 'replace')
            count = v.value
            total_deployments += count
            if count > 0:
                print(f"Container {container_id}: {count} deployments")
        
        print(f"Total deployments tracked: {total_deployments}")
        print("===========================\n")
    
    def run(self):
        """Main loop"""
        # Start Prometheus metrics server
        start_http_server(9090)
        print("Prometheus metrics available at :9090/metrics")
        
        # Attach event processor
        self.bpf["events"].open_perf_buffer(self.process_event)
        
        print("eBPF Deployment Tracker started...")
        print("Tracking container lifecycle events")
        print("Press Ctrl+C to stop\n")
        
        # Main loop
        try:
            while True:
                self.bpf.perf_buffer_poll(timeout=1000)
                
                # Print stats every 30 seconds
                if int(time.time()) % 30 == 0:
                    self.print_stats()
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.print_stats()


def main():
    # Check for root/CAP_BPF
    import os
    if os.geteuid() != 0:
        print("This program requires root privileges or CAP_BPF capability")
        print("Run with: sudo python3 deployment_tracker.py")
        return
    
    tracker = DeploymentTracker()
    tracker.run()


if __name__ == "__main__":
    main()