-- سكربت اختبار سرعة الفهارس في PostgreSQL
-- شغّل هذا السكربت في بيئة اختبارية بعد ضبط الاتصال بقاعدة البيانات

-- 1. تفعيل التوقيت
\timing on

-- 2. قياس الاستعلامات قبل الفهارس
-- استعلام رسائل طفل حسب التاريخ
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM messages WHERE child_id = '123' ORDER BY created_at DESC LIMIT 20;

-- استعلام محادثات مستخدم حسب التاريخ
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM conversations WHERE user_id = '456' ORDER BY created_at DESC LIMIT 10;

-- بحث نصي في محتوى الرسائل
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM messages WHERE content ILIKE '%hello%' LIMIT 10;

-- 3. إنشاء الفهارس (نفذ كل أمر على حدة وسجّل الوقت)
CREATE INDEX CONCURRENTLY ix_messages_child_id_created_at ON messages(child_id, created_at DESC);
CREATE INDEX CONCURRENTLY ix_conversations_user_id_created_at ON conversations(user_id, created_at DESC);
CREATE INDEX CONCURRENTLY ix_messages_content_trgm ON messages USING GIN (content gin_trgm_ops);

-- 4. مراقبة الـ locks أثناء الإنشاء
SELECT pid, relation::regclass, mode, granted FROM pg_locks WHERE relation IS NOT NULL;

-- 5. إعادة قياس الاستعلامات بعد الفهارس
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM messages WHERE child_id = '123' ORDER BY created_at DESC LIMIT 20;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM conversations WHERE user_id = '456' ORDER BY created_at DESC LIMIT 10;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM messages WHERE content ILIKE '%hello%' LIMIT 10;

-- 6. إيقاف التوقيت
\timing off

-- ملاحظة: غيّر القيم ('123', '456', '%hello%') حسب بياناتك الفعلية في الاختبار.
