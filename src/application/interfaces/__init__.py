"""
Application Interfaces Module
=============================

This module provides a centralized access point for all application-layer interfaces.
It re-exports important interfaces to improve developer experience and maintain
clean architectural boundaries.

Usage:
    from src.application.interfaces import (
        IDataRetentionService,
        SafetyMonitor,
        TextToSpeechService,
        SpeechProcessor
    )

Architecture:
    - All interfaces follow the Dependency Inversion Principle
    - Abstract base classes (ABC) for strict contracts
    - Protocol types for structural typing where appropriate
    - COPPA compliance considerations built into all child-related interfaces
"""

# Infrastructure Services - COPPA compliant services for child data management
from .infrastructure_services import (
    # Service Interfaces
    IDataRetentionService,
    IParentVerificationService,
    IAuditLogger,
    IAccessControlService,
    INotificationService,
    # Enums for type safety
    DataRetentionStatus,
    VerificationMethod,
    ConsentType,
    AccessOperation,
    ContentSafetyLevel,
    AuditEventType,
    # Data Classes
    DataRetentionInfo,
    ContentFilterResult,
    VerificationResult,
)

# Safety and Content Monitoring - Critical for child safety
from .safety_monitor import (
    # Core Interfaces
    IBehavioralSafetyMonitor,
    ISafetyIncidentManager,
    ISafetyReportingService,
    ISafetyConfigurationService,
    # Backward Compatibility
    SafetyMonitor,
    # Enums for safety operations
    SafetyThreatType,
    SafetyMonitoringScope,
    SafetyAction,
    SafetyConfidenceLevel,
    SafetyMonitoringMode,
    # Data Classes
    SafetyThreat,
    SafetyAnalysisReport,
    BehavioralPattern,
    SafetyIncident,
    # Core types (no name conflicts)
    RiskLevel,
    SafetyAnalysisResult,
)

# Audio Processing Services - For voice interactions with children
from .speech_processor import SpeechProcessor

# TextToSpeechService DELETED - use ITTSService from src.interfaces.providers.tts_provider

# Security and Encryption - Practical child data protection
from .security.encryption_interfaces import (
    # Core Encryption Interfaces
    IChildDataEncryption,
    IFieldLevelEncryption,
    ISecureStorageEncryption,
    IEncryptionKeyManager,
    # Enums
    EncryptionStrength,
    DataClassification,
    # Data Classes
    EncryptionResult,
    DecryptionResult,
)

# Re-export interfaces from main interfaces directory
try:
    from src.interfaces.read_model_interfaces import (
        IChildProfileReadModel,
        IChildProfileReadModelStore,
    )
    from src.interfaces.providers.ai_provider import AIProvider
except ImportError:
    # Fallback if the interfaces are moved or renamed
    pass

# Type aliases for better API clarity
DataRetentionService = IDataRetentionService
ParentVerificationService = IParentVerificationService
AuditLogger = IAuditLogger
AccessControlService = IAccessControlService
NotificationService = INotificationService

# Export lists for different interface categories
__all__ = [
    # Infrastructure Services
    "IDataRetentionService",
    "IParentVerificationService",
    "IAuditLogger",
    "IAccessControlService",
    "INotificationService",
    # Type aliases
    "DataRetentionService",
    "ParentVerificationService",
    "AuditLogger",
    "AccessControlService",
    "NotificationService",
    # Enums for type safety
    "DataRetentionStatus",
    "VerificationMethod",
    "ConsentType",
    "AccessOperation",
    "ContentSafetyLevel",
    "AuditEventType",
    # Data Classes
    "DataRetentionInfo",
    "ContentFilterResult",
    "VerificationResult",
    # Safety and Monitoring - Comprehensive child safety interfaces
    "IBehavioralSafetyMonitor",
    "ISafetyIncidentManager",
    "ISafetyReportingService",
    "ISafetyConfigurationService",
    "SafetyMonitor",  # Backward compatibility
    # Safety Enums
    "SafetyThreatType",
    "SafetyMonitoringScope",
    "SafetyAction",
    "SafetyConfidenceLevel",
    "SafetyMonitoringMode",
    # Safety Data Classes
    "SafetyThreat",
    "SafetyAnalysisReport",
    "BehavioralPattern",
    "SafetyIncident",
    # Core Safety Types
    "RiskLevel",
    "SafetyAnalysisResult",
    # Audio Processing - Basic speech processing interfaces
    "SpeechProcessor",
    # "IAdvancedSpeechProcessor", - Missing
    # "ISpeechConfigurationService", - Missing
    # Speech Processing Enums (removed missing ones)
    # "AudioFormat", - Missing
    # "SpeechQuality", - Missing
    # "VoiceGender", - Missing
    # "VoiceEmotion", - Missing
    # Speech Processing Data Classes (removed missing ones)
    # "SpeechToTextResult", - Missing
    # "TextToSpeechResult", - Missing
    # "VoiceProfile", - Missing
    # "AudioAnalysis", - Missing
    # Speech Processing Exceptions (removed missing ones)
    # "SpeechProcessingError", - Missing
    # "AudioFormatError", - Missing
    # "AudioQualityError", - Missing
    # "VoiceNotFoundError", - Missing
    # "LanguageNotSupportedError", - Missing
    # "ContentFilteringError", - Missing
    # "SpeechProcessingTimeoutError", - Missing
    # Security and Encryption
    "IChildDataEncryption",
    "IFieldLevelEncryption",
    "ISecureStorageEncryption",
    "IEncryptionKeyManager",
    "EncryptionStrength",
    "DataClassification",
    "EncryptionResult",
    "DecryptionResult",
    # Read Models (if available)
    "IChildProfileReadModel",
    "IChildProfileReadModelStore",
    # AI Provider (unified interface)
    "AIProvider",
]

# Interface categories for easier discovery
INFRASTRUCTURE_INTERFACES = [
    "IDataRetentionService",
    "IParentVerificationService",
    "IAuditLogger",
    "IAccessControlService",
    "INotificationService",
]

SAFETY_INTERFACES = [
    # Core Safety Interfaces
    "ISafetyMonitor",
    "IBehavioralSafetyMonitor",
    "ISafetyIncidentManager",
    "ISafetyReportingService",
    "ISafetyConfigurationService",
    "SafetyMonitor",  # Backward compatibility
    # Safety Types
    "SafetyThreatType",
    "SafetyMonitoringScope",
    "SafetyAction",
    "SafetyConfidenceLevel",
    "SafetyMonitoringMode",
    "RiskLevel",
    "SafetyAnalysisResult",
]

AUDIO_INTERFACES = [
    # Core Speech Processing
    "SpeechProcessor",
    "IAdvancedSpeechProcessor",
    "ISpeechConfigurationService",
    # "TextToSpeechService", DELETED - use ITTSService
    # Speech Processing Types
    "AudioFormat",
    "SpeechQuality",
    "VoiceGender",
    "VoiceEmotion",
    "SpeechToTextResult",
    "TextToSpeechResult",
    "VoiceProfile",
    "AudioAnalysis",
    # Speech Processing Exceptions
    "SpeechProcessingError",
    "AudioFormatError",
    "AudioQualityError",
    "VoiceNotFoundError",
    "LanguageNotSupportedError",
    "ContentFilteringError",
    "SpeechProcessingTimeoutError",
]

SECURITY_INTERFACES = [
    "IChildDataEncryption",
    "IFieldLevelEncryption",
    "ISecureStorageEncryption",
    "IEncryptionKeyManager",
    "EncryptionStrength",
    "DataClassification",
    "EncryptionResult",
    "DecryptionResult",
]

READ_MODEL_INTERFACES = [
    "IChildProfileReadModel",
    "IChildProfileReadModelStore",
]

AI_PROVIDER_INTERFACES = [
    "AIProvider",
]

# Compliance reminder for developers
COPPA_COMPLIANCE_NOTE = """
�  COPPA COMPLIANCE REMINDER �

All interfaces in this module are designed with COPPA compliance in mind.
When implementing these interfaces, ensure:

1. Age validation (3-13 years only)
2. Parental consent verification
3. Data minimization principles
4. Secure data storage and transmission
5. Audit logging for all child data access
6. Content safety validation

For more information, see: src/core/constants.py
"""


def get_interface_info() -> dict[str, list[str]]:
    """
    Get information about available interface categories.

    Returns:
        Dictionary mapping category names to interface lists
    """
    return {
        "infrastructure": INFRASTRUCTURE_INTERFACES,
        "safety": SAFETY_INTERFACES,
        "audio": AUDIO_INTERFACES,
        "security": SECURITY_INTERFACES,
        "read_models": READ_MODEL_INTERFACES,
        "ai_providers": AI_PROVIDER_INTERFACES,
    }


def get_coppa_compliance_note() -> str:
    """
    Get COPPA compliance reminder for developers.

    Returns:
        String containing COPPA compliance guidelines
    """
    return COPPA_COMPLIANCE_NOTE


# Validation function to ensure interfaces are properly imported
def validate_interfaces() -> bool:
    """
    Validate that all expected interfaces are available.

    Returns:
        True if all interfaces are available, False otherwise
    """
    expected_interfaces = set(__all__)
    available_interfaces = set(globals().keys())

    missing = expected_interfaces - available_interfaces
    if missing:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Missing interfaces: {missing}")
        return False

    return True


# Auto-validation on import (development mode only)
if __debug__:
    validate_interfaces()
