# Database Migration & Index Deployment Runbook

## التسلسل الصحيح للتنفيذ

1. **Migration Alembic**
   - نفّذ سكريبت Alembic المناسب (مثلاً عبر `alembic upgrade head`).
2. **إضافة الفهارس الحرجة يدويًا**
   - نفّذ `manual_add_critical_indexes.sql` يدويًا على قاعدة البيانات.
3. **مراقبة الأداء والـ locks أثناء التنفيذ**
   - راقب الـ locks:
     ```sql
     SELECT pid, locktype, relation::regclass, mode, granted, query
     FROM pg_locks l
     LEFT JOIN pg_stat_activity a ON l.pid = a.pid
     WHERE NOT granted;
     ```
   - راقب استهلاك الموارد (Linux):
     ```sh
     top
     iotop
     vmstat 1
     ```
   - راقب استهلاك الموارد (PostgreSQL):
     ```sql
     SELECT * FROM pg_stat_activity;
     ```
4. **اختبارات سريعة بعد التنفيذ**
   - نفّذ smoke tests للتأكد من سلامة النظام.

## الطوارئ (Rollback)
- استخدم `rollback_indexes.sql` فقط في حال ظهور مشاكل حرجة (توقف الخدمة، أخطاء كتابة/قراءة).
- يجب التنسيق مع الفريق قبل أي تراجع.

## تجربة الخطة في بيئة Staging
- نفّذ migration + الفهارس يدويًا في قاعدة بيانات تجريبية.
- راقب الوقت والموارد وأي مشاكل.
- وثّق النتائج.

## التوقيت الأمثل للتنفيذ في الإنتاج
- اختر نافذة زمنية منخفضة الحمل (مثلاً منتصف الليل).
- نسّق مع المستخدمين أو الأنظمة المرتبطة.

## توثيق
- جميع الملفات في `ops/sql/` ويجب تحديث هذا الدليل مع أي تغيير مستقبلي.
