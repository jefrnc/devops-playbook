#!/usr/bin/env python3
"""
Deployment Frequency Calculator
Calculates DORA deployment frequency metric from multiple sources
"""

import boto3
import click
import yaml
import json
import pandas as pd
from datetime import datetime, timedelta
from dateutil.parser import parse
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import os
import sys
from tabulate import tabulate
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeploymentSource(ABC):
    """Abstract base class for deployment data sources"""
    
    @abstractmethod
    def get_deployments(self, start_date: datetime, end_date: datetime, 
                       environments: List[str]) -> List[Dict]:
        """Fetch deployment data from source"""
        pass


class AWSCloudTrailSource(DeploymentSource):
    """Fetch deployment data from AWS CloudTrail"""
    
    def __init__(self, profile: str, region: str):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.cloudtrail = self.session.client('cloudtrail')
        
    def get_deployments(self, start_date: datetime, end_date: datetime,
                       environments: List[str]) -> List[Dict]:
        """Fetch ECS/EKS deployment events from CloudTrail"""
        deployments = []
        
        # Define deployment event names
        event_names = [
            'UpdateService',  # ECS
            'CreateDeployment',  # EKS
            'UpdateStack'  # CloudFormation
        ]
        
        for event_name in event_names:
            lookup_attributes = [
                {
                    'AttributeKey': 'EventName',
                    'AttributeValue': event_name
                }
            ]
            
            paginator = self.cloudtrail.get_paginator('lookup_events')
            iterator = paginator.paginate(
                StartTime=start_date,
                EndTime=end_date,
                LookupAttributes=lookup_attributes
            )
            
            for page in iterator:
                for event in page.get('Events', []):
                    # Parse event details
                    event_detail = json.loads(event.get('CloudTrailEvent', '{}'))
                    
                    deployment = {
                        'timestamp': parse(event['EventTime']),
                        'service': self._extract_service_name(event_detail),
                        'environment': self._extract_environment(event_detail),
                        'type': event_name,
                        'user': event.get('Username', 'unknown'),
                        'status': 'success'  # CloudTrail only logs successful API calls
                    }
                    
                    # Filter by environment if specified
                    if not environments or deployment['environment'] in environments:
                        deployments.append(deployment)
                        
        return deployments
    
    def _extract_service_name(self, event_detail: Dict) -> str:
        """Extract service name from CloudTrail event"""
        # Try different paths based on event type
        paths = [
            ['requestParameters', 'service'],
            ['requestParameters', 'stackName'],
            ['requestParameters', 'deploymentConfigName']
        ]
        
        for path in paths:
            value = event_detail
            for key in path:
                value = value.get(key, {})
                if isinstance(value, str):
                    return value
                    
        return 'unknown'
    
    def _extract_environment(self, event_detail: Dict) -> str:
        """Extract environment from tags or naming convention"""
        # Check tags
        tags = event_detail.get('requestParameters', {}).get('tags', [])
        for tag in tags:
            if tag.get('key', '').lower() == 'environment':
                return tag.get('value', 'unknown')
        
        # Check naming convention (e.g., service-prod, service-staging)
        service_name = self._extract_service_name(event_detail)
        for env in ['prod', 'production', 'staging', 'dev', 'development']:
            if env in service_name.lower():
                return env
                
        return 'unknown'


class GitHubSource(DeploymentSource):
    """Fetch deployment data from GitHub"""
    
    def __init__(self, token: str, organization: str, repositories: List[str]):
        from github import Github
        self.github = Github(token)
        self.organization = organization
        self.repositories = repositories
        
    def get_deployments(self, start_date: datetime, end_date: datetime,
                       environments: List[str]) -> List[Dict]:
        """Fetch deployment data from GitHub deployments API"""
        deployments = []
        
        for repo_name in self.repositories:
            try:
                repo = self.github.get_repo(f"{self.organization}/{repo_name}")
                
                # Get deployments
                for deployment in repo.get_deployments():
                    if deployment.created_at < start_date:
                        break  # Deployments are returned in reverse chronological order
                        
                    if deployment.created_at <= end_date:
                        # Check environment filter
                        if not environments or deployment.environment in environments:
                            deployments.append({
                                'timestamp': deployment.created_at,
                                'service': repo_name,
                                'environment': deployment.environment,
                                'type': 'github_deployment',
                                'user': deployment.creator.login if deployment.creator else 'unknown',
                                'status': self._get_deployment_status(deployment),
                                'sha': deployment.sha[:7]
                            })
            except Exception as e:
                logger.error(f"Error fetching deployments for {repo_name}: {e}")
                
        return deployments
    
    def _get_deployment_status(self, deployment) -> str:
        """Get the latest status of a deployment"""
        statuses = list(deployment.get_statuses())
        if statuses:
            return statuses[0].state
        return 'unknown'


class DeploymentFrequencyCalculator:
    """Calculate deployment frequency metrics"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.source = self._initialize_source()
        
    def _initialize_source(self) -> DeploymentSource:
        """Initialize the appropriate data source"""
        source_type = self.config.get('data_source', 'aws')
        
        if source_type == 'aws':
            return AWSCloudTrailSource(
                profile=self.config.get('aws', {}).get('profile', 'default'),
                region=self.config.get('aws', {}).get('region', 'us-east-1')
            )
        elif source_type == 'github':
            return GitHubSource(
                token=os.environ.get('GITHUB_TOKEN') or self.config.get('github', {}).get('token'),
                organization=self.config.get('github', {}).get('organization'),
                repositories=self.config.get('github', {}).get('repositories', [])
            )
        else:
            raise ValueError(f"Unsupported data source: {source_type}")
    
    def calculate(self) -> Dict:
        """Calculate deployment frequency metrics"""
        # Parse time range
        start_date, end_date = self._parse_time_range()
        environments = self.config.get('environments', [])
        
        # Fetch deployments
        logger.info(f"Fetching deployments from {start_date} to {end_date}")
        deployments = self.source.get_deployments(start_date, end_date, environments)
        
        if not deployments:
            logger.warning("No deployments found in the specified time range")
            return self._empty_results(start_date, end_date)
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(deployments)
        
        # Calculate metrics
        total_deployments = len(df)
        days_in_period = (end_date - start_date).days
        daily_average = total_deployments / days_in_period if days_in_period > 0 else 0
        
        # Group by environment
        by_environment = df.groupby('environment').size().to_dict()
        
        # Group by service
        by_service = df.groupby('service').size().to_dict()
        
        # Calculate daily deployments for trend analysis
        df['date'] = df['timestamp'].dt.date
        daily_counts = df.groupby('date').size()
        
        # Determine performance level
        performance_level = self._determine_performance_level(daily_average)
        
        # Calculate trend
        trend = self._calculate_trend(daily_counts)
        
        return {
            'metric': 'deployment_frequency',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'results': {
                'total_deployments': total_deployments,
                'daily_average': round(daily_average, 2),
                'by_environment': by_environment,
                'by_service': by_service,
                'performance_level': performance_level,
                'trend': trend,
                'daily_breakdown': daily_counts.to_dict()
            }
        }
    
    def _parse_time_range(self) -> tuple:
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
    
    def _determine_performance_level(self, daily_average: float) -> str:
        """Determine DORA performance level"""
        if daily_average >= 1:
            return 'Elite'
        elif daily_average >= 1/7:  # At least once per week
            return 'High'
        elif daily_average >= 1/30:  # At least once per month
            return 'Medium'
        else:
            return 'Low'
    
    def _calculate_trend(self, daily_counts: pd.Series) -> str:
        """Calculate deployment trend"""
        if len(daily_counts) < 7:
            return 'insufficient_data'
            
        # Compare last week to previous week
        last_week = daily_counts[-7:].mean()
        prev_week = daily_counts[-14:-7].mean() if len(daily_counts) >= 14 else daily_counts[:-7].mean()
        
        if prev_week == 0:
            return 'increasing' if last_week > 0 else 'stable'
            
        change_percent = ((last_week - prev_week) / prev_week) * 100
        
        if change_percent > 10:
            return 'increasing'
        elif change_percent < -10:
            return 'decreasing'
        else:
            return 'stable'
    
    def _empty_results(self, start_date: datetime, end_date: datetime) -> Dict:
        """Return empty results structure"""
        return {
            'metric': 'deployment_frequency',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'results': {
                'total_deployments': 0,
                'daily_average': 0,
                'by_environment': {},
                'by_service': {},
                'performance_level': 'Low',
                'trend': 'no_data'
            }
        }


class MetricsExporter:
    """Export metrics in various formats"""
    
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
    
    @staticmethod
    def export_csv(metrics: Dict, output_file: Optional[str] = None):
        """Export metrics as CSV"""
        results = metrics['results']
        
        # Create summary data
        summary_data = {
            'Metric': ['Deployment Frequency'],
            'Period Start': [metrics['period']['start']],
            'Period End': [metrics['period']['end']],
            'Total Deployments': [results['total_deployments']],
            'Daily Average': [results['daily_average']],
            'Performance Level': [results['performance_level']],
            'Trend': [results['trend']]
        }
        
        df = pd.DataFrame(summary_data)
        
        if output_file:
            df.to_csv(output_file, index=False)
            logger.info(f"Metrics exported to {output_file}")
        else:
            print(df.to_csv(index=False))
    
    @staticmethod
    def export_prometheus(metrics: Dict, push_gateway: Optional[str] = None):
        """Export metrics to Prometheus"""
        registry = CollectorRegistry()
        
        # Create gauges
        deployment_total = Gauge('deployment_frequency_total', 
                               'Total deployments in period', 
                               registry=registry)
        deployment_daily = Gauge('deployment_frequency_daily_average', 
                               'Daily average deployments', 
                               registry=registry)
        
        # Set values
        deployment_total.set(metrics['results']['total_deployments'])
        deployment_daily.set(metrics['results']['daily_average'])
        
        # By environment
        deployment_by_env = Gauge('deployment_frequency_by_environment', 
                                'Deployments by environment', 
                                ['environment'], 
                                registry=registry)
        
        for env, count in metrics['results']['by_environment'].items():
            deployment_by_env.labels(environment=env).set(count)
        
        if push_gateway:
            push_to_gateway(push_gateway, job='deployment_frequency', registry=registry)
            logger.info(f"Metrics pushed to {push_gateway}")
        else:
            # Print in Prometheus format
            from prometheus_client import generate_latest
            print(generate_latest(registry).decode('utf-8'))
    
    @staticmethod
    def generate_report(metrics: Dict):
        """Generate a human-readable report"""
        results = metrics['results']
        
        print("\n" + "="*60)
        print("DEPLOYMENT FREQUENCY REPORT")
        print("="*60)
        
        print(f"\nPeriod: {metrics['period']['start']} to {metrics['period']['end']}")
        print(f"\nSummary:")
        print(f"  Total Deployments: {results['total_deployments']}")
        print(f"  Daily Average: {results['daily_average']}")
        print(f"  Performance Level: {results['performance_level']}")
        print(f"  Trend: {results['trend']}")
        
        if results['by_environment']:
            print(f"\nDeployments by Environment:")
            env_data = [[env, count] for env, count in results['by_environment'].items()]
            print(tabulate(env_data, headers=['Environment', 'Count'], tablefmt='grid'))
        
        if results['by_service']:
            print(f"\nTop Services by Deployment Count:")
            service_data = sorted(results['by_service'].items(), key=lambda x: x[1], reverse=True)[:10]
            print(tabulate(service_data, headers=['Service', 'Count'], tablefmt='grid'))
        
        print("\nPerformance Level Guide:")
        print("  Elite: Multiple deployments per day")
        print("  High: Between once per day and once per week")
        print("  Medium: Between once per week and once per month")
        print("  Low: Less than once per month")
        print("\n" + "="*60)


@click.command()
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--output', type=click.Choice(['json', 'csv', 'prometheus']), 
              default='json', help='Output format')
@click.option('--output-file', help='Output file path')
@click.option('--push-gateway', help='Prometheus push gateway URL')
@click.option('--report', is_flag=True, help='Generate human-readable report')
def main(config, output, output_file, push_gateway, report):
    """Calculate deployment frequency metrics"""
    try:
        # Load configuration
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Calculate metrics
        calculator = DeploymentFrequencyCalculator(config_data)
        metrics = calculator.calculate()
        
        # Export or display results
        if report:
            MetricsExporter.generate_report(metrics)
        elif output == 'json':
            MetricsExporter.export_json(metrics, output_file)
        elif output == 'csv':
            MetricsExporter.export_csv(metrics, output_file)
        elif output == 'prometheus':
            MetricsExporter.export_prometheus(metrics, push_gateway)
            
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error calculating deployment frequency: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()