"""
مقارنة شاملة بين مكتبات Redis للـ Python
==========================================

# 1. aioredis (المكتبة المنفصلة)
الإصدار: 2.0.1 (آخر إصدار)
المطور: مجتمع منفصل
الحالة: مهجورة جزئياً

المزايا:
✅ مصممة خصيصاً للـ async/await
✅ API بسيط ومباشر
✅ دعم جيد للـ Redis Streams
✅ مستقرة وموثوقة

العيوب:
❌ تطويرها بطيء
❌ مكتبة إضافية للتثبيت
❌ قد لا تدعم ميزات Redis الجديدة بسرعة
❌ مجتمع أصغر

# 2. redis.asyncio (الرسمية)
الإصدار: جزء من redis-py 4.0+
المطور: Redis Labs (الشركة الرسمية)
الحالة: التطوير النشط

المزايا:
✅ مكتبة رسمية من Redis Labs
✅ تطوير نشط ومستمر
✅ دعم فوري لميزات Redis الجديدة
✅ API متوافق مع redis-py العادي
✅ لا تحتاج تثبيت مكتبة إضافية
✅ مجتمع كبير ودعم رسمي

العيوب:
❌ أحدث (قد تكون أقل اختباراً)
❌ بعض الاختلافات البسيطة في API

# 3. مثال عملي للفروق:

## aioredis (المنفصلة):
import aioredis

async def old_way():
    redis = aioredis.from_url("redis://localhost")
    await redis.set("key", "value")
    value = await redis.get("key")
    await redis.close()

## redis.asyncio (الرسمية):
import redis.asyncio as aioredis

async def new_way():
    redis = aioredis.from_url("redis://localhost")
    await redis.set("key", "value")
    value = await redis.get("key")
    await redis.close()

# الـ API متشابه تقريباً، لكن التفاصيل مختلفة!

# 4. الفروق في Connection Pool:

## aioredis:
pool = aioredis.ConnectionPool.from_url(url)
redis = aioredis.Redis(connection_pool=pool)

## redis.asyncio:
pool = aioredis.ConnectionPool.from_url(url)
redis = aioredis.Redis(connection_pool=pool)

# 5. إدارة الاتصالات:

## aioredis:
await redis.wait_closed()  # طريقة قديمة

## redis.asyncio:
await redis.aclose()  # طريقة جديدة محسنة

# 6. دعم المزايا:

Feature                    | aioredis | redis.asyncio
---------------------------|----------|---------------
Redis Streams             | ✅       | ✅
Redis Modules              | ⚠️       | ✅
Latest Redis Commands      | ⚠️       | ✅
Connection Pooling         | ✅       | ✅
Sentinel Support           | ✅       | ✅
Cluster Support            | ✅       | ✅
Official Support           | ❌       | ✅
"""
