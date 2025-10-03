import os
import hmac
import hashlib
DEVICE_ID = "test_device_001"
SECRET = os.getenv("ESP32_SHARED_SECRET", "46a1d7e1d6719f4a74404a01a7a18bd5734c824b461708a5123a5f42618c6bc5")
print('SECRET len', len(SECRET))
TOKEN = hmac.new(SECRET.encode(), DEVICE_ID.encode(), hashlib.sha256).hexdigest()
print('TOKEN', TOKEN)
