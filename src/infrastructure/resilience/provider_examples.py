"""
Provider Circuit Breaker & Health Monitor Examples
================================================
Comprehensive examples showing how to integrate circuit breakers and health monitoring
with all external providers in the AI Teddy Bear system:
- AI Provider integration (OpenAI, Anthropic, Azure)
- Storage Provider integration (S3, Azure Blob, MinIO)
- Communication Provider integration (SendGrid, FCM)
- Audio Provider integration (ElevenLabs, Whisper)
- Database and Cache Provider integration
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from .provider_registry import ProviderRegistry, ProviderConfiguration, LoadBalancingStrategy
from .provider_circuit_breaker import ProviderType, CircuitBreakerConfig
from .provider_health_monitor import HealthCheckType
from .provider_integration import create_provider_app, setup_provider_integration
from .fallback_logger import FallbackLogger


class ProviderExamples:
    """Comprehensive examples for provider circuit breaker and health monitoring integration."""
    
    def __init__(self):
        self.logger = FallbackLogger("provider_examples")
        self.registry = ProviderRegistry()
    
    async def setup_ai_providers(self):
        """Setup circuit breakers and health monitoring for AI providers."""
        
        # OpenAI GPT-4 Provider
        openai_config = ProviderConfiguration(
            provider_id="openai_gpt4",
            provider_type=ProviderType.AI_PROVIDER,
            name="OpenAI GPT-4",
            description="OpenAI GPT-4 for AI conversation generation",
            endpoint_url="https://api.openai.com/v1",
            region="us-east-1",
            weight=100,
            max_concurrent_requests=50,
            priority=1,
            cost_per_request=0.03,  # $0.03 per request
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="openai_gpt4",
                provider_type=ProviderType.AI_PROVIDER,
                failure_threshold=5,
                failure_rate_threshold=20.0,
                timeout_duration=30.0,
                recovery_timeout=300,
                max_cost_per_minute=5.0,
                adaptive_thresholds=True
            ),
            tags={
                "model": "gpt-4",
                "capability": "conversation",
                "child_safe": "true"
            }
        )
        await self.registry.register_provider(openai_config)
        
        # Register health check function
        health_monitor = self.registry.health_monitors["openai_gpt4"]
        health_monitor.register_health_check(
            HealthCheckType.SYNTHETIC,
            self._ai_provider_synthetic_check
        )
        
        # Anthropic Claude Provider
        claude_config = ProviderConfiguration(
            provider_id="anthropic_claude",
            provider_type=ProviderType.AI_PROVIDER,
            name="Anthropic Claude",
            description="Anthropic Claude for AI conversation generation",
            endpoint_url="https://api.anthropic.com/v1",
            region="us-west-2",
            weight=90,
            max_concurrent_requests=40,
            priority=2,
            cost_per_request=0.025,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="anthropic_claude",
                provider_type=ProviderType.AI_PROVIDER,
                failure_threshold=4,
                failure_rate_threshold=15.0,
                timeout_duration=25.0,
                recovery_timeout=240,
                max_cost_per_minute=4.0
            ),
            tags={
                "model": "claude-3",
                "capability": "conversation",
                "child_safe": "true"
            }
        )
        await self.registry.register_provider(claude_config)
        
        # Azure OpenAI Provider (fallback)
        azure_openai_config = ProviderConfiguration(
            provider_id="azure_openai",
            provider_type=ProviderType.AI_PROVIDER,
            name="Azure OpenAI",
            description="Azure OpenAI Service for AI conversation",
            endpoint_url="https://your-resource.openai.azure.com",
            region="eastus",
            weight=70,
            max_concurrent_requests=30,
            priority=3,
            cost_per_request=0.028,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="azure_openai",
                provider_type=ProviderType.AI_PROVIDER,
                failure_threshold=6,
                failure_rate_threshold=25.0,
                timeout_duration=35.0,
                recovery_timeout=360
            ),
            tags={
                "model": "gpt-4",
                "capability": "conversation",
                "region": "enterprise"
            }
        )
        await self.registry.register_provider(azure_openai_config)
        
        self.logger.info("AI providers configured with circuit breakers and health monitoring")
    
    async def setup_storage_providers(self):
        """Setup circuit breakers and health monitoring for storage providers."""
        
        # AWS S3 Provider
        s3_config = ProviderConfiguration(
            provider_id="aws_s3_primary",
            provider_type=ProviderType.STORAGE_PROVIDER,
            name="AWS S3 Primary",
            description="AWS S3 for primary file storage",
            endpoint_url="https://s3.amazonaws.com",
            region="us-east-1",
            weight=100,
            max_concurrent_requests=200,
            priority=1,
            cost_per_request=0.0004,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="aws_s3_primary",
                provider_type=ProviderType.STORAGE_PROVIDER,
                failure_threshold=10,
                failure_rate_threshold=5.0,
                timeout_duration=15.0,
                recovery_timeout=180,
                max_cost_per_minute=2.0
            ),
            tags={
                "storage_class": "standard",
                "encryption": "enabled",
                "backup": "enabled"
            }
        )
        await self.registry.register_provider(s3_config)
        
        # Register storage health check
        s3_health_monitor = self.registry.health_monitors["aws_s3_primary"]
        s3_health_monitor.register_health_check(
            HealthCheckType.SYNTHETIC,
            self._storage_provider_synthetic_check
        )
        
        # Azure Blob Storage Provider
        azure_blob_config = ProviderConfiguration(
            provider_id="azure_blob_secondary",
            provider_type=ProviderType.STORAGE_PROVIDER,
            name="Azure Blob Secondary",
            description="Azure Blob Storage for secondary/backup storage",
            endpoint_url="https://storage.blob.core.windows.net",
            region="eastus",
            weight=80,
            max_concurrent_requests=150,
            priority=2,
            cost_per_request=0.0003,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="azure_blob_secondary",
                provider_type=ProviderType.STORAGE_PROVIDER,
                failure_threshold=8,
                failure_rate_threshold=8.0,
                timeout_duration=20.0,
                recovery_timeout=240
            )
        )
        await self.registry.register_provider(azure_blob_config)
        
        # MinIO Provider (on-premises)
        minio_config = ProviderConfiguration(
            provider_id="minio_onprem",
            provider_type=ProviderType.STORAGE_PROVIDER,
            name="MinIO On-Premises",
            description="MinIO for on-premises storage",
            endpoint_url="https://minio.internal.company.com",
            region="datacenter-1",
            weight=60,
            max_concurrent_requests=100,
            priority=3,
            cost_per_request=0.0001,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="minio_onprem",
                provider_type=ProviderType.STORAGE_PROVIDER,
                failure_threshold=5,
                failure_rate_threshold=10.0,
                timeout_duration=10.0,
                recovery_timeout=120
            ),
            tags={
                "location": "onprem",
                "compliance": "internal"
            }
        )
        await self.registry.register_provider(minio_config)
        
        self.logger.info("Storage providers configured with circuit breakers and health monitoring")
    
    async def setup_communication_providers(self):
        """Setup circuit breakers and health monitoring for communication providers."""
        
        # SendGrid Email Provider
        sendgrid_config = ProviderConfiguration(
            provider_id="sendgrid_email",
            provider_type=ProviderType.COMMUNICATION_PROVIDER,
            name="SendGrid Email",
            description="SendGrid for email notifications",
            endpoint_url="https://api.sendgrid.com/v3",
            region="global",
            weight=100,
            max_concurrent_requests=50,
            priority=1,
            cost_per_request=0.001,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="sendgrid_email",
                provider_type=ProviderType.COMMUNICATION_PROVIDER,
                failure_threshold=3,
                failure_rate_threshold=10.0,
                timeout_duration=10.0,
                recovery_timeout=300
            ),
            tags={
                "channel": "email",
                "priority": "high"
            }
        )
        await self.registry.register_provider(sendgrid_config)
        
        # Firebase Cloud Messaging Provider
        fcm_config = ProviderConfiguration(
            provider_id="firebase_fcm",
            provider_type=ProviderType.COMMUNICATION_PROVIDER,
            name="Firebase Cloud Messaging",
            description="FCM for push notifications",
            endpoint_url="https://fcm.googleapis.com/fcm",
            region="global",
            weight=100,
            max_concurrent_requests=100,
            priority=1,
            cost_per_request=0.0001,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="firebase_fcm",
                provider_type=ProviderType.COMMUNICATION_PROVIDER,
                failure_threshold=5,
                failure_rate_threshold=15.0,
                timeout_duration=5.0,
                recovery_timeout=180
            ),
            tags={
                "channel": "push",
                "realtime": "true"
            }
        )
        await self.registry.register_provider(fcm_config)
        
        # Register communication health check
        fcm_health_monitor = self.registry.health_monitors["firebase_fcm"]
        fcm_health_monitor.register_health_check(
            HealthCheckType.FUNCTIONAL,
            self._communication_provider_functional_check
        )
        
        self.logger.info("Communication providers configured with circuit breakers and health monitoring")
    
    async def setup_audio_providers(self):
        """Setup circuit breakers and health monitoring for audio providers."""
        
        # ElevenLabs TTS Provider
        elevenlabs_config = ProviderConfiguration(
            provider_id="elevenlabs_tts",
            provider_type=ProviderType.AUDIO_PROVIDER,
            name="ElevenLabs TTS",
            description="ElevenLabs for text-to-speech generation",
            endpoint_url="https://api.elevenlabs.io/v1",
            region="us-east-1",
            weight=100,
            max_concurrent_requests=20,
            priority=1,
            cost_per_request=0.18,  # $0.18 per 1000 characters
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="elevenlabs_tts",
                provider_type=ProviderType.AUDIO_PROVIDER,
                failure_threshold=3,
                failure_rate_threshold=20.0,
                timeout_duration=30.0,
                recovery_timeout=300,
                max_cost_per_minute=10.0
            ),
            tags={
                "capability": "tts",
                "voice_quality": "premium",
                "child_friendly": "true"
            }
        )
        await self.registry.register_provider(elevenlabs_config)
        
        # OpenAI Whisper STT Provider
        whisper_config = ProviderConfiguration(
            provider_id="openai_whisper",
            provider_type=ProviderType.AUDIO_PROVIDER,
            name="OpenAI Whisper",
            description="OpenAI Whisper for speech-to-text",
            endpoint_url="https://api.openai.com/v1",
            region="us-east-1",
            weight=100,
            max_concurrent_requests=30,
            priority=1,
            cost_per_request=0.006,  # $0.006 per minute
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="openai_whisper",
                provider_type=ProviderType.AUDIO_PROVIDER,
                failure_threshold=4,
                failure_rate_threshold=15.0,
                timeout_duration=60.0,
                recovery_timeout=240
            ),
            tags={
                "capability": "stt",
                "accuracy": "high",
                "languages": "multilingual"
            }
        )
        await self.registry.register_provider(whisper_config)
        
        # Register audio health checks
        elevenlabs_health_monitor = self.registry.health_monitors["elevenlabs_tts"]
        elevenlabs_health_monitor.register_health_check(
            HealthCheckType.PERFORMANCE,
            self._audio_provider_performance_check
        )
        
        self.logger.info("Audio providers configured with circuit breakers and health monitoring")
    
    async def setup_database_providers(self):
        """Setup circuit breakers and health monitoring for database providers."""
        
        # Primary PostgreSQL Database
        postgres_primary_config = ProviderConfiguration(
            provider_id="postgres_primary",
            provider_type=ProviderType.DATABASE_PROVIDER,
            name="PostgreSQL Primary",
            description="Primary PostgreSQL database",
            endpoint_url="postgresql://primary.db.company.com:5432",
            region="us-east-1",
            weight=100,
            max_concurrent_requests=500,
            priority=1,
            cost_per_request=0.0001,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="postgres_primary",
                provider_type=ProviderType.DATABASE_PROVIDER,
                failure_threshold=10,
                failure_rate_threshold=2.0,
                timeout_duration=5.0,
                recovery_timeout=60,
                consecutive_failure_threshold=5
            ),
            tags={
                "role": "primary",
                "backup": "enabled",
                "replication": "synchronous"
            }
        )
        await self.registry.register_provider(postgres_primary_config)
        
        # Read Replica Database
        postgres_replica_config = ProviderConfiguration(
            provider_id="postgres_replica",
            provider_type=ProviderType.DATABASE_PROVIDER,
            name="PostgreSQL Read Replica",
            description="PostgreSQL read replica for read operations",
            endpoint_url="postgresql://replica.db.company.com:5432",
            region="us-west-2",
            weight=80,
            max_concurrent_requests=300,
            priority=2,
            cost_per_request=0.00008,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="postgres_replica",
                provider_type=ProviderType.DATABASE_PROVIDER,
                failure_threshold=8,
                failure_rate_threshold=3.0,
                timeout_duration=5.0,
                recovery_timeout=90
            ),
            tags={
                "role": "replica",
                "read_only": "true"
            }
        )
        await self.registry.register_provider(postgres_replica_config)
        
        self.logger.info("Database providers configured with circuit breakers and health monitoring")
    
    async def setup_cache_providers(self):
        """Setup circuit breakers and health monitoring for cache providers."""
        
        # Redis Primary Cache
        redis_primary_config = ProviderConfiguration(
            provider_id="redis_primary",
            provider_type=ProviderType.CACHE_PROVIDER,
            name="Redis Primary Cache",
            description="Primary Redis cache for session and application data",
            endpoint_url="redis://cache-primary.company.com:6379",
            region="us-east-1",
            weight=100,
            max_concurrent_requests=1000,
            priority=1,
            cost_per_request=0.00001,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="redis_primary",
                provider_type=ProviderType.CACHE_PROVIDER,
                failure_threshold=15,
                failure_rate_threshold=5.0,
                timeout_duration=2.0,
                recovery_timeout=30,
                consecutive_failure_threshold=10
            ),
            tags={
                "role": "primary",
                "cluster": "enabled",
                "persistence": "enabled"
            }
        )
        await self.registry.register_provider(redis_primary_config)
        
        # Redis Fallback Cache
        redis_fallback_config = ProviderConfiguration(
            provider_id="redis_fallback",
            provider_type=ProviderType.CACHE_PROVIDER,
            name="Redis Fallback Cache",
            description="Fallback Redis cache instance",
            endpoint_url="redis://cache-fallback.company.com:6379",
            region="us-west-2",
            weight=70,
            max_concurrent_requests=500,
            priority=2,
            cost_per_request=0.00001,
            circuit_breaker_config=CircuitBreakerConfig(
                provider_id="redis_fallback",
                provider_type=ProviderType.CACHE_PROVIDER,
                failure_threshold=12,
                failure_rate_threshold=8.0,
                timeout_duration=2.5,
                recovery_timeout=45
            ),
            tags={
                "role": "fallback",
                "cluster": "disabled"
            }
        )
        await self.registry.register_provider(redis_fallback_config)
        
        # Register cache health checks
        redis_health_monitor = self.registry.health_monitors["redis_primary"]
        redis_health_monitor.register_health_check(
            HealthCheckType.PERFORMANCE,
            self._cache_provider_performance_check
        )
        
        self.logger.info("Cache providers configured with circuit breakers and health monitoring")
    
    # Custom health check functions
    async def _ai_provider_synthetic_check(self) -> Dict[str, Any]:
        """Synthetic health check for AI providers."""
        try:
            # Simulate AI provider synthetic transaction
            await asyncio.sleep(0.5)  # Simulate API call
            
            return {
                "connectivity_success": True,
                "functionality_success": True,
                "performance_success": True,
                "throughput": 15.0,
                "latency_p95": 2.5,
                "cost_per_request": 0.03
            }
        except Exception as e:
            return {
                "connectivity_success": False,
                "errors": [f"AI provider synthetic check failed: {str(e)}"]
            }
    
    async def _storage_provider_synthetic_check(self) -> Dict[str, Any]:
        """Synthetic health check for storage providers."""
        try:
            # Simulate storage operations
            await asyncio.sleep(0.2)  # Upload test
            await asyncio.sleep(0.1)  # Download test
            await asyncio.sleep(0.05)  # Delete test
            
            return {
                "connectivity_success": True,
                "functionality_success": True,
                "performance_success": True,
                "throughput": 100.0,
                "latency_p95": 0.5,
                "cost_per_request": 0.0004,
                "cost_efficiency_score": 95.0
            }
        except Exception as e:
            return {
                "connectivity_success": False,
                "errors": [f"Storage provider synthetic check failed: {str(e)}"]
            }
    
    async def _communication_provider_functional_check(self) -> Dict[str, Any]:
        """Functional health check for communication providers."""
        try:
            # Simulate message sending test
            await asyncio.sleep(0.3)
            
            return {
                "connectivity_success": True,
                "functionality_success": True,
                "security_success": True,
                "throughput": 50.0,
                "cost_per_request": 0.001
            }
        except Exception as e:
            return {
                "functionality_success": False,
                "errors": [f"Communication provider functional check failed: {str(e)}"]
            }
    
    async def _audio_provider_performance_check(self) -> Dict[str, Any]:
        """Performance health check for audio providers."""
        try:
            # Simulate audio processing test
            await asyncio.sleep(1.0)  # Audio generation/processing
            
            return {
                "connectivity_success": True,
                "functionality_success": True,
                "performance_success": True,
                "throughput": 5.0,  # Lower throughput for audio
                "latency_p95": 3.0,
                "cost_per_request": 0.18,
                "cpu_usage": 60.0,
                "memory_usage": 40.0
            }
        except Exception as e:
            return {
                "performance_success": False,
                "errors": [f"Audio provider performance check failed: {str(e)}"]
            }
    
    async def _cache_provider_performance_check(self) -> Dict[str, Any]:
        """Performance health check for cache providers."""
        try:
            # Simulate cache operations
            await asyncio.sleep(0.001)  # SET operation
            await asyncio.sleep(0.001)  # GET operation
            await asyncio.sleep(0.001)  # DEL operation
            
            return {
                "connectivity_success": True,
                "functionality_success": True,
                "performance_success": True,
                "throughput": 10000.0,  # High throughput for cache
                "latency_p95": 0.005,
                "memory_usage": 75.0,
                "network_latency": 0.001
            }
        except Exception as e:
            return {
                "performance_success": False,
                "errors": [f"Cache provider performance check failed: {str(e)}"]
            }
    
    async def demonstrate_provider_selection(self):
        """Demonstrate intelligent provider selection."""
        self.logger.info("Demonstrating provider selection strategies")
        
        # Test AI provider selection with different strategies
        strategies = [
            LoadBalancingStrategy.HEALTH_WEIGHTED,
            LoadBalancingStrategy.LEAST_LATENCY,
            LoadBalancingStrategy.COST_OPTIMIZED,
            LoadBalancingStrategy.ROUND_ROBIN
        ]
        
        for strategy in strategies:
            selected = await self.registry.select_provider(
                provider_type=ProviderType.AI_PROVIDER,
                strategy=strategy
            )
            self.logger.info(f"{strategy.value} strategy selected: {selected}")
        
        # Test multi-provider selection
        storage_providers = await self.registry.select_providers(
            count=2,
            provider_type=ProviderType.STORAGE_PROVIDER,
            strategy=LoadBalancingStrategy.HEALTH_WEIGHTED
        )
        self.logger.info(f"Selected storage providers: {storage_providers}")
        
        # Test regional selection
        us_ai_provider = await self.registry.select_provider(
            provider_type=ProviderType.AI_PROVIDER,
            region="us-east-1",
            strategy=LoadBalancingStrategy.GEOGRAPHIC
        )
        self.logger.info(f"US region AI provider: {us_ai_provider}")
    
    async def demonstrate_circuit_breaker_scenarios(self):
        """Demonstrate circuit breaker scenarios."""
        self.logger.info("Demonstrating circuit breaker scenarios")
        
        # Simulate provider failures
        ai_provider = "openai_gpt4"
        
        # Get circuit breaker
        circuit_breaker = self.registry.circuit_breakers[ai_provider]
        
        # Simulate successful requests
        async def successful_request():
            await asyncio.sleep(0.1)
            return "Success"
        
        for i in range(5):
            try:
                result = await circuit_breaker.call(successful_request)
                self.logger.info(f"Request {i+1} successful: {result}")
            except Exception as e:
                self.logger.error(f"Request {i+1} failed: {str(e)}")
        
        # Simulate failing requests
        async def failing_request():
            await asyncio.sleep(0.1)
            raise Exception("Simulated provider failure")
        
        for i in range(7):  # Exceed failure threshold
            try:
                result = await circuit_breaker.call(failing_request)
                self.logger.info(f"Failing request {i+1} successful: {result}")
            except Exception as e:
                self.logger.warning(f"Failing request {i+1} failed: {str(e)}")
        
        # Show circuit breaker status
        status = circuit_breaker.get_status()
        self.logger.info(f"Circuit breaker status: {status['state']}")
        
        # Demonstrate fast-fail when circuit is open
        try:
            result = await circuit_breaker.call(successful_request)
            self.logger.info(f"Request after circuit open: {result}")
        except Exception as e:
            self.logger.info(f"Fast-fail when circuit open: {str(e)}")
    
    async def demonstrate_health_monitoring(self):
        """Demonstrate health monitoring features."""
        self.logger.info("Demonstrating health monitoring")
        
        # Get health reports for all providers
        for provider_id in self.registry.providers:
            if provider_id in self.registry.health_monitors:
                health_monitor = self.registry.health_monitors[provider_id]
                
                # Trigger health checks
                basic_result = await health_monitor.perform_health_check(HealthCheckType.BASIC)
                self.logger.info(f"Basic health check for {provider_id}: {basic_result.status.value}")
                
                # Get comprehensive health report
                health_report = health_monitor.get_health_report()
                self.logger.info(f"Health report for {provider_id}: {health_report['overall_status']}")
    
    async def demonstrate_cost_monitoring(self):
        """Demonstrate cost monitoring and optimization."""
        self.logger.info("Demonstrating cost monitoring")
        
        # Get cost-optimized provider selection
        ai_provider = await self.registry.select_provider(
            provider_type=ProviderType.AI_PROVIDER,
            strategy=LoadBalancingStrategy.COST_OPTIMIZED,
            max_cost=0.05
        )
        self.logger.info(f"Cost-optimized AI provider: {ai_provider}")
        
        # Show cost metrics for all providers
        overview = self.registry.get_registry_overview()
        total_cost = overview["aggregate_metrics"]["total_cost"]
        self.logger.info(f"Total estimated cost: ${total_cost:.4f}")
    
    async def run_comprehensive_demo(self):
        """Run comprehensive demonstration of all features."""
        self.logger.info("🚀 Starting comprehensive provider circuit breaker and health monitoring demo")
        
        try:
            # Start registry
            await self.registry.start()
            
            # Setup all providers
            await self.setup_ai_providers()
            await self.setup_storage_providers()
            await self.setup_communication_providers()
            await self.setup_audio_providers()
            await self.setup_database_providers()
            await self.setup_cache_providers()
            
            # Wait for initial health checks
            await asyncio.sleep(5)
            
            # Demonstrate features
            await self.demonstrate_provider_selection()
            await self.demonstrate_circuit_breaker_scenarios()
            await self.demonstrate_health_monitoring()
            await self.demonstrate_cost_monitoring()
            
            # Show registry overview
            overview = self.registry.get_registry_overview()
            self.logger.info(f"Registry overview: {json.dumps(overview, indent=2)}")
            
        except Exception as e:
            self.logger.error(f"Demo failed: {str(e)}")
        
        finally:
            # Cleanup
            await self.registry.stop()
            self.logger.info("✅ Comprehensive demo completed")


async def run_fastapi_integration_example():
    """Example of FastAPI integration with provider management."""
    logger = FallbackLogger("fastapi_integration")
    logger.info("🌐 Starting FastAPI integration example")
    
    # Create FastAPI app with provider integration
    app = create_provider_app()
    
    # Setup example providers
    examples = ProviderExamples()
    
    # Register example providers through API
    # This would typically be done via HTTP requests to the API
    await examples.registry.start()
    await examples.setup_ai_providers()
    await examples.setup_storage_providers()
    
    # Setup provider integration
    setup_provider_integration(app, examples.registry)
    
    logger.info("FastAPI app configured with provider integration")
    logger.info("Available endpoints:")
    logger.info("- POST /api/providers/register")
    logger.info("- GET /api/providers")
    logger.info("- GET /api/providers/{provider_id}/status")
    logger.info("- POST /api/providers/select")
    logger.info("- GET /api/dashboard/providers")
    logger.info("- GET /api/dashboard/metrics")
    
    await examples.registry.stop()
    logger.info("✅ FastAPI integration example completed")


async def main():
    """Run all examples."""
    print("🎯 AI Teddy Bear Provider Circuit Breaker & Health Monitoring Examples")
    print("=" * 80)
    
    # Run comprehensive demo
    examples = ProviderExamples()
    await examples.run_comprehensive_demo()
    
    print("\n" + "=" * 80)
    
    # Run FastAPI integration example
    await run_fastapi_integration_example()
    
    print("\n🎉 All examples completed successfully!")


if __name__ == "__main__":
    # Set up environment for testing
    os.environ.setdefault("LOG_LEVEL", "INFO")
    
    # Run examples
    asyncio.run(main())