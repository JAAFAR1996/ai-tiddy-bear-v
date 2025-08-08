import time
import requests
import os

APIS = [
    (
        "signup",
        "post",
        "/api/signup",
        {"email": os.environ.get("TEST_EMAIL", "test_parent@example.com"), "password": os.environ.get("TEST_PASSWORD", "Test1234!")},
    ),
    ("register_child", "post", "/api/child/register", {"name": "TestChild", "age": 7}),
    (
        "pair_device",
        "post",
        "/api/device/pair",
        {"child_id": 1, "device_id": "esp32-001", "pairing_code": "123456"},
    ),
    (
        "audio_interaction",
        "post",
        "/api/audio/interact",
        {"audio": "<base64-audio-data>"},
    ),
    ("receive_notification", "get", "/api/notifications", None),
    ("disconnect", "post", "/api/device/disconnect", None),
    ("recover", "post", "/api/device/recover", None),
]

BASE_URL = "http://localhost:8000"

with open("../logs/benchmarks/manual_latency_log.csv", "w", encoding="utf-8") as f:
    f.write("api,latency_seconds,status_code,timestamp\n")
    for api, method, endpoint, payload in APIS:
        url = BASE_URL + endpoint
        start = time.time()
        if method == "post":
            resp = requests.post(url, json=payload)
        else:
            resp = requests.get(url)
        latency = time.time() - start
        f.write(f"{api},{latency:.4f},{resp.status_code},{int(time.time())}\n")
        print(f"{api}: {latency:.3f}s, status: {resp.status_code}")
