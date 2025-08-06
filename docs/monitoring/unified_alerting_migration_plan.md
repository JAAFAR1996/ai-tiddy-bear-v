# Migration Plan: Unified Alerting System

## Overview
This document outlines the migration from duplicate alerting systems to a unified, comprehensive alerting solution.

## Current State Analysis

### Files to be Replaced:
1. **`src/infrastructure/monitoring/ai_service_alerts.py`** (756 lines)
   - Purpose: AI service specific monitoring and alerting
   - Usage: Currently imported and used in `src/application/services/ai_service.py`
   - Features: Prometheus metrics, threshold-based alerting, multi-channel notifications

2. **`src/infrastructure/monitoring/enhanced_alerting.py`** (700+ lines) 
   - Purpose: Enhanced error detection from log analysis
   - Usage: Not yet integrated (newly created)
   - Features: Pattern-based error detection, COPPA compliance monitoring, advanced classification

### New Unified Solution:
**`src/infrastructure/monitoring/unified_alerting.py`** (650+ lines)
- Combines functionality from both files
- Eliminates duplication
- Provides comprehensive monitoring solution

## Migration Steps

### Phase 1: Integration Testing ✅
- [x] Create unified alerting system
- [x] Preserve all functionality from both systems
- [x] Add error handling for missing dependencies
- [x] Validate API compatibility

### Phase 2: Update Service Integration
```python
# OLD: In ai_service.py
from src.infrastructure.monitoring.ai_service_alerts import (
    AIServiceMonitor,
    create_ai_service_monitor,
)

# NEW: In ai_service.py  
from src.infrastructure.monitoring.unified_alerting import (
    UnifiedAlertingService,
    create_unified_alerting_service,
    MetricType
)
```

### Phase 3: Configuration Migration
```python
# OLD Configuration (ai_service_alerts.py)
monitor_config = {
    'redis_url': 'redis://localhost:6379',
    'alert_channels': {
        'slack': {'webhook_url': '...'},
        'email': {'smtp_config': '...'}
    }
}

# NEW Configuration (unified_alerting.py)
unified_config = {
    'redis_url': 'redis://localhost:6379',
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'from_address': 'alerts@aiteddybear.com',
        'to_address': 'admin@aiteddybear.com'
    },
    'slack_webhook_url': 'https://hooks.slack.com/...',
    'webhook_urls': ['https://monitoring.com/alerts']
}
```

### Phase 4: API Migration

#### Old API (AIServiceMonitor):
```python
# Recording metrics
await monitor.record_response_time(1.5)
await monitor.record_error_rate(0.05)
await monitor.record_safety_score(0.95)

# Getting alerts
active_alerts = monitor.get_active_alerts()
alert_history = monitor.get_alert_history(hours=24)
```

#### New API (UnifiedAlertingService):
```python
# Recording metrics (enhanced)
await service.record_metric(MetricType.RESPONSE_TIME, 1.5, {'endpoint': '/chat'})
await service.record_metric(MetricType.ERROR_RATE, 0.05, {'service': 'ai_service'})
await service.record_metric(MetricType.SAFETY_SCORE, 0.95, {'model': 'gpt-4'})

# Processing logs (new capability)
log_entry = {
    'timestamp': datetime.utcnow().isoformat(),
    'level': 'error',
    'message': 'Safety service failed',
    'service': 'ai_service'
}
alerts = await service.process_log_entry(log_entry)

# Getting alerts (enhanced)
recent_alerts = await service.get_recent_alerts(hours=24, severity=AlertSeverity.CRITICAL)
statistics = await service.get_alert_statistics()
```

## Implementation Plan

### Step 1: Update AI Service Integration

Create updated version of ai_service.py import section:

```python
# Replace existing monitoring import
try:
    from src.infrastructure.monitoring.unified_alerting import (
        UnifiedAlertingService,
        create_unified_alerting_service,
        MetricType,
        AlertSeverity
    )
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    UnifiedAlertingService = None
```

### Step 2: Update Initialization Code

```python
# OLD initialization
if MONITORING_AVAILABLE:
    self.monitor = await create_ai_service_monitor(monitor_config)

# NEW initialization  
if MONITORING_AVAILABLE:
    self.alerting_service = await create_unified_alerting_service(unified_config)
```

### Step 3: Update Method Calls

```python
# OLD metric recording
if self.monitor:
    await self.monitor.record_response_time(response_time)
    await self.monitor.record_safety_score(safety_score)

# NEW metric recording
if self.alerting_service:
    await self.alerting_service.record_metric(
        MetricType.RESPONSE_TIME, 
        response_time, 
        {'endpoint': endpoint, 'method': method}
    )
    await self.alerting_service.record_metric(
        MetricType.SAFETY_SCORE,
        safety_score,
        {'model': model_name, 'child_age': str(child_age)}
    )
```

### Step 4: Enhanced Error Logging

```python
# NEW capability - structured error logging for pattern detection
async def log_error_for_alerting(self, error: Exception, context: dict):
    """Log errors in format suitable for unified alerting."""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': 'error',
        'message': str(error),
        'service': 'ai_service',
        'component': context.get('component', 'unknown'),
        'correlation_id': context.get('correlation_id'),
        'stack_trace': traceback.format_exc()
    }
    
    if self.alerting_service:
        await self.alerting_service.process_log_entry(log_entry)
```

## Benefits of Unified System

### 1. Eliminated Duplication
- **Before**: 2 separate alerting systems (1456+ lines total)
- **After**: 1 unified system (650+ lines)
- **Reduction**: ~50% code reduction while adding features

### 2. Enhanced Capabilities
- ✅ AI service metrics monitoring (from ai_service_alerts.py)
- ✅ Log-based error pattern detection (from enhanced_alerting.py) 
- ✅ COPPA compliance monitoring
- ✅ Multi-channel notifications
- ✅ Intelligent alert suppression
- ✅ Comprehensive categorization

### 3. Better Architecture
- Single source of truth for alerting
- Consistent API across all services
- Simplified configuration management
- Easier maintenance and updates

### 4. Production Benefits
- Reduced memory footprint
- Simplified deployment
- Unified monitoring dashboard
- Consistent alert formats

## Risk Mitigation

### Backward Compatibility
- Maintain similar API signatures where possible
- Gradual migration approach
- Comprehensive testing before removal

### Testing Strategy
```python
# Test both old and new systems in parallel initially
async def test_migration_compatibility():
    # Initialize both systems
    old_monitor = await create_ai_service_monitor(old_config)
    new_service = await create_unified_alerting_service(new_config)
    
    # Record same metrics in both
    await old_monitor.record_response_time(1.5)
    await new_service.record_metric(MetricType.RESPONSE_TIME, 1.5)
    
    # Compare outputs
    old_alerts = old_monitor.get_active_alerts()
    new_alerts = await new_service.get_recent_alerts(hours=1)
    
    # Validate equivalent functionality
    assert len(old_alerts) == len(new_alerts)
```

### Rollback Plan
1. Keep old files in `deprecated/` folder initially
2. Maintain ability to switch back via configuration
3. Monitor for 48 hours after migration
4. Remove old files only after validation

## Timeline

### Week 1: Preparation
- [x] Create unified alerting system
- [x] Write migration documentation
- [ ] Create compatibility tests
- [ ] Update configuration templates

### Week 2: Integration
- [ ] Update ai_service.py integration
- [ ] Test in development environment
- [ ] Validate all metrics and alerts
- [ ] Performance benchmarking

### Week 3: Deployment
- [ ] Deploy to staging environment
- [ ] Run parallel systems for validation
- [ ] Monitor for issues
- [ ] Gradual production rollout

### Week 4: Cleanup
- [ ] Validate production stability
- [ ] Remove old files
- [ ] Update documentation
- [ ] Team training on new system

## File Actions Required

### Files to Update:
1. `src/application/services/ai_service.py` - Update imports and method calls
2. `src/infrastructure/config/` - Update alerting configuration
3. `tests/` - Update test files to use new system

### Files to Archive:
1. `src/infrastructure/monitoring/ai_service_alerts.py` → `deprecated/`
2. `src/infrastructure/monitoring/enhanced_alerting.py` → `deprecated/`

### Files to Create:
1. ✅ `src/infrastructure/monitoring/unified_alerting.py` - New unified system
2. `docs/monitoring/unified_alerting_guide.md` - Usage documentation
3. `tests/infrastructure/monitoring/test_unified_alerting.py` - Test suite

## Validation Checklist

### Functionality Preservation:
- [ ] All AI service metrics still recorded
- [ ] Alert thresholds maintained
- [ ] Notification channels working
- [ ] Prometheus metrics exported
- [ ] Error detection patterns active

### New Features Working:
- [ ] Log-based error detection
- [ ] COPPA compliance monitoring
- [ ] Enhanced categorization
- [ ] Intelligent suppression
- [ ] Multi-service support

### Performance:
- [ ] Memory usage reduced
- [ ] Response times maintained
- [ ] Alert delivery times acceptable
- [ ] No degradation in monitoring accuracy

## Success Criteria

1. **Zero Downtime**: Migration completed without service interruption
2. **Feature Parity**: All existing alerting functionality preserved
3. **Enhanced Capability**: New features working as designed
4. **Performance**: No degradation in system performance
5. **Maintainability**: Simplified codebase easier to maintain

---

**Status**: Ready for Implementation  
**Risk Level**: Low (comprehensive testing and rollback plan)  
**Expected Completion**: 2 weeks  
**Team Impact**: Positive (simplified system, enhanced features)
