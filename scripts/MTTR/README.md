# MTTR (Mean Time to Recovery) Calculator

## Overview
This tool calculates the Mean Time to Recovery (MTTR) metric, one of the four key DORA metrics. MTTR measures how quickly teams can recover from failures in production, directly impacting customer experience and system reliability.

## Features
- Multiple incident management platform support:
  - PagerDuty
  - OpsGenie
  - AWS CloudWatch Alarms
- Severity-based analysis
- Service-level MTTR tracking
- Statistical analysis with percentiles
- Trend analysis over time
- Performance level classification

## Prerequisites
- Python 3.8+
- API access to your incident management platform

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `config.yaml` file:

```yaml
# Incident source: pagerduty, opsgenie, cloudwatch
incident_source: pagerduty

time_range:
  start_date: "30d"
  end_date: "now"

# Optional: Filter by severity
severity_filter: ["P1", "P2"]

pagerduty:
  api_key: ${PAGERDUTY_TOKEN}
```

## Usage

```bash
# Generate report
python mttr_calculator.py

# Export as JSON
python mttr_calculator.py --output json --output-file mttr.json

# With custom config
python mttr_calculator.py --config production_config.yaml
```

## Understanding MTTR

### Calculation
```
MTTR = (Incident Resolved Time - Incident Created Time) / Number of Incidents
```

### Performance Levels
| Level | MTTR |
|-------|------|
| Elite | Less than one hour |
| High | Less than one day |
| Medium | Less than one week |
| Low | More than one week |

### Key Metrics
- **Mean MTTR**: Average recovery time
- **Median MTTR**: Middle value (less affected by outliers)
- **P90/P95**: 90th/95th percentile - worst-case scenarios
- **By Severity**: Breakdown by incident priority
- **By Service**: Identify problematic services

## API Configuration

### PagerDuty
1. Generate API key: https://support.pagerduty.com/docs/api-access-keys
2. Required permissions: Read access to incidents
3. Set environment variable: `export PAGERDUTY_TOKEN=your_token`

### OpsGenie
1. Create API key: Settings → API key management
2. Required permissions: Read access to alerts
3. Set environment variable: `export OPSGENIE_TOKEN=your_token`

### AWS CloudWatch
1. Configure AWS CLI: `aws configure`
2. Required IAM permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "cloudwatch:DescribeAlarmHistory",
         "cloudwatch:DescribeAlarms"
       ],
       "Resource": "*"
     }]
   }
   ```

## Output Example

```
MEAN TIME TO RECOVERY (MTTR) REPORT
==================================================

Period: 2024-01-01T00:00:00 to 2024-01-31T23:59:59

Summary:
  Total Incidents: 47
  Performance Level: High

MTTR Statistics:
  Mean: 145.3 minutes (2.4 hours)
  Median: 87.5 minutes (1.5 hours)
  Min: 5.2 minutes
  Max: 1440.7 minutes
  Std Dev: 234.1 minutes

MTTR by Severity:
┌─────────────┬─────────────┬───────┐
│ Severity    │ Avg Minutes │ Count │
├─────────────┼─────────────┼───────┤
│ P1-Critical │ 45.2        │ 8     │
│ P2-High     │ 132.7       │ 15    │
│ P3-Medium   │ 198.4       │ 24    │
└─────────────┴─────────────┴───────┘
```

## Best Practices

1. **Incident Classification**: Ensure consistent severity classification
2. **Automation**: Integrate with your incident response workflow
3. **Regular Reviews**: Analyze MTTR trends in post-mortems
4. **Service Ownership**: Track MTTR by service and team
5. **Runbooks**: Create runbooks for common incidents to reduce MTTR

## Integration Examples

### Grafana Dashboard
```promql
# Average MTTR by severity
avg by (severity) (incident_recovery_time_minutes)

# MTTR trend
avg_over_time(incident_recovery_time_minutes[7d])
```

### Slack Notification
```yaml
# Send weekly MTTR report
0 9 * * MON python mttr_calculator.py --output json | \
  curl -X POST -H 'Content-type: application/json' \
  --data @- https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Troubleshooting

### No incidents found
- Verify API credentials
- Check time range includes resolved incidents
- Ensure incidents are properly closed in your system

### API rate limits
- PagerDuty: 900 requests/minute
- OpsGenie: 130 requests/minute
- Implement caching for frequent queries
