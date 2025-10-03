#!/usr/bin/env python3
"""
إنشاء Pairing Code لـ ESP32
==========================
هذا السكريبت ينشئ pairing code للجهاز ويحفظه في قاعدة البيانات
"""

import secrets
import hashlib
import requests
import json
from datetime import datetime, timedelta

# إعدادات السيرفر
SERVER_URL = "http://localhost:8000"
DEVICE_ID = "teddy-esp32-ccdba795baa4"  # من ESP32 logs
CHILD_ID = "02a154bf-4e0b-4532-ac07-18d68fc0e20f"  # من الاختبارات السابقة


def generate_pairing_code(device_id):
    """إنشاء pairing code فريد للجهاز"""
    # إنشاء pairing code عشوائي
    pairing_code = secrets.token_hex(16)  # 32 character hex string
    print(f"🔑 Generated Pairing Code: {pairing_code}")
    return pairing_code


def create_device_pairing(device_id, child_id, pairing_code):
    """إنشاء pairing في قاعدة البيانات"""

    # بيانات الطلب - استخدام claim endpoint
    import hmac
    import time
    import hashlib

    # إنشاء nonce فريد - يجب أن يكون hex فقط
    nonce = secrets.token_hex(16)  # 32 character hex string

    # إنشاء HMAC signature (مبسط للتطوير)
    secret = "dev_secret_key"  # في الإنتاج: استخدام secret حقيقي
    message = f"{device_id}:{child_id}:{nonce}"
    hmac_signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    pairing_data = {
        "device_id": device_id,
        "child_id": child_id,
        "nonce": nonce,
        "hmac_hex": hmac_signature,
        "device_name": "AI Teddy Bear ESP32",
        "device_type": "teddy_bear"
    }

    try:
        # إرسال طلب claim device
        response = requests.post(
            f"{SERVER_URL}/api/v1/pair/claim",
            json=pairing_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            print("✅ Device claimed successfully!")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"❌ Failed to claim device: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False


def verify_device_status(device_id):
    """التحقق من حالة الجهاز"""

    try:
        # محاولة الاتصال بـ WebSocket endpoint
        response = requests.get(
            f"{SERVER_URL}/api/v1/esp32/status",
            params={"device_id": device_id},
            timeout=10
        )

        if response.status_code == 200:
            print("✅ Device status verified successfully!")
            return True
        else:
            print(f"❌ Device status check failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False


def main():
    print("🧸 AI Teddy Bear - ESP32 Pairing Code Generator")
    print("=" * 50)

    # 1. إنشاء pairing code
    pairing_code = generate_pairing_code(DEVICE_ID)

    # 2. إنشاء pairing في قاعدة البيانات
    print(f"\n📝 Creating device pairing...")
    print(f"Device ID: {DEVICE_ID}")
    print(f"Child ID: {CHILD_ID}")
    print(f"Pairing Code: {pairing_code}")

    success = create_device_pairing(DEVICE_ID, CHILD_ID, pairing_code)

    if success:
        # 3. التحقق من حالة الجهاز
        print(f"\n🔍 Verifying device status...")
        verify_success = verify_device_status(DEVICE_ID)

        if verify_success:
            print("\n🎉 SUCCESS! ESP32 device is ready!")
            print(f"\n📋 Next Steps:")
            print(f"1. ESP32 device is now claimed and ready")
            print(f"2. Device should be able to authenticate")
            print(f"3. Test WebSocket connection")
            print(f"\n⚠️ Note: If still having issues, try switching to development mode:")
            print(f"   - Set PRODUCTION_MODE=0 in ESP32")
            print(f"   - Use local development environment")
        else:
            print("\n❌ Device status verification failed")
            print("⚠️ Try switching ESP32 to development mode")
    else:
        print("\n❌ Failed to claim device")
        print("⚠️ Try switching ESP32 to development mode")


if __name__ == "__main__":
    main()
