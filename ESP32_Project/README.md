# 🧸 ESP32 AI Teddy Bear Project

## 📋 ما تحتاجه

### الأجهزة
- **ESP32 Development Board**
- **LED Strip WS2812B** (10 LEDs)
- **Servo Motor SG90**
- **Speaker/Buzzer** (3-5V)
- **Push Button**
- **Breadboard & Jumper Wires**

### التوصيلات
```
ESP32 Pin    →    Component
---------         ---------
GPIO 2       →    LED Strip (Data)
GPIO 18      →    Servo (Signal)
GPIO 25      →    Speaker (+)
GPIO 0       →    Button (one side)
GND          →    All GND connections
3.3V         →    Button pull-up
5V           →    LED Strip VCC, Servo VCC
```

## 🚀 كيفية الاستخدام

### 1. تحديث الإعدادات
افتح `include/config.h` وغير:
```cpp
const char* WIFI_SSID = "اسم_الشبكة";
const char* WIFI_PASSWORD = "كلمة_المرور";
const char* SERVER_HOST = "192.168.1.100";  // IP الخادم
```

### 2. رفع الكود
1. افتح المشروع في VS Code مع PlatformIO
2. اضغط على "Upload" أو Ctrl+Alt+U
3. راقب Serial Monitor للتأكد من الاتصال

### 3. اختبار الوظائف
- **الزر**: اضغط لإرسال حدث للخادم
- **LEDs**: ستضيء عند الاتصال
- **Servo**: سيتحرك عند استلام أوامر
- **Speaker**: سيصدر أصوات عند الأحداث

## 📡 الأوامر المدعومة

### LED Control
```json
{
  "type": "led_control",
  "params": {
    "color": "red",
    "brightness": 100
  }
}
```

### Servo Control
```json
{
  "type": "motor_control",
  "params": {
    "direction": "left",
    "speed": 50
  }
}
```

### Audio Play
```json
{
  "type": "audio_play",
  "params": {
    "file": "happy",
    "volume": 70
  }
}
```

### Animation
```json
{
  "type": "animation",
  "params": {
    "type": "rainbow"
  }
}
```

## 🔧 استكشاف الأخطاء

### ESP32 لا يتصل بالـ WiFi
- تأكد من صحة اسم الشبكة وكلمة المرور
- تأكد أن الشبكة 2.4GHz (ليس 5GHz)
- تحقق من قوة الإشارة

### WebSocket لا يعمل
- تأكد من IP الخادم صحيح
- تأكد أن الخادم يعمل على Port 8000
- تحقق من Firewall

### LEDs لا تعمل
- تأكد من توصيل Data Pin على GPIO 2
- تأكد من مصدر الطاقة (5V)
- تحقق من نوع LED Strip (WS2812B)

## 📊 مراقبة النظام

افتح Serial Monitor لمشاهدة:
- حالة الاتصال بالـ WiFi
- رسائل WebSocket
- أحداث الأزرار
- معلومات النظام

## 🎯 الميزات

- ✅ اتصال WiFi تلقائي
- ✅ WebSocket للتواصل مع الخادم
- ✅ تحكم في LEDs بألوان مختلفة
- ✅ تحريك Servo في اتجاهات مختلفة
- ✅ تشغيل أصوات مختلفة
- ✅ رسوم متحركة للـ LEDs
- ✅ إرسال أحداث الأزرار
- ✅ مراقبة حالة النظام
- ✅ إعادة الاتصال التلقائي

## 🔄 التحديثات المستقبلية

يمكن إضافة:
- كاميرا للرؤية
- حساسات إضافية
- تحديثات OTA
- تخزين محلي
- إدارة البطارية