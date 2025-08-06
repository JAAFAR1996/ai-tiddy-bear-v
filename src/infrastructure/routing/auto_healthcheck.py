import threading
import time
import os
from src.infrastructure.routing.route_manager import RouteManager
from src.infrastructure.logging.production_logger import get_logger


class AutoHealthcheckThread(threading.Thread):
    def __init__(self, route_manager: RouteManager, interval: int = 60):
        super().__init__(daemon=True)
        self.route_manager = route_manager
        self.interval = interval
        self.logger = get_logger("auto_healthcheck")
        self.running = True
        self.env = os.environ.get("ENV", "production").lower()

    def run(self):
        while self.running:
            try:
                summary = self.route_manager.get_registration_summary()
                if summary["route_health"] not in ("HEALTHY", "MINOR_ISSUES"):
                    self.logger.critical(
                        f"[AUTO-HEALTHCHECK] Route health problem: {summary}"
                    )
                    if self.env == "production":
                        # Here you would send to ELK/Sentry/Prometheus
                        pass
                else:
                    self.logger.info("[AUTO-HEALTHCHECK] All routes healthy.")
            except Exception as e:
                self.logger.critical(f"[AUTO-HEALTHCHECK] Exception: {e}")
                if self.env == "production":
                    # Here you would send to ELK/Sentry/Prometheus
                    pass
            time.sleep(self.interval)

    def stop(self):
        self.running = False
