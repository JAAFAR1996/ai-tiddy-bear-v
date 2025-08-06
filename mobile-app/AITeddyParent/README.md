# AI Teddy Parent - تطبيق مراقبة الوالدين

تطبيق React Native بسيط لمراقبة تفاعلات الأطفال مع الدب الذكي AI Teddy Bear.

## المميزات الحالية (MVP)

- ✅ تسجيل دخول بـ JWT
- ✅ عرض قائمة الأطفال
- ✅ عرض آخر 10 تفاعلات لكل طفل
- ✅ تنبيهات الأمان (كلمات محظورة/تجاوز وقت الاستخدام)
- ✅ واجهة عربية بسيطة

## التشغيل السريع

### المتطلبات
```bash
# Node.js 18+
# Expo CLI
npm install -g @expo/cli

# Android Studio (للأندرويد)
# Xcode (للـ iOS - Mac فقط)
```

### التثبيت والتشغيل
```bash
# التثبيت
cd mobile-app/AITeddyParent
npm install

# تشغيل التطبيق
npm start

# أو تشغيل مباشر على المنصات
npm run android    # Android
npm run ios        # iOS (Mac فقط)
npm run web        # متصفح
```

### ربط مع Backend

1. **تشغيل FastAPI Backend أولاً:**
```bash
cd "c:\Users\jaafa\Desktop\ai teddy bear"
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

2. **تحديث عنوان API في التطبيق:**
- للأندرويد Emulator: `http://10.0.2.2:8000`
- للـ iOS Simulator: `http://localhost:8000`
- للجهاز الحقيقي: `http://YOUR_COMPUTER_IP:8000`

### بيانات اختبارية
```
البريد الإلكتروني: parent@test.com
كلمة المرور: secure-password
```

## هيكل المشروع

```
src/
├── screens/
│   ├── LoginScreen.tsx     # شاشة تسجيل الدخول
│   └── DashboardScreen.tsx # لوحة التحكم الرئيسية
├── services/
│   └── api.ts             # خدمات API
├── types/
│   └── index.ts           # أنواع البيانات
└── config.ts              # إعدادات التطبيق
```

## إنشاء APK للاختبار

### طريقة 1: Expo Build Service (EAS)
```bash
# تثبيت EAS CLI
npm install -g @expo/cli

# إنشاء حساب Expo
expo login

# بناء APK
eas build --platform android --profile preview
```

### طريقة 2: محلي (Android Studio مطلوب)
```bash
# تصدير ملفات Android
expo run:android

# أو بناء APK يدوياً
cd android
./gradlew assembleDebug
# APK في: android/app/build/outputs/apk/debug/
```

## اختبار على الجهاز الحقيقي

### Android
```bash
# تثبيت Expo Go من Play Store
# تشغيل التطبيق
npm start

# مسح QR Code من Expo Go
```

### iOS
```bash
# تثبيت Expo Go من App Store
# تشغيل التطبيق
npm start

# مسح QR Code من Expo Go
```

## API Endpoints المطلوبة

التطبيق يتوقع هذه Endpoints من FastAPI Backend:

```
POST /api/auth/login
GET  /api/dashboard/children
GET  /api/dashboard/children/{childId}/interactions
GET  /api/dashboard/safety/alerts
```

## حل المشاكل الشائعة

### مشكلة الاتصال بـ API
```bash
# تأكد من تشغيل Backend
# تحقق من firewall/antivirus
# استخدم IP الصحيح للجهاز
```

### مشكلة Metro Bundler
```bash
# مسح cache
npm start -- --clear

# إعادة تثبيت
rm -rf node_modules
npm install
```

### مشكلة Android Emulator
```bash
# تأكد من تشغيل emulator أولاً
# استخدم cold boot إذا لزم الأمر
```

## المرحلة التالية

بعد نجاح MVP الحالي:
- 🔄 Push Notifications
- 📊 إحصائيات مفصلة
- ⚙️ إعدادات متقدمة
- 🎨 تصميم محسن
- 🔐 ميزات أمان إضافية

---

## النتائج المطلوبة

- [x] تطبيق يعمل على الهاتف
- [x] شاشة login وظيفية
- [x] شاشة dashboard تعرض البيانات
- [x] ربط حقيقي مع FastAPI
- [ ] فيديو/صور من الهاتف الحقيقي
- [ ] APK جاهز للتثبيت
