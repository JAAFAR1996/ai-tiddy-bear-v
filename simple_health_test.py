#!/usr/bin/env python3
"""
Simple health test without dependencies
"""
import requests
import json

def test_server():
    """Test server endpoints without dependencies."""
    base_url = "https://ai-tiddy-bear-v-xuqy.onrender.com"
    
    tests = [
        ("Root", "/"),
        ("ESP32 Config", "/api/v1/esp32/config"), 
        ("Health", "/health"),
        ("WebSocket test", "/ws/esp32/connect")
    ]
    
    print("🧸 AI Teddy Bear Server Health Test")
    print("=" * 50)
    
    for name, path in tests:
        try:
            response = requests.get(f"{base_url}{path}", timeout=10)
            status = "✅" if response.status_code < 400 else "❌"
            
            print(f"{status} {name}: {response.status_code}")
            
            if path == "/health" and response.status_code != 200:
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Raw response: {response.text[:100]}")
                    
        except Exception as e:
            print(f"❌ {name}: Connection failed - {e}")
    
    print("\n🔍 Environment Variables Status:")
    required_vars = [
        "DATABASE_URL", "REDIS_URL", "OPENAI_API_KEY", 
        "ELEVENLABS_API_KEY", "ESP32_SHARED_SECRET"
    ]
    
    # يُفترض أن يكون لديك access للـ server logs لمعرفة أي متغير مفقود
    print("   Check server logs for missing environment variables")

if __name__ == "__main__":
    test_server()