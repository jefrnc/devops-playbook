#!/usr/bin/env python3
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("DeploymentStatus")

response = table.scan()
deployments = response["Items"]

successful_deployments = [d for d in deployments if d["status"] == "success"]
failed_deployments = [d for d in deployments if d["status"] == "failure"]

change_failure_rate = len(failed_deployments) / (
    len(successful_deployments) + len(failed_deployments)
)

print(f"Change Failure Rate: {change_failure_rate:.2%}")
