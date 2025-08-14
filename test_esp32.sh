#!/bin/bash

# AI Teddy Bear - فحص ESP32 endpoints
# ===================================

echo ""
echo "🤖 AI Teddy Bear - فحص ESP32 endpoints"
echo "========================================"
echo ""

# التحقق من وجود Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Python غير مثبت أو غير موجود في PATH"
        echo "يرجى تثبيت Python أولاً"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# التحقق من وجود الملفات المطلوبة
if [ ! -f "esp32_comprehensive_test.py" ]; then
    echo "❌ ملف esp32_comprehensive_test.py غير موجود"
    exit 1
fi

echo "✅ Python متاح ($PYTHON_CMD)"
echo "✅ ملفات الاختبار موجودة"
echo ""

# عرض الخيارات
echo "اختر نوع الفحص:"
echo ""
echo "1. فحص سريع (30 ثانية)"
echo "2. فحص شامل (3 دقائق)"
echo "3. فحص الأداء (5 دقائق)"
echo "4. مراقبة مستمرة (10 دقائق)"
echo "5. تشغيل جميع الاختبارات (15 دقيقة)"
echo "0. خروج"
echo ""

read -p "أدخل اختيارك (0-5): " choice

case $choice in
    0)
        echo "👋 وداعاً!"
        exit 0
        ;;
    1)
        echo "🚀 بدء الفحص السريع..."
        $PYTHON_CMD quick_esp32_check.py
        ;;
    2)
        echo "🚀 بدء الفحص الشامل..."
        $PYTHON_CMD esp32_comprehensive_test.py
        ;;
    3)
        echo "🚀 بدء فحص الأداء..."
        $PYTHON_CMD esp32_performance_test.py
        ;;
    4)
        echo "🚀 بدء المراقبة المستمرة..."
        $PYTHON_CMD esp32_monitor.py --duration 10
        ;;
    5)
        echo "🚀 بدء جميع الاختبارات..."
        $PYTHON_CMD run_esp32_tests.py
        ;;
    *)
        echo "❌ اختيار غير صحيح"
        exit 1
        ;;
esac

echo ""
echo "✅ انتهى الفحص"
echo "📋 تحقق من الملفات المُنشأة للتقارير التفصيلية"
echo ""