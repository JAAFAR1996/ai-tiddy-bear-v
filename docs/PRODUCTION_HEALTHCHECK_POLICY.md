# Production Healthcheck Policy

## Auto Healthcheck & Alerting

- The system runs an automated healthcheck on all registered routers and routes at a configurable interval (default: every 60 seconds in production).
- If any route conflict, missing router, or unhealthy status is detected, an alert is raised immediately.
- Alerts are sent to the central monitoring system (ELK/Sentry/Prometheus) if the environment is production.
- Healthcheck covers:
  - Router registration completeness (all core routers must be present)
  - Route/path conflict detection
  - Prefix overlap and duplication
  - Route health status (HEALTHY, WARNING, BROKEN)
  - Registration timestamp and summary

## Fatal Error Policy

- If any core router (auth, dashboard, core_api, web_interface, esp32) fails to load or register, the system will immediately terminate startup (SystemExit) and log a critical error.
- No fallback or silent failure is allowed for core routers.
- On registration failure, all routes of the failed router type are purged from the registry.

## Logging & Monitoring

- All logs in production are sent to a central monitoring system (ELK/Sentry/Prometheus) via the production logger.
- All critical errors, registration failures, and healthcheck alerts are logged with full context and stacktrace.
- Healthcheck results are available via the admin healthcheck endpoint and are also pushed to monitoring.

## Code Quality & Safety

- No duplicate functions, variables, or incomplete code is allowed in production.
- All imports are explicit and at the top of the file.
- Only internal, explicitly defined variables are used for route tracking (self.registered_routes, self.registered_prefixes).
- All comments, TODOs, and unused code are removed before production deployment.

## Integration Testing

- All route management and monitoring logic is covered by integration and unit tests.
- Tests cover: registration, conflict detection, prefix overlap, route removal on failure, and healthcheck status.
- Tests are located in `tests_consolidated/test_route_monitor.py` and `tests_consolidated/test_route_manager_integration.py`.

---

For further details, see the implementation in `src/infrastructure/routing/route_manager.py` and `route_monitor.py`.
