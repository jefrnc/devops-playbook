#\!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
import datetime

# Set your JIRA API credentials and base URL
jira_username = "your_jira_username"
jira_password = "your_jira_password"
jira_base_url = "https://your_jira_instance.atlassian.net"

# Set the JQL query to get the relevant issues (adjust the query as needed)
jql_query = "project = YOUR_PROJECT_KEY AND issuetype = Bug AND status = Resolved"

# Set the date format used by JIRA
jira_date_format = "%Y-%m-%dT%H:%M:%S.%f%z"

# Function to get issues from JIRA using the REST API
def get_jira_issues(jql):
    url = f"{jira_base_url}/rest/api/3/search"
    headers = {"Accept": "application/json"}
    params = {"jql": jql, "fields": "created, resolutiondate"}

    response = requests.get(url, headers=headers, params=params, auth=HTTPBasicAuth(jira_username, jira_password))
    response.raise_for_status()
    return response.json()["issues"]

# Function to calculate resolution time for a JIRA issue
def calculate_resolution_time(issue):
    created_date = datetime.datetime.strptime(issue["fields"]["created"], jira_date_format)
    resolution_date = datetime.datetime.strptime(issue["fields"]["resolutiondate"], jira_date_format)
    resolution_time = (resolution_date - created_date).total_seconds() / 3600  # Calculate time in hours
    return resolution_time

# Get the issues from JIRA
issues = get_jira_issues(jql_query)

# Calculate resolution time for each issue
resolution_times = [calculate_resolution_time(issue) for issue in issues]

# Calculate the Mean Time To Resolve (MTTR)
mttr = sum(resolution_times) / len(resolution_times)

print(f"Mean Time To Resolve (MTTR): {mttr:.2f} hours")
