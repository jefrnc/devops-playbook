# Monitoring Stack Terraform Module

This Terraform module deploys a complete monitoring stack on Kubernetes, including:
- Prometheus for metrics collection
- Grafana for visualization
- AlertManager for alert routing
- Pre-configured DORA metrics dashboards

## Prerequisites

- Kubernetes cluster (1.19+)
- Terraform (1.0+)
- Helm provider configured
- kubectl configured

## Usage

```hcl
module "monitoring" {
  source = "./monitoring-stack"
  
  namespace              = "monitoring"
  grafana_admin_password = var.grafana_password
  slack_webhook_url      = var.slack_webhook
  storage_class          = "gp2"
}
```

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| namespace | Kubernetes namespace | string | monitoring | no |
| grafana_admin_password | Grafana admin password | string | - | yes |
| slack_webhook_url | Slack webhook for alerts | string | "" | no |
| storage_class | Storage class for PVs | string | gp2 | no |

## Outputs

| Name | Description |
|------|-------------|
| grafana_url | External Grafana URL |
| prometheus_url | Internal Prometheus URL |
| alertmanager_url | Internal AlertManager URL |

## DORA Metrics Integration

This module includes pre-configured ServiceMonitors for DORA metrics:

1. **Deployment Frequency**: Tracks deployment events
2. **Lead Time**: Measures commit to deployment time
3. **MTTR**: Monitors incident recovery time
4. **Change Failure Rate**: Tracks deployment failures

## Accessing Grafana

After deployment:

```bash
# Get admin password
kubectl get secret --namespace monitoring prometheus-grafana \
  -o jsonpath="{.data.admin-password}" | base64 --decode

# Port forward (for testing)
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

## Adding Custom Dashboards

Place dashboard JSON files in `templates/grafana/` and reference them:

```hcl
dashboards:
  default:
    my-dashboard:
      url: https://raw.githubusercontent.com/.../my-dashboard.json
```

## Alerting Rules

Example DORA metric alerts are included:
- High change failure rate (>15%)
- MTTR exceeding SLA
- Deployment frequency below target

## Security Considerations

- Enable RBAC for service accounts
- Use network policies to restrict access
- Rotate Grafana admin password regularly
- Secure Prometheus endpoints

## Troubleshooting

### Prometheus not scraping metrics
```bash
kubectl logs -n monitoring prometheus-kube-prometheus-prometheus-0
```

### Grafana login issues
```bash
kubectl exec -n monitoring deployment/prometheus-grafana -- \
  grafana-cli admin reset-admin-password newpassword
```

### Storage issues
Ensure your storage class supports dynamic provisioning:
```bash
kubectl get storageclass
```
