"""
Tests for AI Provider Factory.
"""

import pytest
from unittest.mock import Mock, patch
from src.infrastructure.external.ai_providers.ai_factory import AIProviderFactory, AIProviderError


class TestAIProviderFactory:
    
    def test_get_supported_providers(self):
        providers = AIProviderFactory.get_supported_providers()
        assert "openai" in providers
        assert "claude" in providers
    
    def test_validate_api_key_empty(self):
        with pytest.raises(AIProviderError, match="API key cannot be empty"):
            AIProviderFactory._validate_api_key("")
    
    def test_validate_api_key_too_short(self):
        with pytest.raises(AIProviderError, match="API key appears to be invalid"):
            AIProviderFactory._validate_api_key("short")
    
    def test_validate_provider_empty(self):
        with pytest.raises(AIProviderError, match="Provider name cannot be empty"):
            AIProviderFactory._validate_provider("")
    
    def test_validate_provider_unsupported(self):
        with pytest.raises(AIProviderError, match="Unsupported provider"):
            AIProviderFactory._validate_provider("unknown")
    
    @patch('src.infrastructure.external.ai_providers.ai_factory.OpenAIClient')
    def test_get_openai_provider(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        result = AIProviderFactory.get_provider("openai", "valid_api_key_123")
        
        mock_openai.assert_called_once_with("valid_api_key_123")
        assert result == mock_client
    
    @patch('src.infrastructure.external.ai_providers.ai_factory.ClaudeClient')
    def test_get_claude_provider(self, mock_claude):
        mock_client = Mock()
        mock_claude.return_value = mock_client
        
        result = AIProviderFactory.get_provider("claude", "valid_api_key_123")
        
        mock_claude.assert_called_once_with("valid_api_key_123")
        assert result == mock_client
    
    def test_get_provider_case_insensitive(self):
        with patch('src.infrastructure.external.ai_providers.ai_factory.OpenAIClient') as mock_openai:
            AIProviderFactory.get_provider("OPENAI", "valid_api_key_123")
            mock_openai.assert_called_once()