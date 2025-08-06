"""
خطة توحيد استخدام Redis في المشروع
===================================

# المشكلة الحالية:
المشروع يستخدم مكتبتين مختلفتين:
1. redis.asyncio (في ai_service.py) ✅
2. aioredis منفصلة (في caching services) ❌

# الحل:
توحيد الاستخدام على redis.asyncio في كل المشروع

# الملفات التي تحتاج تصحيح:

## 1. src/infrastructure/caching/production_tts_cache_service.py
الحالي:
```python
import aioredis
from aioredis import Redis, ConnectionPool
```

المطلوب:
```python
import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
```

## 2. src/infrastructure/caching/production_redis_cache.py
الحالي:
```python
import aioredis
from aioredis import Redis, ConnectionPool
```

المطلوب:
```python
import redis.asyncio as aioredis
from redis.asyncio import Redis, ConnectionPool
```

## 3. src/infrastructure/config/loader.py
الحالي:
```python
import aioredis
```

المطلوب:
```python
import redis.asyncio as aioredis
```

# التأثير على البنية:

## قبل التوحيد:
- أنماط اتصال مختلفة
- استثناءات مختلفة
- طرق إغلاق مختلفة
- dependency conflicts محتملة

## بعد التوحيد:
- نمط واحد موحد
- استثناءات موحدة
- طرق إغلاق موحدة
- لا توجد conflicts
- سهولة الصيانة
- تحديثات موحدة

# الفوائد:
1. ✅ توافق كامل مع requirements.txt
2. ✅ لا حاجة لتثبيت مكتبات إضافية
3. ✅ دعم رسمي من Redis Labs
4. ✅ تحديثات سريعة لميزات Redis الجديدة
5. ✅ مجتمع أكبر ودعم أفضل
6. ✅ بنية كود موحدة وواضحة
"""
