"""
Tests for ESP32 Router
======================

Tests for ESP32 WebSocket endpoint.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.adapters.esp32_router import router, test_esp32_connection


class TestESP32Router:
    """Test ESP32 router endpoints."""

    @pytest.mark.asyncio
    async def test_test_connection_valid(self):
        """Test valid connection parameters."""
        with patch('src.adapters.esp32_router.validate_device_id', return_value=True):
            result = await test_esp32_connection("device123", 8)
            
            assert result["status"] == "valid"
            assert result["device_id"] == "device123"
            assert result["child_age"] == 8

    @pytest.mark.asyncio
    async def test_test_connection_invalid_device_id(self):
        """Test invalid device ID."""
        with patch('src.adapters.esp32_router.validate_device_id', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await test_esp32_connection("invalid", 8)
            
            assert exc_info.value.status_code == 400
            assert "Invalid device ID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_test_connection_invalid_age(self):
        """Test invalid child age."""
        with patch('src.adapters.esp32_router.validate_device_id', return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await test_esp32_connection("device123", 15)
            
            assert exc_info.value.status_code == 400
            assert "Invalid child age" in exc_info.value.detail

    def test_router_prefix(self):
        """Test router has correct prefix."""
        assert router.prefix == "/esp32"
        assert "ESP32" in router.tags