"""
Tests for Speech-to-Text Factory.
"""

import pytest
from unittest.mock import Mock, patch
from src.infrastructure.external.speech_services.speech_factory import SpeechToTextFactory, SpeechProviderError


class TestSpeechToTextFactory:
    
    def test_get_supported_providers(self):
        providers = SpeechToTextFactory.get_supported_providers()
        assert "google" in providers
        assert "azure" in providers
    
    def test_validate_api_key_empty(self):
        with pytest.raises(SpeechProviderError, match="API key cannot be empty"):
            SpeechToTextFactory._validate_api_key("")
    
    def test_validate_provider_empty(self):
        with pytest.raises(SpeechProviderError, match="Provider name cannot be empty"):
            SpeechToTextFactory._validate_provider("")
    
    def test_validate_provider_unsupported(self):
        with pytest.raises(SpeechProviderError, match="Unsupported provider"):
            SpeechToTextFactory._validate_provider("unknown")
    
    @patch('src.infrastructure.external.speech_services.speech_factory.GoogleSpeechToText')
    def test_get_google_provider(self, mock_google):
        mock_client = Mock()
        mock_google.return_value = mock_client
        
        result = SpeechToTextFactory.get_provider("google", "valid_key")
        
        mock_google.assert_called_once_with("valid_key")
        assert result == mock_client
    
    @patch('src.infrastructure.external.speech_services.speech_factory.AzureSpeechToText')
    def test_get_azure_provider(self, mock_azure):
        mock_client = Mock()
        mock_azure.return_value = mock_client
        
        result = SpeechToTextFactory.get_provider("azure", "valid_key")
        
        mock_azure.assert_called_once_with("valid_key")
        assert result == mock_client