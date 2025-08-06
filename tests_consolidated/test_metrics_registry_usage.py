"""
Test that all metrics_registry public API can be called without error (smoke test).
"""


def test_metrics_registry_api():
    from src.infrastructure.monitoring import metrics_registry

    reg = metrics_registry.get_metrics_registry()
    c = reg.get_counter("test_counter", "desc")
    h = reg.get_histogram("test_histogram", "desc")
    g = reg.get_gauge("test_gauge", "desc")
    s = reg.get_summary("test_summary", "desc")
    i = reg.get_info("test_info", "desc")
    e = reg.get_enum("test_enum", "desc", ["a", "b"])
    # Call some methods to ensure no crash
    c.inc()
    h.observe(1.0)
    g.set(5)
    s.observe(2.0)
    i.info({"foo": "bar"})
    e.state("a")
