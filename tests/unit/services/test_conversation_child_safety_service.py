"""
Unit tests for ConversationChildSafetyService
Tests advanced conversation-specific child safety features
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from src.services.conversation_child_safety_service import (
    ConversationChildSafetyService,
    ConversationThreatType,
    ConversationRiskLevel,
    ConversationSafetyMetrics,
    ConversationAlert,
    create_conversation_child_safety_service
)
from src.core.entities import Message, Conversation


class TestConversationChildSafetyService:
    """Test ConversationChildSafetyService functionality."""

    @pytest.fixture
    def mock_base_safety_service(self):
        """Mock base safety service."""
        mock_service = Mock()
        mock_service.validate_content = AsyncMock(return_value={"is_safe": True})
        mock_service.filter_content = AsyncMock(return_value="[FILTERED]")
        return mock_service

    @pytest.fixture
    def mock_conversation_cache(self):
        """Mock conversation cache service."""
        mock_cache = Mock()
        mock_cache.get_conversation_messages = AsyncMock(return_value=[])
        return mock_cache

    @pytest.fixture
    def safety_service(self, mock_base_safety_service, mock_conversation_cache):
        """Create ConversationChildSafetyService instance."""
        return ConversationChildSafetyService(
            base_safety_service=mock_base_safety_service,
            conversation_cache=mock_conversation_cache
        )

    @pytest.fixture
    def sample_conversation(self):
        """Sample conversation for testing."""
        return Conversation(
            id=uuid4(),
            child_id=uuid4(),
            status="active",
            interaction_type="chat",
            message_count=5
        )

    @pytest.fixture
    def sample_message(self, sample_conversation):
        """Sample message for testing."""
        return Message(
            id=uuid4(),
            conversation_id=sample_conversation.id,
            message_type="user_input",
            content="Hello, how are you?",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={}
        )

    def test_initialization(self, mock_base_safety_service):
        """Test service initialization."""
        service = ConversationChildSafetyService(mock_base_safety_service)
        
        assert service.base_safety == mock_base_safety_service
        assert service.risk_threshold_warning == 0.6
        assert service.risk_threshold_critical == 0.8
        assert service.conversations_analyzed == 0

    def test_factory_function(self, mock_base_safety_service):
        """Test factory function."""
        service = create_conversation_child_safety_service(mock_base_safety_service)
        assert isinstance(service, ConversationChildSafetyService)

    @pytest.mark.asyncio
    async def test_analyze_conversation_safety_normal(self, safety_service, sample_message, sample_conversation):
        """Test normal conversation analysis."""
        is_safe, risk_level, alerts = await safety_service.analyze_conversation_safety(
            sample_message, sample_conversation, child_age=10
        )
        
        assert is_safe is True
        assert risk_level == ConversationRiskLevel.NORMAL
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_analyze_conversation_safety_grooming_pattern(self, safety_service, sample_conversation):
        """Test grooming pattern detection."""
        suspicious_message = Message(
            id=uuid4(),
            conversation_id=sample_conversation.id,
            message_type="user_input",
            content="You're so mature for your age. This will be our secret, don't tell your parents.",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={}
        )
        
        is_safe, risk_level, alerts = await safety_service.analyze_conversation_safety(
            suspicious_message, sample_conversation, child_age=10
        )
        
        assert is_safe is False
        assert risk_level in [ConversationRiskLevel.HIGH_RISK, ConversationRiskLevel.CRITICAL]
        assert len(alerts) > 0
        assert any(alert.threat_type == ConversationThreatType.GROOMING_PATTERN for alert in alerts)

    @pytest.mark.asyncio
    async def test_analyze_conversation_patterns(self, safety_service, sample_message, sample_conversation):
        """Test conversation pattern analysis."""
        # Test with grooming content
        grooming_message = Message(
            id=uuid4(),
            conversation_id=sample_conversation.id,
            message_type="user_input",
            content="You're special to me, trust me, don't tell anyone about our friendship",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={}
        )
        
        result = await safety_service._analyze_conversation_patterns(
            grooming_message, sample_conversation, []
        )
        
        assert result["grooming_indicators"] > 0
        assert result["trust_building_score"] > 0
        assert result["isolation_attempts"] > 0
        assert len(result["detected_patterns"]) > 0

    @pytest.mark.asyncio
    async def test_boundary_testing_analysis(self, safety_service, sample_conversation):
        """Test boundary testing analysis."""
        boundary_message = Message(
            id=uuid4(),
            conversation_id=sample_conversation.id,
            message_type="user_input",
            content="This is our secret, just between friends, don't tell anyone",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={}
        )
        
        context_messages = [
            Message(
                id=uuid4(),
                conversation_id=sample_conversation.id,
                message_type="user_input",
                content="You're special",
                sender_id=uuid4(),
                timestamp=datetime.now() - timedelta(minutes=5),
                metadata={}
            )
        ]
        
        score = await safety_service._analyze_boundary_testing(boundary_message, context_messages)
        assert score > 0

    @pytest.mark.asyncio
    async def test_update_conversation_metrics(self, safety_service):
        """Test conversation metrics update."""
        conversation_id = uuid4()
        analysis_result = {
            "grooming_indicators": 2,
            "trust_building_score": 0.7,
            "isolation_attempts": 1,
            "escalation_score": 0.6,
            "pressure_indicators": 1,
            "boundary_testing": 0.5
        }
        
        await safety_service._update_conversation_metrics(conversation_id, analysis_result)
        
        conv_id_str = str(conversation_id)
        assert conv_id_str in safety_service._conversation_metrics
        
        metrics = safety_service._conversation_metrics[conv_id_str]
        assert metrics.total_messages == 1
        assert metrics.trust_building_score == 0.7
        assert metrics.isolation_attempts == 1
        assert metrics.cumulative_risk_score > 0

    @pytest.mark.asyncio
    async def test_risk_progression_analysis(self, safety_service):
        """Test risk progression analysis."""
        conversation_id = uuid4()
        
        # Create initial metrics
        safety_service._conversation_metrics[str(conversation_id)] = ConversationSafetyMetrics(
            conversation_id=str(conversation_id),
            total_messages=5,
            risk_progression_score=0.5,
            trust_building_score=0.6,
            isolation_attempts=2,
            personal_info_requests=1,
            escalation_indicators=["escalation_2023-01-01T10:00:00"],
            last_risk_assessment=datetime.now() - timedelta(hours=1),
            cumulative_risk_score=60.0
        )
        
        progression = await safety_service._analyze_risk_progression(conversation_id)
        
        assert "progression_rate" in progression
        assert "trend" in progression
        assert progression["progression_rate"] >= 0

    def test_calculate_overall_risk_level(self, safety_service):
        """Test overall risk level calculation."""
        base_validation = {"is_safe": False}
        conversation_analysis = {
            "grooming_indicators": 3,
            "trust_building_score": 0.8,
            "isolation_attempts": 2,
            "escalation_score": 0.7,
            "pressure_indicators": 1
        }
        risk_progression = {"progression_rate": 0.6, "trend": 0.5}
        
        risk_level = safety_service._calculate_overall_risk_level(
            base_validation, conversation_analysis, risk_progression
        )
        
        assert risk_level in [ConversationRiskLevel.HIGH_RISK, ConversationRiskLevel.CRITICAL]

    @pytest.mark.asyncio
    async def test_generate_conversation_alerts(self, safety_service, sample_message, sample_conversation):
        """Test conversation alert generation."""
        analysis_result = {
            "grooming_indicators": 3,
            "trust_building_score": 0.8,
            "isolation_attempts": 1,
            "escalation_score": 0.8,
            "detected_patterns": ["grooming: pattern1", "trust_building: pattern2"]
        }
        
        alerts = await safety_service._generate_conversation_alerts(
            sample_message, sample_conversation, ConversationRiskLevel.HIGH_RISK, analysis_result
        )
        
        assert len(alerts) > 0
        assert any(alert.threat_type == ConversationThreatType.GROOMING_PATTERN for alert in alerts)
        assert any(alert.requires_immediate_action for alert in alerts)

    @pytest.mark.asyncio
    async def test_validate_conversation_message(self, safety_service, sample_message, sample_conversation):
        """Test simplified validation interface."""
        is_safe, filtered_content, safety_details = await safety_service.validate_conversation_message(
            sample_message, sample_conversation, child_age=10
        )
        
        assert isinstance(is_safe, bool)
        assert "risk_level" in safety_details
        assert "alerts_count" in safety_details
        assert "immediate_action_required" in safety_details

    @pytest.mark.asyncio
    async def test_get_conversation_safety_report(self, safety_service):
        """Test conversation safety report generation."""
        conversation_id = uuid4()
        
        # Create test metrics
        safety_service._conversation_metrics[str(conversation_id)] = ConversationSafetyMetrics(
            conversation_id=str(conversation_id),
            total_messages=10,
            risk_progression_score=0.4,
            trust_building_score=0.3,
            isolation_attempts=1,
            personal_info_requests=0,
            escalation_indicators=[],
            last_risk_assessment=datetime.now(),
            cumulative_risk_score=30.0
        )
        
        report = await safety_service.get_conversation_safety_report(conversation_id)
        
        assert "conversation_id" in report
        assert "metrics" in report
        assert "alerts" in report
        assert "recommendations" in report
        assert "overall_assessment" in report

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, safety_service):
        """Test old data cleanup."""
        # Add old data
        old_alert = ConversationAlert(
            alert_id=str(uuid4()),
            conversation_id=str(uuid4()),
            child_id=str(uuid4()),
            threat_type=ConversationThreatType.GROOMING_PATTERN,
            severity=ConversationRiskLevel.HIGH_RISK,
            description="Test alert",
            evidence_patterns=[],
            context_messages=[],
            recommended_action="Test action",
            timestamp=datetime.now() - timedelta(hours=100)
        )
        
        safety_service._conversation_alerts.append(old_alert)
        
        await safety_service.cleanup_old_data(retention_hours=72)
        
        assert len(safety_service._conversation_alerts) == 0

    @pytest.mark.asyncio
    async def test_get_service_statistics(self, safety_service):
        """Test service statistics."""
        safety_service.conversations_analyzed = 10
        safety_service.high_risk_conversations_detected = 2
        safety_service.grooming_attempts_blocked = 1
        
        stats = await safety_service.get_service_statistics()
        
        assert stats["service"] == "ConversationChildSafetyService"
        assert stats["statistics"]["conversations_analyzed"] == 10
        assert stats["statistics"]["high_risk_conversations_detected"] == 2
        assert stats["statistics"]["grooming_attempts_blocked"] == 1

    def test_generate_safety_recommendations(self, safety_service):
        """Test safety recommendations generation."""
        metrics = ConversationSafetyMetrics(
            conversation_id="test",
            total_messages=10,
            risk_progression_score=0.8,
            trust_building_score=0.7,
            isolation_attempts=2,
            personal_info_requests=1,
            escalation_indicators=[],
            last_risk_assessment=datetime.now(),
            cumulative_risk_score=80.0
        )
        
        alerts = [{"requires_immediate_action": True}]
        
        recommendations = safety_service._generate_safety_recommendations(metrics, alerts)
        
        assert len(recommendations) > 0
        assert any("immediate" in rec.lower() for rec in recommendations)

    def test_get_overall_assessment(self, safety_service):
        """Test overall assessment generation."""
        high_risk_metrics = ConversationSafetyMetrics(
            conversation_id="test",
            total_messages=10,
            risk_progression_score=0.8,
            trust_building_score=0.7,
            isolation_attempts=2,
            personal_info_requests=1,
            escalation_indicators=[],
            last_risk_assessment=datetime.now(),
            cumulative_risk_score=85.0
        )
        
        assessment = safety_service._get_overall_assessment(high_risk_metrics)
        assert "CRITICAL" in assessment

    @pytest.mark.asyncio
    async def test_conversation_cache_integration(self, safety_service, sample_message, sample_conversation):
        """Test integration with conversation cache."""
        # Mock cache to return context messages
        mock_cached_message = Mock()
        mock_cached_message.message_id = str(uuid4())
        mock_cached_message.conversation_id = str(sample_conversation.id)
        mock_cached_message.message_type = "user_input"
        mock_cached_message.content = "Previous message"
        mock_cached_message.sender_id = str(uuid4())
        mock_cached_message.timestamp = datetime.now().isoformat()
        mock_cached_message.metadata = {}
        
        safety_service.conversation_cache.get_conversation_messages.return_value = [mock_cached_message]
        
        is_safe, filtered_content, safety_details = await safety_service.validate_conversation_message(
            sample_message, sample_conversation, child_age=10
        )
        
        # Verify cache was called
        safety_service.conversation_cache.get_conversation_messages.assert_called_once()

    def test_pattern_initialization(self, safety_service):
        """Test that threat patterns are properly initialized."""
        assert len(safety_service.grooming_patterns) > 0
        assert len(safety_service.trust_building_patterns) > 0
        assert len(safety_service.isolation_patterns) > 0
        assert len(safety_service.escalation_patterns) > 0
        assert len(safety_service.pressure_patterns) > 0

    @pytest.mark.asyncio
    async def test_multiple_threat_detection(self, safety_service, sample_conversation):
        """Test detection of multiple threat types in one message."""
        multi_threat_message = Message(
            id=uuid4(),
            conversation_id=sample_conversation.id,
            message_type="user_input",
            content="You're so mature and special. Trust me, this is our secret. Send me a picture quickly before someone comes.",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={}
        )
        
        is_safe, risk_level, alerts = await safety_service.analyze_conversation_safety(
            multi_threat_message, sample_conversation, child_age=10
        )
        
        assert is_safe is False
        assert risk_level in [ConversationRiskLevel.HIGH_RISK, ConversationRiskLevel.CRITICAL]
        assert len(alerts) >= 2  # Should detect multiple threat types

    @pytest.mark.asyncio
    async def test_escalation_tracking(self, safety_service):
        """Test escalation indicator tracking."""
        conversation_id = uuid4()
        
        # Simulate multiple escalation events
        for i in range(3):
            analysis_result = {
                "grooming_indicators": 1,
                "trust_building_score": 0.5,
                "isolation_attempts": 0,
                "escalation_score": 0.8,  # High escalation
                "pressure_indicators": 0,
                "boundary_testing": 0.3
            }
            
            await safety_service._update_conversation_metrics(conversation_id, analysis_result)
        
        metrics = safety_service._conversation_metrics[str(conversation_id)]
        assert len(metrics.escalation_indicators) == 3

    def test_risk_level_enum_values(self):
        """Test ConversationRiskLevel enum values."""
        assert ConversationRiskLevel.NORMAL.value == "normal"
        assert ConversationRiskLevel.MONITORING.value == "monitoring"
        assert ConversationRiskLevel.ELEVATED.value == "elevated"
        assert ConversationRiskLevel.HIGH_RISK.value == "high_risk"
        assert ConversationRiskLevel.CRITICAL.value == "critical"

    def test_threat_type_enum_values(self):
        """Test ConversationThreatType enum values."""
        assert ConversationThreatType.GROOMING_PATTERN.value == "grooming_pattern"
        assert ConversationThreatType.TRUST_BUILDING_MANIPULATION.value == "trust_building_manipulation"
        assert ConversationThreatType.ISOLATION_ATTEMPT.value == "isolation_attempt"