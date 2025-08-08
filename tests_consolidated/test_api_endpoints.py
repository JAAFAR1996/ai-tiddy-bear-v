import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_chat_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "message": "Hello Teddy!",
            "child_id": "test-child-1",
            "child_age": 7,
        }
        response = await ac.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        assert "response" in response.json()


@pytest.mark.asyncio
async def test_auth_login_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"email": "parent@example.com", "password": "StrongPassword123"}
        response = await ac.post("/api/v1/auth/login", json=payload)
        assert response.status_code in [200, 400, 403, 429]  # يعتمد على البيانات


@pytest.mark.asyncio
async def test_esp32_audio_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"child_id": "test-child-1", "text_input": "Say hello"}
        response = await ac.post("/api/v1/esp32/audio", json=payload)
        assert response.status_code in [200, 400, 403]


@pytest.mark.asyncio
async def test_dashboard_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/dashboard")
        assert response.status_code in [200, 401, 403]


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
