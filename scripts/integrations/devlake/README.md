# Apache DevLake Integration

[Apache DevLake](https://devlake.apache.org/) is an open-source dev data platform that provides actionable insights for engineering teams. This integration allows you to push DORA metrics from our collectors to DevLake.

## Features

- Push deployment data to DevLake via webhooks
- Sync incident data from multiple sources
- Unified DORA metrics dashboard
- Support for multiple data sources

## Prerequisites

- Apache DevLake instance (v0.18+)
- API access to DevLake
- Python 3.8+

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `devlake_config.yaml`:

```yaml
devlake:
  url: http://localhost:8080
  api_key: ${DEVLAKE_API_KEY}
  
connections:
  - name: github
    plugin: github
    endpoint: https://api.github.com
    token: ${GITHUB_TOKEN}
    
  - name: jenkins
    plugin: jenkins
    endpoint: https://jenkins.example.com
    username: ${JENKINS_USER}
    password: ${JENKINS_PASS}

projects:
  - name: main-project
    connections:
      - github
      - jenkins
```

## Usage

### Push Deployment Data

```python
from devlake_integration import DevLakeClient

client = DevLakeClient(config_file='devlake_config.yaml')

# Push deployment event
client.push_deployment({
    'deployment_id': 'deploy-123',
    'commit_sha': 'abc123',
    'environment': 'production',
    'status': 'success',
    'deployed_at': '2024-01-20T10:30:00Z',
    'service': 'api-service'
})
```

### Sync with Our Collectors

```bash
# Sync deployment frequency data
python sync_deployments.py --source deployment_frequency --target devlake

# Sync all DORA metrics
python sync_all_metrics.py --config devlake_config.yaml
```

## Webhook Integration

DevLake can receive deployment data via webhooks:

```bash
curl -X POST http://devlake:8080/api/plugins/webhook/connections/1/deployments \
  -H "Content-Type: application/json" \
  -d '{
    "commit_sha": "abc123",
    "repo_url": "https://github.com/org/repo",
    "environment": "production",
    "result": "SUCCESS",
    "created_date": "2024-01-20T10:30:00Z"
  }'
```

## Dashboard Setup

1. Import the DORA dashboard template:
   ```bash
   curl -X POST http://devlake:3002/api/dashboards/import \
     -H "Content-Type: application/json" \
     -d @templates/devlake-dora-dashboard.json
   ```

2. Configure data sources in Grafana
3. Set up alerts based on DORA thresholds

## Data Mapping

| Our Metric | DevLake Entity | Notes |
|------------|----------------|-------|
| Deployment | cicd_deployment | Includes environment, result, duration |
| Incident | issue | Maps to Jira/GitHub issues |
| Lead Time | Calculated | From commit to deployment |
| CFR | Calculated | Failed deployments / total |

## Advantages of DevLake

- **Unified Platform**: Consolidates data from multiple sources
- **Historical Analysis**: Built-in data lake for trend analysis  
- **Customizable**: Flexible dashboard and metric definitions
- **Open Source**: No vendor lock-in, community support

## Troubleshooting

### Connection Issues
```bash
# Test DevLake API
curl http://devlake:8080/api/health

# Check plugin status
curl http://devlake:8080/api/plugins
```

### Data Not Showing
1. Verify data collection tasks completed
2. Check transformation rules
3. Ensure Grafana data source is configured

## Contributing

See [CONTRIBUTING.md](../../../CONTRIBUTING.md) for guidelines.
