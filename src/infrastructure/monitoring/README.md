# Enhanced AI Service Monitoring System

## نظرة عامة / Overview

تم دمج جميع أنظمة المراقبة والتنبيهات في ملف واحد موحد: `ai_service_alerts.py`

This unified system combines all monitoring and alerting functionality into a single file: `ai_service_alerts.py`

## الميزات المدمجة / Integrated Features

### 1. نظام المراقبة الأساسي / Basic Monitoring System
- `AIServiceMonitor`: المراقب الأساسي للخدمة
- `Alert`: هيكل التنبيهات الأساسي
- `MetricThreshold`: عتبات المقاييس
- `AlertChannel`: قنوات التنبيه المختلفة

### 2. نظام المراقبة المحسن / Enhanced Monitoring System
- `EnhancedAIServiceMonitor`: مراقب محسن مع كشف الأخطاء المتقدم
- `EnhancedAlertEvent`: تنبيهات محسنة مع معلومات إضافية
- `ErrorPattern`: أنماط كشف الأخطاء
- `AlertCategory`: فئات التنبيهات الموسعة

## كيفية الاستخدام / Usage

### الاستخدام الأساسي / Basic Usage

```python
from src.infrastructure.monitoring.ai_service_alerts import (
    create_ai_service_monitor,
    MetricType,
    AlertSeverity
)

# إنشاء مراقب أساسي
monitor = create_ai_service_monitor(
    redis_url="redis://localhost:6379",
    slack_webhook_url="https://hooks.slack.com/...",
)

# تسجيل مقياس
await monitor.record_metric(MetricType.RESPONSE_TIME, 150.0)

# إرسال تنبيه
await monitor.send_alert(
    severity=AlertSeverity.WARNING,
    metric_type=MetricType.RESPONSE_TIME,
    message="High response time detected",
    value=150.0,
    threshold=100.0
)
```

### الاستخدام المحسن / Enhanced Usage

```python
from src.infrastructure.monitoring.ai_service_alerts import (
    create_enhanced_ai_service_monitor,
    ErrorPattern,
    AlertSeverity,
    AlertCategory
)

# إنشاء أنماط أخطاء مخصصة
custom_patterns = [
    ErrorPattern(
        name="custom_safety_check",
        pattern="custom.*safety.*failed",
        severity=AlertSeverity.CRITICAL,
        category=AlertCategory.SAFETY,
        threshold_count=1,
        time_window_minutes=1,
        description="Custom safety check failed"
    )
]

# إنشاء مراقب محسن
enhanced_monitor = create_enhanced_ai_service_monitor(
    redis_url="redis://localhost:6379",
    slack_webhook_url="https://hooks.slack.com/...",
    webhook_url="https://your-webhook.com/alerts",
    custom_error_patterns=custom_patterns
)

# معالجة إدخالات السجل
log_entry = {
    "message": "Custom safety check failed for user interaction",
    "timestamp": "2025-08-02T10:30:00Z",
    "service": "ai_service",
    "level": "ERROR"
}

alerts = await enhanced_monitor.process_log_entry(log_entry)
```

## أنماط الأخطاء المحددة مسبقاً / Pre-defined Error Patterns

### أمان الطفل / Child Safety
- `inappropriate_content_detected`: كشف محتوى غير مناسب
- `child_safety_violation`: انتهاك أمان الطفل

### الأداء / Performance  
- `high_response_time`: أوقات استجابة عالية

### الأمان / Security
- `unauthorized_access_attempt`: محاولات وصول غير مصرح بها

### امتثال COPPA / COPPA Compliance
- `coppa_data_violation`: انتهاك بيانات COPPA

### الخدمات الخارجية / External Services
- `openai_api_failure`: فشل OpenAI API

## قنوات التنبيه / Alert Channels

### المتاحة / Available Channels
1. **Slack**: إرسال التنبيهات لـ Slack
2. **Email**: إرسال بريد إلكتروني
3. **PagerDuty**: تكامل مع PagerDuty
4. **Webhook**: إرسال HTTP webhooks

### إعداد قنوات متعددة / Multi-Channel Setup

```python
monitor = create_enhanced_ai_service_monitor(
    slack_webhook_url="https://hooks.slack.com/...",
    email_config={
        "smtp": {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "your-email@gmail.com",
            "password": "app-password"
        },
        "recipients": ["admin@yourcompany.com"]
    },
    pagerduty_key="your-pagerduty-key",
    webhook_url="https://your-system.com/webhooks/alerts"
)
```

## المقاييس المدعومة / Supported Metrics

- `RESPONSE_TIME`: وقت الاستجابة
- `ERROR_RATE`: معدل الأخطاء  
- `THROUGHPUT`: معدل النقل
- `SAFETY_SCORE`: نتيجة الأمان
- `RATE_LIMIT_VIOLATIONS`: انتهاكات حد المعدل
- `REDIS_PERFORMANCE`: أداء Redis
- `CONCURRENT_REQUESTS`: الطلبات المتزامنة

## الترحيل من الملفات السابقة / Migration from Previous Files

إذا كنت تستخدم `enhanced_alerting.py` أو `unified_alerting.py` سابقاً:

```python
# القديم / Old
from src.infrastructure.monitoring.enhanced_alerting import EnhancedAlertingService

# الجديد / New  
from src.infrastructure.monitoring.ai_service_alerts import EnhancedAIServiceMonitor
```

## الاختبار / Testing

```python
import pytest
from src.infrastructure.monitoring.ai_service_alerts import ErrorPattern, AlertSeverity, AlertCategory

def test_error_pattern_detection():
    pattern = ErrorPattern(
        name="test_pattern",
        pattern="test.*error",
        severity=AlertSeverity.WARNING,
        category=AlertCategory.PERFORMANCE,
        threshold_count=1
    )
    
    assert pattern.matches_message("Test error occurred")
    assert not pattern.matches_message("No issues here")
```

## أفضل الممارسات / Best Practices

1. **استخدم المراقب المحسن للبيئات الإنتاجية** / Use enhanced monitor for production
2. **قم بتخصيص أنماط الأخطاء حسب احتياجاتك** / Customize error patterns for your needs
3. **اختبر قنوات التنبيه قبل النشر** / Test alert channels before deployment
4. **راقب استهلاك الذاكرة للمراقبين** / Monitor memory usage of monitors
5. **نظف البيانات التاريخية بانتظام** / Clean up historical data regularly

## الدعم / Support

للمساعدة أو الإبلاغ عن مشاكل، يرجى مراجعة:
- التوثيق الكامل في `docs/`
- ملفات الاختبار في `tests_consolidated/`
- أمثلة الاستخدام في `examples/`
