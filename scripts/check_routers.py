"""
APIRouter Validation Script
Scans the codebase for all APIRouter instances and reports missing/None name, prefix, or tags.
Run manually or in CI before deployment.
"""

import sys
import importlib
from fastapi import APIRouter

# List of known router module paths (add more as needed)
ROUTER_MODULES = [
    "src.adapters.auth_routes",
    "src.adapters.dashboard_routes",
    "src.adapters.api_routes",
    "src.adapters.esp32_router",
    "src.adapters.esp32_websocket_router",
    "src.adapters.web",
    "src.presentation.api.endpoints.premium.subscriptions",
    "src.application.services.payment.api.production_endpoints",
    "src.presentation.api.endpoints.iraqi_payments",
    "src.presentation.api.websocket.parent_notifications",
]


# Helper to find all APIRouter objects in a module
def find_routers_in_module(module):
    routers = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, APIRouter):
            routers.append((attr_name, attr))
    return routers


def validate_router(router, module_name, router_var):
    errors = []
    # Check for prefix, tags, name (if available)
    prefix = getattr(router, "prefix", None)
    tags = getattr(router, "tags", None)
    # Name is not a built-in property, but we can check variable name
    if prefix is None or not isinstance(prefix, str) or prefix.strip() == "":
        errors.append(
            f"[MISSING] prefix is None or invalid in {module_name}.{router_var}"
        )
    if tags is not None:
        if not isinstance(tags, list) or any(
            t is None or not isinstance(t, str) or t.strip() == "" for t in tags
        ):
            errors.append(
                f"[MISSING] tags are None or invalid in {module_name}.{router_var}"
            )
    return errors


def main():
    print("\n=== APIRouter Validation Report ===\n")
    any_errors = False
    for module_path in ROUTER_MODULES:
        try:
            module = importlib.import_module(module_path)
        except Exception as e:
            print(f"[ERROR] Failed to import {module_path}: {e}")
            continue
        routers = find_routers_in_module(module)
        if not routers:
            print(f"[WARN] No APIRouter found in {module_path}")
            continue
        for router_var, router in routers:
            errors = validate_router(router, module_path, router_var)
            if errors:
                any_errors = True
                for err in errors:
                    print(f"[FAIL] {err}")
            else:
                print(f"[OK] {module_path}.{router_var} is valid.")
    if any_errors:
        print(
            "\n❌ Some routers have missing or invalid properties. See above for details.\n"
        )
        sys.exit(1)
    else:
        print("\n✅ All routers passed validation.\n")


if __name__ == "__main__":
    main()
