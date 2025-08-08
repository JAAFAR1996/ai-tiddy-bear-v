"""
Tests for Safety Monitor Interfaces
===================================

Critical safety tests for child protection monitoring interfaces.
These tests ensure comprehensive child safety coverage.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from src.application.interfaces.safety_monitor import (
    ISafetyMonitor,
    IBehavioralSafetyMonitor,
    ISafetyIncidentManager,
    ISafetyReportingService,
    ISafetyConfigurationService,
    SafetyThreatType,
    SafetyMonitoringScope,
    SafetyAction,
    SafetyConfidenceLevel,
    SafetyThreat,
    SafetyAnalysisReport,
    BehavioralPattern,
    SafetyIncident
)
from src.core.models import RiskLevel


class TestSafetyMonitorInterfaces:
    """Test safety monitor interface contracts."""

    def test_safety_threat_type_enum(self):
        """Test safety threat type enumeration."""
        assert SafetyThreatType.INAPPROPRIATE_CONTENT.value == "inappropriate_content"
        assert SafetyThreatType.PERSONAL_INFO_REQUEST.value == "personal_info_request"
        assert SafetyThreatType.STRANGER_CONTACT.value == "stranger_contact"
        assert SafetyThreatType.BULLYING_BEHAVIOR.value == "bullying_behavior"

    def test_safety_action_enum(self):
        """Test safety action enumeration."""
        assert SafetyAction.ALLOW.value == "allow"
        assert SafetyAction.FILTER.value == "filter"
        assert SafetyAction.BLOCK.value == "block"
        assert SafetyAction.ESCALATE.value == "escalate"

    def test_safety_monitoring_scope_enum(self):
        """Test safety monitoring scope enumeration."""
        assert SafetyMonitoringScope.REAL_TIME.value == "real_time"
        assert SafetyMonitoringScope.BEHAVIORAL.value == "behavioral"
        assert SafetyMonitoringScope.PREDICTIVE.value == "predictive"

    def test_safety_threat_structure(self):
        """Test safety threat data structure."""
        threat = SafetyThreat(
            threat_type=SafetyThreatType.INAPPROPRIATE_CONTENT,
            severity=RiskLevel.HIGH,
            confidence=0.85,
            description="Inappropriate content detected",
            detected_content="test content",
            recommended_action=SafetyAction.BLOCK,
            metadata={"source": "content_filter"}
        )
        
        assert threat.threat_type == SafetyThreatType.INAPPROPRIATE_CONTENT
        assert threat.severity == RiskLevel.HIGH
        assert threat.confidence == 0.85
        assert threat.recommended_action == SafetyAction.BLOCK

    def test_safety_analysis_report_structure(self):
        """Test safety analysis report structure."""
        report = SafetyAnalysisReport(
            content_id="content123",
            child_id="child123",
            analysis_timestamp=datetime.now(),
            overall_safety_score=0.75,
            risk_level=RiskLevel.MEDIUM,
            confidence_level=SafetyConfidenceLevel.HIGH,
            threats_detected=[],
            recommended_actions=[SafetyAction.FILTER],
            filtered_content="safe content",
            metadata={"analysis_version": "1.0"},
            processing_time_ms=150.5
        )
        
        assert report.content_id == "content123"
        assert report.child_id == "child123"
        assert report.overall_safety_score == 0.75
        assert report.risk_level == RiskLevel.MEDIUM
        assert SafetyAction.FILTER in report.recommended_actions


class TestISafetyMonitor:
    """Test core safety monitor interface."""

    @pytest.fixture
    def mock_safety_monitor(self):
        """Create mock safety monitor service."""
        service = Mock(spec=ISafetyMonitor)
        service.analyze_content_safety = AsyncMock()
        service.detect_threats = AsyncMock()
        service.assess_risk_level = AsyncMock()
        service.recommend_safety_actions = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_analyze_content_safety_interface(self, mock_safety_monitor):
        """Test content safety analysis interface."""
        content = "Hello, what's your name?"
        child_id = "child123"
        context = {"conversation_history": ["Hi teddy!"]}
        
        expected_report = SafetyAnalysisReport(
            content_id="content123",
            child_id=child_id,
            analysis_timestamp=datetime.now(),
            overall_safety_score=0.95,
            risk_level=RiskLevel.LOW,
            confidence_level=SafetyConfidenceLevel.HIGH,
            threats_detected=[],
            recommended_actions=[SafetyAction.ALLOW],
            filtered_content=content,
            metadata={},
            processing_time_ms=50.0
        )
        mock_safety_monitor.analyze_content_safety.return_value = expected_report
        
        result = await mock_safety_monitor.analyze_content_safety(
            content, child_id, context, SafetyMonitoringScope.REAL_TIME
        )
        
        mock_safety_monitor.analyze_content_safety.assert_called_once_with(
            content, child_id, context, SafetyMonitoringScope.REAL_TIME
        )
        assert result == expected_report

    @pytest.mark.asyncio
    async def test_detect_threats_interface(self, mock_safety_monitor):
        """Test threat detection interface."""
        content = "Can you tell me where you live?"
        child_age = 8
        conversation_history = ["Hi!", "Hello there!"]
        
        expected_threats = [
            SafetyThreat(
                threat_type=SafetyThreatType.PERSONAL_INFO_REQUEST,
                severity=RiskLevel.HIGH,
                confidence=0.9,
                description="Request for personal location information",
                detected_content=content,
                recommended_action=SafetyAction.BLOCK,
                metadata={"pattern": "location_request"}
            )
        ]
        mock_safety_monitor.detect_threats.return_value = expected_threats
        
        result = await mock_safety_monitor.detect_threats(
            content, child_age, conversation_history
        )
        
        mock_safety_monitor.detect_threats.assert_called_once_with(
            content, child_age, conversation_history, None
        )
        assert result == expected_threats
        assert len(result) == 1
        assert result[0].threat_type == SafetyThreatType.PERSONAL_INFO_REQUEST

    @pytest.mark.asyncio
    async def test_assess_risk_level_interface(self, mock_safety_monitor):
        """Test risk level assessment interface."""
        threats = [
            SafetyThreat(
                threat_type=SafetyThreatType.INAPPROPRIATE_CONTENT,
                severity=RiskLevel.MEDIUM,
                confidence=0.7,
                description="Mild inappropriate content",
                detected_content="test",
                recommended_action=SafetyAction.FILTER,
                metadata={}
            )
        ]
        child_profile = {"age": 8, "safety_level": "strict"}
        
        expected_assessment = {
            "overall_risk": RiskLevel.MEDIUM,
            "risk_score": 0.65,
            "contributing_factors": ["inappropriate_content"],
            "mitigation_suggestions": ["content_filtering"],
            "confidence": 0.8
        }
        mock_safety_monitor.assess_risk_level.return_value = expected_assessment
        
        result = await mock_safety_monitor.assess_risk_level(
            threats, child_profile
        )
        
        mock_safety_monitor.assess_risk_level.assert_called_once_with(
            threats, child_profile, None
        )
        assert result == expected_assessment
        assert result["overall_risk"] == RiskLevel.MEDIUM


class TestIBehavioralSafetyMonitor:
    """Test behavioral safety monitor interface."""

    @pytest.fixture
    def mock_behavioral_monitor(self):
        """Create mock behavioral monitor service."""
        service = Mock(spec=IBehavioralSafetyMonitor)
        service.analyze_behavioral_patterns = AsyncMock()
        service.detect_behavioral_anomalies = AsyncMock()
        service.generate_behavioral_safety_report = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_analyze_behavioral_patterns_interface(self, mock_behavioral_monitor):
        """Test behavioral pattern analysis interface."""
        child_id = "child123"
        time_window = timedelta(days=30)
        
        expected_patterns = [
            BehavioralPattern(
                child_id=child_id,
                pattern_type="conversation_frequency",
                frequency=15,
                first_detected=datetime.now() - timedelta(days=20),
                last_detected=datetime.now(),
                severity=RiskLevel.LOW,
                confidence=0.8,
                context={"daily_average": 2.5}
            )
        ]
        mock_behavioral_monitor.analyze_behavioral_patterns.return_value = expected_patterns
        
        result = await mock_behavioral_monitor.analyze_behavioral_patterns(
            child_id, time_window
        )
        
        mock_behavioral_monitor.analyze_behavioral_patterns.assert_called_once_with(
            child_id, time_window, None
        )
        assert result == expected_patterns
        assert len(result) == 1
        assert result[0].child_id == child_id

    @pytest.mark.asyncio
    async def test_detect_behavioral_anomalies_interface(self, mock_behavioral_monitor):
        """Test behavioral anomaly detection interface."""
        child_id = "child123"
        baseline_period = timedelta(days=7)
        anomaly_threshold = 0.7
        
        expected_anomalies = [
            {
                "anomaly_type": "conversation_time_spike",
                "severity": RiskLevel.MEDIUM,
                "confidence": 0.85,
                "description": "Unusual increase in conversation duration",
                "detected_at": datetime.now(),
                "baseline_value": 15.0,
                "current_value": 45.0
            }
        ]
        mock_behavioral_monitor.detect_behavioral_anomalies.return_value = expected_anomalies
        
        result = await mock_behavioral_monitor.detect_behavioral_anomalies(
            child_id, baseline_period, anomaly_threshold
        )
        
        mock_behavioral_monitor.detect_behavioral_anomalies.assert_called_once_with(
            child_id, baseline_period, anomaly_threshold
        )
        assert result == expected_anomalies


class TestISafetyIncidentManager:
    """Test safety incident manager interface."""

    @pytest.fixture
    def mock_incident_manager(self):
        """Create mock incident manager service."""
        service = Mock(spec=ISafetyIncidentManager)
        service.create_safety_incident = AsyncMock()
        service.escalate_incident = AsyncMock()
        service.resolve_incident = AsyncMock()
        service.get_incident_history = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_create_safety_incident_interface(self, mock_incident_manager):
        """Test safety incident creation interface."""
        child_id = "child123"
        incident_type = SafetyThreatType.INAPPROPRIATE_CONTENT
        severity = RiskLevel.HIGH
        details = {"content": "inappropriate message", "context": "conversation"}
        
        expected_incident = SafetyIncident(
            incident_id="incident123",
            child_id=child_id,
            incident_type=incident_type,
            severity=severity,
            detected_at=datetime.now(),
            resolved_at=None,
            status="open",
            actions_taken=[],
            details=details,
            follow_up_required=True
        )
        mock_incident_manager.create_safety_incident.return_value = expected_incident
        
        result = await mock_incident_manager.create_safety_incident(
            child_id, incident_type, severity, details
        )
        
        mock_incident_manager.create_safety_incident.assert_called_once_with(
            child_id, incident_type, severity, details, "system"
        )
        assert result == expected_incident

    @pytest.mark.asyncio
    async def test_escalate_incident_interface(self, mock_incident_manager):
        """Test incident escalation interface."""
        incident_id = "incident123"
        escalation_reason = "High severity threat detected"
        escalated_by = "safety_system"
        
        mock_incident_manager.escalate_incident.return_value = True
        
        result = await mock_incident_manager.escalate_incident(
            incident_id, escalation_reason, escalated_by
        )
        
        mock_incident_manager.escalate_incident.assert_called_once_with(
            incident_id, escalation_reason, escalated_by, "human_review"
        )
        assert result is True


class TestISafetyConfigurationService:
    """Test safety configuration service interface."""

    @pytest.fixture
    def mock_config_service(self):
        """Create mock configuration service."""
        service = Mock(spec=ISafetyConfigurationService)
        service.get_child_safety_settings = AsyncMock()
        service.update_safety_settings = AsyncMock()
        service.get_monitoring_configuration = AsyncMock()
        service.validate_safety_policy = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_child_safety_settings_interface(self, mock_config_service):
        """Test child safety settings retrieval interface."""
        child_id = "child123"
        expected_settings = {
            "monitoring_level": "strict",
            "content_filters": ["inappropriate", "personal_info"],
            "allowed_topics": ["stories", "games", "learning"],
            "blocked_topics": ["adult_content", "violence"],
            "parental_notifications": True
        }
        mock_config_service.get_child_safety_settings.return_value = expected_settings
        
        result = await mock_config_service.get_child_safety_settings(child_id)
        
        mock_config_service.get_child_safety_settings.assert_called_once_with(child_id)
        assert result == expected_settings

    @pytest.mark.asyncio
    async def test_validate_safety_policy_interface(self, mock_config_service):
        """Test safety policy validation interface."""
        child_age = 8
        proposed_settings = {
            "monitoring_level": "moderate",
            "content_filters": ["inappropriate"]
        }
        
        expected_validation = {
            "valid": True,
            "conflicts": [],
            "recommendations": ["Enable personal_info filter for age 8"],
            "required_changes": []
        }
        mock_config_service.validate_safety_policy.return_value = expected_validation
        
        result = await mock_config_service.validate_safety_policy(
            child_age, proposed_settings
        )
        
        mock_config_service.validate_safety_policy.assert_called_once_with(
            child_age, proposed_settings
        )
        assert result == expected_validation
        assert result["valid"] is True