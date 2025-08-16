# 🚀 Production Deployment Checklist - AI Teddy Bear v5

## Pre-Deployment

### 1. Dependencies ✅
- [x] `psycopg2-binary>=2.9.9` in requirements.txt
- [ ] All dependencies installed: `pip install -r requirements.txt`
- [ ] Virtual environment activated

### 2. Environment Variables 🔧
```bash
# Database (Required)
export DATABASE_URL="postgresql+asyncpg://user:pass@host:port/db"

# For Alembic migrations (sync driver)
export MIGRATIONS_DATABASE_URL="postgresql+psycopg2://user:pass@host:port/db"

# Feature Flags (Conservative Production Defaults)
export ENABLE_IDEMPOTENCY=false          # Enable after staging tests
export DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE=true
export ENABLE_AUTO_REGISTER=false        # Security risk if true
export FAIL_OPEN_ON_REDIS_ERROR=false
export NORMALIZE_IDS_IN_HMAC=false       # Requires firmware update

# Redis (Required for idempotency)
export REDIS_URL="redis://localhost:6379/0"
```

### 3. Database Migrations 🗄️

#### Step 1: Run Alembic Migrations
```bash
# Check current status
alembic current

# Apply migrations
alembic upgrade head
```

#### Step 2: Run Production Fixes (STAGING FIRST!)
```bash
# On staging
DATABASE_URL=$STAGING_DB_URL ./deploy_database_fixes.sh

# Verify on staging for 24 hours

# On production
DATABASE_URL=$PRODUCTION_DB_URL ./deploy_database_fixes.sh
```

## Deployment Steps

### 1. Staging Deployment 🧪
```bash
# 1. Deploy code with all features enabled
export ENABLE_IDEMPOTENCY=true
export ENABLE_AUTO_REGISTER=true

# 2. Run health checks
curl https://staging.api/health

# 3. Test ESP32 claim endpoint
./test_e2e_claim.sh

# 4. Monitor for 24 hours
# Check metrics: claim_success_total, claim_replay_cached_total
```

### 2. Production Deployment 🏭
```bash
# 1. Deploy with conservative settings
export ENABLE_IDEMPOTENCY=false
export ENABLE_AUTO_REGISTER=false

# 2. Verify deployment
curl https://production.api/health

# 3. Gradual feature rollout
# After 1 hour: Enable idempotency
export ENABLE_IDEMPOTENCY=true

# After 24 hours: Consider auto-register (if needed)
# export ENABLE_AUTO_REGISTER=true
```

## Post-Deployment Verification

### 1. Health Checks ✅
```bash
# API Health
curl https://api/health

# Database connectivity
curl https://api/health/db

# Redis connectivity (if idempotency enabled)
curl https://api/health/redis
```

### 2. Log Monitoring 📊
Watch for:
- `correlation_id` in all requests
- HTTP status codes: 401, 409, 5xx
- Masked sensitive data (device_id, child_id, tokens)
- Idempotency cache hits/misses

### 3. Metrics to Track 📈
```
claim_success_total            # Successful claims
claim_replay_cached_total       # Idempotent cache hits
claim_replay_conflict_total     # 409 responses (replay attacks)
claim_auto_register_total       # Auto-registered devices
```

### 4. ESP32 Integration Test 🔌
```bash
# Test device claiming
python3 test_esp32_claim.py

# Expected: 200 OK with JWT token
# Retry same request: 200 OK with same token (if idempotency enabled)
# Different HMAC: 409 Conflict
```

## Rollback Plan 🔄

### Quick Rollback (No Code Changes)
```bash
# Disable problematic features immediately
export ENABLE_IDEMPOTENCY=false
export ENABLE_AUTO_REGISTER=false

# Restart service
systemctl restart ai-teddy-bear
```

### Database Rollback
```sql
-- Only if absolutely necessary
BEGIN;
-- Remove normalization constraint
ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_device_id_lower;
-- Revert is_active changes
ALTER TABLE devices ALTER COLUMN is_active DROP NOT NULL;
ALTER TABLE devices ALTER COLUMN is_active DROP DEFAULT;
COMMIT;
```

## Security Checklist 🔒

- [ ] No secrets in logs (HMAC, tokens, OOB secrets)
- [ ] `ENABLE_AUTO_REGISTER=false` in production
- [ ] Redis password protected if exposed
- [ ] Database SSL enabled (`sslmode=require`)
- [ ] JWT secrets rotated
- [ ] Rate limiting enabled

## Known Issues & Solutions

### Issue: "Configuration not loaded"
**Solution**: Alembic migrations now use `APP_BOOTSTRAP_MODE=migrations`

### Issue: Device ID case sensitivity
**Solution**: Database stores lowercase, queries use LOWER()

### Issue: HMAC verification failures
**Solution**: Keep `NORMALIZE_IDS_IN_HMAC=false` until firmware updated

### Issue: Redis connection failures
**Solution**: `DISABLE_IDEMPOTENCY_ON_REDIS_FAILURE=true` ensures continuity

## Support Contacts

- **On-Call Engineer**: Check PagerDuty
- **Database Team**: #database-support
- **ESP32 Team**: #hardware-integration
- **Security Team**: #security-incidents

## Sign-Off

- [ ] Code reviewed and approved
- [ ] Staging tests passed (24 hours)
- [ ] Database backups verified
- [ ] Rollback plan tested
- [ ] Security review completed
- [ ] Documentation updated

**Deployment Date**: _______________
**Deployed By**: _______________
**Version**: v5.0.0
**Git Commit**: _______________

---

Remember: **Test on staging first!** 🧪 → 🏭