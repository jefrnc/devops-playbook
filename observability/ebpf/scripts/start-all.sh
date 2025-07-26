#!/bin/bash
#
# Start all eBPF collectors for DORA metrics
#

set -e

# Check if running with sufficient privileges
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run with root privileges or CAP_BPF capability"
    exit 1
fi

# Verify kernel version
KERNEL_VERSION=$(uname -r | cut -d. -f1,2)
REQUIRED_VERSION="5.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$KERNEL_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Warning: Kernel version $KERNEL_VERSION may not fully support all eBPF features"
    echo "Recommended kernel version: 5.8 or higher"
fi

# Mount debugfs if not already mounted
if ! mountpoint -q /sys/kernel/debug; then
    echo "Mounting debugfs..."
    mount -t debugfs none /sys/kernel/debug
fi

# Mount bpffs if not already mounted
if ! mountpoint -q /sys/fs/bpf; then
    echo "Mounting bpffs..."
    mount -t bpf none /sys/fs/bpf
fi

# Function to start a collector
start_collector() {
    local name=$1
    local script=$2
    local port=$3
    
    echo "Starting $name on port $port..."
    python3 /opt/ebpf/$script > /var/log/$name.log 2>&1 &
    local pid=$!
    
    # Wait for collector to start
    sleep 5
    
    if kill -0 $pid 2>/dev/null; then
        echo "$name started successfully (PID: $pid)"
        echo $pid > /var/run/$name.pid
    else
        echo "Failed to start $name"
        cat /var/log/$name.log
        exit 1
    fi
}

# Create log directory
mkdir -p /var/log /var/run

# Start collectors
start_collector "deployment-tracker" "deployment_tracker.py" 9090
start_collector "latency-tracker" "latency_tracker.py" 9091
start_collector "error-detector" "error_detector.py" 9092

echo ""
echo "All eBPF collectors started successfully!"
echo "Metrics endpoints:"
echo "  - Deployment metrics: http://localhost:9090/metrics"
echo "  - Latency metrics: http://localhost:9091/metrics"
echo "  - Error metrics: http://localhost:9092/metrics"
echo ""

# Function to handle shutdown
shutdown() {
    echo "\nShutting down collectors..."
    
    for pidfile in /var/run/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            if kill -0 $pid 2>/dev/null; then
                kill $pid
                echo "Stopped process $pid"
            fi
            rm -f "$pidfile"
        fi
    done
    
    exit 0
}

# Set up signal handlers
trap shutdown SIGINT SIGTERM

# Monitor collectors
while true; do
    for name in deployment-tracker latency-tracker error-detector; do
        pidfile="/var/run/$name.pid"
        
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            
            if ! kill -0 $pid 2>/dev/null; then
                echo "$name (PID: $pid) died, restarting..."
                
                case $name in
                    deployment-tracker)
                        start_collector "$name" "deployment_tracker.py" 9090
                        ;;
                    latency-tracker)
                        start_collector "$name" "latency_tracker.py" 9091
                        ;;
                    error-detector)
                        start_collector "$name" "error_detector.py" 9092
                        ;;
                esac
            fi
        fi
    done
    
    sleep 30
done