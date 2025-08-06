import os

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        Info,
        Enum as PrometheusEnum,
        CollectorRegistry,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError as e:
    # Fail fast in production, allow fallback only in development/testing
    if os.environ.get("ENV", "production").lower() == "production":
        raise RuntimeError("Fatal: prometheus_client is required in production") from e
    PROMETHEUS_AVAILABLE = False

    # -----------------------------
    # Fallback/mock classes section (development/testing only)
    # -----------------------------
    # These classes are used ONLY in development/testing if prometheus_client is not installed.
    # They provide a no-op/mock implementation to keep the app running and avoid crashes.
    # All metrics will be local-only and not exported/prometheus-compatible.
    # DO NOT USE THIS IN PRODUCTION!
    class Counter:
        """Mock Counter for fallback if prometheus_client is missing (development only)."""

        def __init__(self, *args, **kwargs):
            self._value = 0

        def inc(self, amount=1):
            self._value += amount

        def labels(self, *kwargs):
            return self

    class Histogram:
        """Mock Histogram for fallback if prometheus_client is missing (development only)."""

        def __init__(self, *args, **kwargs):
            self._observations = []

        def observe(self, amount):
            self._observations.append(amount)

        def labels(self, *kwargs):
            return self

    class Gauge:
        """Mock Gauge for fallback if prometheus_client is missing (development only)."""

        def __init__(self, *args, **kwargs):
            self._value = 0

        def set(self, value):
            self._value = value

        def inc(self, amount=1):
            self._value += amount

        def dec(self, amount=1):
            self._value -= amount

        def set_to_current_time(self):
            import time

            self._value = time.time()

        def labels(self, *kwargs):
            return self

    class Summary:
        """Mock Summary for fallback if prometheus_client is missing (development only)."""

        def __init__(self, *args, **kwargs):
            self._observations = []

        def observe(self, amount):
            self._observations.append(amount)

        def labels(self, *kwargs):
            return self

    class Info:
        """Mock Info for fallback if prometheus_client is missing (development only)."""

        def __init__(self, *args, **kwargs):
            self._info = {}

        def info(self, data):
            self._info.update(data)

        def labels(self, *kwargs):
            return self

    class PrometheusEnum:
        """Mock Enum for fallback if prometheus_client is missing (development only)."""

        def __init__(self, *args, **kwargs):
            self._state = None

        def state(self, state):
            self._state = state

        def labels(self, *kwargs):
            return self

    class CollectorRegistry:
        """Mock CollectorRegistry for fallback if prometheus_client is missing (development only)."""

        def __init__(self):
            self._collectors = {}

        def register(self, collector):
            pass

        def unregister(self, collector):
            pass
            self._value = 0

        def set(self, value):
            self._value = value

        def inc(self, amount=1):
            self._value += amount

        def dec(self, amount=1):
            self._value -= amount

        def set_to_current_time(self):
            self._value = time.time()

        def labels(self, **kwargs):
            return self

    class Summary:
        def __init__(self, *args, **kwargs):
            self._observations = []

        def observe(self, amount):
            self._observations.append(amount)

        def labels(self, **kwargs):
            return self

    class Info:
        def __init__(self, *args, **kwargs):
            self._info = {}

        def info(self, data):
            self._info.update(data)

        def labels(self, **kwargs):
            return self

    class PrometheusEnum:
        def __init__(self, *args, **kwargs):
            self._state = None

        def state(self, state):
            self._state = state

        def labels(self, **kwargs):
            return self

    class CollectorRegistry:
        def __init__(self):
            self._collectors = {}

        def register(self, collector):
            pass

        def unregister(self, collector):
            pass


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Supported Prometheus metric types."""

    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"
    INFO = "info"
    ENUM = "enum"


class MetricsRegistry:
    """
    Centralized registry for Prometheus metrics.

    Provides thread-safe access to metrics with automatic creation,
    caching, and fallback mechanisms when Prometheus is unavailable.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MetricsRegistry, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the metrics registry."""
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._metrics_cache: Dict[str, Any] = {}
        self._registry_lock = threading.RLock()

        # Initialize Prometheus registry
        if PROMETHEUS_AVAILABLE:
            self._registry = CollectorRegistry()
            logger.info("Prometheus metrics registry initialized")
        else:
            self._registry = CollectorRegistry()  # Mock registry
            logger.warning("Prometheus not available - using mock metrics registry")

    @property
    def registry(self) -> CollectorRegistry:
        """Get the underlying Prometheus registry."""
        return self._registry

    def get_counter(
        self,
        name: str,
        documentation: str,
        labelnames: Optional[List[str]] = None,
        namespace: str = "ai_teddy_bear",
        subsystem: str = "",
        unit: str = "",
        **kwargs,
    ) -> Counter:
        """
        Get or create a Counter metric.

        Args:
            name: Metric name
            documentation: Help text for the metric
            labelnames: List of label names
            namespace: Metric namespace
            subsystem: Metric subsystem
            unit: Unit of measurement
            **kwargs: Additional arguments

        Returns:
            Counter metric instance
        """
        return self._get_or_create_metric(
            MetricType.COUNTER,
            name,
            documentation,
            labelnames or [],
            namespace,
            subsystem,
            unit,
            **kwargs,
        )

    def get_histogram(
        self,
        name: str,
        documentation: str,
        labelnames: Optional[List[str]] = None,
        namespace: str = "ai_teddy_bear",
        subsystem: str = "",
        unit: str = "",
        buckets: Optional[List[float]] = None,
        **kwargs,
    ) -> Histogram:
        """
        Get or create a Histogram metric.

        Args:
            name: Metric name
            documentation: Help text for the metric
            labelnames: List of label names
            namespace: Metric namespace
            subsystem: Metric subsystem
            unit: Unit of measurement
            buckets: Histogram buckets
            **kwargs: Additional arguments

        Returns:
            Histogram metric instance
        """
        if buckets is not None:
            kwargs["buckets"] = buckets

        return self._get_or_create_metric(
            MetricType.HISTOGRAM,
            name,
            documentation,
            labelnames or [],
            namespace,
            subsystem,
            unit,
            **kwargs,
        )

    def get_gauge(
        self,
        name: str,
        documentation: str,
        labelnames: Optional[List[str]] = None,
        namespace: str = "ai_teddy_bear",
        subsystem: str = "",
        unit: str = "",
        **kwargs,
    ) -> Gauge:
        """
        Get or create a Gauge metric.

        Args:
            name: Metric name
            documentation: Help text for the metric
            labelnames: List of label names
            namespace: Metric namespace
            subsystem: Metric subsystem
            unit: Unit of measurement
            **kwargs: Additional arguments

        Returns:
            Gauge metric instance
        """
        return self._get_or_create_metric(
            MetricType.GAUGE,
            name,
            documentation,
            labelnames or [],
            namespace,
            subsystem,
            unit,
            **kwargs,
        )

    def get_summary(
        self,
        name: str,
        documentation: str,
        labelnames: Optional[List[str]] = None,
        namespace: str = "ai_teddy_bear",
        subsystem: str = "",
        unit: str = "",
        **kwargs,
    ) -> Summary:
        """
        Get or create a Summary metric.

        Args:
            name: Metric name
            documentation: Help text for the metric
            labelnames: List of label names
            namespace: Metric namespace
            subsystem: Metric subsystem
            unit: Unit of measurement
            **kwargs: Additional arguments

        Returns:
            Summary metric instance
        """
        return self._get_or_create_metric(
            MetricType.SUMMARY,
            name,
            documentation,
            labelnames or [],
            namespace,
            subsystem,
            unit,
            **kwargs,
        )

    def get_info(
        self,
        name: str,
        documentation: str,
        labelnames: Optional[List[str]] = None,
        namespace: str = "ai_teddy_bear",
        subsystem: str = "",
        **kwargs,
    ) -> Info:
        """
        Get or create an Info metric.

        Args:
            name: Metric name
            documentation: Help text for the metric
            labelnames: List of label names
            namespace: Metric namespace
            subsystem: Metric subsystem
            **kwargs: Additional arguments

        Returns:
            Info metric instance
        """
        return self._get_or_create_metric(
            MetricType.INFO,
            name,
            documentation,
            labelnames or [],
            namespace,
            subsystem,
            "",
            **kwargs,
        )

    def get_enum(
        self,
        name: str,
        documentation: str,
        states: List[str],
        labelnames: Optional[List[str]] = None,
        namespace: str = "ai_teddy_bear",
        subsystem: str = "",
        **kwargs,
    ) -> PrometheusEnum:
        """
        Get or create an Enum metric.

        Args:
            name: Metric name
            documentation: Help text for the metric
            states: List of possible states
            labelnames: List of label names
            namespace: Metric namespace
            subsystem: Metric subsystem
            **kwargs: Additional arguments

        Returns:
            Enum metric instance
        """
        kwargs["states"] = states
        return self._get_or_create_metric(
            MetricType.ENUM,
            name,
            documentation,
            labelnames or [],
            namespace,
            subsystem,
            "",
            **kwargs,
        )

    def _get_or_create_metric(
        self,
        metric_type: MetricType,
        name: str,
        documentation: str,
        labelnames: List[str],
        namespace: str,
        subsystem: str,
        unit: str,
        **kwargs,
    ) -> Any:
        """
        Get existing metric or create new one.

        Args:
            metric_type: Type of metric to create
            name: Metric name
            documentation: Help text
            labelnames: Label names
            namespace: Namespace
            subsystem: Subsystem
            unit: Unit of measurement
            **kwargs: Additional arguments

        Returns:
            Metric instance
        """
        # Create cache key
        cache_key = self._create_cache_key(
            metric_type, name, namespace, subsystem, unit, labelnames
        )

        with self._registry_lock:
            # Check cache first
            if cache_key in self._metrics_cache:
                return self._metrics_cache[cache_key]

            try:
                # Create new metric
                metric = self._create_metric(
                    metric_type,
                    name,
                    documentation,
                    labelnames,
                    namespace,
                    subsystem,
                    unit,
                    **kwargs,
                )

                # Cache the metric
                self._metrics_cache[cache_key] = metric

                logger.debug(
                    f"Created {metric_type.value} metric: {cache_key}",
                    extra={
                        "metric_type": metric_type.value,
                        "metric_name": name,
                        "namespace": namespace,
                        "subsystem": subsystem,
                    },
                )

                return metric

            except Exception as e:
                logger.error(
                    f"Failed to create metric {cache_key}: {e}",
                    extra={
                        "metric_type": metric_type.value,
                        "metric_name": name,
                        "error": str(e),
                    },
                )
                # Return a mock metric to prevent application crashes
                return self._create_mock_metric(metric_type)

    def _create_metric(
        self,
        metric_type: MetricType,
        name: str,
        documentation: str,
        labelnames: List[str],
        namespace: str,
        subsystem: str,
        unit: str,
        **kwargs,
    ) -> Any:
        """Create a new Prometheus metric."""
        # Build full metric name
        full_name = self._build_metric_name(name, namespace, subsystem, unit)

        # Common arguments
        common_args = {
            "name": full_name,
            "documentation": documentation,
            "labelnames": labelnames,
            "registry": self._registry,
        }
        common_args.update(kwargs)

        # Create metric based on type
        if metric_type == MetricType.COUNTER:
            return Counter(**common_args)
        elif metric_type == MetricType.HISTOGRAM:
            return Histogram(**common_args)
        elif metric_type == MetricType.GAUGE:
            return Gauge(**common_args)
        elif metric_type == MetricType.SUMMARY:
            return Summary(**common_args)
        elif metric_type == MetricType.INFO:
            return Info(**common_args)
        elif metric_type == MetricType.ENUM:
            return PrometheusEnum(**common_args)
        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")

    def _create_mock_metric(self, metric_type: MetricType) -> Any:
        """Create a mock metric when Prometheus is unavailable or creation fails."""
        if metric_type == MetricType.COUNTER:
            return Counter()
        elif metric_type == MetricType.HISTOGRAM:
            return Histogram()
        elif metric_type == MetricType.GAUGE:
            return Gauge()
        elif metric_type == MetricType.SUMMARY:
            return Summary()
        elif metric_type == MetricType.INFO:
            return Info()
        elif metric_type == MetricType.ENUM:
            return PrometheusEnum()
        else:
            return Gauge()  # Default fallback

    def _build_metric_name(
        self, name: str, namespace: str, subsystem: str, unit: str
    ) -> str:
        """Build full metric name following Prometheus conventions."""
        parts = []

        if namespace:
            parts.append(namespace)
        if subsystem:
            parts.append(subsystem)

        parts.append(name)

        if unit:
            parts.append(unit)

        return "_".join(parts)

    def _create_cache_key(
        self,
        metric_type: MetricType,
        name: str,
        namespace: str,
        subsystem: str,
        unit: str,
        labelnames: List[str],
    ) -> str:
        """Create cache key for metric."""
        full_name = self._build_metric_name(name, namespace, subsystem, unit)
        labels_str = ",".join(sorted(labelnames))
        return f"{metric_type.value}:{full_name}:{labels_str}"

    def clear_cache(self):
        """Clear the metrics cache."""
        with self._registry_lock:
            self._metrics_cache.clear()
            logger.info("Metrics cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._registry_lock:
            return {
                "cached_metrics": len(self._metrics_cache),
                "prometheus_available": PROMETHEUS_AVAILABLE,
                "registry_type": type(self._registry).__name__,
            }

    def get_metrics_output(self) -> str:
        """Get metrics in Prometheus format."""
        if PROMETHEUS_AVAILABLE:
            try:
                return generate_latest(self._registry).decode("utf-8")
            except Exception as e:
                logger.error(f"Failed to generate metrics output: {e}")
                return "# Metrics generation failed\n"
        else:
            return "# Prometheus not available\n"

    @contextmanager
    def measure_time(self, histogram_metric: Histogram, **labels):
        """Context manager to measure execution time."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            if labels:
                histogram_metric.labels(**labels).observe(duration)
            else:
                histogram_metric.observe(duration)

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the metrics registry."""
        return {
            "status": "healthy" if PROMETHEUS_AVAILABLE else "degraded",
            "prometheus_available": PROMETHEUS_AVAILABLE,
            "cached_metrics": len(self._metrics_cache),
            "registry_initialized": hasattr(self, "_registry"),
            "thread_safe": True,
        }


# Global registry instance
_global_registry = None
_global_registry_lock = threading.Lock()


def get_metrics_registry() -> MetricsRegistry:
    """
    Get the global metrics registry instance.

    Returns:
        MetricsRegistry: Global singleton instance
    """
    global _global_registry

    if _global_registry is None:
        with _global_registry_lock:
            if _global_registry is None:
                _global_registry = MetricsRegistry()
                logger.info("Global metrics registry initialized")

    return _global_registry


def reset_metrics_registry():
    """Reset the global metrics registry (mainly for testing)."""
    global _global_registry

    with _global_registry_lock:
        _global_registry = None
        logger.info("Global metrics registry reset")


# Convenience functions for common metrics
def create_counter(
    name: str, documentation: str, labelnames: Optional[List[str]] = None, **kwargs
) -> Counter:
    """Create a counter metric."""
    registry = get_metrics_registry()
    return registry.get_counter(name, documentation, labelnames, **kwargs)


def create_histogram(
    name: str,
    documentation: str,
    labelnames: Optional[List[str]] = None,
    buckets: Optional[List[float]] = None,
    **kwargs,
) -> Histogram:
    """Create a histogram metric."""
    registry = get_metrics_registry()
    return registry.get_histogram(
        name, documentation, labelnames, buckets=buckets, **kwargs
    )


def create_gauge(
    name: str, documentation: str, labelnames: Optional[List[str]] = None, **kwargs
) -> Gauge:
    """Create a gauge metric."""
    registry = get_metrics_registry()
    return registry.get_gauge(name, documentation, labelnames, **kwargs)


def create_summary(
    name: str, documentation: str, labelnames: Optional[List[str]] = None, **kwargs
) -> Summary:
    """Create a summary metric."""
    registry = get_metrics_registry()
    return registry.get_summary(name, documentation, labelnames, **kwargs)


# Export commonly used items
__all__ = [
    "MetricsRegistry",
    "MetricType",
    "get_metrics_registry",
    "reset_metrics_registry",
    "create_counter",
    "create_histogram",
    "create_gauge",
    "create_summary",
    "PROMETHEUS_AVAILABLE",
]


if __name__ == "__main__":
    # Demo usage
    print("🎯 Metrics Registry - Centralized Prometheus Management")

    # Get registry
    registry = get_metrics_registry()

    # Create some demo metrics
    counter = registry.get_counter(
        "demo_requests_total", "Total demo requests", ["method", "status"]
    )

    histogram = registry.get_histogram(
        "demo_request_duration_seconds",
        "Demo request duration",
        ["endpoint"],
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0],
    )

    gauge = registry.get_gauge("demo_active_connections", "Active demo connections")

    # Use metrics
    counter.labels(method="GET", status="200").inc()
    histogram.labels(endpoint="/api/demo").observe(0.5)
    gauge.set(42)

    # Print stats
    print(f"Cache stats: {registry.get_cache_stats()}")
    print(f"Health check: {registry.health_check()}")

    if PROMETHEUS_AVAILABLE:
        print("Prometheus metrics available")
    else:
        print("Using mock metrics (Prometheus not available)")
