"""
AI TEDDY BEAR - ROUTE MONITORING
Production-grade route monitoring and conflict detection system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any

from fastapi import FastAPI
from fastapi.routing import APIRoute


logger = logging.getLogger(__name__)


@dataclass
class RouteConflict:
    """Represents a route conflict with detailed information."""

    conflict_type: str
    path: str
    details: Dict[str, Any]
    severity: str
    timestamp: datetime

    @staticmethod
    def method_conflict(path: str, methods_a: Set[str], methods_b: Set[str]) -> "RouteConflict":
        overlap = sorted((methods_a & methods_b))
        details = {
            "methods_overlap": overlap,
            "methods_a": sorted(methods_a),
            "methods_b": sorted(methods_b),
        }
        return RouteConflict(
            conflict_type="method_conflict",
            path=path,
            details=details,
            severity="HIGH" if overlap else "LOW",
            timestamp=datetime.utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.conflict_type,
            "path": self.path,
            "severity": self.severity,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class RouteMonitor:
    """
    Advanced route monitoring system for FastAPI applications.
    Detects conflicts, validates organization, and provides comprehensive reporting.
    """

    def __init__(self, app: FastAPI):
        self.app = app
        self.route_registry: Dict[str, Dict[str, Any]] = {}
        self.conflicts: List[RouteConflict] = []
        self.last_scan_time: Optional[datetime] = None

    def scan_routes(self) -> Dict[str, Any]:
        """
        Comprehensive route scanning with conflict detection.

        Returns:
            Dict containing detailed route analysis
        """
        routes_by_path: Dict[str, List[Dict[str, Any]]] = {}
        routes_by_prefix: Dict[str, List[Dict[str, Any]]] = {}
        health_routes: List[Dict[str, Any]] = []
        api_routes: List[Dict[str, Any]] = []
        web_routes: List[Dict[str, Any]] = []

        # Reset previous state
        self.conflicts.clear()
        self.route_registry.clear()

        for route in self.app.routes:
            if not isinstance(route, APIRoute):
                continue

            path: str = route.path
            methods: Set[str] = set(route.methods or [])
            name: str = route.name or "unknown"

            # Categorize route by simple heuristics
            if path.startswith("/health"):
                category_list = health_routes
            elif path.startswith("/api"):
                category_list = api_routes
            else:
                category_list = web_routes

            info = {"path": path, "methods": sorted(methods), "name": name}
            category_list.append(info)
            self.route_registry[path] = info

            # Track by prefix (everything up to the last '/segment')
            if path == "/":
                prefix = "/"
            else:
                prefix = path.rstrip("/").rsplit("/", 1)[0] or "/"

            routes_by_prefix.setdefault(prefix, []).append(info)

            # Detect method conflicts for the same path
            items = routes_by_path.setdefault(path, [])
            for existing in items:
                m_old = set(existing["methods"])  # type: ignore[arg-type]
                overlap = m_old & methods
                if overlap:
                    self.conflicts.append(
                        RouteConflict.method_conflict(path, m_old, methods)
                    )
            items.append(info)

        self.last_scan_time = datetime.utcnow()

        result: Dict[str, Any] = {
            "scan_timestamp": self.last_scan_time.isoformat(),
            "routes_by_prefix": routes_by_prefix,
            "route_categories": {
                "api_routes": len(api_routes),
                "web_routes": len(web_routes),
                "health_routes": len(health_routes),
            },
            "total_routes": len(self.route_registry),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "conflicts_detected": len(self.conflicts),
            "overall_status": "HEALTHY" if not self.conflicts else "ISSUES_DETECTED",
        }

        return result

    def validate_route_organization(self) -> Dict[str, Any]:
        """
        Validate route organization and detect potential issues.
        """
        scan = self.scan_routes()

        recommendations: List[Dict[str, Any]] = []

        # Recommend grouping if too many API routes under root
        api_count = scan["route_categories"]["api_routes"]
        if api_count > 0 and api_count >= 10:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "ORGANIZATION",
                    "message": "Consider grouping API routes by feature area (e.g., /api/v1/esp32)",
                }
            )

        status = (
            "HEALTHY"
            if scan["conflicts_detected"] == 0
            else ("WARNING" if scan["conflicts_detected"] <= 2 else "CRITICAL")
        )

        return {
            "overall_status": status,
            "conflicts_detected": scan["conflicts_detected"],
            "recommendations": recommendations,
        }

    def generate_route_report(self) -> str:
        """
        Generate a simple markdown report of routes and conflicts.
        """
        validation = self.validate_route_organization()
        scan = self.scan_routes()

        lines: List[str] = []
        lines.append("# AI Teddy Bear - Route Analysis Report")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Generated: {datetime.utcnow().isoformat()}")
        lines.append(f"Total Routes: {scan['total_routes']}")
        lines.append(f"Conflicts Detected: {scan['conflicts_detected']}")
        lines.append(f"Overall Status: {validation['overall_status']}")
        lines.append("")

        # Executive Summary
        lines.extend(
            [
                "## Executive Summary",
                f"- API Routes: {scan['route_categories']['api_routes']}",
                f"- Web Routes: {scan['route_categories']['web_routes']}",
                f"- Health Routes: {scan['route_categories']['health_routes']}",
                "",
            ]
        )

        # Conflicts
        if scan["conflicts_detected"]:
            lines.append("## Detected Conflicts")
            lines.append("")
            for c in self.conflicts:
                lines.extend(
                    [
                        f"### {c.severity} - {c.conflict_type}",
                        f"Path: `{c.path}`",
                        f"Details: {c.details}",
                        "",
                    ]
                )
        else:
            lines.extend(
                [
                    "## No Conflicts Detected",
                    "All routes are properly organized without conflicts.",
                    "",
                ]
            )

        # Routes by Prefix
        lines.append("## Routes by Prefix")
        lines.append("")
        for prefix, routes in scan["routes_by_prefix"].items():
            lines.append(f"### {prefix} ({len(routes)} routes)")
            for r in routes[:5]:
                methods_str = ", ".join(r["methods"]) if isinstance(r["methods"], list) else r["methods"]
                lines.append(f"- `{r['path']}` - [{methods_str}] - {r['name']}")
            if len(routes) > 5:
                lines.append(f"- ... and {len(routes) - 5} more routes")
            lines.append("")

        return "\n".join(lines)

    def get_route_summary(self) -> Dict[str, Any]:
        """Get a concise summary of route status."""
        if not self.last_scan_time:
            scan_results = self.scan_routes()
        else:
            # Use cached results if recent (less than 5 minutes)
            if (datetime.utcnow() - self.last_scan_time).seconds < 300:
                scan_results = {
                    "total_routes": len(self.route_registry),
                    "conflicts_detected": len(self.conflicts),
                }
            else:
                scan_results = self.scan_routes()

        return {
            "total_routes": scan_results["total_routes"],
            "conflicts": scan_results.get("conflicts_detected", 0),
            "last_scan": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "status": (
                "HEALTHY" if scan_results.get("conflicts_detected", 0) == 0 else "ISSUES_DETECTED"
            ),
        }


def monitor_routes(app: FastAPI) -> RouteMonitor:
    """
    Create and return a route monitor for the given FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        RouteMonitor instance
    """
    return RouteMonitor(app)


def validate_application_routes(app: FastAPI) -> bool:
    """Validate routes for a FastAPI app and return True if acceptable."""
    monitor = RouteMonitor(app)
    result = monitor.validate_route_organization()
    status = result.get("overall_status", "HEALTHY")
    if status in ("HEALTHY", "MINOR_ISSUES", "WARNING"):
        return True
    return False

