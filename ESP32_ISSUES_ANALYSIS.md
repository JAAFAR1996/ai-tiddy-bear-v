# ESP32 Issues Analysis & Fixes

## 🔍 المشاكل المكتشفة

### 1. **مشكلة التعقيد في المصادقة**
- ❌ ESP32 يحاول استخدام HMAC و JWT معاً
- ❌ كود معقد لحساب HMAC-SHA256
- ❌ يتطلب مفاتيح سرية معقدة

**الحل**: تبسيط المصادقة لتتطلب فقط `device_id`

### 2. **مشكلة في WebSocket URL**
- ❌ ESP32 يستخدم `/ws/esp32/connect` 
- ❌ Server يتوقع `/api/v1/esp32/chat`

**الحل**: تحديث ESP32 ليستخدم المسار الصحيح

### 3. **مشكلة في إعدادات الخادم**
- ❌ ESP32 يحاول الاتصال بـ `192.168.0.133`
- ❌ قد لا يكون هذا هو عنوان الخادم الصحيح

**الحل**: تحديث عنوان الخادم

## 🛠️ الإصلاحات المطلوبة

### 1. تحديث WebSocket Handler في ESP32

```cpp
// في websocket_handler.cpp
String wsPath = "/api/v1/esp32/chat";  // بدلاً من /ws/esp32/connect
wsPath += "?device_id=" + deviceId;
wsPath += "&child_name=" + childName;
wsPath += "&child_age=" + String(childAge);
// إزالة HMAC token - لا حاجة له
```

### 2. تبسيط المصادقة

```cpp
// إزالة هذا الكود المعقد:
String token = hmac_sha256_hex_raw(String(ESP32_SHARED_SECRET), deviceId);

// استخدام اتصال مباشر بدون token
```

### 3. تحديث عنوان الخادم

```cpp
// في config.h
#define DEFAULT_SERVER_HOST "localhost"  // أو عنوان الخادم الصحيح
#define DEFAULT_SERVER_PORT 8000
```

## 🧪 خطة الاختبار

### 1. اختبار الخادم
```bash
# تشغيل الخادم
cd "ai teddy bear"
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. اختبار الاتصال
```bash
# تشغيل اختبار ESP32
python test_esp32_simplified.py
```

### 3. اختبار WebSocket يدوياً
```javascript
// في المتصفح
const ws = new WebSocket('ws://localhost:8000/api/v1/esp32/chat?device_id=TEST001&child_name=Ahmed&child_age=8');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Received:', e.data);
```

## 📋 قائمة التحقق

- [ ] تحديث WebSocket URL في ESP32
- [ ] إزالة HMAC token من ESP32
- [ ] تحديث عنوان الخادم
- [ ] اختبار REST endpoints
- [ ] اختبار WebSocket connection
- [ ] اختبار تدفق الصوت
- [ ] اختبار heartbeat

## 🎯 النتيجة المتوقعة

بعد هذه الإصلاحات:
- ✅ ESP32 يتصل بسهولة بدون tokens معقدة
- ✅ WebSocket يعمل مع device_id فقط
- ✅ تدفق الصوت يعمل بشكل طبيعي
- ✅ النظام أبسط وأكثر استقراراً