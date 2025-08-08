"""
Tests for SafetyMonitor - real safety monitoring functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime

from src.application.services.safety_monitor import SafetyMonitor
from src.core.models import RiskLevel


class TestSafetyMonitor:
    @pytest.fixture
    def mock_content_validator(self):
        validator = Mock()
        validator.validate_content = AsyncMock()
        return validator

    @pytest.fixture
    def mock_age_filter(self):
        filter = Mock()
        filter.is_age_appropriate = AsyncMock()
        return filter

    @pytest.fixture
    def safety_monitor(self, mock_content_validator, mock_age_filter):
        return SafetyMonitor(mock_content_validator, mock_age_filter)

    @pytest.mark.asyncio
    async def test_check_content_safe(self, safety_monitor, mock_content_validator):
        """Test content safety check with safe content."""
        content = "Tell me a story about friendly animals"
        risk_level = RiskLevel.SAFE
        
        mock_content_validator.validate_content.return_value = {
            "is_safe": True,
            "risk_level": RiskLevel.SAFE,
            "confidence": 0.95,
            "violations": []
        }
        
        result = await safety_monitor.check_content(content, risk_level)
        
        assert result.is_safe is True
        assert result.risk_level == RiskLevel.SAFE
        assert result.confidence == 0.95
        assert result.violations == []
        mock_content_validator.validate_content.assert_called_once_with(content, risk_level)

    @pytest.mark.asyncio
    async def test_check_content_unsafe(self, safety_monitor, mock_content_validator):
        """Test content safety check with unsafe content."""
        content = "violent content here"
        risk_level = RiskLevel.SAFE
        
        mock_content_validator.validate_content.return_value = {
            "is_safe": False,
            "risk_level": RiskLevel.HIGH,
            "confidence": 0.9,
            "violations": ["violence", "inappropriate_content"],
            "reason": "Content contains violent themes"
        }
        
        result = await safety_monitor.check_content(content, risk_level)
        
        assert result.is_safe is False
        assert result.risk_level == RiskLevel.HIGH
        assert result.confidence == 0.9
        assert "violence" in result.violations
        assert result.reason == "Content contains violent themes"

    @pytest.mark.asyncio
    async def test_check_age_appropriateness_appropriate(self, safety_monitor, mock_age_filter):
        """Test age appropriateness check with appropriate content."""
        content = "Let's learn about colors and shapes"
        child_age = 5
        
        mock_age_filter.is_age_appropriate.return_value = {
            "is_appropriate": True,
            "recommended_age_range": "3-7",
            "complexity_score": 0.3
        }
        
        result = await safety_monitor.check_age_appropriateness(content, child_age)
        
        assert result.is_appropriate is True
        assert result.recommended_age_range == "3-7"
        assert result.complexity_score == 0.3
        mock_age_filter.is_age_appropriate.assert_called_once_with(content, child_age)

    @pytest.mark.asyncio
    async def test_check_age_appropriateness_inappropriate(self, safety_monitor, mock_age_filter):
        """Test age appropriateness check with inappropriate content."""
        content = "Complex quantum physics concepts"
        child_age = 5
        
        mock_age_filter.is_age_appropriate.return_value = {
            "is_appropriate": False,
            "recommended_age_range": "12+",
            "complexity_score": 0.9,
            "reason": "Content too complex for age group"
        }
        
        result = await safety_monitor.check_age_appropriateness(content, child_age)
        
        assert result.is_appropriate is False
        assert result.recommended_age_range == "12+"
        assert result.complexity_score == 0.9
        assert result.reason == "Content too complex for age group"

    @pytest.mark.asyncio
    async def test_monitor_conversation_safe(self, safety_monitor, mock_content_validator, mock_age_filter):
        """Test monitoring entire conversation with safe content."""
        conversation = [
            {"role": "user", "content": "Hi teddy!"},
            {"role": "assistant", "content": "Hello! How are you today?"},
            {"role": "user", "content": "I want to hear a story"}
        ]
        child_id = uuid4()
        child_age = 7
        
        # Mock all content as safe
        mock_content_validator.validate_content.return_value = {
            "is_safe": True,
            "risk_level": RiskLevel.SAFE,
            "confidence": 0.95,
            "violations": []
        }
        
        mock_age_filter.is_age_appropriate.return_value = {
            "is_appropriate": True,
            "recommended_age_range": "5-9",
            "complexity_score": 0.4
        }
        
        result = await safety_monitor.monitor_conversation(conversation, child_id, child_age)
        
        assert result.overall_safety == RiskLevel.SAFE
        assert result.is_conversation_safe is True
        assert len(result.message_results) == 3
        assert all(msg.is_safe for msg in result.message_results)

    @pytest.mark.asyncio
    async def test_monitor_conversation_unsafe_message(self, safety_monitor, mock_content_validator, mock_age_filter):
        """Test monitoring conversation with one unsafe message."""
        conversation = [
            {"role": "user", "content": "Hi teddy!"},
            {"role": "user", "content": "Tell me about violence"}  # Unsafe
        ]
        child_id = uuid4()
        child_age = 7
        
        # First message safe, second unsafe
        mock_content_validator.validate_content.side_effect = [
            {
                "is_safe": True,
                "risk_level": RiskLevel.SAFE,
                "confidence": 0.95,
                "violations": []
            },
            {
                "is_safe": False,
                "risk_level": RiskLevel.HIGH,
                "confidence": 0.9,
                "violations": ["violence"],
                "reason": "Violent content detected"
            }
        ]
        
        mock_age_filter.is_age_appropriate.return_value = {
            "is_appropriate": True,
            "recommended_age_range": "5-9",
            "complexity_score": 0.4
        }
        
        result = await safety_monitor.monitor_conversation(conversation, child_id, child_age)
        
        assert result.overall_safety == RiskLevel.HIGH
        assert result.is_conversation_safe is False
        assert len(result.unsafe_messages) == 1
        assert result.unsafe_messages[0].content == "Tell me about violence"

    @pytest.mark.asyncio
    async def test_log_safety_incident(self, safety_monitor):
        """Test logging safety incidents."""
        incident_data = {
            "child_id": str(uuid4()),
            "content": "unsafe content",
            "violation_type": "violence",
            "severity": "high",
            "timestamp": datetime.now()
        }
        
        with patch.object(safety_monitor, '_store_incident') as mock_store:
            await safety_monitor.log_safety_incident(incident_data)
            
            mock_store.assert_called_once_with(incident_data)

    @pytest.mark.asyncio
    async def test_get_safety_report_for_child(self, safety_monitor):
        """Test getting safety report for specific child."""
        child_id = uuid4()
        
        with patch.object(safety_monitor, '_fetch_child_incidents') as mock_fetch:
            mock_incidents = [
                {"type": "mild_language", "timestamp": datetime.now()},
                {"type": "inappropriate_topic", "timestamp": datetime.now()}
            ]
            mock_fetch.return_value = mock_incidents
            
            result = await safety_monitor.get_safety_report(child_id)
            
            assert result.child_id == str(child_id)
            assert result.total_incidents == 2
            assert len(result.incidents) == 2
            assert result.safety_score < 1.0  # Should be reduced due to incidents

    @pytest.mark.asyncio
    async def test_update_safety_rules(self, safety_monitor):
        """Test updating safety rules."""
        new_rules = {
            "blocked_words": ["bad_word1", "bad_word2"],
            "age_restrictions": {"violence": 13, "complex_topics": 10},
            "content_filters": {"strict_mode": True}
        }
        
        result = await safety_monitor.update_safety_rules(new_rules)
        
        assert result is True
        assert safety_monitor.safety_rules == new_rules

    @pytest.mark.asyncio
    async def test_check_personal_info_detection(self, safety_monitor):
        """Test detection of personal information."""
        content_with_info = "My name is John and I live at 123 Main Street"
        
        result = await safety_monitor._check_personal_info(content_with_info)
        
        assert result.contains_personal_info is True
        assert "name" in result.detected_types
        assert "address" in result.detected_types

    @pytest.mark.asyncio
    async def test_check_personal_info_safe(self, safety_monitor):
        """Test content without personal information."""
        safe_content = "I like playing with toys and reading books"
        
        result = await safety_monitor._check_personal_info(safe_content)
        
        assert result.contains_personal_info is False
        assert result.detected_types == []

    @pytest.mark.asyncio
    async def test_emergency_shutdown_trigger(self, safety_monitor):
        """Test emergency shutdown when critical violation detected."""
        critical_content = "extremely dangerous content"
        
        mock_content_validator = safety_monitor.content_validator
        mock_content_validator.validate_content.return_value = {
            "is_safe": False,
            "risk_level": RiskLevel.CRITICAL,
            "confidence": 0.99,
            "violations": ["extreme_violence", "dangerous_instructions"],
            "emergency_shutdown": True
        }
        
        with patch.object(safety_monitor, '_trigger_emergency_shutdown') as mock_shutdown:
            result = await safety_monitor.check_content(critical_content, RiskLevel.SAFE)
            
            assert result.risk_level == RiskLevel.CRITICAL
            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_safety_statistics(self, safety_monitor):
        """Test getting safety monitoring statistics."""
        with patch.object(safety_monitor, '_calculate_stats') as mock_calc:
            mock_calc.return_value = {
                "total_checks": 1000,
                "safe_content": 950,
                "unsafe_content": 50,
                "safety_rate": 0.95,
                "common_violations": ["mild_language", "off_topic"]
            }
            
            result = await safety_monitor.get_safety_statistics()
            
            assert result["total_checks"] == 1000
            assert result["safety_rate"] == 0.95
            assert "mild_language" in result["common_violations"]

    @pytest.mark.asyncio
    async def test_validate_input_length(self, safety_monitor):
        """Test input length validation."""
        # Test normal length
        normal_content = "This is a normal message"
        result = await safety_monitor._validate_input_length(normal_content)
        assert result is True
        
        # Test too long
        long_content = "x" * 10001  # Exceeds limit
        result = await safety_monitor._validate_input_length(long_content)
        assert result is False

    @pytest.mark.asyncio
    async def test_content_preprocessing(self, safety_monitor):
        """Test content preprocessing before safety checks."""
        raw_content = "  Hello WORLD!!! 123  "
        
        processed = await safety_monitor._preprocess_content(raw_content)
        
        assert processed == "hello world 123"  # Cleaned and normalized

    @pytest.mark.asyncio
    async def test_batch_content_check(self, safety_monitor, mock_content_validator):
        """Test batch processing of multiple content items."""
        content_batch = [
            "Safe message 1",
            "Safe message 2", 
            "Unsafe message with violence"
        ]
        
        mock_content_validator.validate_content.side_effect = [
            {"is_safe": True, "risk_level": RiskLevel.SAFE, "violations": []},
            {"is_safe": True, "risk_level": RiskLevel.SAFE, "violations": []},
            {"is_safe": False, "risk_level": RiskLevel.HIGH, "violations": ["violence"]}
        ]
        
        results = await safety_monitor.batch_check_content(content_batch)
        
        assert len(results) == 3
        assert results[0].is_safe is True
        assert results[1].is_safe is True
        assert results[2].is_safe is False