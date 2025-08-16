BEGIN;

-- 1) Check what we have currently
SELECT 'Current children table structure:' as info;

-- 2) Add columns we need if they don't exist
ALTER TABLE children ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE children ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE children ADD COLUMN IF NOT EXISTS parental_consent BOOLEAN DEFAULT TRUE NOT NULL;

-- 3) Add hashed_identifier as alias for id (since current table uses string id)
ALTER TABLE children ADD COLUMN IF NOT EXISTS hashed_identifier VARCHAR(100);

-- 4) Populate hashed_identifier with existing id values (for compatibility)
UPDATE children 
SET hashed_identifier = id 
WHERE hashed_identifier IS NULL;

-- 5) Add unique constraint on hashed_identifier
ALTER TABLE children ADD CONSTRAINT children_hashed_identifier_unique UNIQUE (hashed_identifier);

-- 6) Set active status based on consent (with proper COALESCE)
UPDATE children
SET is_active = (COALESCE(parental_consent, data_collection_consent) = TRUE AND is_deleted = FALSE);

-- 7) Add case-insensitive index for performance
CREATE INDEX IF NOT EXISTS idx_children_hashed_identifier_lower
ON children (LOWER(hashed_identifier));

-- 8) Insert test child
INSERT INTO children (
  id, parent_id, name, age, hashed_identifier,
  data_collection_consent, parental_consent, is_active, is_deleted,
  safety_settings, preferences, data_retention_days,
  created_at, updated_at
)
VALUES (
  'test-child-001', 'test-parent-001', 'Test Child', 7, 'test-child-001',
  TRUE, TRUE, TRUE, FALSE,
  '{"level": "safe", "content_filtering": true}',
  '{}',
  90,
  NOW(), NOW()
)
ON CONFLICT (hashed_identifier) DO UPDATE
SET data_collection_consent=TRUE, parental_consent=TRUE, is_active=TRUE, is_deleted=FALSE;

-- 9) Verify the result
SELECT id, name, age, hashed_identifier, parental_consent, is_active, is_deleted 
FROM children 
WHERE hashed_identifier = 'test-child-001';

COMMIT;