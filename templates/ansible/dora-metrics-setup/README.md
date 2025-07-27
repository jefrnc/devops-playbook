# DORA Metrics Setup Ansible Playbook

This Ansible playbook automates the deployment and configuration of DORA metrics collectors across your infrastructure.

## Features

- Installs Python-based DORA metrics collectors
- Configures automated metric collection via cron
- Sets up Prometheus exporters
- Integrates with existing monitoring infrastructure
- Includes log rotation and service management

## Prerequisites

- Ansible 2.9+
- Target hosts running Ubuntu/Debian or RHEL/CentOS
- SSH access with sudo privileges
- Prometheus server (optional, for metrics export)

## Quick Start

1. **Clone this repository**
   ```bash
   git clone https://github.com/jefrnc/devops-playbook.git
   cd devops-playbook/templates/ansible/dora-metrics-setup
   ```

2. **Configure inventory**
   ```ini
   # inventory/hosts
   [metrics_collectors]
   collector1.example.com
   collector2.example.com

   [prometheus_servers]
   prometheus.example.com

   [all:vars]
   ansible_python_interpreter=/usr/bin/python3
   ```

3. **Configure variables**
   ```yaml
   # group_vars/all.yml
   github_token: "{{ vault_github_token }}"
   gitlab_token: "{{ vault_gitlab_token }}"
   pagerduty_token: "{{ vault_pagerduty_token }}"
   prometheus_pushgateway_url: "http://prometheus-pushgateway:9091"
   ```

4. **Run the playbook**
   ```bash
   ansible-playbook -i inventory/hosts playbook.yml
   ```

## Configuration Templates

### deployment_frequency_config.j2
```yaml
deployment_source: github
time_range:
  start_date: "30d"
  end_date: "now"
github:
  token: {{ github_token }}
  organization: {{ github_organization }}
  repositories: {{ github_repositories | to_yaml }}
```

### lead_time_config.j2
```yaml
source_type: github
time_range:
  start_date: "30d"
  end_date: "now"
github:
  token: {{ github_token }}
  organization: {{ github_organization }}
  repositories: {{ github_repositories | to_yaml }}
```

## Customization

### Adding New Metrics

1. Create a new configuration template
2. Add the metric to the cron jobs list
3. Update the Python dependencies if needed

### Changing Collection Frequency

Modify the cron job schedules in the playbook:

```yaml
- name: "Collect Deployment Frequency"
  minute: "*/15"  # Every 15 minutes
  hour: "*"
```

### Integration with CI/CD

Add this playbook to your CI/CD pipeline:

```yaml
# .gitlab-ci.yml
deploy_metrics:
  stage: deploy
  script:
    - ansible-playbook -i inventory/production playbook.yml
  only:
    - main
```

## Service Management

The playbook creates systemd services for continuous metric collection:

```bash
# Check service status
systemctl status dora-metrics-exporter

# View logs
journalctl -u dora-metrics-exporter -f

# Restart service
systemctl restart dora-metrics-exporter
```

## Monitoring Integration

### Prometheus Configuration

The playbook automatically configures Prometheus targets. Verify with:

```bash
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="dora_metrics")'
```

### Grafana Dashboards

Import the provided dashboards:
1. Go to Grafana → Import
2. Upload `templates/grafana/dora-dashboard.json`
3. Select your Prometheus datasource

## Troubleshooting

### Metric Collection Failing

1. Check service logs:
   ```bash
   journalctl -u dora-metrics-exporter -n 100
   ```

2. Verify API tokens:
   ```bash
   sudo -u dora-metrics /opt/dora-metrics/devops-playbook/venv/bin/python \
     /opt/dora-metrics/devops-playbook/scripts/DeploymentFrequency/deployment_frequency.py \
     --config /opt/dora-metrics/config/deployment_frequency.yaml
   ```

3. Check cron job execution:
   ```bash
   grep CRON /var/log/syslog | grep dora-metrics
   ```

### Permission Issues

Ensure the metrics user has proper permissions:
```bash
sudo chown -R dora-metrics:dora-metrics /opt/dora-metrics
sudo chmod -R 750 /opt/dora-metrics/config
```

## Security Considerations

- Store sensitive tokens in Ansible Vault
- Use minimal permissions for API tokens
- Restrict network access to metrics endpoints
- Rotate credentials regularly

## Tags

Use tags to run specific parts of the playbook:

```bash
# Only install dependencies
ansible-playbook playbook.yml --tags dependencies

# Only update configuration
ansible-playbook playbook.yml --tags configuration

# Only manage services
ansible-playbook playbook.yml --tags services
```

## Contributing

See the main [CONTRIBUTING.md](../../../CONTRIBUTING.md) for guidelines.
