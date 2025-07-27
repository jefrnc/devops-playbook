#!/usr/bin/env python3
import json
from datetime import datetime

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("DeploymentTimeTable")


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    service = event["detail"]["service"]
    task_definition_arn = event["detail"]["taskDefinitionArn"]
    start_time = datetime.fromisoformat(event["detail"]["createdAt"])
    end_time = datetime.fromisoformat(event["detail"]["completedAt"])
    deployment_time = (end_time - start_time).total_seconds()

    response = table.put_item(
        Item={
            "service": service,
            "task_definition_arn": task_definition_arn,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "deployment_time": deployment_time,
        }
    )

    print(f"Stored deployment information: {response}")
