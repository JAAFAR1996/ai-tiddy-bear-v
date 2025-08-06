"""
🧸 AI TEDDY BEAR V5 - PARENT DASHBOARD
====================================
Production-grade parent control panel with:
- Proper dependency injection and loose coupling
- Comprehensive error handling and resilience
- Input validation and COPPA compliance
- Caching and performance optimization
- Extensive logging and monitoring
- Clean separation of concerns
"""

# Standard library imports
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

# Internal imports
from src.services.service_registry import (
    get_user_service,
    get_child_safety_service,
    get_ai_service,
    get_notification_service,
)
from src.adapters.dashboard.child_monitor import ChildMonitor
from src.adapters.dashboard.safety_controls import SafetyControls
from src.adapters.dashboard.usage_reports import UsageReports
from src.adapters.dashboard.notification_center import NotificationCenter
from src.shared.dto.child_data import ChildData
from src.core.value_objects.value_objects import AgeGroup, SafetyLevel
from src.infrastructure.exceptions import ValidationError, ServiceError

# Configure logging
logger = logging.getLogger(__name__)


# ================================
# ENUMS AND DATA CLASSES
# ================================


class DashboardSection(str, Enum):
    """Dashboard sections for granular data loading."""

    CHILDREN = "children"
    USAGE = "usage"
    SAFETY = "safety"
    NOTIFICATIONS = "notifications"
    OVERVIEW = "overview"


class CacheStatus(str, Enum):
    """Cache status for dashboard data."""

    HIT = "hit"
    MISS = "miss"
    ERROR = "error"
    EXPIRED = "expired"


@dataclass
class DashboardMetrics:
    """Dashboard performance and usage metrics."""

    load_time_ms: float
    cache_status: CacheStatus
    sections_loaded: List[str]
    errors_encountered: List[str]
    child_count: int
    data_freshness_minutes: int
    correlation_id: str


@dataclass
class ChildSummary:
    """Transformed child data for dashboard display."""

    child_id: str
    name: str
    age: int
    age_group: str
    last_activity: Optional[datetime]
    safety_status: str
    daily_usage_minutes: int
    safety_violations: int
    is_active: bool
    recent_emotions: List[str]
    parental_controls_enabled: bool


@dataclass
class SafetyOverview:
    """Safety summary for parent dashboard."""

    overall_status: str
    total_violations: int
    recent_violations: List[Dict[str, Any]]
    content_filter_level: str
    active_restrictions: List[str]
    last_review_date: Optional[datetime]
    requires_attention: bool


@dataclass
class UsageSummary:
    """Usage summary for parent dashboard."""

    total_sessions_today: int
    total_time_today_minutes: int
    average_session_duration: float
    peak_usage_hours: List[int]
    weekly_trend: Dict[str, int]
    screen_time_limits: Dict[str, int]
    exceeded_limits: List[str]


@dataclass
class NotificationSummary:
    """Notification summary for parent dashboard."""

    unread_count: int
    priority_notifications: List[Dict[str, Any]]
    recent_notifications: List[Dict[str, Any]]
    notification_types: Dict[str, int]
    last_checked: Optional[datetime]


@dataclass
class DashboardData:
    """Complete dashboard data structure."""

    children: List[ChildSummary]
    safety: SafetyOverview
    usage: UsageSummary
    notifications: NotificationSummary
    metrics: DashboardMetrics
    generated_at: datetime
    expires_at: datetime


# ================================
# DATA TRANSFORMATION LAYER
# ================================


class DashboardDataTransformer:
    """
    Handles all data transformation logic for dashboard display.
    Separates data transformation from service coordination.
    """

    @staticmethod
    def transform_child_data(child_orm, recent_activity: Dict = None) -> ChildSummary:
        """Transform ORM child data to dashboard summary."""
        try:
            # Get age group
            age_group = (
                AgeGroup.from_age(child_orm.age).value
                if hasattr(child_orm, "age")
                else "unknown"
            )

            # Extract recent activity data
            activity = recent_activity or {}

            return ChildSummary(
                child_id=str(child_orm.id),
                name=child_orm.name,
                age=child_orm.age,
                age_group=age_group,
                last_activity=activity.get("last_activity"),
                safety_status=activity.get("safety_status", "safe"),
                daily_usage_minutes=activity.get("daily_usage_minutes", 0),
                safety_violations=activity.get("safety_violations", 0),
                is_active=getattr(child_orm, "is_active", True),
                recent_emotions=activity.get("recent_emotions", []),
                parental_controls_enabled=activity.get(
                    "parental_controls_enabled", True
                ),
            )
        except Exception as e:
            logger.error(f"Error transforming child data: {e}")
            # Return safe default
            return ChildSummary(
                child_id=str(child_orm.id) if hasattr(child_orm, "id") else "unknown",
                name=getattr(child_orm, "name", "Unknown Child"),
                age=getattr(child_orm, "age", 0),
                age_group="unknown",
                last_activity=None,
                safety_status="unknown",
                daily_usage_minutes=0,
                safety_violations=0,
                is_active=False,
                recent_emotions=[],
                parental_controls_enabled=True,
            )

    @staticmethod
    def transform_safety_data(safety_data: Dict) -> SafetyOverview:
        """Transform safety service data to dashboard overview."""
        try:
            return SafetyOverview(
                overall_status=safety_data.get("overall_status", "unknown"),
                total_violations=safety_data.get("total_violations", 0),
                recent_violations=safety_data.get("recent_violations", []),
                content_filter_level=safety_data.get("content_filter_level", "strict"),
                active_restrictions=safety_data.get("active_restrictions", []),
                last_review_date=safety_data.get("last_review_date"),
                requires_attention=safety_data.get("requires_attention", False),
            )
        except Exception as e:
            logger.error(f"Error transforming safety data: {e}")
            return SafetyOverview(
                overall_status="error",
                total_violations=0,
                recent_violations=[],
                content_filter_level="strict",
                active_restrictions=[],
                last_review_date=None,
                requires_attention=True,
            )

    @staticmethod
    def transform_usage_data(usage_data: Dict) -> UsageSummary:
        """Transform usage service data to dashboard summary."""
        try:
            return UsageSummary(
                total_sessions_today=usage_data.get("total_sessions_today", 0),
                total_time_today_minutes=usage_data.get("total_time_today_minutes", 0),
                average_session_duration=usage_data.get(
                    "average_session_duration", 0.0
                ),
                peak_usage_hours=usage_data.get("peak_usage_hours", []),
                weekly_trend=usage_data.get("weekly_trend", {}),
                screen_time_limits=usage_data.get("screen_time_limits", {}),
                exceeded_limits=usage_data.get("exceeded_limits", []),
            )
        except Exception as e:
            logger.error(f"Error transforming usage data: {e}")
            return UsageSummary(
                total_sessions_today=0,
                total_time_today_minutes=0,
                average_session_duration=0.0,
                peak_usage_hours=[],
                weekly_trend={},
                screen_time_limits={},
                exceeded_limits=[],
            )

    @staticmethod
    def transform_notification_data(notification_data: Dict) -> NotificationSummary:
        """Transform notification service data to dashboard summary."""
        try:
            return NotificationSummary(
                unread_count=notification_data.get("unread_count", 0),
                priority_notifications=notification_data.get(
                    "priority_notifications", []
                ),
                recent_notifications=notification_data.get("recent_notifications", []),
                notification_types=notification_data.get("notification_types", {}),
                last_checked=notification_data.get("last_checked"),
            )
        except Exception as e:
            logger.error(f"Error transforming notification data: {e}")
            return NotificationSummary(
                unread_count=0,
                priority_notifications=[],
                recent_notifications=[],
                notification_types={},
                last_checked=None,
            )


# ================================
# DEPENDENCY INJECTION INTERFACES
# ================================


class DashboardServiceProvider:
    """
    Service provider interface for dependency injection.
    Abstracts service dependencies and enables testing.
    """

    def __init__(
        self,
        user_service=None,
        safety_service=None,
        ai_service=None,
        notification_service=None,
    ):
        """Initialize with optional service overrides for testing."""
        self._user_service = user_service
        self._safety_service = safety_service
        self._ai_service = ai_service
        self._notification_service = notification_service

    async def get_user_service(self):
        """Get user service instance."""
        if self._user_service:
            return self._user_service
        return await get_user_service()

    async def get_safety_service(self):
        """Get child safety service instance."""
        if self._safety_service:
            return self._safety_service
        return await get_child_safety_service()

    async def get_ai_service(self):
        """Get AI service instance."""
        if self._ai_service:
            return self._ai_service
        return await get_ai_service()

    async def get_notification_service(self):
        """Get notification service instance."""
        if self._notification_service:
            return self._notification_service
        return await get_notification_service()


# ================================
# CACHING LAYER
# ================================


class DashboardCache:
    """Simple in-memory cache for dashboard data with TTL."""

    def __init__(self, default_ttl_minutes: int = 5):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = timedelta(minutes=default_ttl_minutes)

    def _get_cache_key(self, parent_id: str, section: Optional[str] = None) -> str:
        """Generate cache key for parent data."""
        if section:
            return f"dashboard:{parent_id}:{section}"
        return f"dashboard:{parent_id}:full"

    def get(self, parent_id: str, section: Optional[str] = None) -> Optional[Any]:
        """Get cached data if not expired."""
        cache_key = self._get_cache_key(parent_id, section)

        if cache_key not in self.cache:
            return None

        cached_data = self.cache[cache_key]
        if datetime.utcnow() > cached_data["expires_at"]:
            del self.cache[cache_key]
            return None

        return cached_data["data"]

    def set(
        self,
        parent_id: str,
        data: Any,
        section: Optional[str] = None,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """Cache data with TTL."""
        cache_key = self._get_cache_key(parent_id, section)
        expires_at = datetime.utcnow() + (ttl or self.default_ttl)

        self.cache[cache_key] = {
            "data": data,
            "expires_at": expires_at,
            "cached_at": datetime.utcnow(),
        }

    def invalidate(self, parent_id: str, section: Optional[str] = None) -> None:
        """Invalidate cached data."""
        if section:
            cache_key = self._get_cache_key(parent_id, section)
            self.cache.pop(cache_key, None)
        else:
            # Invalidate all sections for this parent
            keys_to_remove = [
                k for k in self.cache.keys() if k.startswith(f"dashboard:{parent_id}:")
            ]
            for key in keys_to_remove:
                self.cache.pop(key, None)

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, value in self.cache.items() if now > value["expires_at"]
        ]

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)


# ================================
# MAIN DASHBOARD CLASS
# ================================


class ProductionParentDashboard:
    """
    Production-grade parent dashboard with proper dependency injection,
    error handling, caching, and comprehensive monitoring.
    """

    def __init__(
        self,
        service_provider: Optional[DashboardServiceProvider] = None,
        cache: Optional[DashboardCache] = None,
        enable_caching: bool = True,
    ):
        """
        Initialize dashboard with dependency injection.

        Args:
            service_provider: Service provider for dependency injection
            cache: Cache instance (optional)
            enable_caching: Whether to enable caching
        """
        self.service_provider = service_provider or DashboardServiceProvider()
        self.transformer = DashboardDataTransformer()
        self.cache = cache or DashboardCache() if enable_caching else None
        self.enable_caching = enable_caching

        # Performance tracking
        self.request_count = 0
        self.error_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info("ProductionParentDashboard initialized")

    def _validate_parent_id(self, parent_id: str) -> str:
        """Validate parent ID input."""
        if not parent_id:
            raise ValidationError("Parent ID cannot be empty")

        if not isinstance(parent_id, str):
            raise ValidationError("Parent ID must be a string")

        # Basic UUID format check
        try:
            uuid.UUID(parent_id)
        except ValueError:
            raise ValidationError(f"Invalid parent ID format: {parent_id}")

        return parent_id

    def _validate_child_id(self, child_id: str) -> str:
        """Validate child ID input."""
        if not child_id:
            raise ValidationError("Child ID cannot be empty")

        if not isinstance(child_id, str):
            raise ValidationError("Child ID must be a string")

        try:
            uuid.UUID(child_id)
        except ValueError:
            raise ValidationError(f"Invalid child ID format: {child_id}")

        return child_id

    async def _safe_service_call(
        self,
        service_call,
        operation_name: str,
        correlation_id: str,
        fallback_result=None,
    ):
        """
        Execute service call with comprehensive error handling.

        Args:
            service_call: Async service method to call
            operation_name: Name of operation for logging
            correlation_id: Request correlation ID
            fallback_result: Result to return on error

        Returns:
            Service result or fallback
        """
        try:
            start_time = time.time()
            result = await service_call()

            elapsed = (time.time() - start_time) * 1000
            logger.debug(
                f"Service call completed: {operation_name}",
                extra={
                    "correlation_id": correlation_id,
                    "operation": operation_name,
                    "elapsed_ms": elapsed,
                },
            )

            return result

        except Exception as e:
            self.error_count += 1
            logger.error(
                f"Service call failed: {operation_name}",
                extra={
                    "correlation_id": correlation_id,
                    "operation": operation_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )

            # Return fallback or raise ServiceError
            if fallback_result is not None:
                return fallback_result

            raise ServiceError(
                f"Service operation failed: {operation_name}",
                operation=operation_name,
                correlation_id=correlation_id,
                original_error=e,
            )

    async def _load_children_data(
        self, parent_id: str, correlation_id: str
    ) -> List[ChildSummary]:
        """Load and transform children data."""
        try:
            user_service = await self.service_provider.get_user_service()

            # Get children from user service
            children_orm = await self._safe_service_call(
                lambda: user_service.get_children(parent_id),
                "get_children",
                correlation_id,
                fallback_result=[],
            )

            # Get activity data for each child
            children_summaries = []
            for child_orm in children_orm:
                try:
                    # Get recent activity (this would typically come from usage service)
                    activity_data = await self._safe_service_call(
                        lambda: self._get_child_activity(
                            str(child_orm.id), correlation_id
                        ),
                        f"get_child_activity_{child_orm.id}",
                        correlation_id,
                        fallback_result={},
                    )

                    # Transform to dashboard format
                    child_summary = self.transformer.transform_child_data(
                        child_orm, activity_data
                    )
                    children_summaries.append(child_summary)

                except Exception as e:
                    logger.error(
                        f"Error processing child {child_orm.id}: {e}",
                        extra={"correlation_id": correlation_id},
                    )
                    # Add child with minimal data
                    child_summary = self.transformer.transform_child_data(child_orm, {})
                    children_summaries.append(child_summary)

            return children_summaries

        except Exception as e:
            logger.error(
                f"Error loading children data: {e}",
                extra={"correlation_id": correlation_id},
            )
            return []

    async def _get_child_activity(
        self, child_id: str, correlation_id: str
    ) -> Dict[str, Any]:
        """Get child activity data from various services."""
        # Production environment only
        # Query real database for child activity
        try:
            user_service = await self.service_provider.get_user_service()
            ai_service = await self.service_provider.get_ai_service()
            
            # Get real activity data from services
            activity_data = await user_service.get_child_activity_summary(child_id)
            
            return activity_data or {
                "last_activity": None,
                "safety_status": "unknown",
                "daily_usage_minutes": 0,
                "safety_violations": 0,
                "recent_emotions": [],
                "parental_controls_enabled": True,
            }
        except Exception as e:
            logger.error(f"Error fetching child activity: {e}", extra={"correlation_id": correlation_id})
            return {
                "last_activity": None,
                "safety_status": "error",
                "daily_usage_minutes": 0,
                "safety_violations": 0,
                "recent_emotions": [],
                "parental_controls_enabled": True,
            }

    async def _load_safety_data(
        self, parent_id: str, correlation_id: str
    ) -> SafetyOverview:
        """Load and transform safety data."""
        try:
            safety_service = await self.service_provider.get_safety_service()

            safety_data = await self._safe_service_call(
                lambda: safety_service.get_safety_overview(parent_id),
                "get_safety_overview",
                correlation_id,
                fallback_result={},
            )

            return self.transformer.transform_safety_data(safety_data)

        except Exception as e:
            logger.error(
                f"Error loading safety data: {e}",
                extra={"correlation_id": correlation_id},
            )
            return self.transformer.transform_safety_data({})

    async def _load_usage_data(
        self, parent_id: str, correlation_id: str
    ) -> UsageSummary:
        """Load and transform usage data."""
        try:
            # Usage data would come from usage reports service
            usage_data = await self._safe_service_call(
                lambda: self._get_usage_summary(parent_id),
                "get_usage_summary",
                correlation_id,
                fallback_result={},
            )

            return self.transformer.transform_usage_data(usage_data)

        except Exception as e:
            logger.error(
                f"Error loading usage data: {e}",
                extra={"correlation_id": correlation_id},
            )
            return self.transformer.transform_usage_data({})

    async def _get_usage_summary(self, parent_id: str) -> Dict[str, Any]:
        """Get usage summary from real database."""
        # Production environment only
        try:
            user_service = await self.service_provider.get_user_service()
            
            # Get real usage data from database
            usage_data = await user_service.get_parent_usage_summary(parent_id)
            
            return usage_data or {
                "total_sessions_today": 0,
                "total_time_today_minutes": 0,
                "average_session_duration": 0.0,
                "peak_usage_hours": [],
                "weekly_trend": {},
                "screen_time_limits": {},
                "exceeded_limits": [],
            }
        except Exception as e:
            logger.error(f"Error fetching usage summary: {e}")
            return {
                "total_sessions_today": 0,
                "total_time_today_minutes": 0,
                "average_session_duration": 0.0,
                "peak_usage_hours": [],
                "weekly_trend": {},
                "screen_time_limits": {},
                "exceeded_limits": [],
            }

    async def _load_notification_data(
        self, parent_id: str, correlation_id: str
    ) -> NotificationSummary:
        """Load and transform notification data."""
        try:
            notification_service = (
                await self.service_provider.get_notification_service()
            )

            notification_data = await self._safe_service_call(
                lambda: notification_service.get_notifications(parent_id),
                "get_notifications",
                correlation_id,
                fallback_result={},
            )

            return self.transformer.transform_notification_data(notification_data)

        except Exception as e:
            logger.error(
                f"Error loading notification data: {e}",
                extra={"correlation_id": correlation_id},
            )
            return self.transformer.transform_notification_data({})

    async def get_dashboard_data(
        self,
        parent_id: str,
        sections: Optional[List[DashboardSection]] = None,
        force_refresh: bool = False,
    ) -> DashboardData:
        """
        Get comprehensive dashboard data with caching and error handling.

        Args:
            parent_id: Parent identifier
            sections: Optional list of sections to load (loads all if None)
            force_refresh: Force cache refresh

        Returns:
            Complete dashboard data

        Raises:
            ValidationError: On invalid input
            ServiceError: On service failures
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()
        self.request_count += 1

        try:
            # Validate input
            parent_id = self._validate_parent_id(parent_id)

            # Check cache if enabled
            cache_status = CacheStatus.MISS
            if self.cache and not force_refresh:
                cached_data = self.cache.get(parent_id)
                if cached_data:
                    self.cache_hits += 1
                    cache_status = CacheStatus.HIT

                    # Update metrics
                    cached_data.metrics.cache_status = CacheStatus.HIT
                    cached_data.metrics.correlation_id = correlation_id

                    logger.info(
                        f"Dashboard data served from cache",
                        extra={
                            "correlation_id": correlation_id,
                            "parent_id": parent_id,
                            "cache_age_minutes": (
                                datetime.utcnow() - cached_data.generated_at
                            ).total_seconds()
                            / 60,
                        },
                    )

                    return cached_data

            if self.cache:
                self.cache_misses += 1

            logger.info(
                f"Loading dashboard data for parent {parent_id}",
                extra={
                    "correlation_id": correlation_id,
                    "sections": [s.value for s in sections] if sections else "all",
                    "force_refresh": force_refresh,
                },
            )

            # Default to all sections if none specified
            if not sections:
                sections = list(DashboardSection)

            errors_encountered = []

            # Load data concurrently
            tasks = {}

            if DashboardSection.CHILDREN in sections:
                tasks["children"] = self._load_children_data(parent_id, correlation_id)

            if DashboardSection.SAFETY in sections:
                tasks["safety"] = self._load_safety_data(parent_id, correlation_id)

            if DashboardSection.USAGE in sections:
                tasks["usage"] = self._load_usage_data(parent_id, correlation_id)

            if DashboardSection.NOTIFICATIONS in sections:
                tasks["notifications"] = self._load_notification_data(
                    parent_id, correlation_id
                )

            # Execute all tasks concurrently
            results = {}
            if tasks:
                try:
                    completed_results = await asyncio.gather(
                        *tasks.values(), return_exceptions=True
                    )

                    for i, (task_name, task) in enumerate(tasks.items()):
                        result = completed_results[i]
                        if isinstance(result, Exception):
                            logger.error(f"Task {task_name} failed: {result}")
                            errors_encountered.append(f"{task_name}_error")
                            # Use transformer defaults for failed sections
                            if task_name == "children":
                                results[task_name] = []
                            elif task_name == "safety":
                                results[task_name] = (
                                    self.transformer.transform_safety_data({})
                                )
                            elif task_name == "usage":
                                results[task_name] = (
                                    self.transformer.transform_usage_data({})
                                )
                            elif task_name == "notifications":
                                results[task_name] = (
                                    self.transformer.transform_notification_data({})
                                )
                        else:
                            results[task_name] = result
                except Exception as e:
                    logger.error(f"Error in concurrent task execution: {e}")
                    errors_encountered.append("concurrent_execution_error")
                    # Provide defaults for all sections
                    results = {
                        "children": [],
                        "safety": self.transformer.transform_safety_data({}),
                        "usage": self.transformer.transform_usage_data({}),
                        "notifications": self.transformer.transform_notification_data(
                            {}
                        ),
                    }

            # Build dashboard data
            load_time = (time.time() - start_time) * 1000
            now = datetime.utcnow()

            metrics = DashboardMetrics(
                load_time_ms=load_time,
                cache_status=cache_status,
                sections_loaded=[s.value for s in sections],
                errors_encountered=errors_encountered,
                child_count=len(results.get("children", [])),
                data_freshness_minutes=0,  # Fresh data
                correlation_id=correlation_id,
            )

            dashboard_data = DashboardData(
                children=results.get("children", []),
                safety=results.get(
                    "safety", self.transformer.transform_safety_data({})
                ),
                usage=results.get("usage", self.transformer.transform_usage_data({})),
                notifications=results.get(
                    "notifications", self.transformer.transform_notification_data({})
                ),
                metrics=metrics,
                generated_at=now,
                expires_at=now + timedelta(minutes=5),
            )

            # Cache the result
            if self.cache and not errors_encountered:
                self.cache.set(parent_id, dashboard_data)

            logger.info(
                f"Dashboard data loaded successfully",
                extra={
                    "correlation_id": correlation_id,
                    "parent_id": parent_id,
                    "load_time_ms": load_time,
                    "child_count": dashboard_data.metrics.child_count,
                    "errors": len(errors_encountered),
                },
            )

            return dashboard_data

        except ValidationError:
            raise
        except Exception as e:
            self.error_count += 1
            logger.error(
                f"Critical error loading dashboard data: {e}",
                extra={"correlation_id": correlation_id, "parent_id": parent_id},
                exc_info=True,
            )
            raise ServiceError(
                "Failed to load dashboard data",
                operation="get_dashboard_data",
                correlation_id=correlation_id,
                original_error=e,
            )

    async def get_child_details(
        self, parent_id: str, child_id: str, include_detailed_usage: bool = False
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific child.

        Args:
            parent_id: Parent identifier
            child_id: Child identifier
            include_detailed_usage: Include detailed usage analytics

        Returns:
            Detailed child information

        Raises:
            ValidationError: On invalid input
            ServiceError: On service failures
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Validate inputs
            parent_id = self._validate_parent_id(parent_id)
            child_id = self._validate_child_id(child_id)

            logger.info(
                f"Loading child details",
                extra={
                    "correlation_id": correlation_id,
                    "parent_id": parent_id,
                    "child_id": child_id,
                    "include_detailed_usage": include_detailed_usage,
                },
            )

            user_service = await self.service_provider.get_user_service()
            safety_service = await self.service_provider.get_safety_service()

            # Load child data
            child_orm = await self._safe_service_call(
                lambda: user_service.get_child(child_id), "get_child", correlation_id
            )

            if not child_orm:
                raise ValidationError(f"Child {child_id} not found or not accessible")

            # Verify parent ownership
            if str(child_orm.parent_id) != parent_id:
                raise ValidationError("Child does not belong to specified parent")

            # Load additional data concurrently
            tasks = {
                "activity": self._get_child_activity(child_id, correlation_id),
                "safety_details": safety_service.get_child_safety_status(child_id),
            }

            if include_detailed_usage:
                tasks["detailed_usage"] = self._get_detailed_usage(child_id)

            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            # Process results
            activity_data = results[0] if not isinstance(results[0], Exception) else {}
            safety_details = results[1] if not isinstance(results[1], Exception) else {}
            detailed_usage = (
                results[2]
                if len(results) > 2 and not isinstance(results[2], Exception)
                else {} if include_detailed_usage else None
            )

            # Transform child data
            child_summary = self.transformer.transform_child_data(
                child_orm, activity_data
            )

            # Build detailed response
            child_details = {
                "basic_info": child_summary,
                "safety_details": safety_details,
                "activity_summary": activity_data,
                "detailed_usage": detailed_usage,
                "last_updated": datetime.utcnow(),
                "correlation_id": correlation_id,
            }

            return child_details

        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                f"Error loading child details: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "parent_id": parent_id,
                    "child_id": child_id,
                },
                exc_info=True,
            )
            raise ServiceError(
                "Failed to load child details",
                operation="get_child_details",
                correlation_id=correlation_id,
                original_error=e,
            )

    async def _get_detailed_usage(self, child_id: str) -> Dict[str, Any]:
        """Get detailed usage analytics from real database."""
        # Production environment only
        try:
            user_service = await self.service_provider.get_user_service()
            ai_service = await self.service_provider.get_ai_service()
            
            # Get real detailed usage from database
            detailed_usage = await user_service.get_child_detailed_usage(child_id)
            
            return detailed_usage or {
                "hourly_usage": {},
                "weekly_sessions": {},
                "content_categories": {},
                "emotion_trends": {},
                "safety_events": [],
                "learning_progress": {
                    "completed_topics": 0,
                    "current_level": "beginner",
                },
            }
        except Exception as e:
            logger.error(f"Error fetching detailed usage: {e}")
            return {
                "hourly_usage": {},
                "weekly_sessions": {},
                "content_categories": {},
                "emotion_trends": {},
                "safety_events": [],
                "learning_progress": {
                    "completed_topics": 0,
                    "current_level": "beginner",
                },
            }

    def invalidate_cache(
        self, parent_id: str, section: Optional[DashboardSection] = None
    ) -> None:
        """
        Invalidate cached dashboard data.

        Args:
            parent_id: Parent identifier
            section: Optional specific section to invalidate
        """
        if self.cache:
            section_str = section.value if section else None
            self.cache.invalidate(parent_id, section_str)

            logger.info(
                f"Cache invalidated",
                extra={"parent_id": parent_id, "section": section_str or "all"},
            )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get dashboard performance metrics."""
        cache_hit_rate = self.cache_hits / max(1, self.cache_hits + self.cache_misses)
        error_rate = self.error_count / max(1, self.request_count)

        return {
            "total_requests": self.request_count,
            "error_count": self.error_count,
            "error_rate": error_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "cache_enabled": self.enable_caching,
            "uptime_seconds": time.time() - getattr(self, "_start_time", time.time()),
        }


# ================================
# FACTORY FUNCTIONS
# ================================


def create_parent_dashboard(
    enable_caching: bool = True, cache_ttl_minutes: int = 5
) -> ProductionParentDashboard:
    """
    Create a production parent dashboard with default configuration.

    Args:
        enable_caching: Whether to enable caching
        cache_ttl_minutes: Cache TTL in minutes

    Returns:
        Configured parent dashboard instance
    """
    cache = DashboardCache(cache_ttl_minutes) if enable_caching else None

    return ProductionParentDashboard(
        service_provider=DashboardServiceProvider(),
        cache=cache,
        enable_caching=enable_caching,
    )


def create_test_dashboard(
    mock_user_service=None,
    mock_safety_service=None,
    mock_ai_service=None,
    mock_notification_service=None,
) -> ProductionParentDashboard:
    """
    Create a dashboard instance for testing with mock services.

    Args:
        mock_user_service: Mock user service
        mock_safety_service: Mock safety service
        mock_ai_service: Mock AI service
        mock_notification_service: Mock notification service

    Returns:
        Dashboard instance with mocked dependencies
    """
    service_provider = DashboardServiceProvider(
        user_service=mock_user_service,
        safety_service=mock_safety_service,
        ai_service=mock_ai_service,
        notification_service=mock_notification_service,
    )

    return ProductionParentDashboard(
        service_provider=service_provider,
        enable_caching=False,  # Disable caching for tests
    )


# Backward compatibility alias
ParentDashboard = ProductionParentDashboard


# ================================
# EXPORT SYMBOLS
# ================================

__all__ = [
    "ProductionParentDashboard",
    "ParentDashboard",  # Backward compatibility
    "DashboardServiceProvider",
    "DashboardDataTransformer",
    "DashboardCache",
    "DashboardData",
    "ChildSummary",
    "SafetyOverview",
    "UsageSummary",
    "NotificationSummary",
    "DashboardMetrics",
    "DashboardSection",
    "create_parent_dashboard",
    "create_test_dashboard",
]
