"""
Grafana Dashboards - Comprehensive Dashboard Definitions
======================================================
Production-ready Grafana dashboards for AI Teddy Bear system:
- System overview dashboard with key metrics
- HTTP performance and traffic analysis
- Business metrics and child safety monitoring
- Provider performance and circuit breaker status
- Database and cache performance monitoring
- Security and compliance dashboards
- Cost optimization and budget tracking
- ML model performance monitoring
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from ..resilience.fallback_logger import FallbackLogger


class DashboardType(Enum):
    """Types of dashboards."""
    OVERVIEW = "overview"
    HTTP_PERFORMANCE = "http_performance"
    BUSINESS_METRICS = "business_metrics"
    PROVIDER_MONITORING = "provider_monitoring"
    DATABASE_PERFORMANCE = "database_performance"
    SECURITY_COMPLIANCE = "security_compliance"
    COST_OPTIMIZATION = "cost_optimization"
    ML_MONITORING = "ml_monitoring"


@dataclass
class GrafanaPanel:
    """Grafana panel configuration."""
    id: int
    title: str
    type: str
    targets: List[Dict[str, Any]]
    gridPos: Dict[str, int]
    options: Dict[str, Any] = None
    fieldConfig: Dict[str, Any] = None
    alert: Dict[str, Any] = None


@dataclass
class GrafanaDashboard:
    """Grafana dashboard configuration."""
    id: Optional[int]
    title: str
    tags: List[str]
    timezone: str
    panels: List[GrafanaPanel]
    time: Dict[str, str]
    refresh: str
    version: int
    
    def to_json(self) -> str:
        """Convert dashboard to Grafana JSON format."""
        dashboard_dict = {
            "dashboard": {
                "id": self.id,
                "title": self.title,
                "tags": self.tags,
                "timezone": self.timezone,
                "panels": [asdict(panel) for panel in self.panels],
                "time": self.time,
                "refresh": self.refresh,
                "version": self.version,
                "schemaVersion": 30,
                "style": "dark",
                "uid": f"ai-teddy-{self.title.lower().replace(' ', '-')}",
                "editable": True,
                "gnetId": None,
                "graphTooltip": 1,
                "links": [],
                "templating": {
                    "list": []
                }
            },
            "folderId": 0,
            "overwrite": True
        }
        return json.dumps(dashboard_dict, indent=2)


class GrafanaDashboardGenerator:
    """Generator for comprehensive Grafana dashboards."""
    
    def __init__(self):
        self.logger = FallbackLogger("grafana_dashboards")
        self.panel_id_counter = 1
    
    def _get_next_panel_id(self) -> int:
        """Get next panel ID."""
        panel_id = self.panel_id_counter
        self.panel_id_counter += 1
        return panel_id
    
    def generate_overview_dashboard(self) -> GrafanaDashboard:
        """Generate system overview dashboard."""
        panels = [
            # System uptime and health
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="System Uptime",
                type="stat",
                targets=[{
                    "expr": "application_uptime_seconds",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 0, "y": 0},
                options={
                    "reduceOptions": {
                        "values": False,
                        "calcs": ["lastNotNull"],
                        "fields": ""
                    },
                    "orientation": "auto",
                    "textMode": "auto",
                    "colorMode": "value",
                    "graphMode": "area"
                },
                fieldConfig={
                    "defaults": {
                        "unit": "s",
                        "thresholds": {
                            "steps": [
                                {"color": "red", "value": 0},
                                {"color": "yellow", "value": 3600},
                                {"color": "green", "value": 86400}
                            ]
                        }
                    }
                }
            ),
            
            # Total HTTP requests
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="HTTP Requests (Total)",
                type="stat",
                targets=[{
                    "expr": "sum(rate(http_requests_total[5m]))",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 6, "y": 0},
                options={
                    "reduceOptions": {
                        "values": False,
                        "calcs": ["lastNotNull"],
                        "fields": ""
                    },
                    "orientation": "auto",
                    "textMode": "auto",
                    "colorMode": "value",
                    "graphMode": "area"
                },
                fieldConfig={
                    "defaults": {
                        "unit": "reqps",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 100},
                                {"color": "red", "value": 1000}
                            ]
                        }
                    }
                }
            ),
            
            # Active child sessions
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Active Child Sessions",
                type="stat",
                targets=[{
                    "expr": "sum(child_sessions_active)",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 12, "y": 0},
                options={
                    "reduceOptions": {
                        "values": False,
                        "calcs": ["lastNotNull"],
                        "fields": ""
                    },
                    "orientation": "auto",
                    "textMode": "auto",
                    "colorMode": "value",
                    "graphMode": "area"
                },
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 50},
                                {"color": "red", "value": 100}
                            ]
                        }
                    }
                }
            ),
            
            # Safety violations
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Safety Violations (24h)",
                type="stat",
                targets=[{
                    "expr": "sum(increase(safety_violations_total[24h]))",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 18, "y": 0},
                options={
                    "reduceOptions": {
                        "values": False,
                        "calcs": ["lastNotNull"],
                        "fields": ""
                    },
                    "orientation": "auto",
                    "textMode": "auto",
                    "colorMode": "value",
                    "graphMode": "area"
                },
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                },
                alert={
                    "conditions": [
                        {
                            "evaluator": {"params": [1], "type": "gt"},
                            "operator": {"type": "and"},
                            "query": {"params": ["A", "5m", "now"]},
                            "reducer": {"params": [], "type": "avg"},
                            "type": "query"
                        }
                    ],
                    "executionErrorState": "alerting",
                    "for": "5m",
                    "frequency": "10s",
                    "handler": 1,
                    "name": "Safety Violations Alert",
                    "noDataState": "no_data",
                    "notifications": []
                }
            ),
            
            # HTTP response time trend
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="HTTP Response Time Trend",
                type="graph",
                targets=[
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
                        "refId": "A",
                        "legendFormat": "95th percentile"
                    },
                    {
                        "expr": "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
                        "refId": "B", 
                        "legendFormat": "50th percentile"
                    }
                ],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 4},
                options={
                    "legend": {"displayMode": "table", "placement": "bottom"},
                    "tooltip": {"mode": "multi", "sort": "none"}
                },
                fieldConfig={
                    "defaults": {
                        "unit": "s",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                }
            ),
            
            # Provider health scores
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Provider Health Scores",
                type="graph",
                targets=[{
                    "expr": "provider_health_score",
                    "refId": "A",
                    "legendFormat": "{{provider_id}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 4},
                options={
                    "legend": {"displayMode": "table", "placement": "bottom"},
                    "tooltip": {"mode": "multi", "sort": "none"}
                },
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "min": 0,
                        "max": 100,
                        "thresholds": {
                            "steps": [
                                {"color": "red", "value": 0},
                                {"color": "yellow", "value": 50},
                                {"color": "green", "value": 80}
                            ]
                        }
                    }
                }
            )
        ]
        
        return GrafanaDashboard(
            id=None,
            title="AI Teddy Bear - System Overview",
            tags=["ai-teddy-bear", "overview", "production"],
            timezone="browser",
            panels=panels,
            time={"from": "now-1h", "to": "now"},
            refresh="30s",
            version=1
        )
    
    def generate_http_performance_dashboard(self) -> GrafanaDashboard:
        """Generate HTTP performance dashboard."""
        panels = [
            # Request rate by endpoint
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Request Rate by Endpoint",
                type="graph",
                targets=[{
                    "expr": "sum(rate(http_requests_total[5m])) by (endpoint)",
                    "refId": "A",
                    "legendFormat": "{{endpoint}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "reqps"
                    }
                }
            ),
            
            # Error rate by endpoint
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Error Rate by Endpoint",
                type="graph",
                targets=[{
                    "expr": "sum(rate(http_requests_total{status_code=~\"4..|5..\"}[5m])) by (endpoint) / sum(rate(http_requests_total[5m])) by (endpoint) * 100",
                    "refId": "A",
                    "legendFormat": "{{endpoint}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                }
            ),
            
            # Response time percentiles
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Response Time Percentiles",
                type="graph",
                targets=[
                    {
                        "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
                        "refId": "A",
                        "legendFormat": "99th percentile"
                    },
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
                        "refId": "B",
                        "legendFormat": "95th percentile"
                    },
                    {
                        "expr": "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
                        "refId": "C",
                        "legendFormat": "50th percentile"
                    }
                ],
                gridPos={"h": 8, "w": 24, "x": 0, "y": 8},
                fieldConfig={
                    "defaults": {
                        "unit": "s"
                    }
                }
            ),
            
            # Top slowest endpoints
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Top Slowest Endpoints",
                type="table",
                targets=[{
                    "expr": "topk(10, histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)))",
                    "refId": "A",
                    "format": "table",
                    "instant": True
                }],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 16},
                fieldConfig={
                    "defaults": {
                        "unit": "s"
                    }
                }
            ),
            
            # Request size distribution
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Request Size Distribution",
                type="graph",
                targets=[{
                    "expr": "histogram_quantile(0.95, sum(rate(http_request_size_bytes_bucket[5m])) by (le))",
                    "refId": "A",
                    "legendFormat": "95th percentile"
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 16},
                fieldConfig={
                    "defaults": {
                        "unit": "bytes"
                    }
                }
            )
        ]
        
        return GrafanaDashboard(
            id=None,
            title="AI Teddy Bear - HTTP Performance",
            tags=["ai-teddy-bear", "http", "performance"],
            timezone="browser",
            panels=panels,
            time={"from": "now-1h", "to": "now"},
            refresh="30s",
            version=1
        )
    
    def generate_business_metrics_dashboard(self) -> GrafanaDashboard:
        """Generate business metrics dashboard."""
        panels = [
            # Child interactions by type
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Child Interactions by Type",
                type="piechart",
                targets=[{
                    "expr": "sum(rate(child_interactions_total[1h])) by (interaction_type)",
                    "refId": "A",
                    "legendFormat": "{{interaction_type}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 0}
            ),
            
            # Stories generated by age group
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Stories Generated by Age Group",
                type="bargauge",
                targets=[{
                    "expr": "sum(rate(stories_generated_total[1h])) by (age_group)",
                    "refId": "A",
                    "legendFormat": "{{age_group}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "reqps"
                    }
                }
            ),
            
            # Safety violations timeline
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Safety Violations Timeline",
                type="graph",
                targets=[{
                    "expr": "sum(rate(safety_violations_total[5m])) by (violation_type)",
                    "refId": "A",
                    "legendFormat": "{{violation_type}}"
                }],
                gridPos={"h": 8, "w": 24, "x": 0, "y": 8},
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 0.1},
                                {"color": "red", "value": 1}
                            ]
                        }
                    }
                },
                alert={
                    "conditions": [
                        {
                            "evaluator": {"params": [0.1], "type": "gt"},
                            "operator": {"type": "and"},
                            "query": {"params": ["A", "5m", "now"]},
                            "reducer": {"params": [], "type": "avg"},
                            "type": "query"
                        }
                    ],
                    "executionErrorState": "alerting",
                    "for": "2m",
                    "frequency": "10s",
                    "handler": 1,
                    "name": "Safety Violations Rate Alert",
                    "noDataState": "no_data"
                }
            ),
            
            # User engagement duration
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="User Engagement Duration",
                type="graph",
                targets=[{
                    "expr": "histogram_quantile(0.95, sum(rate(user_engagement_duration_seconds_bucket[5m])) by (le, age_group))",
                    "refId": "A",
                    "legendFormat": "{{age_group}} - 95th percentile"
                }],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 16},
                fieldConfig={
                    "defaults": {
                        "unit": "s"
                    }
                }
            ),
            
            # Parent notifications
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Parent Notifications",
                type="graph",
                targets=[{
                    "expr": "sum(rate(parent_notifications_total[5m])) by (notification_type)",
                    "refId": "A",
                    "legendFormat": "{{notification_type}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 16},
                fieldConfig={
                    "defaults": {
                        "unit": "reqps"
                    }
                }
            )
        ]
        
        return GrafanaDashboard(
            id=None,
            title="AI Teddy Bear - Business Metrics",
            tags=["ai-teddy-bear", "business", "children", "safety"],
            timezone="browser",
            panels=panels,
            time={"from": "now-6h", "to": "now"},
            refresh="1m",
            version=1
        )
    
    def generate_provider_monitoring_dashboard(self) -> GrafanaDashboard:
        """Generate provider monitoring dashboard."""
        panels = [
            # Circuit breaker states
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Circuit Breaker States",
                type="stat",
                targets=[{
                    "expr": "count by (circuit_breaker_state) (circuit_breaker_state)",
                    "refId": "A",
                    "legendFormat": "{{circuit_breaker_state}}"
                }],
                gridPos={"h": 4, "w": 8, "x": 0, "y": 0},
                options={
                    "reduceOptions": {
                        "values": False,
                        "calcs": ["lastNotNull"],
                        "fields": ""
                    },
                    "orientation": "auto",
                    "textMode": "auto",
                    "colorMode": "value"
                }
            ),
            
            # Provider response times
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Provider Response Times",
                type="graph",
                targets=[{
                    "expr": "histogram_quantile(0.95, sum(rate(provider_response_duration_seconds_bucket[5m])) by (le, provider_id))",
                    "refId": "A",
                    "legendFormat": "{{provider_id}} - 95th percentile"
                }],
                gridPos={"h": 8, "w": 16, "x": 8, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "s",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                }
            ),
            
            # Provider request rates
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Provider Request Rates",
                type="graph",
                targets=[{
                    "expr": "sum(rate(provider_requests_total[5m])) by (provider_id, status)",
                    "refId": "A",
                    "legendFormat": "{{provider_id}} - {{status}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 8},
                fieldConfig={
                    "defaults": {
                        "unit": "reqps"
                    }
                }
            ),
            
            # Provider error rates
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Provider Error Rates",
                type="graph",
                targets=[{
                    "expr": "sum(rate(provider_requests_total{status=\"error\"}[5m])) by (provider_id) / sum(rate(provider_requests_total[5m])) by (provider_id) * 100",
                    "refId": "A",
                    "legendFormat": "{{provider_id}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 8},
                fieldConfig={
                    "defaults": {
                        "unit": "percent",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                }
            ),
            
            # Provider costs
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Provider Costs (Hourly)",
                type="graph",
                targets=[{
                    "expr": "sum(rate(provider_cost_total[1h])) by (provider_id)",
                    "refId": "A",
                    "legendFormat": "{{provider_id}}"
                }],
                gridPos={"h": 8, "w": 24, "x": 0, "y": 16},
                fieldConfig={
                    "defaults": {
                        "unit": "currencyUSD"
                    }
                }
            )
        ]
        
        return GrafanaDashboard(
            id=None,
            title="AI Teddy Bear - Provider Monitoring",
            tags=["ai-teddy-bear", "providers", "circuit-breakers"],
            timezone="browser",
            panels=panels,
            time={"from": "now-1h", "to": "now"},
            refresh="30s",
            version=1
        )
    
    def generate_security_compliance_dashboard(self) -> GrafanaDashboard:
        """Generate security and compliance dashboard."""
        panels = [
            # COPPA compliance checks
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="COPPA Compliance Checks",
                type="stat",
                targets=[{
                    "expr": "sum(rate(coppa_compliance_checks_total[1h]))",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 0, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "color": {"mode": "thresholds"},
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0}
                            ]
                        }
                    }
                }
            ),
            
            # Authentication failures
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Authentication Failures",
                type="stat",
                targets=[{
                    "expr": "sum(rate(auth_attempts_total{result=\"failure\"}[1h]))",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 6, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 10},
                                {"color": "red", "value": 50}
                            ]
                        }
                    }
                },
                alert={
                    "conditions": [
                        {
                            "evaluator": {"params": [10], "type": "gt"},
                            "operator": {"type": "and"},
                            "query": {"params": ["A", "5m", "now"]},
                            "reducer": {"params": [], "type": "avg"},
                            "type": "query"
                        }
                    ],
                    "executionErrorState": "alerting",
                    "for": "5m",
                    "frequency": "10s",
                    "handler": 1,
                    "name": "High Authentication Failure Rate",
                    "noDataState": "no_data"
                }
            ),
            
            # Rate limit hits
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Rate Limit Hits",
                type="stat",
                targets=[{
                    "expr": "sum(rate(rate_limit_hits_total[1h]))",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 12, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 100},
                                {"color": "red", "value": 1000}
                            ]
                        }
                    }
                }
            ),
            
            # Security violations
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Security Violations",
                type="stat",
                targets=[{
                    "expr": "sum(rate(security_violations_total[1h]))",
                    "refId": "A"
                }],
                gridPos={"h": 4, "w": 6, "x": 18, "y": 0},
                fieldConfig={
                    "defaults": {
                        "unit": "short",
                        "thresholds": {
                            "steps": [
                                {"color": "green", "value": 0},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                },
                alert={
                    "conditions": [
                        {
                            "evaluator": {"params": [1], "type": "gt"},
                            "operator": {"type": "and"},
                            "query": {"params": ["A", "5m", "now"]},
                            "reducer": {"params": [], "type": "avg"},
                            "type": "query"
                        }
                    ],
                    "executionErrorState": "alerting",
                    "for": "1m",
                    "frequency": "10s",
                    "handler": 1,
                    "name": "Security Violations Detected",
                    "noDataState": "no_data"
                }
            ),
            
            # Security violations by type
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Security Violations by Type",
                type="graph",
                targets=[{
                    "expr": "sum(rate(security_violations_total[5m])) by (violation_type)",
                    "refId": "A",
                    "legendFormat": "{{violation_type}}"
                }],
                gridPos={"h": 8, "w": 12, "x": 0, "y": 4},
                fieldConfig={
                    "defaults": {
                        "unit": "short"
                    }
                }
            ),
            
            # Failed login attempts by IP
            GrafanaPanel(
                id=self._get_next_panel_id(),
                title="Top Failed Login IPs",
                type="table",
                targets=[{
                    "expr": "topk(10, sum(rate(failed_login_attempts_total[1h])) by (source_ip))",
                    "refId": "A",
                    "format": "table",
                    "instant": True
                }],
                gridPos={"h": 8, "w": 12, "x": 12, "y": 4}
            )
        ]
        
        return GrafanaDashboard(
            id=None,
            title="AI Teddy Bear - Security & Compliance",
            tags=["ai-teddy-bear", "security", "compliance", "coppa"],
            timezone="browser",
            panels=panels,
            time={"from": "now-6h", "to": "now"},
            refresh="1m",
            version=1
        )
    
    def generate_all_dashboards(self) -> Dict[DashboardType, GrafanaDashboard]:
        """Generate all dashboards."""
        dashboards = {
            DashboardType.OVERVIEW: self.generate_overview_dashboard(),
            DashboardType.HTTP_PERFORMANCE: self.generate_http_performance_dashboard(),
            DashboardType.BUSINESS_METRICS: self.generate_business_metrics_dashboard(),
            DashboardType.PROVIDER_MONITORING: self.generate_provider_monitoring_dashboard(),
            DashboardType.SECURITY_COMPLIANCE: self.generate_security_compliance_dashboard()
        }
        
        self.logger.info(f"Generated {len(dashboards)} Grafana dashboards")
        return dashboards
    
    def export_dashboard_json(self, dashboard: GrafanaDashboard, filename: str):
        """Export dashboard to JSON file."""
        with open(filename, 'w') as f:
            f.write(dashboard.to_json())
        
        self.logger.info(f"Dashboard exported to {filename}")
    
    def export_all_dashboards(self, output_dir: str = "./grafana_dashboards"):
        """Export all dashboards to JSON files."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        dashboards = self.generate_all_dashboards()
        
        for dashboard_type, dashboard in dashboards.items():
            filename = f"{output_dir}/{dashboard_type.value}.json"
            self.export_dashboard_json(dashboard, filename)
        
        self.logger.info(f"All dashboards exported to {output_dir}")


# Global dashboard generator instance
grafana_dashboard_generator = GrafanaDashboardGenerator()