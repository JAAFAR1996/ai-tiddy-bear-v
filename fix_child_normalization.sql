-- Child ID Normalization and Test Data Setup
-- Run this AFTER fix_database_production.sql

BEGIN;

-- ============================================
-- PART 1: Normalize existing child_id data
-- ============================================

-- Check for case-insensitive duplicates before normalization
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM (
      SELECT lower(btrim(child_id)) AS cid, count(*) AS cnt
      FROM children
      GROUP BY 1
      HAVING count(*) > 1
    ) dup
  ) THEN
    RAISE NOTICE 'Warning: Found case-insensitive duplicate child_id(s). Manual resolution may be needed.';
  END IF;
END $$;

-- Normalize existing child IDs (lowercase + trim)
UPDATE children
SET child_id = lower(btrim(child_id))
WHERE child_id <> lower(btrim(child_id));

-- Add CHECK constraint to enforce normalization
ALTER TABLE children DROP CONSTRAINT IF EXISTS children_child_id_normalized;
ALTER TABLE children
  ADD CONSTRAINT children_child_id_normalized
  CHECK (child_id = lower(child_id) AND child_id = btrim(child_id));

-- ============================================
-- PART 2: Add indexes for performance
-- ============================================

-- Create index for normalized lookups (if not exists)
CREATE INDEX IF NOT EXISTS idx_children_child_id_lower 
ON children(lower(child_id));

-- Create index for active children
CREATE INDEX IF NOT EXISTS idx_children_active 
ON children(is_active) 
WHERE is_active = true;

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_children_child_id_active 
ON children(lower(child_id), is_active);

-- ============================================
-- PART 3: Ensure test child exists
-- ============================================

-- Insert test child if not exists
INSERT INTO children (
  child_id,
  parent_id, 
  first_name,
  last_name,
  birth_date,
  is_active,
  created_at,
  updated_at
) VALUES (
  'test-child-001',  -- Already lowercase
  'test-parent-001',
  'Test',
  'Child',
  '2019-01-01'::date,  -- 5 years old
  true,
  NOW(),
  NOW()
) ON CONFLICT (child_id) 
DO UPDATE SET 
  is_active = true,
  updated_at = NOW()
WHERE children.is_active = false;

-- Also ensure the parent exists
INSERT INTO parents (
  parent_id,
  email,
  first_name,
  last_name,
  is_active,
  created_at,
  updated_at
) VALUES (
  'test-parent-001',
  'test@example.com',
  'Test',
  'Parent',
  true,
  NOW(),
  NOW()
) ON CONFLICT (parent_id) DO NOTHING;

-- ============================================
-- PART 4: Fix any NULL is_active values
-- ============================================

-- Ensure no NULL is_active in children table
UPDATE children SET is_active = true WHERE is_active IS NULL;
ALTER TABLE children ALTER COLUMN is_active SET DEFAULT true;
ALTER TABLE children ALTER COLUMN is_active SET NOT NULL;

-- Same for parents
UPDATE parents SET is_active = true WHERE is_active IS NULL;
ALTER TABLE parents ALTER COLUMN is_active SET DEFAULT true;
ALTER TABLE parents ALTER COLUMN is_active SET NOT NULL;

COMMIT;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Check normalization status
SELECT 
  'Children Table Status' as check_type,
  COUNT(*) AS total_children,
  COUNT(*) FILTER (WHERE is_active) AS active_children,
  COUNT(*) FILTER (WHERE NOT is_active) AS inactive_children,
  COUNT(*) FILTER (WHERE child_id <> lower(child_id) OR child_id <> btrim(child_id)) AS non_normalized_ids
FROM children;

-- Verify test child exists and is active
SELECT 
  'Test Child Status' as check_type,
  child_id,
  parent_id,
  first_name,
  is_active,
  created_at
FROM children 
WHERE lower(child_id) = 'test-child-001';

-- Check indexes
SELECT 
  'Indexes' as check_type,
  indexname,
  indexdef
FROM pg_indexes 
WHERE tablename = 'children' 
AND indexname LIKE '%child_id%';

-- Example query showing how to lookup children (use in claim_api.py)
-- This is how the application should query:
/*
SELECT * FROM children 
WHERE lower(child_id) = lower(:child_id) 
AND is_active = true;
*/