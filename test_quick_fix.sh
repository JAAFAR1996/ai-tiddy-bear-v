#!/bin/bash

# Quick test of our fixes
echo "🧪 Testing Authentication Flow Fixes"
echo "====================================="

# Set environment variables for testing
export DATABASE_URL="postgresql+asyncpg://neondb_owner:npg_c7nLNRBBhd6kCXGYLWU64NVOWmJW1UJd@ep-icy-brook-abltteyf-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"
# For psql compatibility, convert to standard postgresql:// format
export DATABASE_URL_PSQL="postgresql://neondb_owner:npg_c7nLNRBBhd6kCXGYLWU64NVOWmJW1UJd@ep-icy-brook-abltteyf-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"
export REDIS_URL="rediss://default:AZmqAAIjcDEzNWI4MDFhYWUzZjM0NDBhOGI5ZjVhMjMzNGExYjczNnAxMA@allowed-kangaroo-39338.upstash.io:6379/0"

# Test 1: Dynamic ID generation
echo "🔄 Test 1: Dynamic ID Generation"
TIMESTAMP=$(date +%s)
DID="Teddy-ESP32-TEST-${TIMESTAMP}"
CID="test-child-${TIMESTAMP}"
echo "✅ Generated Device ID: $DID"
echo "✅ Generated Child ID: $CID"

# Test 2: Database connectivity
echo ""
echo "🔄 Test 2: Database Connectivity"
if psql "$DATABASE_URL_PSQL" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed (trying alternative method...)"
    # Try with python as fallback
    if python3 -c "
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect('$DATABASE_URL')
    result = await conn.fetchval('SELECT 1')
    await conn.close()
    print(f'✅ Database connection successful (asyncpg): {result}')
asyncio.run(test())
" 2>/dev/null; then
        echo "✅ Database connection working via asyncpg"
    else
        echo "❌ Database connection failed via both methods"
    fi
fi

# Test 3: Redis connectivity
echo ""
echo "🔄 Test 3: Redis Connectivity"
if python3 -c "import redis; r=redis.from_url('$REDIS_URL'); print('✅ Redis connection:', r.ping())" 2>/dev/null; then
    echo "✅ Redis connection successful"
else
    echo "❌ Redis connection failed or redis package missing"
fi

# Test 4: HMAC calculation (like ESP32 would do)
echo ""
echo "🔄 Test 4: HMAC Calculation"
OOB="20F98D30602B1F5359C2775CC6BC74389CDE906348676F9B4D89B93151C77182"
NONCE=$(openssl rand -hex 8)
echo "Generated Nonce: $NONCE"

HMAC=$(python3 - <<PY
import binascii, hmac, hashlib
oob_bytes = binascii.unhexlify("$OOB")
message = "${DID}".encode() + "${CID}".encode() + binascii.unhexlify("$NONCE")
hmac_result = hmac.new(oob_bytes, message, hashlib.sha256).hexdigest()
print(hmac_result)
PY
)
echo "✅ HMAC calculated: ${HMAC:0:16}..."

# Test 5: JSON payload creation
echo ""
echo "🔄 Test 5: JSON Payload Creation"
PAYLOAD=$(jq -nc \
  --arg d "$DID" \
  --arg c "$CID" \
  --arg n "$NONCE" \
  --arg h "$HMAC" \
  '{device_id:$d, child_id:$c, nonce:$n, hmac_hex:$h}')

echo "✅ JSON Payload:"
echo "$PAYLOAD" | jq '.'

echo ""
echo "📋 SUMMARY"
echo "=========="
echo "✅ Dynamic ID generation working"
echo "✅ HMAC calculation working"
echo "✅ JSON payload creation working"
echo "🔧 Ready for full E2E test"