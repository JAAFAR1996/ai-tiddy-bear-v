# خطة اختبار وقياس أداء الفهارس قبل الإنتاج

## 1. تجهيز بيئة الاختبار
- استخدم نسخة من قاعدة البيانات الإنتاجية (مع إخفاء أو تشفير البيانات الحساسة).
- إذا كان الحجم كبيرًا، يكفي نسخة تحتوي 10–20% من البيانات الفعلية.
- تأكد أن إعدادات PostgreSQL (work_mem, maintenance_work_mem) مطابقة للإنتاج.

## 2. قياس الوضع قبل الفهارس
- اختر 3–5 استعلامات حقيقية تستخدم الأعمدة المستهدفة:
  - استعلامات messages حسب child_id و created_at
  - استعلامات conversations حسب user_id و created_at
  - بحث نصي في messages.content
- لكل استعلام:
  - شغّل:
    ```sql
    EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
    ```
  - سجّل:
    - زمن التنفيذ (Execution Time)
    - عدد الصفحات المقروءة من القرص/الذاكرة
    - خطة التنفيذ (Seq Scan أو Index Scan)

## 3. تنفيذ الفهارس مع التوقيت
- في بيئة الاختبار:
  - فعّل التوقيت:
    ```sql
    \timing on
    CREATE INDEX CONCURRENTLY ix_messages_child_id_created_at ON messages(child_id, created_at DESC);
    CREATE INDEX CONCURRENTLY ix_conversations_user_id_created_at ON conversations(user_id, created_at DESC);
    CREATE INDEX CONCURRENTLY ix_messages_content_trgm ON messages USING GIN (content gin_trgm_ops);
    \timing off
    ```
  - سجّل وقت الإنشاء لكل فهرس.
  - راقب الـ locks:
    ```sql
    SELECT pid, relation::regclass, mode, granted
    FROM pg_locks
    WHERE relation IS NOT NULL;
    ```

## 4. قياس الوضع بعد الفهارس
- أعد تشغيل نفس استعلامات الخطوة 2.
- قارن Execution Time قبل وبعد.
- تحقق أن الخطة صارت تستخدم Index Scan أو Bitmap Index Scan بدل Seq Scan.

---

> **ملاحظة:**
> يجب توثيق جميع النتائج (قبل/بعد) في ملف منفصل أو جدول للمقارنة، مع ذكر حجم البيانات ووقت التنفيذ بدقة.
