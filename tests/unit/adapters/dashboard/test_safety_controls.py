"""
Tests for SafetyControls - real safety management functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock

from src.adapters.dashboard.safety_controls import (
    SafetyControls,
    SafetyControlsError
)


class TestSafetyControls:
    @pytest.fixture
    def mock_safety_service(self):
        service = Mock()
        service.get_safety_overview = AsyncMock()
        service.update_safety_setting = AsyncMock()
        return service

    @pytest.fixture
    def mock_auth_service(self):
        service = Mock()
        service.is_parent_of_child = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def safety_controls(self, mock_safety_service, mock_auth_service):
        return SafetyControls(mock_safety_service, mock_auth_service)

    def test_valid_settings_constant(self, safety_controls):
        expected_settings = {
            'content_filter_level', 'time_limits', 'blocked_categories',
            'allowed_contacts', 'location_sharing', 'screen_time_limit'
        }
        assert safety_controls.VALID_SETTINGS == expected_settings

    def test_validate_uuid_valid(self, safety_controls):
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = safety_controls._validate_uuid(valid_uuid, "test_id")
        assert result == valid_uuid

    def test_validate_uuid_invalid_format(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_uuid("invalid-uuid", "test_id")
        assert "valid UUID" in str(exc.value)

    def test_validate_uuid_empty(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_uuid("", "test_id")
        assert "non-empty string" in str(exc.value)

    def test_validate_uuid_none(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_uuid(None, "test_id")
        assert "non-empty string" in str(exc.value)

    def test_validate_setting_valid_content_filter(self, safety_controls):
        # Should not raise exception
        safety_controls._validate_setting('content_filter_level', 'high')
        safety_controls._validate_setting('content_filter_level', 'strict')

    def test_validate_setting_invalid_content_filter(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('content_filter_level', 'invalid')
        assert "Invalid value" in str(exc.value)

    def test_validate_setting_valid_time_limits(self, safety_controls):
        valid_time_limits = {
            'weekday': 60,
            'weekend': 120,
            'bedtime': 480
        }
        # Should not raise exception
        safety_controls._validate_setting('time_limits', valid_time_limits)

    def test_validate_setting_invalid_time_limits_not_dict(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('time_limits', "not a dict")
        assert "Invalid value" in str(exc.value)

    def test_validate_setting_invalid_time_limits_negative(self, safety_controls):
        invalid_time_limits = {'weekday': -30}  # Negative time
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('time_limits', invalid_time_limits)
        assert "Invalid value" in str(exc.value)

    def test_validate_setting_invalid_time_limits_too_high(self, safety_controls):
        invalid_time_limits = {'weekday': 1500}  # More than 24 hours
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('time_limits', invalid_time_limits)
        assert "Invalid value" in str(exc.value)

    def test_validate_setting_valid_blocked_categories(self, safety_controls):
        valid_categories = ['violence', 'adult_content', 'gambling']
        # Should not raise exception
        safety_controls._validate_setting('blocked_categories', valid_categories)

    def test_validate_setting_invalid_blocked_categories(self, safety_controls):
        invalid_categories = ['valid', 123, 'another_valid']  # Contains non-string
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('blocked_categories', invalid_categories)
        assert "Invalid value" in str(exc.value)

    def test_validate_setting_valid_screen_time_limit(self, safety_controls):
        # Should not raise exception
        safety_controls._validate_setting('screen_time_limit', 120)
        safety_controls._validate_setting('screen_time_limit', 0)
        safety_controls._validate_setting('screen_time_limit', 1440)

    def test_validate_setting_invalid_screen_time_limit(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('screen_time_limit', -30)
        assert "Invalid value" in str(exc.value)

        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('screen_time_limit', 1500)
        assert "Invalid value" in str(exc.value)

    def test_validate_setting_unknown_setting(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            safety_controls._validate_setting('unknown_setting', 'value')
        assert "Invalid setting" in str(exc.value)

    def test_validate_setting_no_validator(self, safety_controls):
        # Test setting that exists but has no validator
        # Should not raise exception
        safety_controls._validate_setting('allowed_contacts', ['contact1', 'contact2'])

    @pytest.mark.asyncio
    async def test_check_parent_access_authorized(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        # Should not raise exception
        await safety_controls._check_parent_access(parent_id, child_id)
        
        safety_controls.auth_service.is_parent_of_child.assert_called_once_with(parent_id, child_id)

    @pytest.mark.asyncio
    async def test_check_parent_access_denied(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        safety_controls.auth_service.is_parent_of_child.return_value = False
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls._check_parent_access(parent_id, child_id)
        
        assert "Access denied" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_safety_overview_success(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        expected_overview = {
            "overall_status": "safe",
            "total_violations": 2,
            "content_filter_level": "high"
        }
        
        safety_controls.safety_service.get_safety_overview.return_value = expected_overview
        
        result = await safety_controls.get_safety_overview(parent_id)
        
        assert result == expected_overview
        safety_controls.safety_service.get_safety_overview.assert_called_once_with(parent_id)

    @pytest.mark.asyncio
    async def test_get_safety_overview_invalid_parent_id(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.get_safety_overview("invalid-uuid")
        
        assert "valid UUID" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_safety_overview_service_error(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        safety_controls.safety_service.get_safety_overview.side_effect = Exception("Service error")
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.get_safety_overview(parent_id)
        
        assert "Failed to retrieve safety overview" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_success(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        setting = "content_filter_level"
        value = "strict"
        
        expected_result = {"success": True, "setting": setting, "value": value}
        safety_controls.safety_service.update_safety_setting.return_value = expected_result
        
        result = await safety_controls.update_safety_setting(parent_id, child_id, setting, value)
        
        assert result == expected_result
        safety_controls.safety_service.update_safety_setting.assert_called_once_with(child_id, setting, value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_invalid_parent_id(self, safety_controls):
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.update_safety_setting("invalid-uuid", "child-id", "setting", "value")
        
        assert "valid UUID" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_invalid_child_id(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.update_safety_setting(parent_id, "invalid-uuid", "setting", "value")
        
        assert "valid UUID" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_invalid_setting(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.update_safety_setting(parent_id, child_id, "invalid_setting", "value")
        
        assert "Invalid setting" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_invalid_value(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.update_safety_setting(parent_id, child_id, "content_filter_level", "invalid_level")
        
        assert "Invalid value" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_access_denied(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        safety_controls.auth_service.is_parent_of_child.return_value = False
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.update_safety_setting(parent_id, child_id, "content_filter_level", "high")
        
        assert "Access denied" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_service_error(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        safety_controls.safety_service.update_safety_setting.side_effect = Exception("Service error")
        
        with pytest.raises(SafetyControlsError) as exc:
            await safety_controls.update_safety_setting(parent_id, child_id, "content_filter_level", "high")
        
        assert "Failed to update setting" in str(exc.value)

    @pytest.mark.asyncio
    async def test_update_safety_setting_complex_values(self, safety_controls):
        parent_id = "550e8400-e29b-41d4-a716-446655440000"
        child_id = "550e8400-e29b-41d4-a716-446655440001"
        
        # Test with time limits
        time_limits = {
            'weekday': 90,
            'weekend': 150,
            'bedtime': 540
        }
        
        await safety_controls.update_safety_setting(parent_id, child_id, "time_limits", time_limits)
        
        safety_controls.safety_service.update_safety_setting.assert_called_with(child_id, "time_limits", time_limits)

        # Test with blocked categories
        blocked_categories = ['violence', 'adult_content', 'drugs']
        
        await safety_controls.update_safety_setting(parent_id, child_id, "blocked_categories", blocked_categories)
        
        safety_controls.safety_service.update_safety_setting.assert_called_with(child_id, "blocked_categories", blocked_categories)

    def test_setting_validators_coverage(self, safety_controls):
        """Test that all validators work correctly"""
        validators = safety_controls.SETTING_VALIDATORS
        
        # Test content_filter_level validator
        assert validators['content_filter_level']('low') is True
        assert validators['content_filter_level']('medium') is True
        assert validators['content_filter_level']('high') is True
        assert validators['content_filter_level']('strict') is True
        assert validators['content_filter_level']('invalid') is False
        
        # Test time_limits validator
        assert validators['time_limits']({'weekday': 60, 'weekend': 120}) is True
        assert validators['time_limits']({'weekday': 0}) is True
        assert validators['time_limits']({'weekday': 1440}) is True
        assert validators['time_limits']({'weekday': -1}) is False
        assert validators['time_limits']({'weekday': 1441}) is False
        assert validators['time_limits']("not a dict") is False
        
        # Test blocked_categories validator
        assert validators['blocked_categories'](['cat1', 'cat2']) is True
        assert validators['blocked_categories']([]) is True
        assert validators['blocked_categories'](['cat1', 123]) is False
        assert validators['blocked_categories']("not a list") is False
        
        # Test screen_time_limit validator
        assert validators['screen_time_limit'](60) is True
        assert validators['screen_time_limit'](0) is True
        assert validators['screen_time_limit'](1440) is True
        assert validators['screen_time_limit'](-1) is False
        assert validators['screen_time_limit'](1441) is False
        assert validators['screen_time_limit']("not an int") is False


class TestSafetyControlsError:
    def test_init(self):
        error = SafetyControlsError("Test error message")
        assert str(error) == "Test error message"

    def test_inheritance(self):
        error = SafetyControlsError("Test error")
        assert isinstance(error, Exception)