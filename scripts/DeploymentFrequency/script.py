#!/usr/bin/env python3
import boto3
import datetime
from dateutil.parser import parse

# Configure your AWS profile and region
aws_profile = "your_aws_profile_name"
aws_region = "your_aws_region"

# Set the date range for calculating Deployment Frequency
start_date = datetime.datetime.now() - datetime.timedelta(days=30)
end_date = datetime.datetime.now()

# Initialize Boto3 CloudTrail client
session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
cloudtrail = session.client("cloudtrail")

# Set the filters for the CloudTrail logs
lookup_attributes = [{"AttributeKey": "EventName", "AttributeValue": "UpdateService"}]

paginator = cloudtrail.get_paginator("lookup_events")
iterator = paginator.paginate(
    StartTime=start_date, EndTime=end_date, LookupAttributes=lookup_attributes
)

# Count the number of successful deployments
deployment_count = 0
for page in iterator:
    for event in page["Events"]:
        event_time = parse(event["EventTime"])
        if start_date <= event_time <= end_date:
            deployment_count += 1

# Calculate Deployment Frequency
deployment_frequency = deployment_count

print(f"Deployment Frequency: {deployment_frequency}")
