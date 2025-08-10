"""
Safety Monitor Interfaces
=========================

This module defines comprehensive interfaces for monitoring child safety across
all interactions in the AI Teddy Bear system. These interfaces are designed to
provide multi-layered safety protection with real-time monitoring, threat detection,
and incident response capabilities.

Architecture:
    - Real-time content analysis and threat detection
    - Behavioral pattern monitoring and anomaly detection
    - Comprehensive safety reporting and analytics
    - Integration with parental controls and external safety services
    - COPPA compliance with audit trails for all safety events

Child Safety Priorities:
    - Content appropriateness validation
    - Conversation context analysis
    - Behavioral pattern monitoring
    - Threat detection and prevention
    - Incident response and reporting
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

from src.core.models import RiskLevel, SafetyAnalysisResult


# Enums for comprehensive safety monitoring
class SafetyThreatType(Enum):
    """Types of safety threats that can be detected."""
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    PERSONAL_INFO_REQUEST = "personal_info_request"
    STRANGER_CONTACT = "stranger_contact"
    BULLYING_BEHAVIOR = "bullying_behavior"
    VIOLENCE_REFERENCE = "violence_reference"
    ADULT_CONTENT = "adult_content"
    HARMFUL_INSTRUCTION = "harmful_instruction"
    PRIVACY_VIOLATION = "privacy_violation"
    MANIPULATION_ATTEMPT = "manipulation_attempt"
    EMOTIONAL_DISTRESS = "emotional_distress"


class SafetyMonitoringScope(Enum):
    """Scope of safety monitoring operations."""
    REAL_TIME = "real_time"           # Live conversation monitoring
    BATCH_ANALYSIS = "batch_analysis" # Historical data analysis
    BEHAVIORAL = "behavioral"         # Long-term behavior patterns
    CONTEXTUAL = "contextual"         # Context-aware analysis
    PREDICTIVE = "predictive"         # Predictive threat detection


class SafetyAction(Enum):
    """Actions that can be taken in response to safety concerns."""
    ALLOW = "allow"                   # Content is safe
    FILTER = "filter"                 # Filter/modify content
    BLOCK = "block"                   # Block content completely
    WARN = "warn"                     # Issue warning to child/parent
    ESCALATE = "escalate"             # Escalate to human review
    TERMINATE = "terminate"           # Terminate conversation
    REPORT = "report"                 # Report to authorities


class SafetyConfidenceLevel(Enum):
    """Confidence levels for safety analysis results."""
    VERY_LOW = "very_low"       # 0.0 - 0.2
    LOW = "low"                 # 0.2 - 0.4
    MEDIUM = "medium"           # 0.4 - 0.6
    HIGH = "high"               # 0.6 - 0.8
    VERY_HIGH = "very_high"     # 0.8 - 1.0


class SafetyMonitoringMode(Enum):
    """Different modes of safety monitoring."""
    STRICT = "strict"           # Maximum protection (ages 3-5)
    MODERATE = "moderate"       # Balanced protection (ages 6-9)
    STANDARD = "standard"       # Age-appropriate protection (ages 10-13)
    CUSTOM = "custom"           # Parent-configured settings


# Data classes for structured safety results
@dataclass
class SafetyThreat:
    """Information about a detected safety threat."""
    threat_type: SafetyThreatType
    severity: RiskLevel
    confidence: float
    description: str
    detected_content: str
    recommended_action: SafetyAction
    metadata: Dict[str, Any]


@dataclass
class SafetyAnalysisReport:
    """Comprehensive safety analysis report."""
    content_id: str
    child_id: str
    analysis_timestamp: datetime
    overall_safety_score: float
    risk_level: RiskLevel
    confidence_level: SafetyConfidenceLevel
    threats_detected: List[SafetyThreat]
    recommended_actions: List[SafetyAction]
    filtered_content: Optional[str]
    metadata: Dict[str, Any]
    processing_time_ms: float


@dataclass
class BehavioralPattern:
    """Information about child behavioral patterns."""
    child_id: str
    pattern_type: str
    frequency: int
    first_detected: datetime
    last_detected: datetime
    severity: RiskLevel
    confidence: float
    context: Dict[str, Any]


@dataclass
class SafetyIncident:
    """Information about a safety incident."""
    incident_id: str
    child_id: str
    incident_type: SafetyThreatType
    severity: RiskLevel
    detected_at: datetime
    resolved_at: Optional[datetime]
    status: str
    actions_taken: List[SafetyAction]
    details: Dict[str, Any]
    follow_up_required: bool


# ============================================================================
# CORE SAFETY MONITOR INTERFACE
# ============================================================================

class ISafetyMonitor(ABC):
    """
    Core interface for comprehensive child safety monitoring.
    
    Responsibilities:
    - Real-time content safety analysis
    - Threat detection and classification
    - Risk assessment and scoring
    - Safety action recommendations
    - Integration with external safety services
    
    Child Safety:
    - Multi-layered analysis approach
    - Age-appropriate content validation
    - Context-aware threat detection
    - Real-time response capabilities
    """
    
    @abstractmethod
    async def analyze_content_safety(
        self,
        content: str,
        child_id: str,
        context: Optional[Dict[str, Any]] = None,
        monitoring_scope: SafetyMonitoringScope = SafetyMonitoringScope.REAL_TIME
    ) -> SafetyAnalysisReport:
        """
        Perform comprehensive safety analysis of content.
        
        Args:
            content: Content to analyze for safety
            child_id: Child identifier (for age and settings context)
            context: Additional context (conversation history, location, etc.)
            monitoring_scope: Scope of monitoring to apply
            
        Returns:
            SafetyAnalysisReport: Comprehensive analysis results
            
        Raises:
            ValueError: If child_id is invalid or child age not 3-13
            SafetyAnalysisError: If analysis fails
            
        Analysis Process:
            1. Age-appropriate content validation
            2. Threat pattern detection
            3. Context analysis
            4. Behavioral consistency check
            5. Risk scoring and classification
            6. Action recommendation generation
        """
        pass
    
    @abstractmethod
    async def detect_threats(
        self,
        content: str,
        child_age: int,
        conversation_history: Optional[List[str]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> List[SafetyThreat]:
        """
        Detect specific safety threats in content.
        
        Args:
            content: Content to analyze
            child_age: Child's age (must be 3-13)
            conversation_history: Recent conversation context
            additional_context: Additional analysis context
            
        Returns:
            List of detected threats with details
            
        Threat Detection:
            - Inappropriate content patterns
            - Personal information requests
            - Stranger danger indicators
            - Bullying or harassment
            - Violence references
            - Adult content detection
        """
        pass
    
    @abstractmethod
    async def assess_risk_level(
        self,
        threats: List[SafetyThreat],
        child_profile: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assess overall risk level based on detected threats.
        
        Args:
            threats: List of detected threats
            child_profile: Child profile information
            context: Additional risk assessment context
            
        Returns:
            Dict containing:
                - overall_risk: RiskLevel
                - risk_score: float (0.0 to 1.0)
                - contributing_factors: List[str]
                - mitigation_suggestions: List[str]
                - confidence: float
        """
        pass
    
    @abstractmethod
    async def recommend_safety_actions(
        self,
        analysis_report: SafetyAnalysisReport,
        child_settings: Dict[str, Any],
        parent_preferences: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend safety actions based on analysis results.
        
        Args:
            analysis_report: Safety analysis results
            child_settings: Child-specific safety settings
            parent_preferences: Parent safety preferences
            
        Returns:
            List of recommended actions:
            [
                {
                    "action": SafetyAction,
                    "priority": int,
                    "reason": str,
                    "impact": str,
                    "parameters": Dict[str, Any]
                }
            ]
        """
        pass


# ============================================================================
# BEHAVIORAL MONITORING INTERFACE
# ============================================================================

class IBehavioralSafetyMonitor(ABC):
    """
    Interface for monitoring child behavioral patterns for safety.
    
    Responsibilities:
    - Track behavioral patterns over time
    - Detect concerning behavioral changes
    - Identify potential risks from behavior
    - Generate behavioral safety reports
    
    Child Safety:
    - Early warning system for concerning behaviors
    - Pattern recognition for safety risks
    - Long-term trend analysis
    - Proactive intervention recommendations
    """
    
    @abstractmethod
    async def analyze_behavioral_patterns(
        self,
        child_id: str,
        time_window: timedelta = timedelta(days=30),
        pattern_types: Optional[List[str]] = None
    ) -> List[BehavioralPattern]:
        """
        Analyze child's behavioral patterns for safety concerns.
        
        Args:
            child_id: Child identifier
            time_window: Time period to analyze
            pattern_types: Specific pattern types to analyze
            
        Returns:
            List of detected behavioral patterns
            
        Pattern Analysis:
            - Communication frequency changes
            - Topic preference shifts
            - Emotional tone variations
            - Interaction time patterns
            - Response behavior changes
        """
        pass
    
    @abstractmethod
    async def detect_behavioral_anomalies(
        self,
        child_id: str,
        baseline_period: timedelta = timedelta(days=7),
        anomaly_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Detect behavioral anomalies that might indicate safety concerns.
        
        Args:
            child_id: Child identifier
            baseline_period: Period to establish behavioral baseline
            anomaly_threshold: Threshold for anomaly detection (0.0-1.0)
            
        Returns:
            List of detected anomalies with details
        """
        pass
    
    @abstractmethod
    async def generate_behavioral_safety_report(
        self,
        child_id: str,
        report_period: timedelta = timedelta(days=30)
    ) -> Dict[str, Any]:
        """
        Generate comprehensive behavioral safety report.
        
        Args:
            child_id: Child identifier
            report_period: Period to include in report
            
        Returns:
            Comprehensive behavioral safety report
        """
        pass


# ============================================================================
# INCIDENT MANAGEMENT INTERFACE
# ============================================================================

class ISafetyIncidentManager(ABC):
    """
    Interface for managing safety incidents and responses.
    
    Responsibilities:
    - Create and track safety incidents
    - Coordinate incident response
    - Manage escalation procedures
    - Generate incident reports
    
    Child Safety:
    - Rapid incident response
    - Proper escalation procedures
    - Comprehensive incident tracking
    - Compliance with reporting requirements
    """
    
    @abstractmethod
    async def create_safety_incident(
        self,
        child_id: str,
        incident_type: SafetyThreatType,
        severity: RiskLevel,
        details: Dict[str, Any],
        detected_by: str = "system"
    ) -> SafetyIncident:
        """
        Create a new safety incident record.
        
        Args:
            child_id: Child identifier
            incident_type: Type of safety incident
            severity: Incident severity level
            details: Detailed incident information
            detected_by: Who/what detected the incident
            
        Returns:
            Created safety incident record
        """
        pass
    
    @abstractmethod
    async def escalate_incident(
        self,
        incident_id: str,
        escalation_reason: str,
        escalated_by: str,
        escalation_target: str = "human_review"
    ) -> bool:
        """
        Escalate a safety incident for human review.
        
        Args:
            incident_id: Incident identifier
            escalation_reason: Reason for escalation
            escalated_by: Who initiated escalation
            escalation_target: Target for escalation
            
        Returns:
            True if escalation successful
        """
        pass
    
    @abstractmethod
    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str,
        actions_taken: List[SafetyAction],
        resolved_by: str
    ) -> bool:
        """
        Mark a safety incident as resolved.
        
        Args:
            incident_id: Incident identifier
            resolution: Description of resolution
            actions_taken: Actions taken to resolve
            resolved_by: Who resolved the incident
            
        Returns:
            True if resolution successful
        """
        pass
    
    @abstractmethod
    async def get_incident_history(
        self,
        child_id: str,
        time_window: Optional[timedelta] = None,
        incident_types: Optional[List[SafetyThreatType]] = None
    ) -> List[SafetyIncident]:
        """
        Get safety incident history for a child.
        
        Args:
            child_id: Child identifier
            time_window: Time period to retrieve
            incident_types: Filter by specific incident types
            
        Returns:
            List of safety incidents
        """
        pass


# ============================================================================
# SAFETY REPORTING INTERFACE
# ============================================================================

class ISafetyReportingService(ABC):
    """
    Interface for generating safety reports and analytics.
    
    Responsibilities:
    - Generate safety analytics reports
    - Provide safety trend analysis
    - Create compliance reports
    - Support safety decision making
    
    COPPA Compliance:
    - Generate required safety reports
    - Maintain audit trails
    - Support regulatory compliance
    - Protect child privacy in reports
    """
    
    @abstractmethod
    async def generate_safety_dashboard(
        self,
        child_id: str,
        time_period: timedelta = timedelta(days=7)
    ) -> Dict[str, Any]:
        """
        Generate safety dashboard data for parents.
        
        Args:
            child_id: Child identifier
            time_period: Time period for dashboard
            
        Returns:
            Safety dashboard data
        """
        pass
    
    @abstractmethod
    async def generate_compliance_report(
        self,
        report_type: str,
        time_period: timedelta,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate compliance reports for regulatory requirements.
        
        Args:
            report_type: Type of compliance report
            time_period: Reporting period
            filters: Optional report filters
            
        Returns:
            Compliance report data
        """
        pass
    
    @abstractmethod
    async def analyze_safety_trends(
        self,
        analysis_type: str,
        time_window: timedelta = timedelta(days=30)
    ) -> Dict[str, Any]:
        """
        Analyze safety trends across the system.
        
        Args:
            analysis_type: Type of trend analysis
            time_window: Time window for analysis
            
        Returns:
            Safety trend analysis results
        """
        pass


# ============================================================================
# SAFETY CONFIGURATION INTERFACE  
# ============================================================================

class ISafetyConfigurationService(ABC):
    """
    Interface for managing safety configuration and settings.
    
    Responsibilities:
    - Manage child-specific safety settings
    - Configure monitoring parameters
    - Handle parental safety controls
    - Maintain safety policy enforcement
    
    Child Safety:
    - Age-appropriate default settings
    - Parental override capabilities
    - Dynamic configuration updates
    - Safety policy enforcement
    """
    
    @abstractmethod
    async def get_child_safety_settings(
        self,
        child_id: str
    ) -> Dict[str, Any]:
        """
        Get safety settings for a specific child.
        
        Args:
            child_id: Child identifier
            
        Returns:
            Child-specific safety settings
        """
        pass
    
    @abstractmethod
    async def update_safety_settings(
        self,
        child_id: str,
        settings: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """
        Update safety settings for a child.
        
        Args:
            child_id: Child identifier
            settings: New safety settings
            updated_by: Who updated the settings
            
        Returns:
            True if update successful
        """
        pass
    
    @abstractmethod
    async def get_monitoring_configuration(
        self,
        monitoring_scope: SafetyMonitoringScope
    ) -> Dict[str, Any]:
        """
        Get configuration for specific monitoring scope.
        
        Args:
            monitoring_scope: Monitoring scope to configure
            
        Returns:
            Monitoring configuration
        """
        pass
    
    @abstractmethod
    async def validate_safety_policy(
        self,
        child_age: int,
        proposed_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate proposed safety settings against policies.
        
        Args:
            child_age: Child's age
            proposed_settings: Settings to validate
            
        Returns:
            Validation results with any conflicts
        """
        pass


# Backward compatibility - keep the original simple interface
class SafetyMonitor(ISafetyMonitor):
    """
    Backward compatibility interface for existing code.
    
    This maintains the original simple interface while extending
    from the comprehensive ISafetyMonitor interface.
    """
    
    @abstractmethod
    async def check_content_safety(
        self,
        content: str,
        child_age: int = 0,
        conversation_history: Optional[List[str]] = None,
    ) -> SafetyAnalysisResult:
        """
        Original method signature for backward compatibility.
        
        This method should delegate to analyze_content_safety
        with appropriate parameter mapping.
        """
        pass


# Export all interfaces and types
__all__ = [
    # Enums
    "SafetyThreatType",
    "SafetyMonitoringScope", 
    "SafetyAction",
    "SafetyConfidenceLevel",
    "SafetyMonitoringMode",
    
    # Data Classes
    "SafetyThreat",
    "SafetyAnalysisReport",
    "BehavioralPattern",
    "SafetyIncident",
    
    # Core Interfaces
    "ISafetyMonitor",
    "IBehavioralSafetyMonitor",
    "ISafetyIncidentManager",
    "ISafetyReportingService",
    "ISafetyConfigurationService",
    
    # Backward Compatibility
    "SafetyMonitor",
    
    # Re-exported from core (avoid name conflicts)
    "RiskLevel",
    "SafetyAnalysisResult",
]
