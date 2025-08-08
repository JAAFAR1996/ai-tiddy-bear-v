# Test Migration Guide: From Mocks to Production Integration Tests

## Overview

This guide helps migrate from mock-based tests to production-ready integration tests for the AI Teddy Bear application.

## Problem with Mock Tests

Mock tests were found throughout the codebase (127+ files), creating several issues:
- **False confidence**: Tests pass but real code might fail
- **Maintenance burden**: Mocks must be kept in sync with real implementations  
- **No integration coverage**: Mocks don't test actual service interactions
- **Production gaps**: Issues only surface in production, not during testing

## New Testing Strategy

### Production Integration Tests
- **Real services**: Use actual database, safety service, conversation service
- **Real data flow**: Test complete workflows end-to-end
- **Actual persistence**: Verify data is correctly stored and retrieved
- **True validation**: Catch issues before production deployment

### Test Structure

```
tests/
├── conftest_production.py          # Production fixtures (NO MOCKS)
├── integration/                    # Production integration tests
│   ├── test_production_child_safety.py
│   ├── test_production_conversation_service.py  
│   ├── test_production_audio_pipeline.py
│   ├── test_production_complete_system.py
│   └── test_production_database_operations.py
├── conftest.py                     # Legacy mock fixtures (DEPRECATED)
└── unit/                          # Legacy mock tests (TO BE MIGRATED)
```

## Migration Process

### 1. Identify Critical Mock Tests

Priority order for migration:
1. **Child Safety Service** - Critical for compliance
2. **Conversation Service** - Core functionality  
3. **Database Operations** - Data integrity
4. **Audio Pipeline** - ESP32 integration
5. **Authentication/Authorization** - Security

### 2. Convert Mock to Integration Test

#### Before (Mock-based):
```python
@pytest.fixture
def mock_child_safety_service():
    service = Mock(spec=ChildSafetyService)
    service.validate_content = AsyncMock(
        return_value={"is_safe": True, "confidence": 0.95}
    )
    return service

def test_safety_validation(mock_child_safety_service):
    # Test with mock - doesn't validate real safety logic
    result = await mock_child_safety_service.validate_content("test")
    assert result["is_safe"] is True
```

#### After (Production Integration):
```python
@pytest.mark.asyncio
async def test_real_safety_validation(
    child_safety_service: ChildSafetyService,
    test_child
):
    # Test with real service - validates actual safety logic
    safety_result = await child_safety_service.monitor_conversation_real_time(
        conversation_id=str(uuid4()),
        child_id=test_child.id,
        message_content="I want to hurt someone with a knife",
        child_age=test_child.age
    )
    
    assert safety_result["is_safe"] is False
    assert safety_result["risk_score"] > 0.7
    assert len(safety_result["detected_issues"]) > 0
```

### 3. Use Production Fixtures

#### Production Database Session:
```python
@pytest.fixture
async def db_session(database_manager: DatabaseManager):
    async with database_manager.get_session() as session:
        yield session
```

#### Real Service Instances:
```python  
@pytest.fixture
async def child_safety_service(db_session: AsyncSession):
    return ChildSafetyService()  # Real service, not mock
```

### 4. Test Real Data Flow

#### Test Complete Workflows:
```python
@pytest.mark.asyncio
async def test_complete_safety_workflow(
    child_safety_service,
    conversation_service,
    test_child,
    db_session
):
    # 1. Process unsafe content
    safety_result = await child_safety_service.monitor_conversation_real_time(...)
    
    # 2. Verify conversation is blocked
    assert safety_result["is_safe"] is False
    
    # 3. Check database persistence
    safety_reports = await db_session.execute(...)
    assert len(safety_reports) > 0
    
    # 4. Verify notifications were triggered
    # ... test real notification flow
```

## Migration Checklist

### For Each Test File:

- [ ] **Identify mock dependencies** - List all `Mock`, `AsyncMock`, `MagicMock` usage
- [ ] **Map to real services** - Identify which real services should replace mocks
- [ ] **Update fixtures** - Switch from `conftest.py` to `conftest_production.py`
- [ ] **Rewrite test logic** - Test actual behavior, not mock returns
- [ ] **Add database verification** - Verify data persistence where applicable
- [ ] **Test error scenarios** - Use real error conditions, not mock exceptions
- [ ] **Add performance validation** - Ensure acceptable response times
- [ ] **Verify cleanup** - Ensure test data is properly cleaned up

### Test Categories:

#### ✅ **Completed**
- [x] Child Safety Service Integration Tests
- [x] Conversation Service Integration Tests  
- [x] Database Operations Integration Tests
- [x] Audio Pipeline Integration Tests
- [x] Complete System End-to-End Tests

#### 🔄 **In Progress**
- [ ] Authentication/Authorization Tests
- [ ] API Endpoint Tests
- [ ] WebSocket/Real-time Tests
- [ ] Performance/Load Tests

#### ⏳ **Pending**
- [ ] Error Handling Tests
- [ ] Security Tests
- [ ] COPPA Compliance Tests
- [ ] Monitoring/Metrics Tests

## Benefits of Migration

### 1. **Real Issue Detection**
- Catch database constraint violations
- Identify service integration problems
- Discover performance bottlenecks
- Find configuration issues

### 2. **Production Confidence**
- Tests validate actual production code paths
- Database schema changes are tested
- Service dependencies are verified
- Real error scenarios are covered

### 3. **Reduced Maintenance**
- No need to maintain mock interfaces
- Tests automatically update with service changes
- Fewer false positives from stale mocks
- Clear production readiness validation

### 4. **Better Debugging**
- Test failures indicate real issues
- Stack traces from actual code
- Database state inspection possible
- End-to-end workflow validation

## Running Production Tests

### Environment Setup:
```bash
# Set test database
export DATABASE_URL="sqlite+aiosqlite:///test_production.db"

# Optional: Skip tests requiring external APIs
export OFFLINE_TESTING="true"

# Optional: Provide real API keys for full integration
export OPENAI_API_KEY="your-key-here"
export ELEVENLABS_API_KEY="your-key-here"
```

### Run Production Integration Tests:
```bash
# Run all production tests
pytest tests/integration/ -v

# Run specific test category
pytest tests/integration/test_production_child_safety.py -v

# Run with coverage
pytest tests/integration/ --cov=src --cov-report=html
```

### Performance Testing:
```bash
# Run performance tests
pytest tests/integration/ -k "performance" -v

# Run load tests  
pytest tests/integration/ -k "load" -v
```

## Common Migration Patterns

### 1. **Service Method Testing**
```python
# Before: Mock return values
mock_service.method.return_value = expected_result

# After: Test actual service behavior
actual_result = await real_service.method(input_data)
assert actual_result == expected_result
```

### 2. **Database Testing**
```python
# Before: Mock repository
mock_repo.create.return_value = mock_entity

# After: Test real database operations
entity = await db_session.add(real_entity)
await db_session.commit()
assert entity.id is not None
```

### 3. **Error Handling**
```python
# Before: Mock exceptions
mock_service.method.side_effect = SomeException("error")

# After: Test real error conditions
with pytest.raises(SomeException):
    await real_service.method(invalid_input)
```

### 4. **Integration Testing**
```python
# Before: Test services in isolation with mocks
mock_a.method.return_value = data
mock_b.process.return_value = result

# After: Test services working together
result = await service_a.method(input)
final_result = await service_b.process(result)
assert final_result.is_valid
```

## Success Metrics

Track migration success with these metrics:

1. **Test Coverage**: Real code coverage vs mock coverage
2. **Issue Detection**: Bugs found in integration vs unit tests  
3. **Production Stability**: Reduced production issues after deployment
4. **Development Velocity**: Faster debugging and issue resolution
5. **Maintenance Effort**: Reduced time spent maintaining test mocks

## Next Steps

1. **Complete high-priority migrations** (Child Safety, Conversation Service)
2. **Establish CI/CD integration** for production tests
3. **Create performance benchmarks** for critical workflows  
4. **Document production test standards** for new features
5. **Phase out legacy mock tests** gradually

---

**Remember**: The goal is not to eliminate all mocks, but to ensure critical business logic and integrations are tested with real implementations for production confidence.