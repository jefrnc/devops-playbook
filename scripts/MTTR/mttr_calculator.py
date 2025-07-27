#!/usr/bin/env python3
"""
MTTR (Mean Time to Recovery) Calculator
Measures the time to recover from production incidents
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
import requests
from tabulate import tabulate
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    """Incident severity levels"""

    P1 = "P1 - Critical"
    P2 = "P2 - High"
    P3 = "P3 - Medium"
    P4 = "P4 - Low"


@dataclass
class Incident:
    """Incident data structure"""

    id: str
    title: str
    created_at: datetime
    resolved_at: Optional[datetime]
    severity: str
    service: str
    mttr_minutes: Optional[float] = None

    def calculate_mttr(self):
        """Calculate MTTR for this incident"""
        if self.resolved_at and self.created_at:
            self.mttr_minutes = (
                self.resolved_at - self.created_at
            ).total_seconds() / 60


class IncidentSource:
    """Base class for incident data sources"""

    def get_incidents(self, start_date: datetime, end_date: datetime) -> List[Incident]:
        """Fetch incidents from source"""
        raise NotImplementedError


class PagerDutySource(IncidentSource):
    """Fetch incidents from PagerDuty"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.pagerduty.com"
        self.headers = {
            "Authorization": f"Token token={api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

    def get_incidents(self, start_date: datetime, end_date: datetime) -> List[Incident]:
        """Fetch incidents from PagerDuty API"""
        incidents = []
        offset = 0
        limit = 100

        while True:
            params = {
                "since": start_date.isoformat(),
                "until": end_date.isoformat(),
                "statuses[]": ["triggered", "acknowledged", "resolved"],
                "limit": limit,
                "offset": offset,
            }

            response = requests.get(
                f"{self.base_url}/incidents", headers=self.headers, params=params
            )
            response.raise_for_status()

            data = response.json()

            for inc in data["incidents"]:
                # Only include resolved incidents for MTTR calculation
                if inc["status"] == "resolved":
                    incident = Incident(
                        id=inc["id"],
                        title=inc["title"],
                        created_at=parse(inc["created_at"]),
                        resolved_at=(
                            parse(inc["resolved_at"])
                            if inc.get("resolved_at")
                            else None
                        ),
                        severity=self._map_severity(inc["urgency"]),
                        service=(
                            inc["service"]["summary"]
                            if inc.get("service")
                            else "Unknown"
                        ),
                    )
                    incident.calculate_mttr()
                    incidents.append(incident)

            if not data["more"]:
                break

            offset += limit

        return incidents

    def _map_severity(self, urgency: str) -> str:
        """Map PagerDuty urgency to standard severity"""
        mapping = {
            "high": IncidentSeverity.P1.value,
            "medium": IncidentSeverity.P2.value,
            "low": IncidentSeverity.P3.value,
        }
        return mapping.get(urgency, IncidentSeverity.P3.value)


class OpsGenieSource(IncidentSource):
    """Fetch incidents from OpsGenie"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.opsgenie.com/v2"
        self.headers = {"Authorization": f"GenieKey {api_key}"}

    def get_incidents(self, start_date: datetime, end_date: datetime) -> List[Incident]:
        """Fetch incidents from OpsGenie API"""
        incidents = []

        # OpsGenie uses alerts API
        params = {
            "query": f"createdAt >= {int(start_date.timestamp())} AND createdAt <= {int(end_date.timestamp())}",
            "limit": 100,
            "sort": "createdAt",
            "order": "desc",
        }

        response = requests.get(
            f"{self.base_url}/alerts", headers=self.headers, params=params
        )
        response.raise_for_status()

        data = response.json()

        for alert in data["data"]:
            # Get alert details for resolution time
            detail_response = requests.get(
                f"{self.base_url}/alerts/{alert['id']}", headers=self.headers
            )
            detail_response.raise_for_status()
            details = detail_response.json()["data"]

            if details["status"] == "closed":
                incident = Incident(
                    id=alert["id"],
                    title=alert["message"],
                    created_at=parse(alert["createdAt"]),
                    resolved_at=parse(details["updatedAt"]),
                    severity=self._map_priority(alert["priority"]),
                    service=alert.get("source", "Unknown"),
                )
                incident.calculate_mttr()
                incidents.append(incident)

        return incidents

    def _map_priority(self, priority: str) -> str:
        """Map OpsGenie priority to standard severity"""
        mapping = {
            "P1": IncidentSeverity.P1.value,
            "P2": IncidentSeverity.P2.value,
            "P3": IncidentSeverity.P3.value,
            "P4": IncidentSeverity.P4.value,
            "P5": IncidentSeverity.P4.value,
        }
        return mapping.get(priority, IncidentSeverity.P3.value)


class CloudWatchSource(IncidentSource):
    """Fetch incidents from AWS CloudWatch Alarms"""

    def __init__(self, profile: str, region: str):
        import boto3

        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.cloudwatch = self.session.client("cloudwatch")
        self.logs = self.session.client("logs")

    def get_incidents(self, start_date: datetime, end_date: datetime) -> List[Incident]:
        """Fetch alarm history from CloudWatch"""
        incidents = []

        # Get alarm history
        paginator = self.cloudwatch.get_paginator("describe_alarm_history")
        iterator = paginator.paginate(StartDate=start_date, EndDate=end_date)

        # Group alarm state changes by alarm name
        alarm_events = {}

        for page in iterator:
            for item in page["AlarmHistoryItems"]:
                alarm_name = item["AlarmName"]
                if alarm_name not in alarm_events:
                    alarm_events[alarm_name] = []
                alarm_events[alarm_name].append(item)

        # Process alarm events to find incident pairs
        for alarm_name, events in alarm_events.items():
            # Sort events by timestamp
            events.sort(key=lambda x: x["Timestamp"])

            i = 0
            while i < len(events):
                event = events[i]

                # Look for ALARM state (incident start)
                if event["HistorySummary"].startswith("Alarm updated from OK to ALARM"):
                    incident_start = event["Timestamp"]

                    # Look for corresponding OK state (incident end)
                    j = i + 1
                    while j < len(events):
                        if events[j]["HistorySummary"].startswith(
                            "Alarm updated from ALARM to OK"
                        ):
                            incident_end = events[j]["Timestamp"]

                            incident = Incident(
                                id=f"{alarm_name}_{incident_start.timestamp()}",
                                title=f"Alarm: {alarm_name}",
                                created_at=incident_start,
                                resolved_at=incident_end,
                                severity=self._determine_severity(alarm_name),
                                service=self._extract_service(alarm_name),
                            )
                            incident.calculate_mttr()
                            incidents.append(incident)
                            break
                        j += 1

                i += 1

        return incidents

    def _determine_severity(self, alarm_name: str) -> str:
        """Determine severity based on alarm name patterns"""
        if any(
            keyword in alarm_name.lower() for keyword in ["critical", "p1", "outage"]
        ):
            return IncidentSeverity.P1.value
        elif any(keyword in alarm_name.lower() for keyword in ["high", "p2", "error"]):
            return IncidentSeverity.P2.value
        else:
            return IncidentSeverity.P3.value

    def _extract_service(self, alarm_name: str) -> str:
        """Extract service name from alarm name"""
        # Common patterns: service-name-alarm, service_name_metric
        parts = alarm_name.replace("-", "_").split("_")
        if len(parts) > 0:
            return parts[0]
        return "Unknown"


class MTTRCalculator:
    """Calculate MTTR metrics"""

    def __init__(self, config: Dict):
        self.config = config
        self.source = self._initialize_source()

    def _initialize_source(self) -> IncidentSource:
        """Initialize the appropriate incident source"""
        source_type = self.config.get("incident_source", "pagerduty")

        if source_type == "pagerduty":
            api_key = os.environ.get("PAGERDUTY_TOKEN") or self.config.get(
                "pagerduty", {}
            ).get("api_key")
            if not api_key:
                raise ValueError("PagerDuty API key not found")
            return PagerDutySource(api_key)

        elif source_type == "opsgenie":
            api_key = os.environ.get("OPSGENIE_TOKEN") or self.config.get(
                "opsgenie", {}
            ).get("api_key")
            if not api_key:
                raise ValueError("OpsGenie API key not found")
            return OpsGenieSource(api_key)

        elif source_type == "cloudwatch":
            aws_config = self.config.get("aws", {})
            return CloudWatchSource(
                profile=aws_config.get("profile", "default"),
                region=aws_config.get("region", "us-east-1"),
            )
        else:
            raise ValueError(f"Unsupported incident source: {source_type}")

    def calculate(self) -> Dict:
        """Calculate MTTR metrics"""
        # Parse time range
        start_date, end_date = self._parse_time_range()

        logger.info(f"Calculating MTTR from {start_date} to {end_date}")

        # Fetch incidents
        incidents = self.source.get_incidents(start_date, end_date)

        if not incidents:
            logger.warning("No resolved incidents found in the specified time range")
            return self._empty_results(start_date, end_date)

        # Filter by severity if specified
        severity_filter = self.config.get("severity_filter", [])
        if severity_filter:
            incidents = [
                i
                for i in incidents
                if any(sev in i.severity for sev in severity_filter)
            ]

        # Calculate metrics
        mttr_values = [i.mttr_minutes for i in incidents if i.mttr_minutes is not None]

        if not mttr_values:
            return self._empty_results(start_date, end_date)

        # Basic statistics
        metrics = {
            "total_incidents": len(incidents),
            "mean_mttr_minutes": statistics.mean(mttr_values),
            "median_mttr_minutes": statistics.median(mttr_values),
            "min_mttr_minutes": min(mttr_values),
            "max_mttr_minutes": max(mttr_values),
            "std_dev_minutes": (
                statistics.stdev(mttr_values) if len(mttr_values) > 1 else 0
            ),
        }

        # Convert to hours for readability
        metrics["mean_mttr_hours"] = metrics["mean_mttr_minutes"] / 60
        metrics["median_mttr_hours"] = metrics["median_mttr_minutes"] / 60

        # Group by severity
        df = pd.DataFrame([asdict(i) for i in incidents])
        by_severity = (
            df.groupby("severity")["mttr_minutes"]
            .agg(["mean", "count"])
            .to_dict("index")
        )

        # Group by service
        by_service = (
            df.groupby("service")["mttr_minutes"]
            .agg(["mean", "count"])
            .to_dict("index")
        )

        # Calculate percentiles
        percentiles = {
            "p50": statistics.quantiles(mttr_values, n=2)[0],
            "p75": (
                statistics.quantiles(mttr_values, n=4)[2]
                if len(mttr_values) > 3
                else max(mttr_values)
            ),
            "p90": (
                statistics.quantiles(mttr_values, n=10)[8]
                if len(mttr_values) > 9
                else max(mttr_values)
            ),
            "p95": (
                statistics.quantiles(mttr_values, n=20)[18]
                if len(mttr_values) > 19
                else max(mttr_values)
            ),
        }

        # Determine performance level
        performance_level = self._determine_performance_level(
            metrics["median_mttr_minutes"]
        )

        # Analyze trends
        df["week"] = pd.to_datetime(df["created_at"]).dt.isocalendar().week
        weekly_trend = df.groupby("week")["mttr_minutes"].median().to_dict()

        # Find longest incidents
        longest_incidents = df.nlargest(5, "mttr_minutes")[
            ["id", "title", "mttr_minutes", "severity"]
        ].to_dict("records")

        return {
            "metric": "mean_time_to_recovery",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "results": {
                "statistics": metrics,
                "percentiles": percentiles,
                "by_severity": by_severity,
                "by_service": by_service,
                "performance_level": performance_level,
                "weekly_trend": weekly_trend,
                "longest_incidents": longest_incidents,
            },
        }

    def _parse_time_range(self) -> Tuple[datetime, datetime]:
        """Parse time range from config"""
        time_range = self.config.get("time_range", {})

        # Parse end date
        end_date_str = time_range.get("end_date", "now")
        if end_date_str == "now":
            end_date = datetime.now()
        else:
            end_date = parse(end_date_str)

        # Parse start date
        start_date_str = time_range.get("start_date", "30d")
        if start_date_str.endswith("d"):
            days = int(start_date_str[:-1])
            start_date = end_date - timedelta(days=days)
        else:
            start_date = parse(start_date_str)

        return start_date, end_date

    def _determine_performance_level(self, median_minutes: float) -> str:
        """Determine DORA performance level based on median MTTR"""
        median_hours = median_minutes / 60

        if median_hours <= 1:  # Less than 1 hour
            return "Elite"
        elif median_hours <= 24:  # Less than 1 day
            return "High"
        elif median_hours <= 24 * 7:  # Less than 1 week
            return "Medium"
        else:
            return "Low"

    def _empty_results(self, start_date: datetime, end_date: datetime) -> Dict:
        """Return empty results structure"""
        return {
            "metric": "mean_time_to_recovery",
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "results": {
                "statistics": {
                    "total_incidents": 0,
                    "mean_mttr_minutes": 0,
                    "median_mttr_minutes": 0,
                },
                "performance_level": "No data",
                "by_severity": {},
                "by_service": {},
            },
        }


class MTTRReporter:
    """Generate MTTR reports"""

    @staticmethod
    def generate_report(metrics: Dict):
        """Generate human-readable report"""
        results = metrics["results"]
        stats = results["statistics"]

        print("\n" + "=" * 70)
        print("MEAN TIME TO RECOVERY (MTTR) REPORT")
        print("=" * 70)

        print(f"\nPeriod: {metrics['period']['start']} to {metrics['period']['end']}")

        print(f"\nSummary:")
        print(f"  Total Incidents: {stats['total_incidents']}")
        print(f"  Performance Level: {results['performance_level']}")

        print(f"\nMTTR Statistics:")
        print(
            f"  Mean: {stats['mean_mttr_minutes']:.1f} minutes ({stats['mean_mttr_hours']:.1f} hours)"
        )
        print(
            f"  Median: {stats['median_mttr_minutes']:.1f} minutes ({stats['median_mttr_hours']:.1f} hours)"
        )
        print(f"  Min: {stats['min_mttr_minutes']:.1f} minutes")
        print(f"  Max: {stats['max_mttr_minutes']:.1f} minutes")
        print(f"  Std Dev: {stats['std_dev_minutes']:.1f} minutes")

        if "percentiles" in results:
            print(f"\nPercentiles:")
            for percentile, value in results["percentiles"].items():
                print(f"  {percentile}: {value:.1f} minutes")

        if results.get("by_severity"):
            print(f"\nMTTR by Severity:")
            severity_data = []
            for severity, stats in results["by_severity"].items():
                severity_data.append([severity, f"{stats['mean']:.1f}", stats["count"]])
            print(
                tabulate(
                    severity_data,
                    headers=["Severity", "Avg Minutes", "Count"],
                    tablefmt="grid",
                )
            )

        if results.get("by_service"):
            print(f"\nMTTR by Service (Top 10):")
            service_data = []
            sorted_services = sorted(
                results["by_service"].items(), key=lambda x: x[1]["count"], reverse=True
            )[:10]
            for service, stats in sorted_services:
                service_data.append(
                    [service[:30], f"{stats['mean']:.1f}", stats["count"]]
                )
            print(
                tabulate(
                    service_data,
                    headers=["Service", "Avg Minutes", "Count"],
                    tablefmt="grid",
                )
            )

        if results.get("longest_incidents"):
            print(f"\nLongest Incidents:")
            incident_data = []
            for inc in results["longest_incidents"]:
                incident_data.append(
                    [
                        inc["id"][:20],
                        (
                            inc["title"][:40] + "..."
                            if len(inc["title"]) > 40
                            else inc["title"]
                        ),
                        f"{inc['mttr_minutes']:.1f}",
                        inc["severity"],
                    ]
                )
            print(
                tabulate(
                    incident_data,
                    headers=["ID", "Title", "Minutes", "Severity"],
                    tablefmt="grid",
                )
            )

        print("\nPerformance Level Guide:")
        print("  Elite: Less than one hour")
        print("  High: Less than one day")
        print("  Medium: Less than one week")
        print("  Low: More than one week")
        print("\n" + "=" * 70)

    @staticmethod
    def export_json(metrics: Dict, output_file: Optional[str] = None):
        """Export metrics as JSON"""
        json_str = json.dumps(metrics, indent=2, default=str)

        if output_file:
            with open(output_file, "w") as f:
                f.write(json_str)
            logger.info(f"Metrics exported to {output_file}")
        else:
            print(json_str)


@click.command()
@click.option("--config", default="config.yaml", help="Configuration file path")
@click.option(
    "--output",
    type=click.Choice(["json", "report"]),
    default="report",
    help="Output format",
)
@click.option("--output-file", help="Output file path (for json)")
def main(config, output, output_file):
    """Calculate MTTR (Mean Time to Recovery) metrics"""
    try:
        # Load configuration
        if not os.path.exists(config):
            logger.error(f"Configuration file not found: {config}")
            create_example_config()
            sys.exit(1)

        with open(config, "r") as f:
            config_data = yaml.safe_load(f)

        # Calculate metrics
        calculator = MTTRCalculator(config_data)
        metrics = calculator.calculate()

        # Output results
        if output == "report":
            MTTRReporter.generate_report(metrics)
        elif output == "json":
            MTTRReporter.export_json(metrics, output_file)

    except Exception as e:
        logger.error(f"Error calculating MTTR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def create_example_config():
    """Create an example configuration file"""
    example_config = """# MTTR Calculator Configuration

# Incident source: pagerduty, opsgenie, cloudwatch
incident_source: pagerduty

# Time range for analysis
time_range:
  start_date: "30d"  # or specific date: "2024-01-01"
  end_date: "now"

# Filter by severity (optional)
severity_filter: []  # e.g., ["P1", "P2"]

# PagerDuty configuration
pagerduty:
  api_key: ${PAGERDUTY_TOKEN}  # Set via environment variable

# OpsGenie configuration (if incident_source is opsgenie)
opsgenie:
  api_key: ${OPSGENIE_TOKEN}

# AWS CloudWatch configuration (if incident_source is cloudwatch)
aws:
  profile: default
  region: us-east-1
"""

    with open("config.yaml.example", "w") as f:
        f.write(example_config)

    logger.info(
        "Created config.yaml.example - please copy to config.yaml and update settings"
    )


if __name__ == "__main__":
    main()
