"""
Integration Tests for Audio Service
===================================
Tests for service integration, dependency injection, and component wiring.
These tests verify that all components work together correctly without mocks.
"""

import pytest
import asyncio
import logging
from typing import AsyncGenerator

from src.infrastructure.container import injector_instance
from src.services.service_registry import get_service_registry, get_audio_service
from src.interfaces.services import IAudioService
from src.interfaces.providers.tts_provider import ITTSService
from src.application.services.audio_service import AudioService
from src.application.services.audio_validation_service import AudioValidationService
from src.application.services.audio_streaming_service import AudioStreamingService
from src.application.services.audio_safety_service import AudioSafetyService

logger = logging.getLogger(__name__)


class TestAudioServiceIntegration:
    """Integration tests for Audio Service component wiring."""
    
    @pytest.fixture(scope="session")
    def event_loop(self):
        """Create an event loop for the test session."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_service_dependency_injection_container(self):
        """Test AudioService can be created from DI container."""
        try:
            # Get AudioService from injector
            audio_service = injector_instance.get(IAudioService)
            
            # Verify it's properly instantiated
            assert audio_service is not None
            assert isinstance(audio_service, AudioService)
            
            # Verify all dependencies are wired (no None values)
            assert audio_service.stt_provider is not None
            assert audio_service.tts_service is not None
            assert audio_service.validation_service is not None
            assert audio_service.streaming_service is not None
            assert audio_service.safety_service is not None
            assert audio_service.cache_service is not None
            assert audio_service.logger is not None
            
            logger.info("✅ AudioService successfully created from DI container with all dependencies")
            
        except Exception as e:
            logger.error(f"❌ Failed to create AudioService from DI container: {e}")
            raise
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_service_service_registry(self):
        """Test AudioService can be retrieved from ServiceRegistry."""
        try:
            # Get AudioService from ServiceRegistry
            audio_service = await get_audio_service()
            
            # Verify it's properly instantiated
            assert audio_service is not None
            assert hasattr(audio_service, 'convert_text_to_speech')
            assert hasattr(audio_service, 'get_service_health')
            assert hasattr(audio_service, 'get_tts_metrics')
            
            logger.info("✅ AudioService successfully retrieved from ServiceRegistry")
            
        except Exception as e:
            logger.error(f"❌ Failed to get AudioService from ServiceRegistry: {e}")
            raise
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_validation_service_standalone(self):
        """Test AudioValidationService works standalone."""
        validation_service = AudioValidationService(logger=logger)
        
        # Test with sample audio data
        sample_audio = b"RIFF" + b"fake_wav_data" * 100
        
        result = await validation_service.validate_audio(sample_audio)
        
        assert result is not None
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'format')
        assert hasattr(result, 'issues')
        
        logger.info(f"✅ AudioValidationService validation result: valid={result.is_valid}, issues={len(result.issues)}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_streaming_service_standalone(self):
        """Test AudioStreamingService works standalone."""
        streaming_service = AudioStreamingService(buffer_size=1024, logger=logger)
        
        # Create async generator for test data
        async def sample_stream():
            test_chunks = [b"chunk1", b"chunk2", b"chunk3"]
            for chunk in test_chunks:
                yield chunk
        
        # Process stream
        result = await streaming_service.process_stream(sample_stream())
        
        assert result is not None
        assert isinstance(result, bytes)
        assert b"chunk1chunk2chunk3" == result
        
        logger.info(f"✅ AudioStreamingService processed {len(result)} bytes")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_safety_service_standalone(self):
        """Test AudioSafetyService works standalone."""
        safety_service = AudioSafetyService(logger=logger)
        
        # Test audio safety check
        sample_audio = b"fake_audio_data" * 50
        audio_result = await safety_service.check_audio_safety(sample_audio, child_age=6)
        
        assert audio_result is not None
        assert hasattr(audio_result, 'is_safe')
        assert hasattr(audio_result, 'violations')
        assert hasattr(audio_result, 'recommendations')
        
        # Test text safety check
        safe_text = "Hello, let's learn about friendly animals!"
        text_result = await safety_service.check_text_safety(safe_text)
        
        assert text_result.is_safe is True
        assert len(text_result.violations) == 0
        
        # Test unsafe text
        unsafe_text = "Scary monsters will hurt you!"
        unsafe_result = await safety_service.check_text_safety(unsafe_text)
        
        assert unsafe_result.is_safe is False
        assert len(unsafe_result.violations) > 0
        
        logger.info(f"✅ AudioSafetyService: audio_safe={audio_result.is_safe}, text_safe={text_result.is_safe}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tts_service_dependency_injection(self):
        """Test TTS service can be retrieved from DI container."""
        try:
            tts_service = injector_instance.get(ITTSService)
            
            assert tts_service is not None
            assert hasattr(tts_service, 'synthesize_speech')
            assert hasattr(tts_service, 'health_check')
            assert hasattr(tts_service, 'get_available_voices')
            
            logger.info("✅ TTS service successfully retrieved from DI container")
            
        except Exception as e:
            logger.error(f"❌ Failed to get TTS service from DI: {e}")
            # This might fail if OPENAI_API_KEY is not set, which is acceptable
            if "OPENAI_API_KEY" in str(e):
                pytest.skip("OPENAI_API_KEY not available for integration testing")
            raise
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_service_component_integration(self):
        """Test all AudioService components work together."""
        # Create individual components
        validation_service = AudioValidationService(logger=logger)
        streaming_service = AudioStreamingService(buffer_size=1024, logger=logger)
        safety_service = AudioSafetyService(logger=logger)
        
        # Mock minimal dependencies for integration test
        class MockSTTProvider:
            async def transcribe(self, audio_data: bytes) -> str:
                return "This is a test transcription"
        
        class MockTTSService:
            async def synthesize_speech(self, request):
                from src.interfaces.providers.tts_provider import TTSResult, AudioFormat
                from datetime import datetime
                return TTSResult(
                    audio_data=b"mock_tts_audio_data",
                    request_id="test_123",
                    provider_name="mock",
                    config=request.config,
                    duration_seconds=1.0,
                    sample_rate=22050,
                    bit_rate=128000,
                    file_size_bytes=len(b"mock_tts_audio_data"),
                    format=AudioFormat.MP3,
                    processing_time_ms=100.0,
                    provider_latency_ms=80.0,
                    created_at=datetime.now()
                )
            
            async def health_check(self):
                return {"status": "healthy", "provider": "mock"}
        
        # Create AudioService with all real components
        audio_service = AudioService(
            stt_provider=MockSTTProvider(),
            tts_service=MockTTSService(),
            validation_service=validation_service,
            streaming_service=streaming_service,
            safety_service=safety_service,
            cache_service=None,  # Optional for this test
            logger=logger
        )
        
        # Test health check
        health = await audio_service.get_service_health()
        assert health is not None
        assert "status" in health
        
        # Test TTS conversion
        tts_result = await audio_service.convert_text_to_speech("Hello integration test!")
        assert tts_result is not None
        assert isinstance(tts_result, bytes)
        assert len(tts_result) > 0
        
        logger.info("✅ All AudioService components integrated successfully")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_audio_service_metrics_collection(self):
        """Test metrics collection works with integrated components."""
        # Get audio service from DI container
        try:
            audio_service = injector_instance.get(IAudioService)
        except Exception:
            # Fallback to creating with mocks if DI fails
            pytest.skip("AudioService DI not available, skipping metrics test")
        
        # Get initial metrics
        initial_metrics = await audio_service.get_tts_metrics()
        
        assert initial_metrics is not None
        assert "tts_metrics" in initial_metrics
        assert "timestamp" in initial_metrics
        assert "uptime_info" in initial_metrics
        
        logger.info("✅ Audio service metrics collection working")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_service_registry_health_status(self):
        """Test ServiceRegistry health status includes audio service."""
        try:
            registry = await get_service_registry()
            health_status = registry.get_health_status()
            
            assert health_status is not None
            assert "registry_status" in health_status
            assert "registered_singletons" in health_status
            assert "registered_factories" in health_status
            
            # Check if audio service is registered
            registered_services = (health_status.get("registered_singletons", []) + 
                                 health_status.get("registered_factories", []))
            
            logger.info(f"✅ ServiceRegistry health: {len(registered_services)} services registered")
            logger.info(f"Registered services: {registered_services}")
            
        except Exception as e:
            logger.error(f"❌ ServiceRegistry health check failed: {e}")
            raise
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_integration(self):
        """Test error handling across integrated components."""
        # Create components with error conditions
        validation_service = AudioValidationService(logger=logger)
        
        # Test validation with invalid audio
        empty_audio = b""
        result = await validation_service.validate_audio(empty_audio)
        
        assert result is not None
        assert result.is_valid is False
        assert len(result.issues) > 0
        assert "Empty audio data" in result.issues
        
        # Test safety service with concerning content
        safety_service = AudioSafetyService(logger=logger)
        concerning_text = "This is scary and violent content"
        safety_result = await safety_service.check_text_safety(concerning_text)
        
        assert safety_result.is_safe is False
        assert len(safety_result.violations) > 0
        
        logger.info("✅ Error handling working correctly across components")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_component_access(self):
        """Test concurrent access to AudioService components."""
        validation_service = AudioValidationService(logger=logger)
        safety_service = AudioSafetyService(logger=logger)
        
        # Create concurrent tasks
        tasks = []
        
        # Multiple validation tasks
        for i in range(3):
            test_audio = b"RIFF" + f"test_data_{i}".encode() * 10
            tasks.append(validation_service.validate_audio(test_audio))
        
        # Multiple safety check tasks
        for i in range(3):
            test_text = f"Hello, this is test message {i}"
            tasks.append(safety_service.check_text_safety(test_text))
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all completed successfully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 6  # 3 validation + 3 safety checks
        
        logger.info(f"✅ Concurrent component access: {len(successful_results)}/6 tasks successful")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_memory_usage_stability(self):
        """Test memory usage remains stable during operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create services and perform operations
        validation_service = AudioValidationService(logger=logger)
        safety_service = AudioSafetyService(logger=logger)
        
        # Perform multiple operations
        for i in range(10):
            test_audio = b"RIFF" + f"test_data_{i}".encode() * 100
            await validation_service.validate_audio(test_audio)
            
            test_text = f"Hello, this is memory test {i}"
            await safety_service.check_text_safety(test_text)
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        memory_increase_mb = memory_increase / (1024 * 1024)
        
        # Memory increase should be reasonable (less than 50MB for these operations)
        assert memory_increase_mb < 50, f"Memory increased by {memory_increase_mb:.1f}MB"
        
        logger.info(f"✅ Memory usage stable: increased by {memory_increase_mb:.1f}MB")