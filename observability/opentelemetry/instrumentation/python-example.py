#!/usr/bin/env python3
"""
OpenTelemetry instrumentation example for DORA metrics collection
Shows how to instrument Python applications to send telemetry data
"""

import time
import random
from datetime import datetime
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import Status, StatusCode
from opentelemetry.metrics import set_meter_provider
from opentelemetry.trace import set_tracer_provider
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Configure resource attributes
resource = Resource.create({
    ResourceAttributes.SERVICE_NAME: "dora-metrics-collector",
    ResourceAttributes.SERVICE_VERSION: "1.0.0",
    ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "production",
    "team": "platform-engineering",
    "repository": "devops-playbook"
})

# Configure tracing
trace_provider = TracerProvider(resource=resource)
trace_exporter = OTLPSpanExporter(
    endpoint="localhost:4317",
    insecure=True
)
trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
set_tracer_provider(trace_provider)

# Configure metrics
metric_reader = PeriodicExportingMetricReader(
    exporter=OTLPMetricExporter(
        endpoint="localhost:4317",
        insecure=True
    ),
    export_interval_millis=10000
)
metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
set_meter_provider(metric_provider)

# Get tracer and meter
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create DORA metrics
deployment_counter = meter.create_counter(
    name="dora.deployments.total",
    description="Total number of deployments",
    unit="1"
)

lead_time_histogram = meter.create_histogram(
    name="dora.lead_time.seconds",
    description="Lead time from commit to deployment in seconds",
    unit="s"
)

mttr_histogram = meter.create_histogram(
    name="dora.mttr.minutes",
    description="Mean time to recovery in minutes",
    unit="min"
)

failure_counter = meter.create_counter(
    name="dora.deployments.failed",
    description="Number of failed deployments",
    unit="1"
)

# Instrument HTTP requests automatically
RequestsInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)


class DORAMetricsCollector:
    """Collector that sends DORA metrics with OpenTelemetry"""
    
    def collect_deployment_frequency(self, environment: str, service: str):
        """Record a deployment event"""
        with tracer.start_as_current_span("collect_deployment_frequency") as span:
            span.set_attributes({
                "deployment.environment": environment,
                "deployment.service": service,
                "deployment.timestamp": datetime.utcnow().isoformat()
            })
            
            # Simulate deployment process
            time.sleep(random.uniform(0.1, 0.5))
            
            # Record deployment metric
            deployment_counter.add(
                1,
                {
                    "environment": environment,
                    "service": service,
                    "status": "success"
                }
            )
            
            span.set_status(Status(StatusCode.OK))
            span.add_event("Deployment recorded successfully")
    
    def collect_lead_time(self, commit_sha: str, service: str, commit_time: datetime):
        """Calculate and record lead time"""
        with tracer.start_as_current_span("collect_lead_time") as span:
            deployment_time = datetime.utcnow()
            lead_time_seconds = (deployment_time - commit_time).total_seconds()
            
            span.set_attributes({
                "commit.sha": commit_sha,
                "deployment.service": service,
                "lead_time.seconds": lead_time_seconds
            })
            
            # Record lead time metric
            lead_time_histogram.record(
                lead_time_seconds,
                {
                    "service": service,
                    "repository": "devops-playbook"
                }
            )
            
            # Add span event
            span.add_event(
                "Lead time calculated",
                {
                    "lead_time_hours": lead_time_seconds / 3600
                }
            )
    
    def collect_mttr(self, incident_id: str, service: str, incident_start: datetime):
        """Record incident recovery time"""
        with tracer.start_as_current_span("collect_mttr") as span:
            recovery_time = datetime.utcnow()
            mttr_minutes = (recovery_time - incident_start).total_seconds() / 60
            
            span.set_attributes({
                "incident.id": incident_id,
                "incident.service": service,
                "mttr.minutes": mttr_minutes
            })
            
            # Record MTTR metric
            mttr_histogram.record(
                mttr_minutes,
                {
                    "service": service,
                    "severity": "high"
                }
            )
            
            span.add_event("Incident resolved")
    
    def collect_change_failure_rate(self, deployment_id: str, service: str, failed: bool):
        """Record deployment success/failure"""
        with tracer.start_as_current_span("collect_change_failure_rate") as span:
            span.set_attributes({
                "deployment.id": deployment_id,
                "deployment.service": service,
                "deployment.failed": failed
            })
            
            if failed:
                failure_counter.add(
                    1,
                    {
                        "service": service,
                        "failure_type": "deployment"
                    }
                )
                span.set_status(Status(StatusCode.ERROR, "Deployment failed"))
                span.record_exception(Exception("Deployment failed"))
            else:
                span.set_status(Status(StatusCode.OK))
                
            # Always record total deployments
            deployment_counter.add(
                1,
                {
                    "environment": "production",
                    "service": service,
                    "status": "failed" if failed else "success"
                }
            )


class DORAMetricsProcessor:
    """Process and analyze DORA metrics"""
    
    def __init__(self):
        self.collector = DORAMetricsCollector()
    
    @tracer.start_as_current_span("process_github_webhook")
    def process_github_webhook(self, webhook_data: dict):
        """Process GitHub webhook to extract DORA metrics"""
        span = trace.get_current_span()
        
        try:
            # Extract relevant data
            action = webhook_data.get("action")
            repository = webhook_data.get("repository", {}).get("name")
            
            span.set_attributes({
                "webhook.action": action,
                "webhook.repository": repository
            })
            
            if action == "deployment_created":
                self.collector.collect_deployment_frequency(
                    environment=webhook_data.get("deployment", {}).get("environment", "unknown"),
                    service=repository
                )
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
    
    @tracer.start_as_current_span("calculate_dora_metrics")
    def calculate_all_metrics(self):
        """Calculate all DORA metrics"""
        # This would typically fetch data from various sources
        # For demo purposes, we'll simulate the calculations
        
        # Simulate deployment frequency
        self.collector.collect_deployment_frequency("production", "api-service")
        
        # Simulate lead time
        commit_time = datetime.utcnow()
        commit_time = commit_time.replace(hour=commit_time.hour - 5)  # 5 hours ago
        self.collector.collect_lead_time("abc123", "api-service", commit_time)
        
        # Simulate MTTR
        incident_start = datetime.utcnow()
        incident_start = incident_start.replace(minute=incident_start.minute - 45)  # 45 minutes ago
        self.collector.collect_mttr("INC-123", "api-service", incident_start)
        
        # Simulate change failure rate
        self.collector.collect_change_failure_rate("deploy-456", "api-service", False)


def main():
    """Main function demonstrating OpenTelemetry instrumentation"""
    processor = DORAMetricsProcessor()
    
    # Create a root span for the entire collection process
    with tracer.start_as_current_span("dora_metrics_collection") as span:
        span.set_attributes({
            "collection.type": "scheduled",
            "collection.timestamp": datetime.utcnow().isoformat()
        })
        
        try:
            # Calculate all metrics
            processor.calculate_all_metrics()
            
            # Add custom span event
            span.add_event(
                "Metrics collection completed",
                {
                    "metrics.collected": 4,
                    "duration.seconds": 2.5
                }
            )
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        
    # Ensure all telemetry is exported
    trace_provider.shutdown()
    metric_provider.shutdown()


if __name__ == "__main__":
    main()