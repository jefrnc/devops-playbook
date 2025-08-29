# Lead Time for Changes Calculator

## Overview
This tool calculates the Lead Time for Changes metric, one of the four key DORA metrics. It measures the time from code commit to production deployment, helping teams understand their delivery velocity.

## Features
- Support for GitHub and GitLab
- Automatic matching of commits to deployments
- Statistical analysis (mean, median, percentiles)
- Performance level classification
- Trend analysis over time
- Multiple output formats

## Prerequisites
- Python 3.8+
- Git provider API tokens (GitHub or GitLab)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `config.yaml` file:

```yaml
source_type: github  # or gitlab

time_range:
  start_date: "30d"
  end_date: "now"

github:
  token: ${GITHUB_TOKEN}
  organization: your-org
  repositories:
    - api-service
    - web-frontend
```

## Usage

```bash
# Generate report
python lead_time.py

# Export as JSON
python lead_time.py --output json --output-file metrics.json

# Export as CSV
python lead_time.py --output csv --output-file metrics.csv

# Custom configuration
python lead_time.py --config custom_config.yaml
```

## Understanding the Metrics

### Lead Time Calculation
Lead time is calculated as:
```text
Lead Time = Deployment Time - Commit Time
```

### Performance Levels

| Level | Lead Time for Changes |
|-------|----------------------|
| Elite | Less than one hour |
| High | Less than one week |
| Medium | Less than one month |
| Low | More than one month |

### Key Statistics
- **Mean**: Average lead time across all deployments
- **Median**: Middle value (less affected by outliers)
- **Percentiles**: P50, P75, P90, P95 for distribution analysis
- **Standard Deviation**: Measure of variability

## Output Example

```text
LEAD TIME FOR CHANGES REPORT
==================================================

Period: 2024-01-01T00:00:00 to 2024-01-31T23:59:59

Summary:
  Total Deployments: 127
  Performance Level: High

Lead Time Statistics:
  Mean: 18.5 hours (0.8 days)
  Median: 12.3 hours (0.5 days)
  Min: 0.5 hours
  Max: 168.2 hours
  Std Dev: 28.4 hours

Percentiles:
  p50: 12.3 hours
  p75: 24.1 hours
  p90: 48.7 hours
  p95: 72.3 hours
```

## Best Practices

1. **Deployment Tracking**: Ensure your deployments are properly tagged in your Git provider
2. **Branch Protection**: Use pull requests to track when code is ready for deployment
3. **Automation**: Integrate this tool into your CI/CD pipeline for continuous monitoring
4. **Regular Reviews**: Review lead time trends in team retrospectives

## Troubleshooting

### No deployments found
- Verify your Git provider API token has necessary permissions
- Check that deployments are being tracked (GitHub Deployments API, GitLab Deployments)
- Ensure commit SHAs match between commits and deployments

### Authentication errors
- GitHub: Ensure token has `repo` and `read:deployment` scopes
- GitLab: Ensure token has `read_api` scope

## Integration with CI/CD

### GitHub Actions
```yaml
- name: Calculate Lead Time
  run: |
    pip install -r requirements.txt
    python lead_time.py --output json --output-file lead_time.json
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### GitLab CI
```yaml
lead_time_report:
  script:
    - pip install -r requirements.txt
    - python lead_time.py --output json --output-file lead_time.json
  artifacts:
    reports:
      metrics: lead_time.json
```
