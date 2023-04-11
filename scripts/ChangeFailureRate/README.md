# Change Failure Rate

N/A

```ssh
aws cloudformation create-stack \
  --stack-name DeploymentStatusTableStack \
  --template-body file://deployment_status_table.yaml \
  --region YOUR_AWS_REGION \
  --capabilities CAPABILITY_NAMED_IAM
```
