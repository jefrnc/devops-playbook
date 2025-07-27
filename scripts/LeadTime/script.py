# \!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
import datetime

# Set your JIRA API credentials and base URL
jira_username = "your_jira_username"
jira_password = "your_jira_password"
jira_base_url = "https://your_jira_instance.atlassian.net"

# Set the JQL query to get the relevant issues (adjust the query as needed)
jql_query = "project = YOUR_PROJECT_KEY AND issuetype = Story AND status = Deployed"

# Set the date format used by JIRA
jira_date_format = "%Y-%m-%dT%H:%M:%S.%f%z"


# Function to get issues from JIRA using the REST API
def get_jira_issues(jql):
    url = f"{jira_base_url}/rest/api/3/search"
    headers = {"Accept": "application/json"}
    params = {"jql": jql, "fields": "created,customfield_XXXXX"}

    response = requests.get(
        url,
        headers=headers,
        params=params,
        auth=HTTPBasicAuth(jira_username, jira_password),
    )
    response.raise_for_status()
    return response.json()["issues"]


# Function to calculate lead time from JIRA issue data
def calculate_lead_time(issue):
    start_date = datetime.datetime.strptime(
        issue["fields"]["created"], jira_date_format
    )
    deployment_date = datetime.datetime.strptime(
        issue["fields"]["customfield_XXXXX"], jira_date_format
    )
    lead_time = (deployment_date - start_date).days
    return lead_time


# Get the issues from JIRA
issues = get_jira_issues(jql_query)

# Calculate lead time for each issue
lead_times = [calculate_lead_time(issue) for issue in issues]

# Calculate the average lead time
average_lead_time = sum(lead_times) / len(lead_times)

print(f"Average Lead Time: {average_lead_time} days")

