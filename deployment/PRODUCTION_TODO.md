# Production Readiness TODO

Follow these steps in order whenever preparing the stack for launch (Docker based):

1. **Environment secrets**
   - Copy `.env.production` and replace placeholder secrets (`SECRET_KEY`, `JWT_SECRET_KEY`, `COPPA_ENCRYPTION_KEY`, SMTP/Stripe keys, etc.) with real values.
   - Keep the database (`postgres`) and redis credentials in sync with docker-compose overrides.

2. **Containers up**
   - Start the infrastructure services: `docker compose up -d postgres redis`.
   - Verify health: `docker compose ps` should show both as `healthy`.

3. **Database migrations**
   - Run Alembic migrations inside the app container: `docker compose run --rm app alembic upgrade head`.

4. **Application service**
   - Launch the API: `docker compose up app` (or `docker compose up -d app` for detached).
   - Check `/healthz` and `/ready` (through Nginx: `http(s)://<host>/healthz`).

5. **Edge proxy**
   - Once the API is stable start Nginx: `docker compose up -d nginx`.
   - Confirm TLS certificates and websocket upgrade through the proxy.

6. **Smoke tests**
   - Run `pytest test_websocket.py` (against the compose stack) and ensure all responses succeed.
   - Monitor container logs for errors for at least 10 minutes to confirm stability.

7. **Observability**
   - When Prometheus/Sentry credentials are provided, update `.env.production` and redeploy so metrics and tracing begin streaming.

Document any deviations from this checklist before going live.
