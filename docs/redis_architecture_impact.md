"""
تأثير مكتبات Redis على بنية المشروع
=====================================

# 1. الفروق في هيكل الكود:

## A. aioredis (المنفصلة):
```python
# بنية مختلفة للاتصال
import aioredis

class RedisService:
    def __init__(self):
        self.redis = None
    
    async def connect(self):
        # طريقة الاتصال مختلفة
        self.redis = await aioredis.create_redis_pool('redis://localhost')
    
    async def disconnect(self):
        # طريقة الإغلاق مختلفة
        self.redis.close()
        await self.redis.wait_closed()
```

## B. redis.asyncio (الرسمية):
```python
# بنية موحدة مع redis العادي
import redis.asyncio as aioredis

class RedisService:
    def __init__(self):
        self.redis = None
    
    async def connect(self):
        # طريقة موحدة
        self.redis = aioredis.from_url('redis://localhost')
    
    async def disconnect(self):
        # طريقة محسنة
        await self.redis.aclose()
```

# 2. الفروق في إدارة Connection Pool:

## aioredis:
```python
# Pool منفصل
pool = await aioredis.create_pool('redis://localhost')
redis = aioredis.Redis(pool)
```

## redis.asyncio:
```python
# Pool مدمج مع المكتبة الرئيسية
pool = aioredis.ConnectionPool.from_url('redis://localhost')
redis = aioredis.Redis(connection_pool=pool)
```

# 3. الفروق في معالجة الأخطاء:

## aioredis:
```python
from aioredis import RedisError, ConnectionError

try:
    await redis.get('key')
except RedisError as e:
    # معالجة خاصة بـ aioredis
    pass
```

## redis.asyncio:
```python
from redis.exceptions import RedisError, ConnectionError

try:
    await redis.get('key')
except RedisError as e:
    # معالجة موحدة مع redis-py
    pass
```

# 4. الفروق في Configuration:

## aioredis:
```python
# تكوين خاص
redis = await aioredis.create_redis_pool(
    'redis://localhost',
    encoding='utf-8',
    commands_factory=aioredis.commands.Redis
)
```

## redis.asyncio:
```python
# تكوين موحد
redis = aioredis.from_url(
    'redis://localhost',
    encoding='utf-8',
    decode_responses=True
)
```

# 5. الفروق في Pipeline Operations:

## aioredis:
```python
# Pipeline منفصل
pipe = redis.pipeline()
pipe.set('key1', 'value1')
pipe.set('key2', 'value2')
result = await pipe.execute()
```

## redis.asyncio:
```python
# Pipeline موحد مع async context manager
async with redis.pipeline() as pipe:
    pipe.set('key1', 'value1')
    pipe.set('key2', 'value2')
    result = await pipe.execute()
```

# 6. الفروق في Testing:

## aioredis:
```python
# Mock خاص
from unittest.mock import AsyncMock
mock_redis = AsyncMock(spec=aioredis.Redis)
```

## redis.asyncio:
```python
# Mock موحد
from unittest.mock import AsyncMock
import redis.asyncio as aioredis
mock_redis = AsyncMock(spec=aioredis.Redis)
```
"""
