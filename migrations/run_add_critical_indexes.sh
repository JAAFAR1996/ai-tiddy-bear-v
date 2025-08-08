#!/bin/bash
# Manual index creation and monitoring script for PostgreSQL (production safe)
# Usage: bash run_add_critical_indexes.sh

set -e

LOGFILE="manual_add_critical_indexes.log"
DB_URL=${DATABASE_URL:-"postgresql://<user>:<pass>@<host>:<port>/<db>?sslmode=require"}
SQL_FILE="$(dirname "$0")/manual_add_critical_indexes.sql"

# Log start time
echo "[START] $(date) - Creating indexes..." | tee -a "$LOGFILE"

# Show current locks before
psql "$DB_URL" -c "SELECT pid, relation::regclass, mode, granted FROM pg_locks WHERE relation IS NOT NULL;" | tee -a "$LOGFILE"

# Run index creation
psql "$DB_URL" -f "$SQL_FILE" | tee -a "$LOGFILE"

# Show locks after
psql "$DB_URL" -c "SELECT pid, relation::regclass, mode, granted FROM pg_locks WHERE relation IS NOT NULL;" | tee -a "$LOGFILE"

# Show index sizes
echo "[INDEX SIZES]" | tee -a "$LOGFILE"
psql "$DB_URL" -c "SELECT indexname, pg_size_pretty(pg_relation_size(indexrelid)) FROM pg_stat_user_indexes;" | tee -a "$LOGFILE"

# Log end time
echo "[END] $(date) - Index creation complete." | tee -a "$LOGFILE"
