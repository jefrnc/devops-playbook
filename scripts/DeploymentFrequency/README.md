# Deployment Frequency Metric Calculator

## Overview
This script calculates the Deployment Frequency metric, one of the four key DORA (DevOps Research and Assessment) metrics. It tracks how often an organization successfully releases to production.

## Features
- Multiple data source support (GitHub, GitLab, AWS, Jenkins)
- Configurable time ranges and environments
- Export results to JSON, CSV, or Prometheus format
- Automated reporting and alerting
- Historical trend analysis

## Prerequisites
- Python 3.8+
- AWS CLI configured (if using AWS CloudTrail)
- GitHub/GitLab API tokens (if using Git providers)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `config.yaml` file:

```yaml
data_source: github  # Options: github, gitlab, aws, jenkins
time_range:
  start_date: "30d"  # or specific date: "2024-01-01"
  end_date: "now"
environments:
  - production
  - staging
output_format: json  # Options: json, csv, prometheus
github:
  token: ${GITHUB_TOKEN}
  organization: your-org
  repositories:
    - repo1
    - repo2
```

## Usage

```bash
# Basic usage
python deployment_frequency.py

# With custom config
python deployment_frequency.py --config custom_config.yaml

# Export to Prometheus
python deployment_frequency.py --output prometheus --push-gateway http://prometheus:9091

# Generate report
python deployment_frequency.py --report
```

## Output Example

```json
{
  "metric": "deployment_frequency",
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "results": {
    "total_deployments": 145,
    "daily_average": 4.8,
    "by_environment": {
      "production": 89,
      "staging": 56
    },
    "by_service": {
      "api-service": 45,
      "web-frontend": 38,
      "worker-service": 62
    },
    "performance_level": "Elite",
    "trend": "increasing"
  }
}
```

## Performance Levels

| Level | Deployment Frequency |
|-------|---------------------|
| Elite | On-demand (multiple per day) |
| High | Between once per day and once per week |
| Medium | Between once per week and once per month |
| Low | Between once per month and once every six months |

## Integration Examples

### Grafana Dashboard
```promql
# Average daily deployments
rate(deployments_total[1d])

# Deployments by environment
sum by (environment) (increase(deployments_total[1d]))
```

### CI/CD Pipeline Integration
```yaml
# GitHub Actions example
- name: Track Deployment
  uses: ./scripts/DeploymentFrequency
  with:
    action: record
    environment: production
    service: ${{ github.repository }}
```

## Troubleshooting

### Common Issues

1. **No deployments found**
   - Verify your AWS profile/region or API tokens
   - Check the EventName filter matches your deployment events
   - Ensure time range is correct

2. **Authentication errors**
   - Verify AWS credentials: `aws sts get-caller-identity`
   - Check API token permissions

## Contributing
See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.