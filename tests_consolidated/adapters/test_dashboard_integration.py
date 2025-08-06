"""
Integration test: Dashboard endpoint returns real data from services/models.
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_dashboard_route_returns_real_data(monkeypatch):
    # Patch services to return predictable data
    class DummyUserService:
        async def get_children(self, parent_id):
            class DummyChild:
                id = "child1"
                name = "Ali"
                age = 8
            return [DummyChild()]
        async def get_usage_summary(self, parent_id):
            return {"total_sessions": 2}
        async def get_child_usage_report(self, child_id):
            return {"child_id": child_id, "minutes": 30}
        async def get_notifications(self, parent_id):
            return [{"message": "Test", "timestamp": "2025-07-30T12:00:00"}]
    class DummySafetyService:
        async def get_safety_overview(self, parent_id):
            return {"safe": True}
        async def get_child_status(self, child_id):
            return {"status": "active"}
        async def update_safety_setting(self, child_id, setting, value):
            return {"ok": True}
    monkeypatch.setattr("src.services.service_registry.get_user_service", lambda: DummyUserService())
    monkeypatch.setattr("src.services.service_registry.get_child_safety_service", lambda: DummySafetyService())

    response = client.get("/dashboard?parent_id=parent1")
    assert response.status_code == 200
    data = response.json()
    assert "children" in data and data["children"][0]["name"] == "Ali"
    assert "usage" in data and data["usage"]["total_sessions"] == 2
    assert "safety" in data and data["safety"]["safe"] is True
    assert "notifications" in data and data["notifications"][0]["message"] == "Test"
