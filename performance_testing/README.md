# Performance & Load Testing Guide

## 1. المتطلبات
- Python 3.9+
- Locust (`pip install locust`)
- requests (`pip install requests`)

## 2. تشغيل اختبار الحمل الكامل
```bash
cd performance_testing
locust -f locustfile.py --headless -u 50 -r 5 -t 5m --csv=../logs/benchmarks/locust_run
```
- `-u 50`: عدد المستخدمين الافتراضيين
- `-r 5`: معدل بدء المستخدمين في الثانية
- `-t 5m`: مدة الاختبار
- النتائج في logs/benchmarks/ و logs/graphs/

## 3. قياس زمن الاستجابة يدويًا
```bash
cd performance_testing
python latency_measurement_example.py
```
- النتائج في logs/benchmarks/manual_latency_log.csv

## 4. توثيق النتائج
- استخدم logs/performance_report.md لتوثيق وتحليل النتائج.
- أضف الرسوم البيانية (يمكن رسمها بExcel أو matplotlib من ملفات CSV).

## 5. ملاحظات
- تأكد من تشغيل السيرفر على http://localhost:8000
- عدل بيانات الاختبار حسب الحاجة.
- راقب استهلاك الموارد أثناء الاختبار (CPU/RAM/DB/Redis).

---
> جميع السكريبتات والقوالب متوافقة مع تعليمات الأمان والامتثال للمشروع.
