# Monitoring and Logging

This section covers how to implement monitoring and logging in your applications and infrastructure. We discuss tools like Prometheus and Grafana for monitoring and ELK stack for logging. We also cover best practices for alerting and incident management.

## The Importance of Observability

Observability is the ability to measure the internal states of a system by examining its outputs. In modern distributed systems, observability is crucial for understanding system behavior, troubleshooting issues, and ensuring reliability.

The three pillars of observability are:
- **Metrics**: Numeric measurements collected over time
- **Logs**: Discrete events that happened over time
- **Traces**: The path of a request through your distributed system

## Monitoring with Prometheus and Grafana

### Prometheus Overview

Prometheus is an open-source monitoring and alerting toolkit that has become the de facto standard for Kubernetes monitoring.

**Key Features:**
- Pull-based metrics collection
- Time-series database
- Powerful query language (PromQL)
- Service discovery
- Built-in alerting

**Prometheus Architecture:**
```yaml
# prometheus.yml configuration
global:
  scrape_interval: 15s
  evaluation_interval: 15s

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load rules once and periodically evaluate them
rule_files:
  - "alerts/*.yml"

# Scrape configurations
scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Node exporter for system metrics
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # Application metrics
  - job_name: 'app'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__
```

### Setting Up Application Metrics

#### Example: Node.js Application with Prometheus Metrics
```javascript
const express = require('express');
const promClient = require('prom-client');

const app = express();
const register = new promClient.Registry();

// Default metrics (CPU, memory, etc.)
promClient.collectDefaultMetrics({ register });

// Custom metrics
const httpRequestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.1, 0.5, 1, 2, 5]
});
register.registerMetric(httpRequestDuration);

const httpRequestTotal = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code']
});
register.registerMetric(httpRequestTotal);

// Middleware to track metrics
app.use((req, res, next) => {
  const start = Date.now();
  
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    httpRequestDuration
      .labels(req.method, req.route?.path || req.url, res.statusCode)
      .observe(duration);
    
    httpRequestTotal
      .labels(req.method, req.route?.path || req.url, res.statusCode)
      .inc();
  });
  
  next();
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// Application routes
app.get('/', (req, res) => {
  res.json({ message: 'Hello World' });
});

app.listen(3000, () => {
  console.log('Server running on port 3000');
});
```

#### Example: Python Application with Prometheus Metrics
```python
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, Response
import time

app = Flask(__name__)

# Define metrics
REQUEST_COUNT = Counter(
    'app_requests_total', 
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'app_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

# Decorator to track metrics
def track_metrics(f):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        method = request.method
        endpoint = request.endpoint or 'unknown'
        
        try:
            response = f(*args, **kwargs)
            status = response.status_code
        except Exception as e:
            status = 500
            raise e
        finally:
            duration = time.time() - start_time
            REQUEST_COUNT.labels(method, endpoint, status).inc()
            REQUEST_DURATION.labels(method, endpoint).observe(duration)
        
        return response
    
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/')
@track_metrics
def home():
    return {'message': 'Hello World'}

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Grafana: Visualization and Dashboards

Grafana is the leading open-source platform for monitoring and observability, allowing you to query, visualize, and alert on metrics.

**Docker Compose Setup for Prometheus + Grafana:**
```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./alerts:/etc/prometheus/alerts
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    ports:
      - "9090:9090"
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    networks:
      - monitoring
    depends_on:
      - prometheus

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    ports:
      - "9100:9100"
    networks:
      - monitoring

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    ports:
      - "9093:9093"
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:

networks:
  monitoring:
    driver: bridge
```

**Example Grafana Dashboard JSON:**
```json
{
  "dashboard": {
    "title": "Application Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{route}}"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Response Time",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status_code=~\"5..\"}[5m])",
            "legendFormat": "5xx errors"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

## Logging with the ELK Stack

The ELK Stack (Elasticsearch, Logstash, Kibana) is a popular solution for centralized logging.

### ELK Stack Components

1. **Elasticsearch**: Search and analytics engine
2. **Logstash**: Server-side data processing pipeline
3. **Kibana**: Visualization and exploration tool
4. **Beats**: Lightweight data shippers

**Docker Compose Setup for ELK Stack:**
```yaml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: elasticsearch
    environment:
      - node.name=elasticsearch
      - cluster.name=docker-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - elk

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    container_name: logstash
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
      - ./logstash/config/logstash.yml:/usr/share/logstash/config/logstash.yml
    ports:
      - "5044:5044"
      - "5000:5000/tcp"
      - "5000:5000/udp"
    environment:
      LS_JAVA_OPTS: "-Xmx256m -Xms256m"
    networks:
      - elk
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: kibana
    ports:
      - "5601:5601"
    environment:
      ELASTICSEARCH_URL: http://elasticsearch:9200
      ELASTICSEARCH_HOSTS: '["http://elasticsearch:9200"]'
    networks:
      - elk
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    container_name: filebeat
    user: root
    volumes:
      - ./filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: filebeat -e -strict.perms=false
    networks:
      - elk
    depends_on:
      - elasticsearch
      - logstash

volumes:
  elasticsearch_data:

networks:
  elk:
    driver: bridge
```

**Logstash Configuration (logstash/pipeline/logstash.conf):**
```ruby
input {
  beats {
    port => 5044
  }
  
  tcp {
    port => 5000
    codec => json
  }
}

filter {
  if [kubernetes] {
    mutate {
      add_field => {
        "pod_name" => "%{[kubernetes][pod][name]}"
        "namespace" => "%{[kubernetes][namespace]}"
        "container_name" => "%{[kubernetes][container][name]}"
      }
    }
  }
  
  if [message] =~ /^\{.*\}$/ {
    json {
      source => "message"
      target => "parsed"
    }
  }
  
  grok {
    match => {
      "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:message}"
    }
    overwrite => ["message"]
  }
  
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "logs-%{+YYYY.MM.dd}"
  }
  
  stdout {
    codec => rubydebug
  }
}
```

**Filebeat Configuration (filebeat/filebeat.yml):**
```yaml
filebeat.inputs:
- type: docker
  containers:
    path: "/var/lib/docker/containers"
    stream: "all"
    ids:
      - "*"
  processors:
    - add_docker_metadata:
        host: "unix:///var/run/docker.sock"
    - decode_json_fields:
        fields: ["message"]
        target: "json"
        overwrite_keys: true

- type: log
  enabled: true
  paths:
    - /var/log/*.log
  multiline.pattern: '^\['
  multiline.negate: true
  multiline.match: after

output.logstash:
  hosts: ["logstash:5044"]

processors:
  - add_host_metadata:
      when.not.contains.tags: forwarded
```

## Structured Logging Best Practices

#### Example: Structured Logging in Node.js with Winston
```javascript
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'api-service' },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    }),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

// Logging examples
logger.info('Server started', {
  port: 3000,
  environment: process.env.NODE_ENV
});

logger.error('Database connection failed', {
  error: err.message,
  host: dbConfig.host,
  port: dbConfig.port
});

// Express middleware for request logging
app.use((req, res, next) => {
  const start = Date.now();
  
  res.on('finish', () => {
    logger.info('HTTP Request', {
      method: req.method,
      url: req.url,
      statusCode: res.statusCode,
      duration: Date.now() - start,
      userAgent: req.get('user-agent'),
      ip: req.ip
    });
  });
  
  next();
});
```

#### Example: Structured Logging in Python
```python
import logging
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger

# Configure JSON logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Add custom fields
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['service'] = 'api-service'

# Logging examples
logger.info('Application started', extra={
    'event': 'app_start',
    'version': '1.0.0',
    'environment': 'production'
})

try:
    result = process_data(data)
    logger.info('Data processed successfully', extra={
        'event': 'data_processed',
        'record_count': len(data),
        'duration': processing_time
    })
except Exception as e:
    logger.error('Data processing failed', extra={
        'event': 'data_processing_error',
        'error': str(e),
        'stack_trace': traceback.format_exc()
    })
```

## Alerting Best Practices

### Prometheus Alerting Rules

**Example Alert Rules (alerts/app_alerts.yml):**
```yaml
groups:
  - name: application
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"
          
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
          team: backend
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }} seconds"
          
      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total[5m]) > 0
        for: 5m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Pod {{ $labels.pod }} is crash looping"
          description: "Pod {{ $labels.pod }} has restarted {{ $value }} times in the last 5 minutes"
          
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is {{ $value | humanizePercentage }}"
```

### Alertmanager Configuration

**alertmanager.yml:**
```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'YOUR_SLACK_WEBHOOK_URL'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      continue: true
    - match:
        team: backend
      receiver: 'backend-team'
    - match:
        team: platform
      receiver: 'platform-team'

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#alerts'
        title: 'Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'critical'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
    slack_configs:
      - channel: '#critical-alerts'
        title: 'CRITICAL: {{ .GroupLabels.alertname }}'
        color: 'danger'

  - name: 'backend-team'
    email_configs:
      - to: 'backend-team@company.com'
        headers:
          Subject: 'Backend Alert: {{ .GroupLabels.alertname }}'

  - name: 'platform-team'
    email_configs:
      - to: 'platform-team@company.com'
        headers:
          Subject: 'Platform Alert: {{ .GroupLabels.alertname }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'dev', 'instance']
```

## Distributed Tracing

For microservices architectures, distributed tracing is essential. Tools like Jaeger or Zipkin help track requests across multiple services.

#### Example: OpenTelemetry Setup in Node.js
```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { JaegerExporter } = require('@opentelemetry/exporter-jaeger');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');

const jaegerExporter = new JaegerExporter({
  endpoint: 'http://localhost:14268/api/traces',
});

const sdk = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'api-service',
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
  }),
  traceExporter: jaegerExporter,
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': {
        enabled: false,
      },
    }),
  ],
});

sdk.start();
```

## Monitoring Strategy Best Practices

1. **Define SLIs and SLOs**
   - Service Level Indicators (SLIs): Metrics that matter to users
   - Service Level Objectives (SLOs): Target values for SLIs
   - Error budgets: Allowable downtime based on SLOs

2. **USE Method for Resources**
   - **Utilization**: How busy is the resource?
   - **Saturation**: How much work is queued?
   - **Errors**: Are errors occurring?

3. **RED Method for Services**
   - **Rate**: Requests per second
   - **Errors**: Failed requests
   - **Duration**: Response time

4. **Golden Signals (Google SRE)**
   - Latency
   - Traffic
   - Errors
   - Saturation

5. **Alert Fatigue Prevention**
   - Alert on symptoms, not causes
   - Set appropriate thresholds
   - Use alert grouping and routing
   - Implement escalation policies
   - Regular alert review and tuning

6. **Dashboard Design**
   - Start with overview dashboards
   - Drill down to specific service dashboards
   - Include business metrics
   - Use consistent color schemes
   - Add annotations for deployments and incidents

---

[Back to Main README](./README.md)
