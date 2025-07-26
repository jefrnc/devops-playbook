#!/usr/bin/env python3
"""
Lead Time for Changes Calculator
Measures the time from code commit to production deployment
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
import statistics
from github import Github
import gitlab
import requests
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CommitTracker:
    """Track commits and their deployment status"""
    
    def __init__(self, source_type: str, config: Dict):
        self.source_type = source_type
        self.config = config
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Git client based on source type"""
        if self.source_type == 'github':
            token = os.environ.get('GITHUB_TOKEN') or self.config.get('token')
            self.client = Github(token)
        elif self.source_type == 'gitlab':
            url = self.config.get('url', 'https://gitlab.com')
            token = os.environ.get('GITLAB_TOKEN') or self.config.get('token')
            self.client = gitlab.Gitlab(url, private_token=token)
    
    def get_commits_with_deployments(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get commits and match them with deployments"""
        if self.source_type == 'github':
            return self._get_github_commits(start_date, end_date)
        elif self.source_type == 'gitlab':
            return self._get_gitlab_commits(start_date, end_date)
        else:
            raise ValueError(f"Unsupported source type: {self.source_type}")
    
    def _get_github_commits(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get GitHub commits and their deployment times"""
        commits_data = []
        
        for repo_name in self.config.get('repositories', []):
            try:
                repo = self.client.get_repo(f"{self.config['organization']}/{repo_name}")
                
                # Get commits
                commits = repo.get_commits(since=start_date, until=end_date)
                
                for commit in commits:
                    # Find deployment for this commit
                    deployment_time = self._find_deployment_time(repo, commit.sha)
                    
                    if deployment_time:
                        lead_time = (deployment_time - commit.commit.author.date).total_seconds() / 3600
                        
                        commits_data.append({
                            'commit_sha': commit.sha[:7],
                            'commit_time': commit.commit.author.date,
                            'deployment_time': deployment_time,
                            'lead_time_hours': lead_time,
                            'repository': repo_name,
                            'author': commit.commit.author.name,
                            'message': commit.commit.message.split('\n')[0][:80]
                        })
                        
            except Exception as e:
                logger.error(f"Error processing repository {repo_name}: {e}")
        
        return commits_data
    
    def _find_deployment_time(self, repo, commit_sha: str) -> Optional[datetime]:
        """Find when a commit was deployed"""
        # Check deployments
        for deployment in repo.get_deployments():
            if deployment.sha == commit_sha:
                # Get deployment status
                statuses = list(deployment.get_statuses())
                for status in statuses:
                    if status.state == 'success':
                        return status.created_at
        
        # Check releases (alternative deployment tracking)
        for release in repo.get_releases():
            if release.target_commitish == commit_sha:
                return release.created_at
        
        return None
    
    def _get_gitlab_commits(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get GitLab commits and their deployment times"""
        commits_data = []
        
        for project_id in self.config.get('projects', []):
            try:
                project = self.client.projects.get(project_id)
                
                # Get commits
                commits = project.commits.list(
                    since=start_date.isoformat(),
                    until=end_date.isoformat(),
                    all=True
                )
                
                for commit in commits:
                    # Find deployment for this commit
                    deployment_time = self._find_gitlab_deployment_time(project, commit.id)
                    
                    if deployment_time:
                        commit_time = parse(commit.created_at)
                        lead_time = (deployment_time - commit_time).total_seconds() / 3600
                        
                        commits_data.append({
                            'commit_sha': commit.short_id,
                            'commit_time': commit_time,
                            'deployment_time': deployment_time,
                            'lead_time_hours': lead_time,
                            'repository': project.name,
                            'author': commit.author_name,
                            'message': commit.title[:80]
                        })
                        
            except Exception as e:
                logger.error(f"Error processing project {project_id}: {e}")
        
        return commits_data
    
    def _find_gitlab_deployment_time(self, project, commit_sha: str) -> Optional[datetime]:
        """Find when a GitLab commit was deployed"""
        # Check deployments
        deployments = project.deployments.list(all=True)
        for deployment in deployments:
            if deployment.sha == commit_sha and deployment.status == 'success':
                return parse(deployment.created_at)
        
        # Check pipelines
        pipelines = project.pipelines.list(sha=commit_sha, all=True)
        for pipeline in pipelines:
            if pipeline.status == 'success':
                # Check if this pipeline deployed to production
                jobs = project.jobs.list(pipeline_id=pipeline.id, all=True)
                for job in jobs:
                    if 'deploy' in job.name.lower() and 'prod' in job.name.lower():
                        if job.status == 'success':
                            return parse(job.finished_at)
        
        return None


class LeadTimeCalculator:
    """Calculate lead time metrics"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.tracker = CommitTracker(
            config.get('source_type', 'github'),
            config.get(config.get('source_type', 'github'), {})
        )
    
    def calculate(self) -> Dict:
        """Calculate lead time metrics"""
        # Parse time range
        start_date, end_date = self._parse_time_range()
        
        logger.info(f"Calculating lead time from {start_date} to {end_date}")
        
        # Get commits with deployment data
        commits = self.tracker.get_commits_with_deployments(start_date, end_date)
        
        if not commits:
            logger.warning("No deployed commits found in the specified time range")
            return self._empty_results(start_date, end_date)
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(commits)
        
        # Calculate statistics
        lead_times = df['lead_time_hours'].tolist()
        
        metrics = {
            'total_deployments': len(df),
            'mean_lead_time_hours': statistics.mean(lead_times),
            'median_lead_time_hours': statistics.median(lead_times),
            'min_lead_time_hours': min(lead_times),
            'max_lead_time_hours': max(lead_times),
            'std_dev_hours': statistics.stdev(lead_times) if len(lead_times) > 1 else 0
        }
        
        # Convert to days for readability
        metrics['mean_lead_time_days'] = metrics['mean_lead_time_hours'] / 24
        metrics['median_lead_time_days'] = metrics['median_lead_time_hours'] / 24
        
        # Group by repository
        by_repository = df.groupby('repository')['lead_time_hours'].agg(['mean', 'count']).to_dict('index')
        
        # Calculate percentiles
        percentiles = {
            'p50': statistics.quantiles(lead_times, n=2)[0],
            'p75': statistics.quantiles(lead_times, n=4)[2] if len(lead_times) > 3 else max(lead_times),
            'p90': statistics.quantiles(lead_times, n=10)[8] if len(lead_times) > 9 else max(lead_times),
            'p95': statistics.quantiles(lead_times, n=20)[18] if len(lead_times) > 19 else max(lead_times)
        }
        
        # Determine performance level
        performance_level = self._determine_performance_level(metrics['median_lead_time_hours'])
        
        # Analyze trends
        df['week'] = pd.to_datetime(df['commit_time']).dt.isocalendar().week
        weekly_trend = df.groupby('week')['lead_time_hours'].median().to_dict()
        
        return {
            'metric': 'lead_time_for_changes',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'results': {
                'statistics': metrics,
                'percentiles': percentiles,
                'by_repository': by_repository,
                'performance_level': performance_level,
                'weekly_trend': weekly_trend,
                'recent_deployments': self._get_recent_deployments(df)
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
    
    def _determine_performance_level(self, median_hours: float) -> str:
        """Determine DORA performance level based on median lead time"""
        if median_hours <= 1:  # Less than 1 hour
            return 'Elite'
        elif median_hours <= 24 * 7:  # Less than 1 week
            return 'High'
        elif median_hours <= 24 * 30:  # Less than 1 month
            return 'Medium'
        else:
            return 'Low'
    
    def _get_recent_deployments(self, df: pd.DataFrame, limit: int = 10) -> List[Dict]:
        """Get recent deployments for the report"""
        recent = df.nlargest(limit, 'deployment_time')[
            ['commit_sha', 'repository', 'lead_time_hours', 'author', 'message']
        ].to_dict('records')
        
        # Format lead times
        for item in recent:
            hours = item['lead_time_hours']
            if hours < 1:
                item['lead_time_formatted'] = f"{int(hours * 60)} minutes"
            elif hours < 24:
                item['lead_time_formatted'] = f"{hours:.1f} hours"
            else:
                item['lead_time_formatted'] = f"{hours/24:.1f} days"
                
        return recent
    
    def _empty_results(self, start_date: datetime, end_date: datetime) -> Dict:
        """Return empty results structure"""
        return {
            'metric': 'lead_time_for_changes',
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'results': {
                'statistics': {
                    'total_deployments': 0,
                    'mean_lead_time_hours': 0,
                    'median_lead_time_hours': 0
                },
                'performance_level': 'No data',
                'by_repository': {}
            }
        }


class LeadTimeReporter:
    """Generate lead time reports"""
    
    @staticmethod
    def generate_report(metrics: Dict):
        """Generate human-readable report"""
        results = metrics['results']
        stats = results['statistics']
        
        print("\n" + "="*70)
        print("LEAD TIME FOR CHANGES REPORT")
        print("="*70)
        
        print(f"\nPeriod: {metrics['period']['start']} to {metrics['period']['end']}")
        
        print(f"\nSummary:")
        print(f"  Total Deployments: {stats['total_deployments']}")
        print(f"  Performance Level: {results['performance_level']}")
        
        print(f"\nLead Time Statistics:")
        print(f"  Mean: {stats['mean_lead_time_hours']:.1f} hours ({stats['mean_lead_time_days']:.1f} days)")
        print(f"  Median: {stats['median_lead_time_hours']:.1f} hours ({stats['median_lead_time_days']:.1f} days)")
        print(f"  Min: {stats['min_lead_time_hours']:.1f} hours")
        print(f"  Max: {stats['max_lead_time_hours']:.1f} hours")
        print(f"  Std Dev: {stats['std_dev_hours']:.1f} hours")
        
        if 'percentiles' in results:
            print(f"\nPercentiles:")
            for percentile, value in results['percentiles'].items():
                print(f"  {percentile}: {value:.1f} hours")
        
        if results.get('by_repository'):
            print(f"\nLead Time by Repository:")
            repo_data = []
            for repo, stats in results['by_repository'].items():
                repo_data.append([repo, f"{stats['mean']:.1f}", stats['count']])
            print(tabulate(repo_data, headers=['Repository', 'Avg Hours', 'Deployments'], tablefmt='grid'))
        
        if results.get('recent_deployments'):
            print(f"\nRecent Deployments:")
            recent_data = []
            for dep in results['recent_deployments'][:5]:
                recent_data.append([
                    dep['commit_sha'],
                    dep['repository'],
                    dep['lead_time_formatted'],
                    dep['author'][:20],
                    dep['message'][:40] + '...'
                ])
            print(tabulate(recent_data, 
                         headers=['Commit', 'Repository', 'Lead Time', 'Author', 'Message'], 
                         tablefmt='grid'))
        
        print("\nPerformance Level Guide:")
        print("  Elite: Less than one hour")
        print("  High: Less than one week")
        print("  Medium: Less than one month")
        print("  Low: More than one month")
        print("\n" + "="*70)
    
    @staticmethod
    def export_json(metrics: Dict, output_file: Optional[str] = None):
        """Export metrics as JSON"""
        # Convert datetime objects to strings
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
        
        json_str = json.dumps(metrics, indent=2, default=default_serializer)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_str)
            logger.info(f"Metrics exported to {output_file}")
        else:
            print(json_str)
    
    @staticmethod
    def export_csv(metrics: Dict, output_file: str):
        """Export metrics as CSV"""
        stats = metrics['results']['statistics']
        
        # Create summary DataFrame
        summary_data = {
            'Metric': ['Lead Time for Changes'],
            'Period Start': [metrics['period']['start']],
            'Period End': [metrics['period']['end']],
            'Total Deployments': [stats['total_deployments']],
            'Mean Lead Time (hours)': [stats['mean_lead_time_hours']],
            'Median Lead Time (hours)': [stats['median_lead_time_hours']],
            'Performance Level': [metrics['results']['performance_level']]
        }
        
        df = pd.DataFrame(summary_data)
        df.to_csv(output_file, index=False)
        logger.info(f"Metrics exported to {output_file}")


@click.command()
@click.option('--config', default='config.yaml', help='Configuration file path')
@click.option('--output', type=click.Choice(['json', 'csv', 'report']), 
              default='report', help='Output format')
@click.option('--output-file', help='Output file path (for json/csv)')
def main(config, output, output_file):
    """Calculate lead time for changes metrics"""
    try:
        # Load configuration
        if not os.path.exists(config):
            logger.error(f"Configuration file not found: {config}")
            logger.info("Creating example configuration file...")
            create_example_config()
            sys.exit(1)
            
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Calculate metrics
        calculator = LeadTimeCalculator(config_data)
        metrics = calculator.calculate()
        
        # Output results
        if output == 'report':
            LeadTimeReporter.generate_report(metrics)
        elif output == 'json':
            LeadTimeReporter.export_json(metrics, output_file)
        elif output == 'csv':
            if not output_file:
                logger.error("Output file required for CSV export")
                sys.exit(1)
            LeadTimeReporter.export_csv(metrics, output_file)
            
    except Exception as e:
        logger.error(f"Error calculating lead time: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def create_example_config():
    """Create an example configuration file"""
    example_config = """# Lead Time Calculator Configuration

# Source type: github, gitlab
source_type: github

# Time range for analysis
time_range:
  start_date: "30d"  # or specific date: "2024-01-01"
  end_date: "now"

# GitHub configuration
github:
  token: ${GITHUB_TOKEN}  # Set via environment variable
  organization: your-org
  repositories:
    - api-service
    - web-frontend

# GitLab configuration (if source_type is gitlab)
gitlab:
  url: https://gitlab.com
  token: ${GITLAB_TOKEN}
  projects:
    - 123  # Project IDs
"""
    
    with open('config.yaml.example', 'w') as f:
        f.write(example_config)
    
    logger.info("Created config.yaml.example - please copy to config.yaml and update settings")


if __name__ == '__main__':
    main()