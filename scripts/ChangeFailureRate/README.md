# Change Failure Rate Calculator

## Overview

The Change Failure Rate (CFR) is one of the four DORA metrics that measures the percentage of deployments causing a failure in production that requires immediate remediation (hotfix, rollback, fix forward, or patch).

## What is Change Failure Rate?

Change Failure Rate represents the stability of your deployment process. It answers the question: "What percentage of our deployments result in degraded service?"

### Formula
```text
Change Failure Rate = (Failed Deployments / Total Deployments) × 100
```

## Script Components

### 1. change_failure_rate.py
Main Python script that calculates the change failure rate from various data sources.

### 2. deployment_status_table.yaml
CloudFormation template for creating a DynamoDB table to track deployment statuses.

## Installation

### Prerequisites
- Python 3.7+
- AWS CLI configured (if using DynamoDB)
- Required Python packages:
  ```bash
  pip install -r requirements.txt
  ```

### AWS Infrastructure Setup
Deploy the DynamoDB table for tracking deployment statuses:

```bash
aws cloudformation create-stack \
  --stack-name DeploymentStatusTableStack \
  --template-body file://deployment_status_table.yaml \
  --region YOUR_AWS_REGION \
  --capabilities CAPABILITY_NAMED_IAM
```

## Usage

### Basic Usage
```bash
python change_failure_rate.py --start-date 2024-01-01 --end-date 2024-01-31
```

### With Different Data Sources

#### From CSV File
```bash
python change_failure_rate.py --source csv --file deployments.csv
```

#### From DynamoDB
```bash
python change_failure_rate.py --source dynamodb --table deployment-status
```

#### From CI/CD API
```bash
python change_failure_rate.py --source jenkins --url https://jenkins.example.com
```

### Output Formats
```bash
# JSON output
python change_failure_rate.py --output json > cfr_report.json

# CSV output
python change_failure_rate.py --output csv > cfr_report.csv

# Dashboard-ready format
python change_failure_rate.py --output grafana
```

## Data Format

### Expected CSV Format
```csv
deployment_id,timestamp,status,environment,service,rollback_required
deploy-001,2024-01-15T10:30:00Z,success,production,api-service,false
deploy-002,2024-01-15T14:20:00Z,failed,production,web-app,true
deploy-003,2024-01-15T16:45:00Z,success,production,database,false
```

### Status Values
- `success`: Deployment completed without issues
- `failed`: Deployment caused service degradation
- `partial`: Deployment partially failed (counts as failure)
- `rolled_back`: Deployment was rolled back (counts as failure)

## Integration Examples

### GitHub Actions
```yaml
- name: Calculate Change Failure Rate
  run: |
    python scripts/ChangeFailureRate/change_failure_rate.py \
      --source github \
      --repo ${{ github.repository }} \
      --token ${{ secrets.GITHUB_TOKEN }}
```

### Jenkins Pipeline
```groovy
stage('Calculate CFR') {
    steps {
        sh '''
            python scripts/ChangeFailureRate/change_failure_rate.py \
              --source jenkins \
              --job ${JOB_NAME} \
              --build ${BUILD_NUMBER}
        '''
    }
}
```

### GitLab CI
```yaml
calculate-cfr:
  script:
    - python scripts/ChangeFailureRate/change_failure_rate.py
        --source gitlab
        --project $CI_PROJECT_ID
        --token $GITLAB_TOKEN
```

## Performance Benchmarks

### Industry Standards (2023 State of DevOps Report)
- **Elite**: 0-5%
- **High**: 6-15%
- **Medium**: 16-30%
- **Low**: > 30%

### Improvement Strategies
1. **Increase test coverage** - Catch issues before production
2. **Implement feature flags** - Reduce impact of failures
3. **Use canary deployments** - Detect issues with minimal impact
4. **Improve rollback procedures** - Faster recovery from failures
5. **Enhance monitoring** - Detect issues quickly

## Troubleshooting

### Common Issues

#### No Data Returned
- Verify date range includes deployments
- Check data source connectivity
- Ensure proper authentication

#### Incorrect Calculations
- Validate status field values
- Check for duplicate deployment records
- Verify timezone handling

#### Performance Issues
- Use date filters to limit data range
- Implement pagination for large datasets
- Consider data aggregation for historical data

### Debug Mode
```bash
python change_failure_rate.py --debug --verbose
```

## Advanced Features

### Filtering by Service
```bash
python change_failure_rate.py --service api-gateway --service user-service
```

### Excluding Environments
```bash
python change_failure_rate.py --exclude-env staging --exclude-env development
```

### Trend Analysis
```bash
python change_failure_rate.py --trend weekly --weeks 12
```

### Alerting Integration
```bash
python change_failure_rate.py --alert-threshold 15 --alert-webhook $SLACK_WEBHOOK
```

## Best Practices

1. **Track all production deployments** - Include hotfixes and rollbacks
2. **Define "failure" clearly** - Document what constitutes a failed deployment
3. **Automate data collection** - Reduce manual tracking errors
4. **Review trends regularly** - Weekly or sprint retrospectives
5. **Correlate with other metrics** - Balance speed with stability

## Related Scripts
- [Deployment Frequency](../DeploymentFrequency/README.md)
- [Lead Time](../LeadTime/README.md)
- [MTTR](../MTTR/README.md)

## Contributing
See the main [Contributing Guide](../../CONTRIBUTING.md) for details on submitting improvements.

## Resources
- [DORA Metrics](https://dora.dev/)
- [Accelerate Book](https://itrevolution.com/accelerate-book/)
- [Google Cloud DORA Assessment](https://dora.dev/quickcheck/)
