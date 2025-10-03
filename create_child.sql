CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Upsert parent
WITH upsert_parent AS (
  INSERT INTO users (id, username, role, is_active, is_verified, language, timezone, settings, metadata_json)
  VALUES (gen_random_uuid(), 'parent_iraq', 'PARENT', TRUE, TRUE, 'ar', 'Asia/Baghdad', '{}'::jsonb, '{}'::jsonb)
  ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
  RETURNING id
),
sel AS (
  SELECT id FROM upsert_parent
  UNION ALL
  SELECT id FROM users WHERE username = 'parent_iraq' LIMIT 1
)
INSERT INTO children (
  parent_id, name, birth_date, hashed_identifier, parental_consent, consent_date,
  age_verified, age_verification_date, estimated_age, safety_level,
  content_filtering_enabled, interaction_logging_enabled, data_retention_days, allow_data_sharing,
  favorite_topics, content_preferences, metadata_json
)
SELECT
  id,
  'علي',
  (NOW() - INTERVAL '7 years'),
  'child_2abedbdf',
  TRUE, NOW(),
  TRUE, NOW(),
  7, 'SAFE',
  TRUE, TRUE, 365, FALSE,
  '[]'::jsonb,
  '{ language:ar,content_type:educational}'::jsonb,
  '{created_via:direct_setup,country:IQ}'::jsonb
FROM sel
ON CONFLICT (hashed_identifier) DO NOTHING;
