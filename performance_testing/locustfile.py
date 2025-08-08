from locust import HttpUser, TaskSet, task, between
import random
import time
import os

# Load test user credentials from environment variables
TEST_USER = {
    "email": os.environ.get("TEST_EMAIL", "test_parent@example.com"), 
    "password": os.environ.get("TEST_PASSWORD", "Test1234!")
}

# Validate required environment variables
if not os.environ.get("TEST_EMAIL") or not os.environ.get("TEST_PASSWORD"):
    raise EnvironmentError("TEST_EMAIL and TEST_PASSWORD environment variables are required for production testing")
TEST_CHILD = {"name": "TestChild", "age": 7}
TEST_DEVICE = {"device_id": "esp32-001", "pairing_code": "123456"}


class TeddyBearTasks(TaskSet):
    def on_start(self):
        self.register_parent()
        self.child_id = None
        self.device_token = None

    @task(1)
    def register_parent(self):
        # API expects: email, password, name, phone (optional)
        parent_data = {
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
            "name": "Test Parent",
            "phone": "",
        }
        start = time.time()
        resp = self.client.post("/api/auth/register", json=parent_data)
        latency = time.time() - start
        self.parent_token = resp.json().get("access_token", "")
        self._log_latency("signup", latency, resp.status_code)

    @task(1)
    def register_child(self):
        headers = {"Authorization": f"Bearer {self.parent_token}"}
        start = time.time()
        resp = self.client.post("/api/child/register", json=TEST_CHILD, headers=headers)
        latency = time.time() - start
        if resp.status_code == 200:
            self.child_id = resp.json().get("child_id")
        self._log_latency("register_child", latency, resp.status_code)

    @task(1)
    def pair_device(self):
        if not self.child_id:
            return
        headers = {"Authorization": f"Bearer {self.parent_token}"}
        data = {"child_id": self.child_id, **TEST_DEVICE}
        start = time.time()
        resp = self.client.post("/api/device/pair", json=data, headers=headers)
        latency = time.time() - start
        if resp.status_code == 200:
            self.device_token = resp.json().get("device_token")
        self._log_latency("pair_device", latency, resp.status_code)

    @task(2)
    def audio_interaction(self):
        if not self.device_token:
            return
        headers = {"Authorization": f"Bearer {self.device_token}"}
        data = {"audio": "<base64-audio-data>"}
        start = time.time()
        resp = self.client.post("/api/audio/interact", json=data, headers=headers)
        latency = time.time() - start
        self._log_latency("audio_interaction", latency, resp.status_code)

    @task(1)
    def receive_notification(self):
        if not self.device_token:
            return
        headers = {"Authorization": f"Bearer {self.device_token}"}
        start = time.time()
        resp = self.client.get("/api/notifications", headers=headers)
        latency = time.time() - start
        self._log_latency("receive_notification", latency, resp.status_code)

    @task(1)
    def disconnect_and_recover(self):
        # محاكاة قطع الاتصال وإعادة الاتصال
        if not self.device_token:
            return
        headers = {"Authorization": f"Bearer {self.device_token}"}
        # قطع الاتصال
        start = time.time()
        resp = self.client.post("/api/device/disconnect", headers=headers)
        latency = time.time() - start
        self._log_latency("disconnect", latency, resp.status_code)
        # إعادة الاتصال
        start = time.time()
        resp = self.client.post("/api/device/recover", headers=headers)
        latency = time.time() - start
        self._log_latency("recover", latency, resp.status_code)

    def _log_latency(self, api, latency, status):
        import os

        log_dir = os.path.join(os.path.dirname(__file__), "logs", "benchmarks")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "latency_log.csv")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{api},{latency:.4f},{status},{int(time.time())}\n")


class WebsiteUser(HttpUser):
    tasks = [TeddyBearTasks]
    wait_time = between(1, 3)
    host = "http://localhost:8000"  # عدلها إذا كان السيرفر في مكان آخر
