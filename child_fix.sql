BEGIN;

-- 1) تفعيل دالة gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2) تأكد ما عندك تعارضات قبل جعل hashed_identifier فريد
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM (
      SELECT hashed_identifier, COUNT(*) AS cnt
      FROM children
      WHERE hashed_identifier IS NOT NULL
      GROUP BY 1
      HAVING COUNT(*) > 1
    ) dups
  ) THEN
    RAISE EXCEPTION 'Aborting: duplicate hashed_identifier rows exist in children';
  END IF;
END $$;

-- قيْد فريد (لن يفشل ON CONFLICT بعده)
ALTER TABLE children
  ADD CONSTRAINT children_hashed_identifier_unique UNIQUE (hashed_identifier);

-- عمود is_active
ALTER TABLE children
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;

-- مزامنة is_active مع موافقة الأهل وحالة الحذف
UPDATE children
SET is_active = (parental_consent = TRUE AND is_deleted = FALSE)
WHERE is_active IS DISTINCT FROM (parental_consent = TRUE AND is_deleted = FALSE);

-- طفل اختباري/تعريفي
INSERT INTO children (
  id, parent_id, name, hashed_identifier, estimated_age,
  parental_consent, is_active, is_deleted, safety_level,
  content_filtering_enabled, interaction_logging_enabled
)
VALUES (
  gen_random_uuid(), gen_random_uuid(), 'Test Child', 'test-child-001', 7,
  TRUE, TRUE, FALSE, 'safe', TRUE, TRUE
)
ON CONFLICT ON CONSTRAINT children_hashed_identifier_unique DO UPDATE
SET parental_consent=EXCLUDED.parental_consent,
    is_active=EXCLUDED.is_active,
    is_deleted=EXCLUDED.is_deleted;

COMMIT;