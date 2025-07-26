#!/usr/bin/env python3
"""
Change Failure Rate Calculator
Measures the percentage of deployments causing failures in production
"""

import click
import yaml
import json
import pandas as pd
from datetime import datetime, timedelta
from dateutil.parser import parse
from typing import Dict, List, Optional, Tuple
import os
import sys
import logging
from github import Github
import gitlab
import requests
from tabulate import tabulate
from dataclasses import dataclass
from enum import Enum
import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Deployment status types"""
    SUCCESS = "success"
    FAILURE = "failure"
    ROLLBACK = "rollback"
    UNKNOWN = "unknown"


@dataclass
class Deployment:
    """Deployment data structure"""
    id: str
    timestamp: datetime
    service: str
    environment: str
    status: DeploymentStatus
    version: str
    duration_minutes: Optional[float] = None
    error_message: Optional[str] = None
    rollback_of: Optional[str] = None


class DeploymentSource:
    """Base class for deployment data sources"""
    
    def get_deployments(self, start_date: datetime, end_date: datetime) -> List[Deployment]:
        """Fetch deployments from source"""
        raise NotImplementedError


class GitHubDeploymentSource(DeploymentSource):
    """Fetch deployment data from GitHub"""
    
    def __init__(self, token: str, organization: str, repositories: List[str]):
        self.github = Github(token)
        self.organization = organization
        self.repositories = repositories
    
    def get_deployments(self, start_date: datetime, end_date: datetime) -> List[Deployment]:
        """Fetch deployments from GitHub API"""
        deployments = []
        
        for repo_name in self.repositories:
            try:
                repo = self.github.get_repo(f"{self.organization}/{repo_name}")
                
                for deployment in repo.get_deployments():
                    if deployment.created_at < start_date:
                        break
                    
                    if deployment.created_at <= end_date:
                        # Get deployment statuses
                        statuses = list(deployment.get_statuses())
                        
                        if statuses:
                            latest_status = statuses[0]
                            status = self._map_github_status(latest_status.state)
                            
                            # Calculate duration if completed
                            duration = None
                            if len(statuses) > 1:
                                duration = (statuses[0].created_at - statuses[-1].created_at).total_seconds() / 60
                            
                            deployments.append(Deployment(
                                id=f"{repo_name}_{deployment.id}",
                                timestamp=deployment.created_at,
                                service=repo_name,
                                environment=deployment.environment,
                                status=status,
                                version=deployment.sha[:7],
                                duration_minutes=duration,
                                error_message=latest_status.description if status == DeploymentStatus.FAILURE else None
                            ))
                            
            except Exception as e:
                logger.error(f"Error fetching deployments for {repo_name}: {e}")
        
        return deployments
    
    def _map_github_status(self, state: str) -> DeploymentStatus:
        """Map GitHub deployment state to our status"""
        mapping = {
            'success': DeploymentStatus.SUCCESS,
            'failure': DeploymentStatus.FAILURE,
            'error': DeploymentStatus.FAILURE,
            'inactive': DeploymentStatus.ROLLBACK
        }
        return mapping.get(state, DeploymentStatus.UNKNOWN)


class JenkinsDeploymentSource(DeploymentSource):
    """Fetch deployment data from Jenkins"""
    
    def __init__(self, url: str, username: str, token: str, job_names: List[str]):
        self.url = url.rstrip('/')
        self.auth = (username, token)
        self.job_names = job_names
    
    def get_deployments(self, start_date: datetime, end_date: datetime) -> List[Deployment]:
        """Fetch deployments from Jenkins API"""
        deployments = []
        
        for job_name in self.job_names:
            try:
                # Get job builds
                job_url = f"{self.url}/job/{job_name}/api/json?tree=builds[number,timestamp,result,duration,actions[parameters[name,value]]]"
                response = requests.get(job_url, auth=self.auth)
                response.raise_for_status()
                
                job_data = response.json()
                
                for build in job_data.get('builds', []):
                    build_time = datetime.fromtimestamp(build['timestamp'] / 1000)
                    
                    if build_time < start_date:
                        break
                    
                    if build_time <= end_date and build['result']:
                        # Extract parameters
                        params = self._extract_parameters(build)
                        
                        status = self._map_jenkins_result(build['result'])
                        
                        deployments.append(Deployment(
                            id=f"{job_name}_{build['number']}",
                            timestamp=build_time,
                            service=params.get('service', job_name),
                            environment=params.get('environment', 'production'),
                            status=status,
                            version=params.get('version', str(build['number'])),
                            duration_minutes=build['duration'] / 60000 if build['duration'] else None
                        ))
                        
            except Exception as e:
                logger.error(f"Error fetching deployments for {job_name}: {e}")
        
        return deployments
    
    def _extract_parameters(self, build: Dict) -> Dict:
        """Extract build parameters"""
        params = {}
        for action in build.get('actions', []):
            if 'parameters' in action:
                for param in action['parameters']:
                    params[param['name']] = param.get('value')
        return params
    
    def _map_jenkins_result(self, result: str) -> DeploymentStatus:
        """Map Jenkins build result to our status"""
        mapping = {
            'SUCCESS': DeploymentStatus.SUCCESS,
            'FAILURE': DeploymentStatus.FAILURE,
            'UNSTABLE': DeploymentStatus.FAILURE,
            'ABORTED': DeploymentStatus.FAILURE
        }
        return mapping.get(result, DeploymentStatus.UNKNOWN)


class DynamoDBDeploymentSource(DeploymentSource):
    """Fetch deployment data from DynamoDB"""
    
    def __init__(self, table_name: str, profile: Optional[str] = None, region: str = 'us-east-1'):
        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
            self.dynamodb = session.resource('dynamodb')
        else:
            self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
    
    def get_deployments(self, start_date: datetime, end_date: datetime) -> List[Deployment]:
        """Fetch deployments from DynamoDB"""
        deployments = []
        
        # Scan table (consider using query if you have proper indexes)
        response = self.table.scan()
        
        for item in response['Items']:
            timestamp = parse(item['timestamp']) if isinstance(item['timestamp'], str) else item['timestamp']
            
            if start_date <= timestamp <= end_date:
                deployments.append(Deployment(
                    id=item.get('deployment_id', item.get('id')),
                    timestamp=timestamp,
                    service=item.get('service', 'unknown'),
                    environment=item.get('environment', 'production'),
                    status=DeploymentStatus(item.get('status', 'unknown')),
                    version=item.get('version', 'unknown'),
                    duration_minutes=float(item['duration_minutes']) if 'duration_minutes' in item else None,
                    error_message=item.get('error_message'),
                    rollback_of=item.get('rollback_of')
                ))
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            for item in response['Items']:
                timestamp = parse(item['timestamp']) if isinstance(item['timestamp'], str) else item['timestamp']
                
                if start_date <= timestamp <= end_date:
                    deployments.append(Deployment(
                        id=item.get('deployment_id', item.get('id')),
                        timestamp=timestamp,
                        service=item.get('service', 'unknown'),
                        environment=item.get('environment', 'production'),
                        status=DeploymentStatus(item.get('status', 'unknown')),
                        version=item.get('version', 'unknown'),
                        duration_minutes=float(item['duration_minutes']) if 'duration_minutes' in item else None,
                        error_message=item.get('error_message'),
                        rollback_of=item.get('rollback_of')
                    ))
        
        return deployments


class ChangeFailureRateCalculator:
    """Calculate change failure rate metrics"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.source = self._initialize_source()
    
    def _initialize_source(self) -> DeploymentSource:
        """Initialize the appropriate deployment source"""
        source_type = self.config.get('deployment_source', 'github')
        
        if source_type == 'github':
            return GitHubDeploymentSource(
                token=os.environ.get('GITHUB_TOKEN') or self.config.get('github', {}).get('token'),
                organization=self.config.get('github', {}).get('organization'),
                repositories=self.config.get('github', {}).get('repositories', [])
            )
        elif source_type == 'jenkins':
            jenkins_config = self.config.get('jenkins', {})
            return JenkinsDeploymentSource(
                url=jenkins_config.get('url'),
                username=jenkins_config.get('username'),
                token=os.environ.get('JENKINS_TOKEN') or jenkins_config.get('token'),
                job_names=jenkins_config.get('jobs', [])
            )
        elif source_type == 'dynamodb':
            dynamodb_config = self.config.get('dynamodb', {})
            return DynamoDBDeploymentSource(
                table_name=dynamodb_config.get('table_name', 'DeploymentStatus'),
                profile=dynamodb_config.get('profile'),
                region=dynamodb_config.get('region', 'us-east-1')
            )
        else:
            raise ValueError(f"Unsupported deployment source: {source_type}")
    
    def calculate(self) -> Dict:
        """Calculate change failure rate metrics"""
        # Parse time range
        start_date, end_date = self._parse_time_range()
        
        logger.info(f"Calculating change failure rate from {start_date} to {end_date}")
        
        # Fetch deployments
        deployments = self.source.get_deployments(start_date, end_date)
        
        if not deployments:
            logger.warning("No deployments found in the specified time range")
            return self._empty_results(start_date, end_date)
        
        # Filter by environment if specified
        environments = self.config.get('environments', [])
        if environments:
            deployments = [d for d in deployments if d.environment in environments]
        
        # Calculate metrics
        total_deployments = len(deployments)
        failed_deployments = [d for d in deployments if d.status == DeploymentStatus.FAILURE]
        rollback_deployments = [d for d in deployments if d.status == DeploymentStatus.ROLLBACK]
        
        # Change failure rate calculation
        failure_count = len(failed_deployments) + len(rollback_deployments)
        change_failure_rate = (failure_count / total_deployments * 100) if total_deployments > 0 else 0
        
        # Group by service
        df = pd.DataFrame([{
            'service': d.service,
            'environment': d.environment,
            'status': d.status.value,
            'timestamp': d.timestamp,
            'duration_minutes': d.duration_minutes
        } for d in deployments])
        
        by_service = df.groupby('service').agg({
            'status': [
                lambda x: len(x),  # total
                lambda x: sum(1 for s in x if s in ['failure', 'rollback']),  # failures
                lambda x: (sum(1 for s in x if s in ['failure', 'rollback']) / len(x) * 100) if len(x) > 0 else 0  # rate
            ]
        }).round(2)
        
        by_service.columns = ['total', 'failures', 'failure_rate']
        by_service_dict = by_service.to_dict('index')
        
        # Weekly trend
        df['week'] = pd.to_datetime(df['timestamp']).dt.isocalendar().week
        weekly_stats = df.groupby('week').agg({
            'status': [
                lambda x: len(x),
                lambda x: sum(1 for s in x if s in ['failure', 'rollback']),
                lambda x: (sum(1 for s in x if s in ['failure', 'rollback']) / len(x) * 100) if len(x) > 0 else 0
            ]
        }).round(2)
        weekly_stats.columns = ['total', 'failures', 'failure_rate']
        weekly_trend = weekly_stats.to_dict('index')
        
        # Determine performance level
        performance_level = self._determine_performance_level(change_failure_rate)
        
        # Find recent failures
        recent_failures = sorted(
            [d for d in failed_deployments + rollback_deployments],
            key=lambda x: x.timestamp,
            reverse=True
        )[:10]
        
        return {
            'metric': 'change_failure_rate',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'results': {
                'total_deployments': total_deployments,
                'failed_deployments': len(failed_deployments),
                'rollback_deployments': len(rollback_deployments),
                'change_failure_rate': change_failure_rate,
                'performance_level': performance_level,
                'by_service': by_service_dict,
                'weekly_trend': weekly_trend,
                'recent_failures': [
                    {
                        'id': f.id,
                        'service': f.service,
                        'timestamp': f.timestamp.isoformat(),
                        'error_message': f.error_message
                    } for f in recent_failures
                ]
            }
        }
    
    def _parse_time_range(self) -> Tuple[datetime, datetime]:
        """Parse time range from config"""
        time_range = self.config.get('time_range', {})
        
        # Parse end date
        end_date_str = time_range.get('end_date', 'now')
        if end_date_str == 'now':
            end_date = datetime.now()
        else:
            end_date = parse(end_date_str)
        
        # Parse start date
        start_date_str = time_range.get('start_date', '30d')
        if start_date_str.endswith('d'):
            days = int(start_date_str[:-1])
            start_date = end_date - timedelta(days=days)
        else:
            start_date = parse(start_date_str)
            
        return start_date, end_date
    
    def _determine_performance_level(self, rate: float) -> str:
        """Determine DORA performance level based on change failure rate"""
        if rate <= 15:
            return 'Elite/High/Medium'
        else:
            return 'Low'
    
    def _empty_results(self, start_date: datetime, end_date: datetime) -> Dict:
        """Return empty results structure"""
        return {
            'metric': 'change_failure_rate',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'results': {
                'total_deployments': 0,
                'failed_deployments': 0,
                'rollback_deployments': 0,
                'change_failure_rate': 0,
                'performance_level': 'No data',
                'by_service': {}
            }
        }


class ChangeFailureRateReporter:
    """Generate change failure rate reports"""
    
    @staticmethod
    def generate_report(metrics: Dict):
        """Generate human-readable report"""
        results = metrics['results']
        
        print("\n" + "="*70)
        print("CHANGE FAILURE RATE REPORT")
        print("="*70)
        
        print(f"\nPeriod: {metrics['period']['start']} to {metrics['period']['end']}")
        
        print(f"\nSummary:")
        print(f"  Total Deployments: {results['total_deployments']}")
        print(f"  Failed Deployments: {results['failed_deployments']}")
        print(f"  Rollback Deployments: {results['rollback_deployments']}")
        print(f"  Change Failure Rate: {results['change_failure_rate']:.1f}%")
        print(f"  Performance Level: {results['performance_level']}")
        
        if results.get('by_service'):
            print(f"\nChange Failure Rate by Service:")
            service_data = []
            for service, stats in results['by_service'].items():
                service_data.append([
                    service[:30],
                    int(stats['total']),
                    int(stats['failures']),
                    f"{stats['failure_rate']:.1f}%"
                ])
            print(tabulate(service_data, 
                         headers=['Service', 'Total', 'Failures', 'Rate'], 
                         tablefmt='grid'))
        
        if results.get('weekly_trend'):
            print(f"\nWeekly Trend:")
            trend_data = []
            for week, stats in sorted(results['weekly_trend'].items()):
                trend_data.append([
                    f"Week {week}",
                    int(stats['total']),
                    int(stats['failures']),
                    f"{stats['failure_rate']:.1f}%"
                ])
            print(tabulate(trend_data, 
                         headers=['Week', 'Total', 'Failures', 'Rate'], 
                         tablefmt='grid'))
        
        if results.get('recent_failures'):
            print(f"\nRecent Failures (Last 5):")
            failure_data = []
            for failure in results['recent_failures'][:5]:
                failure_data.append([
                    failure['id'][:20],
                    failure['service'][:20],
                    failure['timestamp'][:19],
                    (failure.get('error_message', 'No error message')[:40] + '...' 
                     if failure.get('error_message') and len(failure.get('error_message', '')) > 40 
                     else failure.get('error_message', 'No error message'))
                ])
            print(tabulate(failure_data, 
                         headers=['ID', 'Service', 'Time', 'Error'], 
                         tablefmt='grid'))
        
        print("\nPerformance Level Guide:")
        print("  Elite/High/Medium: 0-15%")
        print("  Low: 16-100%")
        print("\n" + "="*70)
    
    @staticmethod
    def export_json(metrics: Dict, output_file: Optional[str] = None):
        """Export metrics as JSON"""
        json_str = json.dumps(metrics, indent=2, default=str)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_str)
            logger.info(f"Metrics exported to {output_file}")
        else:
            print(json_str)


@click.command()
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--output', type=click.Choice(['json', 'report']), 
              default='report', help='Output format')
@click.option('--output-file', help='Output file path (for json)')
def main(config, output, output_file):
    """Calculate change failure rate metrics"""
    try:
        # Load configuration
        if not os.path.exists(config):
            logger.error(f"Configuration file not found: {config}")
            create_example_config()
            sys.exit(1)
            
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Calculate metrics
        calculator = ChangeFailureRateCalculator(config_data)
        metrics = calculator.calculate()
        
        # Output results
        if output == 'report':
            ChangeFailureRateReporter.generate_report(metrics)
        elif output == 'json':
            ChangeFailureRateReporter.export_json(metrics, output_file)
            
    except Exception as e:
        logger.error(f"Error calculating change failure rate: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def create_example_config():
    """Create an example configuration file"""
    example_config = """# Change Failure Rate Calculator Configuration

# Deployment source: github, jenkins, dynamodb
deployment_source: github

# Time range for analysis
time_range:
  start_date: "30d"  # or specific date: "2024-01-01"
  end_date: "now"

# Filter by environments (optional)
environments:
  - production

# GitHub configuration
github:
  token: ${GITHUB_TOKEN}  # Set via environment variable
  organization: your-org
  repositories:
    - api-service
    - web-frontend

# Jenkins configuration (if deployment_source is jenkins)
jenkins:
  url: https://jenkins.example.com
  username: ${JENKINS_USER}
  token: ${JENKINS_TOKEN}
  jobs:
    - deploy-production
    - deploy-staging

# DynamoDB configuration (if deployment_source is dynamodb)
dynamodb:
  table_name: DeploymentStatus
  profile: default  # AWS profile (optional)
  region: us-east-1
"""
    
    with open('config.yaml.example', 'w') as f:
        f.write(example_config)
    
    logger.info("Created config.yaml.example - please copy to config.yaml and update settings")


if __name__ == '__main__':
    main()