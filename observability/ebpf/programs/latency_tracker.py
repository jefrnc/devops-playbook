#!/usr/bin/env python3
"""
eBPF-based Latency Tracker for Lead Time Metrics
Tracks request latencies through the system
"""

import time
import json
from datetime import datetime
from collections import defaultdict
from bcc import BPF
from prometheus_client import Histogram, Summary, start_http_server

# eBPF program for latency tracking
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/tcp.h>
#include <net/sock.h>
#include <bcc/proto.h>

// Request tracking structure
struct request_t {
    u64 start_ns;
    u64 end_ns;
    u32 pid;
    u32 tid;
    u16 sport;
    u16 dport;
    u32 saddr;
    u32 daddr;
    char http_method[8];
    char http_path[128];
    u16 http_status;
    u8 completed;
};

// Latency histogram buckets (in microseconds)
struct hist_key {
    char service[32];
    char endpoint[64];
    u16 status_code;
};

// Maps
BPF_HASH(requests, u64, struct request_t);  // Track active requests
BPF_HISTOGRAM(latency_hist, struct hist_key);  // Latency histogram
BPF_PERF_OUTPUT(latency_events);  // Send events to userspace

// Helper to generate request ID
static inline u64 gen_request_id(u32 pid, u16 sport, u16 dport) {
    return ((u64)pid << 32) | ((u64)sport << 16) | dport;
}

// Trace HTTP request start (via accept syscall)
int trace_accept_return(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    
    struct sock *sk = (struct sock *)PT_REGS_RC(ctx);
    if (!sk) return 0;
    
    u16 sport = sk->__sk_common.skc_num;
    u16 dport = sk->__sk_common.skc_dport;
    dport = ntohs(dport);
    
    // Only track HTTP ports
    if (sport != 80 && sport != 8080 && sport != 443 && sport != 8443) {
        return 0;
    }
    
    u64 req_id = gen_request_id(pid, sport, dport);
    struct request_t req = {};
    req.start_ns = ts;
    req.pid = pid;
    req.tid = bpf_get_current_pid_tgid() & 0xFFFFFFFF;
    req.sport = sport;
    req.dport = dport;
    
    requests.update(&req_id, &req);
    return 0;
}

// Trace HTTP request completion (via close syscall)
int trace_close_entry(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    
    // Look for matching request
    struct request_t *req = NULL;
    u64 req_id = 0;
    
    // Iterate through possible request IDs (simplified)
    for (u16 p = 8000; p < 9000; p++) {
        req_id = gen_request_id(pid, 8080, p);
        req = requests.lookup(&req_id);
        if (req && !req->completed) {
            break;
        }
    }
    
    if (!req) return 0;
    
    req->end_ns = ts;
    req->completed = 1;
    
    // Calculate latency
    u64 latency_us = (req->end_ns - req->start_ns) / 1000;
    
    // Update histogram
    struct hist_key key = {};
    __builtin_memcpy(key.service, "api-service", 12);
    __builtin_memcpy(key.endpoint, "/api/metrics", 13);
    key.status_code = 200;
    
    latency_hist.increment(key, latency_us);
    
    // Send event to userspace
    latency_events.perf_submit(ctx, req, sizeof(*req));
    
    // Clean up
    requests.delete(&req_id);
    
    return 0;
}

// Trace database queries (via network send to DB port)
int trace_tcp_sendmsg(struct pt_regs *ctx, struct sock *sk,
                      struct msghdr *msg, size_t size) {
    if (!sk) return 0;
    
    u16 dport = sk->__sk_common.skc_dport;
    dport = ntohs(dport);
    
    // Track PostgreSQL (5432) and MySQL (3306) queries
    if (dport != 5432 && dport != 3306) {
        return 0;
    }
    
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    
    struct request_t req = {};
    req.start_ns = ts;
    req.pid = pid;
    req.dport = dport;
    
    if (dport == 5432) {
        __builtin_memcpy(req.http_method, "QUERY", 6);
        __builtin_memcpy(req.http_path, "postgresql", 11);
    } else {
        __builtin_memcpy(req.http_method, "QUERY", 6);
        __builtin_memcpy(req.http_path, "mysql", 6);
    }
    
    u64 req_id = gen_request_id(pid, 0, dport);
    requests.update(&req_id, &req);
    
    return 0;
}
"""

class LatencyTracker:
    def __init__(self):
        # Load eBPF program
        self.bpf = BPF(text=bpf_program)
        
        # Attach probes
        self.bpf.attach_kretprobe(event="__sys_accept4", fn_name="trace_accept_return")
        self.bpf.attach_kprobe(event="__sys_close", fn_name="trace_close_entry")
        self.bpf.attach_kprobe(event="tcp_sendmsg", fn_name="trace_tcp_sendmsg")
        
        # Metrics
        self.http_latency = Histogram(
            'dora_http_request_duration_seconds',
            'HTTP request latency',
            ['method', 'endpoint', 'status', 'service'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
        )
        
        self.db_latency = Histogram(
            'dora_database_query_duration_seconds',
            'Database query latency',
            ['database', 'operation', 'service'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
        )
        
        self.lead_time = Summary(
            'dora_lead_time_seconds',
            'Lead time from commit to deployment',
            ['service', 'environment']
        )
        
        # Tracking
        self.latency_buffer = defaultdict(list)
        self.service_endpoints = self.load_service_mapping()
        
    def load_service_mapping(self):
        """Load service to endpoint mapping"""
        # In production, this would be loaded from config or service mesh
        return {
            8080: {'service': 'api-service', 'endpoints': [
                '/api/deployments',
                '/api/metrics',
                '/api/health'
            ]},
            3000: {'service': 'web-frontend', 'endpoints': [
                '/',
                '/dashboard',
                '/metrics'
            ]},
            9090: {'service': 'prometheus', 'endpoints': [
                '/metrics',
                '/api/v1/query'
            ]}
        }
    
    def process_latency_event(self, cpu, data, size):
        """Process latency event from eBPF"""
        event = self.bpf["latency_events"].event(data)
        
        latency_ms = (event.end_ns - event.start_ns) / 1e6
        latency_s = latency_ms / 1000
        
        # Determine service and endpoint
        service_info = self.service_endpoints.get(event.sport, {
            'service': 'unknown',
            'endpoints': ['/unknown']
        })
        
        service = service_info['service']
        endpoint = event.http_path.decode('utf-8', 'replace') or '/unknown'
        method = event.http_method.decode('utf-8', 'replace') or 'GET'
        status = event.http_status or 200
        
        # Update metrics
        if event.dport in [5432, 3306]:  # Database query
            db_type = 'postgresql' if event.dport == 5432 else 'mysql'
            self.db_latency.labels(
                database=db_type,
                operation='query',
                service=service
            ).observe(latency_s)
            
            print(f"[DB Query] {db_type} - {latency_ms:.2f}ms")
        else:  # HTTP request
            self.http_latency.labels(
                method=method,
                endpoint=endpoint,
                status=str(status),
                service=service
            ).observe(latency_s)
            
            print(f"[HTTP] {method} {endpoint} - {status} - {latency_ms:.2f}ms")
        
        # Track for lead time calculation
        self.update_lead_time(service, latency_ms)
    
    def update_lead_time(self, service, latency_ms):
        """Update lead time metrics"""
        # Simplified lead time calculation
        # In production, this would track from commit to deployment
        self.latency_buffer[service].append(latency_ms)
        
        # Calculate rolling lead time every 100 requests
        if len(self.latency_buffer[service]) >= 100:
            avg_latency = sum(self.latency_buffer[service]) / len(self.latency_buffer[service])
            
            # Simulate lead time (latency * factor for demo)
            lead_time_minutes = (avg_latency * 60) / 1000  # Convert to minutes
            
            self.lead_time.labels(
                service=service,
                environment='production'
            ).observe(lead_time_minutes * 60)  # Convert to seconds
            
            # Clear buffer
            self.latency_buffer[service] = []
    
    def print_histogram(self):
        """Print latency histogram from eBPF"""
        print("\n=== Latency Histogram ===")
        hist = self.bpf["latency_hist"]
        
        for k, v in sorted(hist.items(), key=lambda x: x[1].value):
            service = k.service.decode('utf-8', 'replace')
            endpoint = k.endpoint.decode('utf-8', 'replace')
            
            if v.value > 0:
                print(f"{service} {endpoint} [{k.status_code}]: {v.value} requests")
        
        hist.clear()
        print("========================\n")
    
    def run(self):
        """Main loop"""
        # Start Prometheus metrics server
        start_http_server(9091)
        print("Prometheus metrics available at :9091/metrics")
        
        # Attach event processor
        self.bpf["latency_events"].open_perf_buffer(self.process_latency_event)
        
        print("eBPF Latency Tracker started...")
        print("Tracking HTTP requests and database queries")
        print("Press Ctrl+C to stop\n")
        
        # Main loop
        try:
            while True:
                self.bpf.perf_buffer_poll(timeout=1000)
                
                # Print histogram every 60 seconds
                if int(time.time()) % 60 == 0:
                    self.print_histogram()
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.print_histogram()


def main():
    import os
    if os.geteuid() != 0:
        print("This program requires root privileges or CAP_BPF capability")
        print("Run with: sudo python3 latency_tracker.py")
        return
    
    tracker = LatencyTracker()
    tracker.run()


if __name__ == "__main__":
    main()