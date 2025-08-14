@echo off
chcp 65001 >nul
echo.
echo 🤖 AI Teddy Bear - فحص ESP32 endpoints
echo ========================================
echo.

REM التحقق من وجود Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت أو غير موجود في PATH
    echo يرجى تثبيت Python أولاً
    pause
    exit /b 1
)

REM التحقق من وجود الملفات المطلوبة
if not exist "esp32_comprehensive_test.py" (
    echo ❌ ملف esp32_comprehensive_test.py غير موجود
    pause
    exit /b 1
)

echo ✅ Python متاح
echo ✅ ملفات الاختبار موجودة
echo.

REM عرض الخيارات
echo اختر نوع الفحص:
echo.
echo 1. فحص سريع (30 ثانية)
echo 2. فحص شامل (3 دقائق)
echo 3. فحص الأداء (5 دقائق)
echo 4. مراقبة مستمرة (10 دقائق)
echo 5. تشغيل جميع الاختبارات (15 دقيقة)
echo 0. خروج
echo.

set /p choice="أدخل اختيارك (0-5): "

if "%choice%"=="0" (
    echo 👋 وداعاً!
    exit /b 0
)

if "%choice%"=="1" (
    echo 🚀 بدء الفحص السريع...
    python quick_esp32_check.py
    goto :end
)

if "%choice%"=="2" (
    echo 🚀 بدء الفحص الشامل...
    python esp32_comprehensive_test.py
    goto :end
)

if "%choice%"=="3" (
    echo 🚀 بدء فحص الأداء...
    python esp32_performance_test.py
    goto :end
)

if "%choice%"=="4" (
    echo 🚀 بدء المراقبة المستمرة...
    python esp32_monitor.py --duration 10
    goto :end
)

if "%choice%"=="5" (
    echo 🚀 بدء جميع الاختبارات...
    python run_esp32_tests.py
    goto :end
)

echo ❌ اختيار غير صحيح
goto :end

:end
echo.
echo ✅ انتهى الفحص
echo 📋 تحقق من الملفات المُنشأة للتقارير التفصيلية
echo.
pause