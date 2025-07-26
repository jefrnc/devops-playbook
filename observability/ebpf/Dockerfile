# eBPF DORA Metrics Collector
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    bpfcc-tools \
    python3-bpfcc \
    libbpf-dev \
    linux-headers-generic \
    clang \
    llvm \
    gcc \
    make \
    pkg-config \
    libelf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install \
    prometheus-client==0.19.0 \
    psutil==5.9.6 \
    requests==2.31.0

# Create directories
RUN mkdir -p /opt/ebpf /sys/fs/bpf

# Copy eBPF programs
COPY programs/*.py /opt/ebpf/
COPY scripts/*.sh /opt/ebpf/

# Make scripts executable
RUN chmod +x /opt/ebpf/*.py /opt/ebpf/*.sh

# Verify BCC installation
RUN python3 -c "from bcc import BPF; print('BCC installed successfully')"

# Default command
CMD ["/bin/bash", "/opt/ebpf/start-all.sh"]