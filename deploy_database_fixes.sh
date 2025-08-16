#!/bin/bash
# Production Database Deployment Script
# Run this on staging first, then production

set -e

echo "================================"
echo "AI Teddy Bear Database Deployment"
echo "================================"

# Check environment
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL not set"
    exit 1
fi

# Extract environment name from prompt
read -p "Which environment? (staging/production): " ENV_NAME

if [ "$ENV_NAME" != "staging" ] && [ "$ENV_NAME" != "production" ]; then
    echo "ERROR: Invalid environment. Use 'staging' or 'production'"
    exit 1
fi

# Safety check for production
if [ "$ENV_NAME" = "production" ]; then
    echo ""
    echo "⚠️  WARNING: You are about to run database changes on PRODUCTION"
    read -p "Have you tested these changes on staging? (yes/no): " TESTED
    if [ "$TESTED" != "yes" ]; then
        echo "Please test on staging first!"
        exit 1
    fi
    
    read -p "Type 'DEPLOY TO PRODUCTION' to confirm: " CONFIRM
    if [ "$CONFIRM" != "DEPLOY TO PRODUCTION" ]; then
        echo "Deployment cancelled"
        exit 1
    fi
fi

echo ""
echo "Running database fixes on $ENV_NAME..."
echo ""

# Run the SQL script
psql "$DATABASE_URL" < fix_database_production.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Database fixes applied successfully to $ENV_NAME"
    echo ""
    echo "Verification query results:"
    psql "$DATABASE_URL" -c "SELECT COUNT(*) AS total_devices, COUNT(*) FILTER (WHERE is_active) AS active_devices, COUNT(*) FILTER (WHERE NOT is_active) AS inactive_devices, COUNT(*) FILTER (WHERE is_active IS NULL) AS null_active_devices, COUNT(*) FILTER (WHERE device_id <> lower(device_id) OR device_id <> btrim(device_id)) AS non_normalized_ids FROM devices;"
else
    echo ""
    echo "❌ Database fixes failed on $ENV_NAME"
    exit 1
fi