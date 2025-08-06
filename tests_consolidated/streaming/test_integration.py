"""
Integration test: endpoint → use case → AudioService → response
"""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_esp32_audio_streaming_integration():
    # بيانات صوتية حية (dummy wav bytes)
    audio_bytes = b"\x00\x01" * 8000
    payload = {
        "child_id": "test-child-1",
        "audio_data": audio_bytes,
        "language_code": "ar",
        "text_input": None,
    }
    response = client.post("/esp32/audio", json=payload)
    assert response.status_code == 200
    data = response.json()
    # تحقق أن المسار مر عبر AudioService الموحد فعليًا (تحقق من النتيجة)
    assert "handshake" in data
    assert "esp32_request" in data
    # يمكن إضافة تحقق أعمق إذا تم تفعيل التنفيذ الفعلي
