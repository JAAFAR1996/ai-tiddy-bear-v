# 🎤 ESP32 Audio Setup - دليل الصوت

## 🔌 التوصيلات الصوتية

### I2S Microphone (INMP441 أو مشابه)
```
ESP32 Pin    →    I2S Microphone
---------         --------------
GPIO 26      →    SCK (Serial Clock)
GPIO 22      →    WS (Word Select)
GPIO 21      →    SD (Serial Data)
3.3V         →    VDD
GND          →    GND
GND          →    L/R (for left channel)
```

### I2S Speaker/Amplifier (MAX98357A أو مشابه)
```
ESP32 Pin    →    I2S Speaker
---------         -----------
GPIO 26      →    BCLK
GPIO 22      →    LRC
GPIO 25      →    DIN
3.3V         →    VIN
GND          →    GND
```

## 🎵 كيف يعمل النظام

### 1. تسجيل الصوت
- اضغط على الزر لبدء التسجيل
- LED يضيء باللون الأزرق أثناء التسجيل
- يسجل لمدة 5 ثوانٍ تلقائياً
- يرسل الصوت للخادم

### 2. معالجة الخادم
- الخادم يستقبل الصوت
- يحوله لنص باستخدام Speech-to-Text
- يرسل النص لـ AI للمعالجة
- يحول الرد لصوت باستخدام Text-to-Speech
- يرسل الصوت للـ ESP32

### 3. تشغيل الرد
- ESP32 يستقبل الصوت
- LED يضيء باللون الأخضر أثناء التشغيل
- يشغل الرد الصوتي عبر السبيكر

## 📊 مواصفات الصوت

```cpp
#define SAMPLE_RATE 16000    // 16 kHz
#define SAMPLE_BITS 16       // 16-bit
#define RECORD_TIME 5        // 5 seconds
#define BUFFER_SIZE 1024     // Buffer size
```

## 🔧 اختبار النظام

### 1. تحقق من التوصيلات
```cpp
void printAudioInfo(); // في Serial Monitor
```

### 2. اختبار التسجيل
- اضغط الزر
- تأكد من ظهور "🎤 Starting audio recording..."
- تأكد من إرسال البيانات "📤 Audio data sent to server"

### 3. اختبار التشغيل
- تأكد من استقبال "🔊 Received audio response from server"
- تأكد من تشغيل الصوت "🔊 Playing audio response"

## 🛠️ استكشاف الأخطاء

### مشكلة: لا يسجل الصوت
```
- تحقق من توصيل I2S Microphone
- تأكد من GPIO pins صحيحة
- تحقق من مصدر الطاقة (3.3V)
```

### مشكلة: لا يشغل الصوت
```
- تحقق من توصيل I2S Speaker
- تأكد من GPIO pins صحيحة
- تحقق من مكبر الصوت
```

### مشكلة: جودة صوت ضعيفة
```
- تحقق من SAMPLE_RATE
- تأكد من عدم وجود تداخل كهربائي
- استخدم أسلاك قصيرة
```

## 📋 رسائل التشخيص

```
🎤 Starting audio recording...     // بدء التسجيل
🎤 Recording complete: X bytes     // انتهاء التسجيل
📤 Sending audio to server...      // إرسال للخادم
📤 Audio data sent to server       // تم الإرسال
🔊 Received audio response         // استقبال الرد
🔊 Playing audio response: X bytes // تشغيل الرد
🔊 Audio playback complete         // انتهاء التشغيل
```

## 🎯 الميزات المتقدمة

### تحسين جودة الصوت
```cpp
// يمكن تعديل هذه القيم في config.h
#define SAMPLE_RATE 22050    // جودة أعلى
#define RECORD_TIME 10       // تسجيل أطول
```

### إضافة فلاتر صوتية
```cpp
// في audio_handler.cpp
void applyNoiseFilter(uint8_t* audioData, size_t length);
void amplifyAudio(uint8_t* audioData, size_t length, float gain);
```

### حفظ الصوت محلياً
```cpp
// حفظ على SD Card للاختبار
void saveAudioToSD(uint8_t* audioData, size_t length);
```

## 🔒 الأمان

- الصوت مشفر أثناء الإرسال
- لا يحفظ الصوت محلياً
- يحذف البيانات بعد الإرسال
- حماية من التسجيل المستمر

## 📞 الدعم

إذا واجهت مشاكل:
1. تحقق من Serial Monitor للأخطاء
2. تأكد من التوصيلات
3. اختبر كل مكون منفصلاً
4. تحقق من إعدادات الخادم