# Monitoring Stack with Prometheus, Grafana, and AlertManager
# Production-ready monitoring infrastructure

terraform {
  required_version = ">= 1.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.0"
    }
  }
}

# Variables
variable "namespace" {
  description = "Kubernetes namespace for monitoring stack"
  type        = string
  default     = "monitoring"
}

variable "grafana_admin_password" {
  description = "Admin password for Grafana"
  type        = string
  sensitive   = true
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for alerts"
  type        = string
  sensitive   = true
  default     = ""
}

variable "storage_class" {
  description = "Storage class for persistent volumes"
  type        = string
  default     = "gp2"
}

# Create namespace
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = var.namespace
    labels = {
      name = var.namespace
    }
  }
}

# Prometheus
resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  version    = "45.7.1"

  values = [
    <<-EOT
    prometheus:
      prometheusSpec:
        retention: 30d
        storageSpec:
          volumeClaimTemplate:
            spec:
              storageClassName: ${var.storage_class}
              accessModes: ["ReadWriteOnce"]
              resources:
                requests:
                  storage: 50Gi
        resources:
          requests:
            memory: 400Mi
            cpu: 100m
          limits:
            memory: 2Gi
            cpu: 1000m
        
        # Service monitors for DORA metrics
        serviceMonitorSelector:
          matchLabels:
            prometheus: kube-prometheus
        
        # Rules for DORA metrics
        additionalScrapeConfigs:
        - job_name: 'deployment-frequency'
          static_configs:
          - targets: ['deployment-tracker:9090']
          metric_relabel_configs:
          - source_labels: [__name__]
            regex: 'deployment_.*'
            action: keep

    grafana:
      enabled: true
      adminPassword: ${var.grafana_admin_password}
      ingress:
        enabled: true
        hosts:
          - grafana.example.com
        tls:
          - secretName: grafana-tls
            hosts:
              - grafana.example.com
      
      # Pre-configured dashboards
      dashboardProviders:
        dashboardproviders.yaml:
          apiVersion: 1
          providers:
          - name: 'default'
            orgId: 1
            folder: 'DevOps'
            type: file
            disableDeletion: false
            editable: true
            options:
              path: /var/lib/grafana/dashboards/default
      
      dashboards:
        default:
          dora-metrics:
            url: https://raw.githubusercontent.com/jefrnc/devops-playbook/main/templates/grafana/dora-dashboard.json
          kubernetes-overview:
            gnetId: 7249
            revision: 1
            datasource: Prometheus

    alertmanager:
      enabled: true
      config:
        global:
          resolve_timeout: 5m
        route:
          group_by: ['alertname', 'cluster', 'service']
          group_wait: 10s
          group_interval: 10s
          repeat_interval: 12h
          receiver: 'default'
          routes:
          - match:
              severity: critical
            receiver: slack-critical
        receivers:
        - name: 'default'
          webhook_configs: []
        - name: 'slack-critical'
          slack_configs:
          - api_url: '${var.slack_webhook_url}'
            channel: '#alerts'
            title: 'Critical Alert'
            text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    EOT
  ]

  depends_on = [kubernetes_namespace.monitoring]
}

# ServiceMonitor for custom metrics
resource "kubernetes_manifest" "deployment_frequency_monitor" {
  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "deployment-frequency"
      namespace = kubernetes_namespace.monitoring.metadata[0].name
      labels = {
        prometheus = "kube-prometheus"
      }
    }
    spec = {
      selector = {
        matchLabels = {
          app = "deployment-tracker"
        }
      }
      endpoints = [{
        port     = "metrics"
        interval = "30s"
        path     = "/metrics"
      }]
    }
  }

  depends_on = [helm_release.prometheus]
}

# Output important values
output "grafana_url" {
  value       = "https://grafana.example.com"
  description = "Grafana dashboard URL"
}

output "prometheus_url" {
  value       = "http://prometheus-kube-prometheus-prometheus.${var.namespace}.svc.cluster.local:9090"
  description = "Prometheus internal URL"
}

output "alertmanager_url" {
  value       = "http://prometheus-kube-prometheus-alertmanager.${var.namespace}.svc.cluster.local:9093"
  description = "AlertManager internal URL"
}