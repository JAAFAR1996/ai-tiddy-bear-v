"""
Service-Specific Fallback Configurations
======================================
Detailed fallback strategies for each AI Teddy Bear service with:
- Provider-specific tier definitions
- Failure-driven fallback rules
- Cost-aware fallback selection
- Health monitoring and recovery policies
"""

import os
from typing import Dict, List
from src.infrastructure.resilience.fallback_manager import (
    ServiceFallbackConfig, FallbackRule, FallbackTier, FailureReason
)


class ServiceFallbackConfigs:
    """
    Centralized fallback configurations for all AI Teddy Bear services.
    
    Each service has:
    - Multi-tier provider setup (PRIMARY -> SECONDARY -> TERTIARY -> EMERGENCY -> OFFLINE)
    - Failure-specific routing rules
    - Circuit breaker configurations
    - Cost optimization strategies
    """
    
    @staticmethod
    def get_ai_service_config() -> ServiceFallbackConfig:
        """AI Service fallback configuration with OpenAI/Claude/Gemini tiers."""
        return ServiceFallbackConfig(
            service_name="ai_service",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout_seconds=60,
            
            tier_providers={
                FallbackTier.PRIMARY: ["openai_gpt4"],
                FallbackTier.SECONDARY: ["anthropic_claude", "openai_gpt35"],
                FallbackTier.TERTIARY: ["google_gemini", "cohere"],
                FallbackTier.EMERGENCY: ["local_llm", "cached_responses"],
                FallbackTier.OFFLINE: ["template_responses"]
            },
            
            rules=[
                # Rate limit -> Move to secondary immediately
                FallbackRule(
                    service_name="ai_service",
                    failure_reasons=[FailureReason.RATE_LIMIT_EXCEEDED],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=1,
                    retry_delay_seconds=0.5,
                    timeout_seconds=30.0,
                    cost_multiplier=1.2,
                    priority=1
                ),
                
                # Quota exceeded -> Skip to tertiary (different providers)
                FallbackRule(
                    service_name="ai_service",
                    failure_reasons=[FailureReason.QUOTA_EXCEEDED],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=30.0,
                    cost_multiplier=0.8,  # Cheaper alternatives
                    priority=1
                ),
                
                # Connection/timeout -> Try secondary with quick retry
                FallbackRule(
                    service_name="ai_service",
                    failure_reasons=[FailureReason.CONNECTION_ERROR, FailureReason.TIMEOUT],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=2,
                    retry_delay_seconds=1.0,
                    timeout_seconds=25.0,
                    cost_multiplier=1.0,
                    priority=2
                ),
                
                # Service unavailable -> Emergency fallback
                FallbackRule(
                    service_name="ai_service",
                    failure_reasons=[FailureReason.SERVICE_UNAVAILABLE],
                    target_tier=FallbackTier.EMERGENCY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=10.0,
                    cost_multiplier=0.1,  # Much cheaper
                    priority=1
                ),
                
                # Authentication -> Skip to different provider family
                FallbackRule(
                    service_name="ai_service",
                    failure_reasons=[FailureReason.AUTHENTICATION_ERROR],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=30.0,
                    cost_multiplier=0.9,
                    priority=1
                )
            ],
            
            health_check_interval_seconds=30,
            health_check_timeout_seconds=10,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_tts_service_config() -> ServiceFallbackConfig:
        """TTS Service fallback configuration with ElevenLabs/OpenAI/Azure tiers."""
        return ServiceFallbackConfig(
            service_name="tts_service",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=3,  # More sensitive for audio
            circuit_breaker_timeout_seconds=45,
            
            tier_providers={
                FallbackTier.PRIMARY: ["elevenlabs_premium"],
                FallbackTier.SECONDARY: ["openai_tts", "azure_tts"],
                FallbackTier.TERTIARY: ["google_tts", "aws_polly"],
                FallbackTier.EMERGENCY: ["espeak_local", "festival_local"],
                FallbackTier.OFFLINE: ["cached_audio", "silence"]
            },
            
            rules=[
                # Rate limit -> Quick switch to secondary
                FallbackRule(
                    service_name="tts_service",
                    failure_reasons=[FailureReason.RATE_LIMIT_EXCEEDED],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=20.0,
                    cost_multiplier=0.7,  # Secondary TTS is cheaper
                    priority=1
                ),
                
                # Quota exceeded -> Different provider ecosystem
                FallbackRule(
                    service_name="tts_service",
                    failure_reasons=[FailureReason.QUOTA_EXCEEDED],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=25.0,
                    cost_multiplier=0.5,
                    priority=1
                ),
                
                # Connection issues -> Retry secondary quickly
                FallbackRule(
                    service_name="tts_service",
                    failure_reasons=[FailureReason.CONNECTION_ERROR, FailureReason.TIMEOUT],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=2,
                    retry_delay_seconds=0.5,
                    timeout_seconds=15.0,
                    cost_multiplier=0.8,
                    priority=2
                ),
                
                # Service unavailable -> Local TTS immediately
                FallbackRule(
                    service_name="tts_service",
                    failure_reasons=[FailureReason.SERVICE_UNAVAILABLE],
                    target_tier=FallbackTier.EMERGENCY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=5.0,
                    cost_multiplier=0.0,  # Local is free
                    priority=1
                )
            ],
            
            health_check_interval_seconds=20,  # More frequent for audio
            health_check_timeout_seconds=8,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_stt_service_config() -> ServiceFallbackConfig:
        """STT Service fallback configuration with Whisper/Azure/Google tiers."""
        return ServiceFallbackConfig(
            service_name="stt_service",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=4,
            circuit_breaker_timeout_seconds=60,
            
            tier_providers={
                FallbackTier.PRIMARY: ["openai_whisper"],
                FallbackTier.SECONDARY: ["azure_stt", "google_stt"],
                FallbackTier.TERTIARY: ["aws_transcribe", "ibm_watson"],
                FallbackTier.EMERGENCY: ["vosk_local", "deepspeech_local"],
                FallbackTier.OFFLINE: ["cached_transcripts", "fallback_text"]
            },
            
            rules=[
                # Rate limit -> Azure/Google quickly
                FallbackRule(
                    service_name="stt_service",
                    failure_reasons=[FailureReason.RATE_LIMIT_EXCEEDED],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=30.0,
                    cost_multiplier=0.9,
                    priority=1
                ),
                
                # Connection issues -> Retry with longer timeout
                FallbackRule(
                    service_name="stt_service",
                    failure_reasons=[FailureReason.CONNECTION_ERROR, FailureReason.TIMEOUT],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=2,
                    retry_delay_seconds=1.5,
                    timeout_seconds=45.0,  # STT needs more time
                    cost_multiplier=1.0,
                    priority=2
                ),
                
                # Service unavailable -> Local processing
                FallbackRule(
                    service_name="stt_service",
                    failure_reasons=[FailureReason.SERVICE_UNAVAILABLE],
                    target_tier=FallbackTier.EMERGENCY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=60.0,  # Local processing is slower
                    cost_multiplier=0.0,
                    priority=1
                )
            ],
            
            health_check_interval_seconds=45,
            health_check_timeout_seconds=15,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_safety_service_config() -> ServiceFallbackConfig:
        """Safety Service fallback - CRITICAL service with multiple validation layers."""
        return ServiceFallbackConfig(
            service_name="safety_service",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=2,  # Very sensitive - child safety is critical
            circuit_breaker_timeout_seconds=30,
            
            tier_providers={
                FallbackTier.PRIMARY: ["openai_moderation", "perspective_api"],
                FallbackTier.SECONDARY: ["azure_content_moderator", "aws_comprehend"],
                FallbackTier.TERTIARY: ["local_keyword_filter", "regex_patterns"],
                FallbackTier.EMERGENCY: ["strict_allowlist_only"],
                FallbackTier.OFFLINE: ["block_all_content"]  # Fail secure
            },
            
            rules=[
                # ANY failure -> Immediate strict secondary
                FallbackRule(
                    service_name="safety_service",
                    failure_reasons=[
                        FailureReason.RATE_LIMIT_EXCEEDED, 
                        FailureReason.CONNECTION_ERROR,
                        FailureReason.TIMEOUT,
                        FailureReason.SERVICE_UNAVAILABLE
                    ],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=10.0,  # Fast safety checks
                    cost_multiplier=1.5,  # Cost is secondary to safety
                    priority=1,
                    health_check_required=True
                ),
                
                # Multiple failures -> Local strict filtering
                FallbackRule(
                    service_name="safety_service",
                    failure_reasons=[FailureReason.UNKNOWN_ERROR],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=0,  # No retries for unknown errors
                    retry_delay_seconds=0.0,
                    timeout_seconds=5.0,
                    cost_multiplier=0.0,
                    priority=1
                )
            ],
            
            health_check_interval_seconds=15,  # Very frequent
            health_check_timeout_seconds=5,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_notification_service_config() -> ServiceFallbackConfig:
        """Notification Service fallback with FCM/SMTP/SMS tiers."""
        return ServiceFallbackConfig(
            service_name="notification_service",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout_seconds=120,  # Longer timeout for notifications
            
            tier_providers={
                FallbackTier.PRIMARY: ["fcm_push", "apns_push"],
                FallbackTier.SECONDARY: ["sendgrid_email", "ses_email"],
                FallbackTier.TERTIARY: ["twilio_sms", "slack_webhook"],
                FallbackTier.EMERGENCY: ["local_queue", "database_log"],
                FallbackTier.OFFLINE: ["file_log"]
            },
            
            rules=[
                # Push notification failures -> Email immediately
                FallbackRule(
                    service_name="notification_service",
                    failure_reasons=[
                        FailureReason.CONNECTION_ERROR,
                        FailureReason.SERVICE_UNAVAILABLE,
                        FailureReason.AUTHENTICATION_ERROR
                    ],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=2,
                    retry_delay_seconds=5.0,  # Give push services time
                    timeout_seconds=30.0,
                    cost_multiplier=0.8,
                    priority=2
                ),
                
                # Rate limits -> Try different channel
                FallbackRule(
                    service_name="notification_service",
                    failure_reasons=[FailureReason.RATE_LIMIT_EXCEEDED],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=25.0,
                    cost_multiplier=2.0,  # SMS is more expensive
                    priority=1
                ),
                
                # Critical failures -> Store for retry
                FallbackRule(
                    service_name="notification_service",
                    failure_reasons=[FailureReason.QUOTA_EXCEEDED],
                    target_tier=FallbackTier.EMERGENCY,
                    max_retries=0,
                    retry_delay_seconds=0.0,
                    timeout_seconds=5.0,
                    cost_multiplier=0.0,
                    priority=1
                )
            ],
            
            health_check_interval_seconds=60,
            health_check_timeout_seconds=20,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_file_storage_config() -> ServiceFallbackConfig:
        """File Storage fallback with S3/Azure/local tiers."""
        return ServiceFallbackConfig(
            service_name="file_storage",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=4,
            circuit_breaker_timeout_seconds=90,
            
            tier_providers={
                FallbackTier.PRIMARY: ["aws_s3_primary"],
                FallbackTier.SECONDARY: ["azure_blob", "aws_s3_secondary"],
                FallbackTier.TERTIARY: ["gcp_storage", "minio_cluster"],
                FallbackTier.EMERGENCY: ["local_filesystem", "nfs_mount"],
                FallbackTier.OFFLINE: ["temp_storage"]
            },
            
            rules=[
                # Connection issues -> Multi-cloud immediately
                FallbackRule(
                    service_name="file_storage",
                    failure_reasons=[
                        FailureReason.CONNECTION_ERROR,
                        FailureReason.TIMEOUT,
                        FailureReason.SERVICE_UNAVAILABLE
                    ],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=2,
                    retry_delay_seconds=2.0,
                    timeout_seconds=60.0,
                    cost_multiplier=1.1,
                    priority=2
                ),
                
                # Authentication -> Different cloud provider
                FallbackRule(
                    service_name="file_storage",
                    failure_reasons=[FailureReason.AUTHENTICATION_ERROR],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=45.0,
                    cost_multiplier=0.9,
                    priority=1
                ),
                
                # Quota/rate limits -> Local storage
                FallbackRule(
                    service_name="file_storage",
                    failure_reasons=[
                        FailureReason.QUOTA_EXCEEDED,
                        FailureReason.RATE_LIMIT_EXCEEDED
                    ],
                    target_tier=FallbackTier.EMERGENCY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=30.0,
                    cost_multiplier=0.0,
                    priority=1
                )
            ],
            
            health_check_interval_seconds=45,
            health_check_timeout_seconds=30,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_database_service_config() -> ServiceFallbackConfig:
        """Database Service fallback with primary/replica/backup tiers."""
        return ServiceFallbackConfig(
            service_name="database_service",
            enabled=True,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=3,  # Database is critical
            circuit_breaker_timeout_seconds=30,
            
            tier_providers={
                FallbackTier.PRIMARY: ["postgres_primary"],
                FallbackTier.SECONDARY: ["postgres_replica_1", "postgres_replica_2"],
                FallbackTier.TERTIARY: ["postgres_backup", "mysql_backup"],
                FallbackTier.EMERGENCY: ["redis_cache", "local_sqlite"],
                FallbackTier.OFFLINE: ["file_cache"]
            },
            
            rules=[
                # Connection failures -> Read replica immediately
                FallbackRule(
                    service_name="database_service",
                    failure_reasons=[
                        FailureReason.CONNECTION_ERROR,
                        FailureReason.TIMEOUT
                    ],
                    target_tier=FallbackTier.SECONDARY,
                    max_retries=2,
                    retry_delay_seconds=0.5,
                    timeout_seconds=10.0,
                    cost_multiplier=1.0,
                    priority=1
                ),
                
                # Service unavailable -> Backup database
                FallbackRule(
                    service_name="database_service",
                    failure_reasons=[FailureReason.SERVICE_UNAVAILABLE],
                    target_tier=FallbackTier.TERTIARY,
                    max_retries=1,
                    retry_delay_seconds=0.0,
                    timeout_seconds=15.0,
                    cost_multiplier=1.2,
                    priority=1
                ),
                
                # Critical failures -> Cache/local only
                FallbackRule(
                    service_name="database_service",
                    failure_reasons=[FailureReason.UNKNOWN_ERROR],
                    target_tier=FallbackTier.EMERGENCY,
                    max_retries=0,
                    retry_delay_seconds=0.0,
                    timeout_seconds=5.0,
                    cost_multiplier=0.0,
                    priority=1
                )
            ],
            
            health_check_interval_seconds=10,  # Very frequent for DB
            health_check_timeout_seconds=5,
            log_all_failures=True,
            log_fallback_decisions=True,
            track_response_times=True
        )
    
    @staticmethod
    def get_all_service_configs() -> Dict[str, ServiceFallbackConfig]:
        """Get all service fallback configurations."""
        return {
            "ai_service": ServiceFallbackConfigs.get_ai_service_config(),
            "tts_service": ServiceFallbackConfigs.get_tts_service_config(),
            "stt_service": ServiceFallbackConfigs.get_stt_service_config(),
            "safety_service": ServiceFallbackConfigs.get_safety_service_config(),
            "notification_service": ServiceFallbackConfigs.get_notification_service_config(),
            "file_storage": ServiceFallbackConfigs.get_file_storage_config(),
            "database_service": ServiceFallbackConfigs.get_database_service_config()
        }
    
    @staticmethod
    def get_environment_specific_overrides() -> Dict[str, Dict[str, Any]]:
        """Get environment-specific configuration overrides."""
        environment = os.getenv("ENVIRONMENT", "development")
        
        if environment == "production":
            return {
                "all_services": {
                    "circuit_breaker_threshold": 3,  # More sensitive in production
                    "health_check_interval_seconds": 15,  # More frequent checks
                    "log_all_failures": True,
                    "log_fallback_decisions": True
                },
                "safety_service": {
                    "circuit_breaker_threshold": 1,  # Extremely sensitive for safety
                    "health_check_interval_seconds": 5
                }
            }
        elif environment == "staging":
            return {
                "all_services": {
                    "circuit_breaker_threshold": 4,
                    "health_check_interval_seconds": 30,
                    "log_all_failures": True
                }
            }
        else:  # development
            return {
                "all_services": {
                    "circuit_breaker_threshold": 10,  # More lenient in dev
                    "health_check_interval_seconds": 60,
                    "log_all_failures": False,  # Reduce noise in dev
                    "log_fallback_decisions": False
                }
            }