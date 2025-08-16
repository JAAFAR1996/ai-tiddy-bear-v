-- Quick database status check
-- Run this to verify current state

-- 1. Check if children table exists and structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'children' 
ORDER BY ordinal_position;

-- 2. Check for test child with text ID
SELECT id, hashed_identifier, name, parental_consent, is_deleted, estimated_age, created_at
FROM children 
WHERE lower(hashed_identifier) = 'test-child-001'
   OR hashed_identifier LIKE '%test%'
LIMIT 5;

-- 3. Check devices table for test device
SELECT device_id, status, is_active, oob_secret IS NOT NULL as has_secret, created_at
FROM devices 
WHERE lower(device_id) = 'test-device-001'
   OR device_id LIKE '%test%'
LIMIT 5;

-- 4. Check if we have any children at all
SELECT COUNT(*) as total_children,
       COUNT(*) FILTER (WHERE parental_consent = true) as consented_children,
       COUNT(*) FILTER (WHERE is_deleted = false) as active_children
FROM children;

-- 5. Verify current table structure matches expected
SELECT 
    EXISTS(SELECT 1 FROM information_schema.columns 
           WHERE table_name = 'children' AND column_name = 'is_active') as has_is_active,
    EXISTS(SELECT 1 FROM information_schema.columns 
           WHERE table_name = 'children' AND column_name = 'hashed_identifier') as has_hashed_identifier,
    EXISTS(SELECT 1 FROM information_schema.columns 
           WHERE table_name = 'children' AND column_name = 'parental_consent') as has_parental_consent;