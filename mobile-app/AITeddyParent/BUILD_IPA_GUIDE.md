# 📱 دليل إنشاء ملف IPA للايفون

## 🚀 **الطريقة الأولى: EAS Build (موصى بها)**

### المتطلبات:
1. **حساب Expo**: مجاني على [expo.dev](https://expo.dev)
2. **Apple Developer Account**: مطلوب للتوقيع ($99/سنة)
3. **EAS CLI**: أداة البناء

### خطوات التنصيب:

#### 1. تنصيب EAS CLI
```bash
npm install -g @expo/eas-cli
```

#### 2. تسجيل الدخول لـ Expo
```bash
eas login
```

#### 3. إعداد المشروع
```bash
cd "/mnt/c/Users/jaafa/Desktop/ai teddy bear/mobile-app/AITeddyParent"
eas build:configure
```

#### 4. بناء IPA للاختبار (بدون App Store)
```bash
# للاختبار الداخلي (لا يحتاج Apple Developer Account)
eas build --platform ios --profile preview

# للإنتاج (يحتاج Apple Developer Account)
eas build --platform ios --profile production
```

### ⏱️ **وقت البناء المتوقع**: 10-15 دقيقة

---

## 🔧 **الطريقة الثانية: Expo Build (كلاسيكية)**

### الخطوات:
```bash
# تنصيب Expo CLI
npm install -g expo-cli

# تسجيل الدخول
expo login

# بناء IPA
expo build:ios
```

### ⚠️ **ملاحظة**: Expo Build الكلاسيكية ستتوقف قريباً، استخدم EAS Build

---

## 🏠 **الطريقة الثالثة: البناء المحلي (متقدم)**

### المتطلبات:
- **macOS** مع Xcode
- **Apple Developer Account**

### الخطوات:
```bash
# إنشاء مشروع iOS محلي
expo eject

# فتح في Xcode
cd ios
open AITeddyParent.xcworkspace

# البناء من Xcode:
# 1. اختر Target Device
# 2. Product → Archive
# 3. Export IPA
```

---

## 📋 **الخطوات التفصيلية لـ EAS Build**

### 1. إعداد بيانات التطبيق

قم بتحديث `app.config.js`:
```javascript
export default {
  expo: {
    name: "AI Teddy Parent",
    slug: "ai-teddy-parent",
    version: "1.0.0",
    ios: {
      bundleIdentifier: "com.aiteddybear.parent",
      buildNumber: "1"
    },
    // باقي الإعدادات...
  }
}
```

### 2. تشغيل البناء
```bash
# للاختبار (مجاني)
eas build --platform ios --profile preview

# للإنتاج (يحتاج Apple Developer)
eas build --platform ios --profile production
```

### 3. تحميل الملف
- ستحصل على رابط تحميل IPA
- يمكنك تنصيبه عبر **TestFlight** أو **AltStore**

---

## 📱 **طرق تنصيب IPA على الايفون**

### الطريقة الأولى: TestFlight (الأفضل)
1. ارفع IPA على **App Store Connect**
2. أضف المختبرين في **TestFlight**
3. المختبرين يحملون من TestFlight

### الطريقة الثانية: AltStore (بدون جيلبريك)
1. حمل **AltStore** على الايفون
2. اربط الايفون بالكمبيوتر
3. انصب IPA عبر AltStore

### الطريقة الثالثة: Sideloadly
1. حمل **Sideloadly** على الكمبيوتر
2. اربط الايفون
3. اسحب IPA إلى Sideloadly

### الطريقة الرابعة: Xcode (للمطورين)
```bash
# تنصيب عبر Xcode
xcrun devicectl device install app --device [DEVICE-ID] AITeddyParent.ipa
```

---

## 🛠️ **إصلاح المشاكل الشائعة**

### مشكلة: "Failed to build iOS app"
**الحل**:
```bash
# تنظيف cache
expo r -c
npm install
eas build --platform ios --clear-cache
```

### مشكلة: "Invalid bundle identifier"
**الحل**: تأكد من أن Bundle ID فريد ومتاح

### مشكلة: "Provisioning profile expired"
**الحل**: 
1. ادخل على **Apple Developer Console**
2. حدث **Provisioning Profiles**
3. أعد البناء

---

## ⚡ **البناء السريع (5 دقائق)**

إذا كنت تريد اختبار سريع بدون Apple Developer Account:

```bash
# 1. تنصيب EAS
npm install -g @expo/eas-cli

# 2. تسجيل دخول
eas login

# 3. بناء للمحاكي (مجاني)
eas build --platform ios --profile development

# 4. تحميل على المحاكي
npx expo run:ios
```

---

## 💡 **نصائح مهمة**

### للاختبار السريع:
- استخدم **preview profile** (مجاني)
- لا يحتاج Apple Developer Account

### للإنتاج:
- احتاج **Apple Developer Account** ($99/سنة)
- استخدم **production profile**

### للتوزيع:
- **TestFlight**: للاختبار المحدود
- **App Store**: للتوزيع العام

---

## 📞 **الدعم والمساعدة**

### إذا واجهت مشاكل:
1. **Expo Discord**: مجتمع نشط
2. **Expo Docs**: [docs.expo.dev](https://docs.expo.dev)
3. **Stack Overflow**: للمشاكل التقنية

### الأوامر المفيدة:
```bash
# عرض تقدم البناء
eas build:list

# إلغاء البناء
eas build:cancel [BUILD-ID]

# عرض logs مفصلة
eas build:view [BUILD-ID]
```

---

## 🎯 **الخلاصة**

**للاختبار السريع**:
```bash
eas build --platform ios --profile preview
```

**للإنتاج**:
```bash
eas build --platform ios --profile production
```

**الوقت المتوقع**: 10-15 دقيقة للبناء + 5 دقائق للتحميل

**التكلفة**: 
- اختبار: مجاني
- إنتاج: $99/سنة (Apple Developer)

🚀 **ابدأ الآن بالأمر الأول وستحصل على IPA خلال 15 دقيقة!**