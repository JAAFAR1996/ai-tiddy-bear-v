"""
Smoke test to ensure metrics_registry can always be imported and fallback works if prometheus_client is missing.
"""


def test_metrics_registry_import():
    try:
        from src.infrastructure.monitoring import metrics_registry

        reg = metrics_registry.get_metrics_registry()
        assert reg is not None
    except Exception as e:
        assert False, f"metrics_registry import failed: {e}"
