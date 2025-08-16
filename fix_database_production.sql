-- Production Database Fixes for ESP32 Claim API
-- Run on staging first.

BEGIN;

-- 0) Abort if case-insensitive duplicates would collide after LOWER/TRIM
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM (
      SELECT lower(btrim(device_id)) AS did, count(*) AS cnt
      FROM devices
      GROUP BY 1
      HAVING count(*) > 1
    ) dup
  ) THEN
    RAISE EXCEPTION 'Aborting: found case-insensitive duplicate device_id(s). Resolve before normalization.';
  END IF;
END $$;

-- 1) Backfill NULLs
UPDATE devices SET is_active = TRUE WHERE is_active IS NULL;

-- 2) Defaults + NOT NULL going forward
ALTER TABLE devices ALTER COLUMN is_active SET DEFAULT TRUE;
ALTER TABLE devices ALTER COLUMN is_active SET NOT NULL;

-- 3) Normalize existing IDs (lower + trim)
UPDATE devices
SET device_id = lower(btrim(device_id))
WHERE device_id <> lower(btrim(device_id));

-- 4) Enforce normalization at the DB layer
ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_device_id_lower;
ALTER TABLE devices
  ADD CONSTRAINT devices_device_id_lower
  CHECK (device_id = lower(device_id) AND device_id = btrim(device_id));

COMMIT;

-- 5) Verify
SELECT
  COUNT(*) AS total_devices,
  COUNT(*) FILTER (WHERE is_active) AS active_devices,
  COUNT(*) FILTER (WHERE NOT is_active) AS inactive_devices,
  COUNT(*) FILTER (WHERE is_active IS NULL) AS null_active_devices,
  COUNT(*) FILTER (WHERE device_id <> lower(device_id) OR device_id <> btrim(device_id)) AS non_normalized_ids;

-- (Optional) Inspect FKs that reference devices before running:
-- SELECT conname, conrelid::regclass AS referencing_table
-- FROM pg_constraint
-- WHERE contype='f' AND confrelid='devices'::regclass;