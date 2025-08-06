"""
Tests for OpenAI provider - real API integration tests
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.adapters.providers.openai_provider import (
    ProductionOpenAIProvider,
    OpenAIProviderError,
    OpenAIErrorType,
    SafetyFilterResult,
    OpenAIUsageStats,
    create_openai_provider,
    create_child_safe_provider
)
from src.core.value_objects.value_objects import SafetyLevel


class TestProductionOpenAIProvider:
    @pytest.fixture
    def mock_config(self):
        config = Mock()
        config.OPENAI_API_KEY = "test-api-key"
        config.OPENAI_MODEL = "gpt-3.5-turbo"
        config.OPENAI_MAX_TOKENS = 150
        config.OPENAI_TEMPERATURE = 0.7
        return config

    @pytest.fixture
    def provider(self, mock_config):
        with patch('src.adapters.providers.openai_provider.get_config', return_value=mock_config):
            return ProductionOpenAIProvider(
                api_key="test-key",
                model="gpt-3.5-turbo"
            )

    def test_init_with_api_key(self, mock_config):
        with patch('src.adapters.providers.openai_provider.get_config', return_value=mock_config):
            provider = ProductionOpenAIProvider(api_key="custom-key")
            assert provider.api_key == "custom-key"
            assert provider.model == "gpt-3.5-turbo"

    def test_init_without_api_key_raises_error(self, mock_config):
        mock_config.OPENAI_API_KEY = None
        with patch('src.adapters.providers.openai_provider.get_config', return_value=mock_config):
            with pytest.raises(ValueError) as exc:
                ProductionOpenAIProvider()
            assert "API key is required" in str(exc.value)

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, provider):
        mock_rate_limiter = Mock()
        mock_result = Mock()
        mock_result.allowed = True
        mock_rate_limiter.check_rate_limit = AsyncMock(return_value=mock_result)
        
        provider.rate_limiter = mock_rate_limiter
        
        result = await provider._check_rate_limit("child-123", Mock())
        
        assert result is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_denied(self, provider):
        mock_rate_limiter = Mock()
        mock_result = Mock()
        mock_result.allowed = False
        mock_result.reason = "Rate limit exceeded"
        mock_rate_limiter.check_rate_limit = AsyncMock(return_value=mock_result)
        
        provider.rate_limiter = mock_rate_limiter
        
        result = await provider._check_rate_limit("child-123", Mock())
        
        assert result is False
        assert provider.usage_stats.rate_limited_requests == 1

    @pytest.mark.asyncio
    async def test_validate_messages_valid(self, provider):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        # Should not raise exception
        await provider._validate_messages(messages)

    @pytest.mark.asyncio
    async def test_validate_messages_empty(self, provider):
        with pytest.raises(ValueError) as exc:
            await provider._validate_messages([])
        assert "cannot be empty" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_messages_missing_role(self, provider):
        messages = [{"content": "Hello"}]  # Missing role
        
        with pytest.raises(ValueError) as exc:
            await provider._validate_messages(messages)
        assert "must have a 'role' field" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_messages_invalid_role(self, provider):
        messages = [{"role": "invalid", "content": "Hello"}]
        
        with pytest.raises(ValueError) as exc:
            await provider._validate_messages(messages)
        assert "Invalid role" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_messages_content_too_long(self, provider):
        messages = [{"role": "user", "content": "x" * 2001}]  # Too long
        
        with pytest.raises(ValueError) as exc:
            await provider._validate_messages(messages)
        assert "content too long" in str(exc.value)

    @pytest.mark.asyncio
    async def test_filter_content_safety_disabled(self, provider):
        provider.enable_content_filter = False
        
        result = await provider._filter_content_safety("Any content")
        
        assert result.is_safe is True
        assert result.severity == SafetyLevel.SAFE

    @pytest.mark.asyncio
    async def test_filter_content_safety_safe_content(self, provider):
        with patch.object(provider.client.moderations, 'create') as mock_moderate:
            mock_result = Mock()
            mock_result.flagged = False
            mock_result.categories.model_dump.return_value = {"hate": False, "violence": False}
            mock_result.category_scores.hate = 0.1
            mock_result.category_scores.violence = 0.05
            
            mock_response = Mock()
            mock_response.results = [mock_result]
            mock_moderate.return_value = mock_response
            
            result = await provider._filter_content_safety("Hello, how are you?")
            
            assert result.is_safe is True
            assert result.severity == SafetyLevel.SAFE

    @pytest.mark.asyncio
    async def test_filter_content_safety_unsafe_content(self, provider):
        with patch.object(provider.client.moderations, 'create') as mock_moderate:
            mock_result = Mock()
            mock_result.flagged = True
            mock_result.categories.model_dump.return_value = {"hate": True, "violence": False}
            mock_result.category_scores.hate = 0.9
            mock_result.category_scores.violence = 0.1
            
            mock_response = Mock()
            mock_response.results = [mock_result]
            mock_moderate.return_value = mock_response
            
            result = await provider._filter_content_safety("Unsafe content")
            
            assert result.is_safe is False
            assert result.severity == SafetyLevel.CRITICAL
            assert "hate" in result.violations

    @pytest.mark.asyncio
    async def test_filter_content_safety_child_age_restriction(self, provider):
        with patch.object(provider.client.moderations, 'create') as mock_moderate:
            mock_result = Mock()
            mock_result.flagged = False
            mock_result.categories.model_dump.return_value = {}
            mock_result.category_scores.hate = 0.15  # Above threshold for young children
            
            mock_response = Mock()
            mock_response.results = [mock_result]
            mock_moderate.return_value = mock_response
            
            result = await provider._filter_content_safety("Some content", child_age=5)
            
            assert result.age_appropriate is False
            assert "child_safety" in result.violations

    def test_calculate_cost_gpt4(self, provider):
        provider.model = "gpt-4"
        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        
        cost = provider._calculate_cost(usage)
        
        expected = (100 * 0.03 / 1000) + (50 * 0.06 / 1000)
        assert cost == expected

    def test_calculate_cost_unknown_model(self, provider):
        provider.model = "unknown-model"
        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        
        cost = provider._calculate_cost(usage)
        
        # Should default to GPT-4 pricing
        expected = (100 * 0.03 / 1000) + (50 * 0.06 / 1000)
        assert cost == expected

    def test_update_usage_stats(self, provider):
        mock_response = Mock()
        mock_usage = Mock()
        mock_usage.model_dump.return_value = {
            "total_tokens": 150,
            "prompt_tokens": 100,
            "completion_tokens": 50
        }
        mock_response.usage = mock_usage
        
        provider._update_usage_stats(mock_response)
        
        assert provider.usage_stats.total_requests == 1
        assert provider.usage_stats.successful_requests == 1
        assert provider.usage_stats.total_tokens == 150
        assert provider.usage_stats.prompt_tokens == 100
        assert provider.usage_stats.completion_tokens == 50

    @pytest.mark.asyncio
    async def test_stream_chat_success(self, provider):
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch.object(provider, '_validate_messages') as mock_validate:
            with patch.object(provider, '_check_rate_limit', return_value=True):
                with patch.object(provider, '_filter_content_safety') as mock_filter:
                    mock_filter.return_value = SafetyFilterResult(
                        is_safe=True,
                        severity=SafetyLevel.SAFE,
                        violations=[],
                        confidence=1.0
                    )
                    
                    with patch.object(provider, '_retry_with_backoff') as mock_retry:
                        # Mock streaming response
                        async def mock_stream():
                            chunks = [
                                Mock(choices=[Mock(delta=Mock(content="Hello"))]),
                                Mock(choices=[Mock(delta=Mock(content=" there!"))])
                            ]
                            for chunk in chunks:
                                yield chunk
                        
                        mock_retry.return_value = mock_stream()
                        
                        result = []
                        async for chunk in provider.stream_chat(messages, "child-123", 8):
                            result.append(chunk)
                        
                        assert result == ["Hello", " there!"]

    @pytest.mark.asyncio
    async def test_stream_chat_rate_limited(self, provider):
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch.object(provider, '_validate_messages'):
            with patch.object(provider, '_check_rate_limit', return_value=False):
                with pytest.raises(OpenAIProviderError) as exc:
                    async for _ in provider.stream_chat(messages, "child-123"):
                        pass
                
                assert exc.value.error_type == OpenAIErrorType.RATE_LIMIT

    @pytest.mark.asyncio
    async def test_stream_chat_unsafe_input(self, provider):
        messages = [{"role": "user", "content": "Unsafe content"}]
        
        with patch.object(provider, '_validate_messages'):
            with patch.object(provider, '_check_rate_limit', return_value=True):
                with patch.object(provider, '_filter_content_safety') as mock_filter:
                    mock_filter.return_value = SafetyFilterResult(
                        is_safe=False,
                        severity=SafetyLevel.HIGH,
                        violations=["hate"],
                        confidence=0.8
                    )
                    
                    with pytest.raises(OpenAIProviderError) as exc:
                        async for _ in provider.stream_chat(messages, "child-123"):
                            pass
                    
                    assert exc.value.error_type == OpenAIErrorType.CONTENT_FILTER

    @pytest.mark.asyncio
    async def test_generate_completion(self, provider):
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch.object(provider, 'stream_chat') as mock_stream:
            async def mock_stream_gen():
                yield "Hello"
                yield " there!"
            
            mock_stream.return_value = mock_stream_gen()
            
            result = await provider.generate_completion(messages, "child-123", 8)
            
            assert result == "Hello there!"

    @pytest.mark.asyncio
    async def test_create_embedding_success(self, provider):
        with patch.object(provider, '_check_rate_limit', return_value=True):
            with patch.object(provider, '_filter_content_safety') as mock_filter:
                mock_filter.return_value = SafetyFilterResult(
                    is_safe=True,
                    severity=SafetyLevel.SAFE,
                    violations=[],
                    confidence=1.0
                )
                
                with patch.object(provider, '_retry_with_backoff') as mock_retry:
                    mock_response = Mock()
                    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
                    mock_response.usage.total_tokens = 10
                    mock_retry.return_value = mock_response
                    
                    result = await provider.create_embedding("Test text", child_id="child-123")
                    
                    assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_create_embedding_text_too_long(self, provider):
        long_text = "x" * 8001  # Too long
        
        with pytest.raises(ValueError) as exc:
            await provider.create_embedding(long_text)
        
        assert "under 8000 characters" in str(exc.value)

    @pytest.mark.asyncio
    async def test_moderate_content_success(self, provider):
        with patch.object(provider, '_retry_with_backoff') as mock_retry:
            mock_result = Mock()
            mock_result.flagged = False
            mock_result.categories.model_dump.return_value = {"hate": False}
            mock_result.category_scores.model_dump.return_value = {"hate": 0.1}
            
            mock_response = Mock()
            mock_response.results = [mock_result]
            mock_retry.return_value = mock_response
            
            result = await provider.moderate_content("Test content")
            
            assert result["flagged"] is False
            assert "categories" in result
            assert "category_scores" in result

    def test_get_usage_stats(self, provider):
        provider.usage_stats.total_requests = 10
        provider.usage_stats.successful_requests = 8
        
        stats = provider.get_usage_stats()
        
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert "success_rate" in stats

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        with patch.object(provider.client.models, 'list') as mock_list:
            mock_model = Mock()
            mock_model.id = "gpt-3.5-turbo"
            mock_response = Mock()
            mock_response.data = [mock_model]
            mock_list.return_value = mock_response
            
            result = await provider.health_check()
            
            assert result["status"] == "healthy"
            assert result["model_available"] is True

    @pytest.mark.asyncio
    async def test_health_check_model_unavailable(self, provider):
        with patch.object(provider.client.models, 'list') as mock_list:
            mock_model = Mock()
            mock_model.id = "other-model"  # Not our model
            mock_response = Mock()
            mock_response.data = [mock_model]
            mock_list.return_value = mock_response
            
            result = await provider.health_check()
            
            assert result["status"] == "degraded"
            assert result["model_available"] is False

    @pytest.mark.asyncio
    async def test_health_check_error(self, provider):
        with patch.object(provider.client.models, 'list') as mock_list:
            mock_list.side_effect = Exception("API Error")
            
            result = await provider.health_check()
            
            assert result["status"] == "unhealthy"
            assert "error" in result


class TestOpenAIUsageStats:
    def test_init(self):
        stats = OpenAIUsageStats()
        
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.total_cost == 0.0
        assert stats.start_time is not None

    def test_to_dict(self):
        stats = OpenAIUsageStats()
        stats.total_requests = 10
        stats.successful_requests = 8
        
        result = stats.to_dict()
        
        assert result["total_requests"] == 10
        assert result["successful_requests"] == 8
        assert result["success_rate"] == 0.8
        assert "uptime_seconds" in result


class TestFactoryFunctions:
    def test_create_openai_provider_default(self):
        with patch('src.adapters.providers.openai_provider.get_config') as mock_config:
            mock_config.return_value.OPENAI_API_KEY = "test-key"
            mock_config.return_value.OPENAI_MODEL = "gpt-3.5-turbo"
            
            provider = create_openai_provider()
            
            assert isinstance(provider, ProductionOpenAIProvider)

    def test_create_openai_provider_with_config(self):
        config = {
            "api_key": "custom-key",
            "model": "gpt-4",
            "temperature": 0.5
        }
        
        with patch('src.adapters.providers.openai_provider.get_config') as mock_get_config:
            mock_get_config.return_value.OPENAI_API_KEY = "default-key"
            
            provider = create_openai_provider(config)
            
            assert provider.api_key == "custom-key"
            assert provider.model == "gpt-4"
            assert provider.temperature == 0.5

    def test_create_child_safe_provider_young_child(self):
        with patch('src.adapters.providers.openai_provider.get_config') as mock_config:
            mock_config.return_value.OPENAI_API_KEY = "test-key"
            
            provider = create_child_safe_provider(child_age=5)
            
            assert provider.model == "gpt-3.5-turbo"
            assert provider.max_tokens == 100  # Restricted for young children
            assert provider.temperature == 0.3  # More predictable
            assert provider.child_safe_mode is True

    def test_create_child_safe_provider_older_child(self):
        with patch('src.adapters.providers.openai_provider.get_config') as mock_config:
            mock_config.return_value.OPENAI_API_KEY = "test-key"
            
            provider = create_child_safe_provider(child_age=12)
            
            assert provider.max_tokens == 300  # More tokens for older children
            assert provider.temperature == 0.5


class TestOpenAIProviderError:
    def test_init_basic(self):
        error = OpenAIProviderError("Test error")
        
        assert error.message == "Test error"
        assert error.error_type == OpenAIErrorType.API_ERROR
        assert error.correlation_id is not None

    def test_init_with_details(self):
        error = OpenAIProviderError(
            "Test error",
            error_type=OpenAIErrorType.RATE_LIMIT,
            correlation_id="test-123",
            details={"retry_after": 60}
        )
        
        assert error.error_type == OpenAIErrorType.RATE_LIMIT
        assert error.correlation_id == "test-123"
        assert error.details["retry_after"] == 60

    def test_to_dict(self):
        error = OpenAIProviderError(
            "Test error",
            error_type=OpenAIErrorType.CONTENT_FILTER
        )
        
        result = error.to_dict()
        
        assert result["message"] == "Test error"
        assert result["error_type"] == "content_filter"
        assert "timestamp" in result
        assert "correlation_id" in result