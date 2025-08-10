"""
🧸 AI TEDDY BEAR - ROUTE MONITORING
Production-grade route monitoring and conflict detection system
"""

import logging
from typing import Dict, List, Set, Optional, Tuple
from fastapi import FastAPI
from fastapi.routing import APIRoute
from datetime import datetime

logger = logging.getLogger(__name__)


class RouteConflict:
    """Represents a route conflict with detailed information."""

    def __init__(self, conflict_type: str, path: str, details: Dict):
        self.conflict_type = conflict_type
        self.path = path
        self.details = details
        self.severity = self._calculate_severity()
        self.timestamp = datetime.utcnow()

    def _calculate_severity(self) -> str:
        """Calculate conflict severity based on type and details."""
        if self.conflict_type == "method_conflict":
            return "HIGH"
        elif self.conflict_type == "auth_inconsistency":
            return "MEDIUM"
        elif self.conflict_type == "prefix_overlap":
            return "LOW"
        else:
            return "MEDIUM"

    def to_dict(self) -> Dict:
        """Convert conflict to dictionary for serialization."""
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
        self.route_registry: Dict[str, Dict] = {}
        self.conflicts: List[RouteConflict] = []
        self.last_scan_time: Optional[datetime] = None

    def scan_routes(self) -> Dict[str, any]:
        """
        Comprehensive route scanning with conflict detection.

        Returns:
            Dict containing detailed route analysis
        """
        logger.info("🔍 Starting comprehensive route scan...")

        routes_by_path = {}
        routes_by_prefix = {}
        auth_patterns = {}
        health_routes = []
        api_routes = []
        web_routes = []

        # Clear previous conflicts
        self.conflicts.clear()

        # Scan all routes
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                path = route.path
                methods = route.methods
                route_name = getattr(route, "name", "unnamed")
                tags = getattr(route, "tags", [])

                # Analyze route characteristics
                self._analyze_route_characteristics(
                    path,
                    methods,
                    route_name,
                    tags,
                    routes_by_path,
                    routes_by_prefix,
                    auth_patterns,
                    health_routes,
                    api_routes,
                    web_routes,
                )

        # Detect conflicts
        self._detect_method_conflicts(routes_by_path)
        self._detect_auth_inconsistencies(auth_patterns)
        self._detect_prefix_overlaps(routes_by_prefix)
        self._detect_health_route_duplication(health_routes)

        self.last_scan_time = datetime.utcnow()

        scan_results = {
            "scan_timestamp": self.last_scan_time.isoformat(),
            "total_routes": len(routes_by_path),
            "conflicts_detected": len(self.conflicts),
            "routes_by_path": routes_by_path,
            "routes_by_prefix": routes_by_prefix,
            "route_categories": {
                "api_routes": len(api_routes),
                "web_routes": len(web_routes),
                "health_routes": len(health_routes),
            },
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "auth_patterns": auth_patterns,
        }

        # Set overall_status for healthcheck integration
        scan_results["overall_status"] = (
            "HEALTHY" if scan_results["conflicts_detected"] == 0 else "CRITICAL"
        )
        logger.info(
            f"✅ Route scan completed: {len(routes_by_path)} routes, {len(self.conflicts)} conflicts"
        )
        return scan_results

    def _analyze_route_characteristics(
        self,
        path: str,
        methods: Set,
        route_name: str,
        tags: List,
        routes_by_path: Dict,
        routes_by_prefix: Dict,
        auth_patterns: Dict,
        health_routes: List,
        api_routes: List,
        web_routes: List,
    ):
        """Analyze individual route characteristics."""

        # Check for existing path conflicts
        if path in routes_by_path:
            existing_methods = routes_by_path[path]["methods"]
            method_conflicts = methods.intersection(existing_methods)
            if method_conflicts:
                self.conflicts.append(
                    RouteConflict(
                        "method_conflict",
                        path,
                        {
                            "conflicting_methods": list(method_conflicts),
                            "existing_route": routes_by_path[path]["name"],
                            "new_route": route_name,
                        },
                    )
                )
        else:
            routes_by_path[path] = {
                "name": route_name,
                "methods": methods,
                "tags": tags,
            }

        # Categorize routes
        if path.startswith("/api/"):
            api_routes.append(path)
        elif path.startswith("/web/") or "dashboard" in path.lower():
            web_routes.append(path)
        elif "health" in path.lower():
            health_routes.append(path)

        # Extract prefix for analysis
        path_parts = path.strip("/").split("/")
        if len(path_parts) >= 2:
            prefix = f"/{path_parts[0]}/{path_parts[1]}"
            if prefix not in routes_by_prefix:
                routes_by_prefix[prefix] = []
            routes_by_prefix[prefix].append(
                {
                    "path": path,
                    "name": route_name,
                    "methods": list(methods),
                    "tags": tags,
                }
            )

        # Analyze authentication patterns
        if "auth" in path.lower():
            auth_type = "unknown"
            if "/api/auth/" in path:
                auth_type = "api_auth"
            elif "/api/v1/auth/" in path:
                auth_type = "versioned_api_auth"
            elif "/auth/" in path:
                auth_type = "simple_auth"

            if auth_type not in auth_patterns:
                auth_patterns[auth_type] = []
            auth_patterns[auth_type].append(path)

    def _detect_method_conflicts(self, routes_by_path: Dict):
        """Detect HTTP method conflicts on same paths."""
        # This is already handled in _analyze_route_characteristics
        pass

    def _detect_auth_inconsistencies(self, auth_patterns: Dict):
        """Detect inconsistent authentication route patterns."""
        if len(auth_patterns) > 1:
            self.conflicts.append(
                RouteConflict(
                    "auth_inconsistency",
                    "multiple_auth_patterns",
                    {
                        "patterns_found": list(auth_patterns.keys()),
                        "recommendation": "Standardize authentication routes under single prefix",
                        "routes_by_pattern": auth_patterns,
                    },
                )
            )

    def _detect_prefix_overlaps(self, routes_by_prefix: Dict):
        """Detect potentially problematic prefix overlaps."""
        api_prefixes = [
            prefix for prefix in routes_by_prefix.keys() if prefix.startswith("/api/")
        ]

        # Check for /api/v1 conflicts
        v1_routes = [prefix for prefix in api_prefixes if "/v1" in prefix]
        if len(v1_routes) > 3:  # Threshold for too many v1 prefixes
            self.conflicts.append(
                RouteConflict(
                    "prefix_overlap",
                    "/api/v1/*",
                    {
                        "overlapping_prefixes": v1_routes,
                        "recommendation": "Consider consolidating similar prefixes",
                        "route_count": sum(
                            len(routes_by_prefix[prefix]) for prefix in v1_routes
                        ),
                    },
                )
            )

    def _detect_health_route_duplication(self, health_routes: List):
        """Detect duplicate health check routes."""
        if len(health_routes) > 3:
            self.conflicts.append(
                RouteConflict(
                    "health_duplication",
                    "multiple_health_routes",
                    {
                        "health_routes": health_routes,
                        "count": len(health_routes),
                        "recommendation": "Consolidate health checks into single endpoint",
                    },
                )
            )

    def validate_route_organization(self) -> Dict[str, any]:
        """
        Validate route organization against best practices.

        Returns:
            Comprehensive validation results with recommendations
        """
        if not self.last_scan_time:
            scan_results = self.scan_routes()
        else:
            scan_results = self.scan_routes()  # Always get fresh data

        validation_results = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "overall_status": "UNKNOWN",
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "metrics": {
                "total_routes": scan_results["total_routes"],
                "conflicts_count": scan_results["conflicts_detected"],
                "api_routes": scan_results["route_categories"]["api_routes"],
                "web_routes": scan_results["route_categories"]["web_routes"],
                "health_routes": scan_results["route_categories"]["health_routes"],
            },
        }

        # Analyze conflicts by severity
        critical_conflicts = [c for c in self.conflicts if c.severity == "HIGH"]
        medium_conflicts = [c for c in self.conflicts if c.severity == "MEDIUM"]
        low_conflicts = [c for c in self.conflicts if c.severity == "LOW"]

        # Determine overall status
        if critical_conflicts:
            validation_results["overall_status"] = "CRITICAL"
            validation_results["critical_issues"] = [
                c.to_dict() for c in critical_conflicts
            ]
        elif medium_conflicts:
            validation_results["overall_status"] = "WARNING"
            validation_results["warnings"] = [c.to_dict() for c in medium_conflicts]
        elif low_conflicts:
            validation_results["overall_status"] = "MINOR_ISSUES"
            validation_results["warnings"] = [c.to_dict() for c in low_conflicts]
        else:
            validation_results["overall_status"] = "HEALTHY"

        # Generate recommendations
        self._generate_recommendations(validation_results, scan_results)

        return validation_results

    def _generate_recommendations(self, validation_results: Dict, scan_results: Dict):
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # API versioning recommendations
        api_routes = scan_results["route_categories"]["api_routes"]
        total_routes = scan_results["total_routes"]

        if api_routes > 0:
            versioned_ratio = (
                len([r for r in scan_results["routes_by_path"].keys() if "/v1/" in r])
                / api_routes
            )
            if versioned_ratio < 0.8:
                recommendations.append(
                    {
                        "priority": "HIGH",
                        "category": "API_VERSIONING",
                        "message": "Add version prefixes to all API routes (e.g., /api/v1/)",
                        "affected_routes": api_routes
                        - int(api_routes * versioned_ratio),
                    }
                )

        # Authentication consolidation
        auth_patterns = scan_results.get("auth_patterns", {})
        if len(auth_patterns) > 1:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "AUTH_CONSISTENCY",
                    "message": "Consolidate authentication routes under single prefix",
                    "patterns": list(auth_patterns.keys()),
                }
            )

        # Health route optimization
        health_count = scan_results["route_categories"]["health_routes"]
        if health_count > 3:
            recommendations.append(
                {
                    "priority": "LOW",
                    "category": "HEALTH_OPTIMIZATION",
                    "message": f"Consider consolidating {health_count} health routes",
                    "current_count": health_count,
                    "recommended_count": "1-2",
                }
            )

        # Route organization
        if total_routes > 50:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "ORGANIZATION",
                    "message": "Consider implementing route grouping for better maintainability",
                    "total_routes": total_routes,
                }
            )

        validation_results["recommendations"] = recommendations

    def generate_route_report(self) -> str:
        """
        Generate comprehensive route documentation report.

        Returns:
            Formatted markdown report
        """
        validation_results = self.validate_route_organization()
        scan_results = self.scan_routes()

        report_lines = [
            "# 🧸 AI Teddy Bear - Route Analysis Report",
            "=" * 60,
            "",
            f"**Generated:** {datetime.utcnow().isoformat()}",
            f"**Total Routes:** {scan_results['total_routes']}",
            f"**Conflicts Detected:** {scan_results['conflicts_detected']}",
            f"**Overall Status:** {validation_results['overall_status']}",
            "",
        ]

        # Executive Summary
        report_lines.extend(
            [
                "## 📊 Executive Summary",
                "",
                f"- **API Routes:** {scan_results['route_categories']['api_routes']}",
                f"- **Web Routes:** {scan_results['route_categories']['web_routes']}",
                f"- **Health Routes:** {scan_results['route_categories']['health_routes']}",
                f"- **Authentication Patterns:** {len(scan_results.get('auth_patterns', {}))}",
                "",
            ]
        )

        # Conflicts Section
        if self.conflicts:
            report_lines.extend(["## ⚠️ Detected Conflicts", ""])

            for conflict in self.conflicts:
                report_lines.extend(
                    [
                        f"### {conflict.severity} - {conflict.conflict_type}",
                        f"**Path:** `{conflict.path}`",
                        f"**Details:** {conflict.details}",
                        "",
                    ]
                )
        else:
            report_lines.extend(
                [
                    "## ✅ No Conflicts Detected",
                    "",
                    "All routes are properly organized without conflicts.",
                    "",
                ]
            )

        # Recommendations
        if validation_results["recommendations"]:
            report_lines.extend(["## 💡 Recommendations", ""])

            for i, rec in enumerate(validation_results["recommendations"], 1):
                report_lines.extend(
                    [
                        f"{i}. **{rec['priority']}** - {rec['category']}",
                        f"   {rec['message']}",
                        "",
                    ]
                )

        # Route Breakdown by Prefix
        report_lines.extend(["## 🗂️ Routes by Prefix", ""])

        for prefix, routes in scan_results["routes_by_prefix"].items():
            report_lines.extend([f"### {prefix} ({len(routes)} routes)", ""])

            for route in routes[:5]:  # Show first 5 routes
                methods_str = ", ".join(route["methods"])
                report_lines.append(
                    f"- `{route['path']}` - [{methods_str}] - {route['name']}"
                )

            if len(routes) > 5:
                report_lines.append(f"- ... and {len(routes) - 5} more routes")

            report_lines.append("")

        return "\n".join(report_lines)

    def get_route_summary(self) -> Dict[str, any]:
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
            "conflicts": scan_results["conflicts_detected"],
            "last_scan": (
                self.last_scan_time.isoformat() if self.last_scan_time else None
            ),
            "status": (
                "HEALTHY"
                if scan_results["conflicts_detected"] == 0
                else "ISSUES_DETECTED"
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
    """
    Validate all routes in the application and log results.

    Args:
        app: FastAPI application instance

    Returns:
        True if validation passed, False otherwise
    """
    monitor = RouteMonitor(app)
    validation_results = monitor.validate_route_organization()

    # Log results
    status = validation_results["overall_status"]
    total_routes = validation_results["metrics"]["total_routes"]
    conflicts = validation_results["metrics"]["conflicts_count"]

    if status == "HEALTHY":
        logger.info(f"✅ Route validation PASSED: {total_routes} routes, no conflicts")
        return True
    elif status == "MINOR_ISSUES":
        logger.warning(
            f"⚠️ Route validation PASSED with minor issues: {total_routes} routes, {conflicts} minor conflicts"
        )
        return True
    elif status == "WARNING":
        logger.warning(
            f"⚠️ Route validation WARNING: {total_routes} routes, {conflicts} conflicts"
        )
        for warning in validation_results["warnings"]:
            logger.warning(f"   - {warning['type']}: {warning['path']}")
        return False
    else:  # CRITICAL
        logger.error(
            f"❌ Route validation FAILED: {total_routes} routes, {conflicts} critical conflicts"
        )
        for issue in validation_results["critical_issues"]:
            logger.error(f"   - {issue['type']}: {issue['path']}")
        return False


def generate_route_documentation(
    app: FastAPI, output_file: Optional[str] = None
) -> str:
    """
    Generate comprehensive route documentation.

    Args:
        app: FastAPI application instance
        output_file: Optional file path to save the report

    Returns:
        Route documentation as string
    """
    monitor = RouteMonitor(app)
    documentation = monitor.generate_route_report()

    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(documentation)
            logger.info(f"📄 Route documentation saved to: {output_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save route documentation: {e}")

    return documentation
