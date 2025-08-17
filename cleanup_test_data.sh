#!/bin/bash

echo "🧹 تنظيف بيانات الاختبار..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable not set"
    exit 1
fi

# حذف child profiles الاختبارية
echo "🗑️ حذف child profiles الاختبارية..."
psql "$DATABASE_URL" -c "DELETE FROM children WHERE hashed_identifier LIKE 'test-child-%';" || echo "⚠️ Warning: Failed to delete test children (table may not exist)"

# حذف device claims الاختبارية  
echo "🗑️ حذف device claims الاختبارية..."
psql "$DATABASE_URL" -c "DELETE FROM devices WHERE device_id LIKE 'Teddy-ESP32-TEST-%';" || echo "⚠️ Warning: Failed to delete test devices (table may not exist)"

# حذف Redis nonce keys
echo "🧹 تنظيف Redis nonce keys..."
if [ -n "$REDIS_URL" ]; then
    python3 - <<'PY'
import os
import sys
try:
    import redis
    r = redis.from_url(os.getenv("REDIS_URL"))
    # Clear test device nonces
    for key in r.scan_iter(match="device_nonce:Teddy-ESP32-TEST-*"):
        r.delete(key)
    # Clear old nonces (older than 1 hour)
    for key in r.scan_iter(match="device_nonce:*"):
        ttl = r.ttl(key)
        if ttl > 3600:  # Keep only fresh nonces
            r.delete(key)
    print("✅ Redis nonces cleaned")
except ImportError:
    print("⚠️ Warning: redis package not found, skipping Redis cleanup")
except Exception as e:
    print(f"⚠️ Warning: Redis cleanup failed: {e}")
PY
else
    echo "⚠️ Warning: REDIS_URL not set, skipping Redis cleanup"
fi

echo "✅ تم تنظيف البيانات الاختبارية"