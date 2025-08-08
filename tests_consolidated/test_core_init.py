import pytest
import importlib


MODULE_PATH = "core"


# --- Test 1: Import error handling ---
def test_imports_do_not_crash():
    try:
        importlib.import_module(MODULE_PATH)
    except ImportError as e:
        pytest.fail(f"ImportError occurred: {e}")


# --- Test 2: Version info and compatibility ---
def test_core_version_info():
    import core

    assert hasattr(core, "__version__"), "__version__ not defined in core"
    assert isinstance(core.__version__, str)
    assert core.__version__.count(".") >= 1


# --- Test 3: Interface segregation (not too many exports) ---
def test_core_exports_reasonable():
    import core

    exported = getattr(core, "__all__", [])
    assert len(exported) <= 30, f"Too many exports in __all__: {len(exported)}"


# --- Test 4: Compatibility check (dummy) ---
def test_core_compatibility():
    import core

    assert hasattr(core, "check_compatibility"), "check_compatibility not defined"
    assert callable(core.check_compatibility)
    # Should not raise
    core.check_compatibility()
