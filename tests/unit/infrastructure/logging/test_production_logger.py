"""
Production Logger Tests
=======================
Tests for comprehensive logging system with structured logging and child safety.
"""

import pytest
import json
import logging
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Log levels for the system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Log categories for filtering and routing."""
    SYSTEM = "system"
    SECURITY = "security"
    CHILD_SAFETY = "child_safety"
    COPPA_COMPLIANCE = "coppa_compliance"
    ESP32_DEVICE = "esp32_device"
    AI_INTERACTION = "ai_interaction"
    AUDIO_PROCESSING = "audio_processing"
    USER_ACTION = "user_action"


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    component: str
    user_id: str = None
    session_id: str = None
    device_id: str = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "category": self.category.value,
            "message": self.message,
            "component": self.component,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "device_id": self.device_id,
            "metadata": self.metadata or {}
        }


class ProductionLogger:
    """Production logging system with structured logging and compliance features."""
    
    def __init__(self, log_file: str = None, enable_console: bool = True):
        self.log_file = log_file
        self.enable_console = enable_console
        self.log_entries: List[LogEntry] = []
        self.sensitive_fields = {"password", "token", "secret", "key", "ssn", "credit_card"}
        
        # Setup Python logger
        self.logger = logging.getLogger("ai_teddy_bear")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Setup handlers
        self._setup_handlers()
        
        # COPPA compliance settings
        self.coppa_mode = os.getenv("COPPA_COMPLIANCE_MODE", "true").lower() == "true"
        self.data_retention_days = int(os.getenv("DATA_RETENTION_DAYS", "90"))
    
    def _setup_handlers(self):
        """Setup logging handlers."""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        if self.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File handler
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize sensitive data from logs."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in self.sensitive_fields:
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        return data
    
    def _apply_coppa_filtering(self, log_entry: LogEntry) -> LogEntry:
        """Apply COPPA compliance filtering to log entries."""
        if not self.coppa_mode:
            return log_entry
        
        # Remove or hash PII for children under 13
        if log_entry.metadata and log_entry.metadata.get("user_age", 0) < 13:
            # Hash user_id for children
            if log_entry.user_id:
                import hashlib
                log_entry.user_id = hashlib.sha256(log_entry.user_id.encode()).hexdigest()[:8]
            
            # Remove potentially identifying metadata
            if log_entry.metadata:
                coppa_safe_metadata = {}
                safe_fields = {"interaction_type", "response_time", "success", "error_code"}
                for key, value in log_entry.metadata.items():
                    if key in safe_fields:
                        coppa_safe_metadata[key] = value
                log_entry.metadata = coppa_safe_metadata
        
        return log_entry
    
    def log(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        component: str,
        user_id: str = None,
        session_id: str = None,
        device_id: str = None,
        **metadata
    ):
        """Log a structured message."""
        # Sanitize metadata
        sanitized_metadata = self._sanitize_data(metadata)
        
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            message=message,
            component=component,
            user_id=user_id,
            session_id=session_id,
            device_id=device_id,
            metadata=sanitized_metadata
        )
        
        # Apply COPPA filtering
        log_entry = self._apply_coppa_filtering(log_entry)
        
        # Store log entry
        self.log_entries.append(log_entry)
        
        # Log to Python logger
        log_data = log_entry.to_dict()
        log_message = f"{message} | {json.dumps(log_data, default=str)}"
        
        if level == LogLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.logger.error(log_message)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_message)
    
    def debug(self, category: LogCategory, message: str, component: str, **kwargs):
        """Log debug message."""
        self.log(LogLevel.DEBUG, category, message, component, **kwargs)
    
    def info(self, category: LogCategory, message: str, component: str, **kwargs):
        """Log info message."""
        self.log(LogLevel.INFO, category, message, component, **kwargs)
    
    def warning(self, category: LogCategory, message: str, component: str, **kwargs):
        """Log warning message."""
        self.log(LogLevel.WARNING, category, message, component, **kwargs)
    
    def error(self, category: LogCategory, message: str, component: str, **kwargs):
        """Log error message."""
        self.log(LogLevel.ERROR, category, message, component, **kwargs)
    
    def critical(self, category: LogCategory, message: str, component: str, **kwargs):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, category, message, component, **kwargs)
    
    def log_child_interaction(
        self,
        message: str,
        user_id: str,
        interaction_type: str,
        success: bool = True,
        **metadata
    ):
        """Log child interaction with special COPPA handling."""
        self.info(
            LogCategory.CHILD_SAFETY,
            message,
            "child_interaction",
            user_id=user_id,
            interaction_type=interaction_type,
            success=success,
            **metadata
        )
    
    def log_security_event(
        self,
        message: str,
        event_type: str,
        severity: str = "medium",
        **metadata
    ):
        """Log security-related events."""
        level = LogLevel.WARNING if severity == "medium" else LogLevel.CRITICAL
        self.log(
            level,
            LogCategory.SECURITY,
            message,
            "security_monitor",
            event_type=event_type,
            severity=severity,
            **metadata
        )
    
    def log_esp32_event(
        self,
        message: str,
        device_id: str,
        event_type: str,
        **metadata
    ):
        """Log ESP32 device events."""
        self.info(
            LogCategory.ESP32_DEVICE,
            message,
            "esp32_handler",
            device_id=device_id,
            event_type=event_type,
            **metadata
        )
    
    def get_logs(
        self,
        category: LogCategory = None,
        level: LogLevel = None,
        component: str = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """Retrieve filtered logs."""
        filtered_logs = self.log_entries
        
        if category:
            filtered_logs = [log for log in filtered_logs if log.category == category]
        
        if level:
            filtered_logs = [log for log in filtered_logs if log.level == level]
        
        if component:
            filtered_logs = [log for log in filtered_logs if log.component == component]
        
        return filtered_logs[-limit:]
    
    def export_logs(self, file_path: str, format: str = "json"):
        """Export logs to file."""
        logs_data = [log.to_dict() for log in self.log_entries]
        
        with open(file_path, 'w') as f:
            if format == "json":
                json.dump(logs_data, f, indent=2, default=str)
            elif format == "csv":
                import csv
                if logs_data:
                    writer = csv.DictWriter(f, fieldnames=logs_data[0].keys())
                    writer.writeheader()
                    writer.writerows(logs_data)
    
    def clear_old_logs(self):
        """Clear logs older than retention period (COPPA compliance)."""
        if not self.coppa_mode:
            return
        
        cutoff_date = datetime.now() - timedelta(days=self.data_retention_days)
        self.log_entries = [
            log for log in self.log_entries
            if log.timestamp > cutoff_date
        ]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get logging metrics."""
        total_logs = len(self.log_entries)
        
        level_counts = {}
        category_counts = {}
        component_counts = {}
        
        for log in self.log_entries:
            level_counts[log.level.value] = level_counts.get(log.level.value, 0) + 1
            category_counts[log.category.value] = category_counts.get(log.category.value, 0) + 1
            component_counts[log.component] = component_counts.get(log.component, 0) + 1
        
        return {
            "total_logs": total_logs,
            "level_distribution": level_counts,
            "category_distribution": category_counts,
            "component_distribution": component_counts,
            "coppa_mode": self.coppa_mode,
            "retention_days": self.data_retention_days
        }


@pytest.fixture
def temp_log_file():
    """Create temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def production_logger(temp_log_file):
    """Create production logger for testing."""
    return ProductionLogger(log_file=temp_log_file, enable_console=False)


@pytest.mark.asyncio
class TestProductionLogger:
    """Test production logging system."""
    
    def test_logger_initialization(self, production_logger):
        """Test logger initialization and setup."""
        assert production_logger.logger.name == "ai_teddy_bear"
        assert production_logger.logger.level == logging.DEBUG
        assert len(production_logger.log_entries) == 0
        assert production_logger.coppa_mode is True
    
    def test_basic_logging(self, production_logger):
        """Test basic logging functionality."""
        # Log different levels
        production_logger.debug(
            LogCategory.SYSTEM,
            "Debug message",
            "test_component",
            test_data="debug_value"
        )
        
        production_logger.info(
            LogCategory.SYSTEM,
            "Info message",
            "test_component",
            test_data="info_value"
        )
        
        production_logger.warning(
            LogCategory.SYSTEM,
            "Warning message",
            "test_component",
            test_data="warning_value"
        )
        
        production_logger.error(
            LogCategory.SYSTEM,
            "Error message",
            "test_component",
            test_data="error_value"
        )
        
        production_logger.critical(
            LogCategory.SYSTEM,
            "Critical message",
            "test_component",
            test_data="critical_value"
        )
        
        # Verify logs stored
        assert len(production_logger.log_entries) == 5
        
        # Verify log levels
        levels = [log.level for log in production_logger.log_entries]
        assert LogLevel.DEBUG in levels
        assert LogLevel.INFO in levels
        assert LogLevel.WARNING in levels
        assert LogLevel.ERROR in levels
        assert LogLevel.CRITICAL in levels
    
    def test_structured_logging(self, production_logger):
        """Test structured logging with metadata."""
        production_logger.info(
            LogCategory.AI_INTERACTION,
            "AI response generated",
            "conversation_service",
            user_id="child_123",
            session_id="session_456",
            device_id="esp32_001",
            response_time=150.5,
            tokens_used=45,
            model="gpt-4"
        )
        
        # Verify structured data
        log_entry = production_logger.log_entries[0]
        assert log_entry.category == LogCategory.AI_INTERACTION
        assert log_entry.user_id == "child_123"
        assert log_entry.session_id == "session_456"
        assert log_entry.device_id == "esp32_001"
        assert log_entry.metadata["response_time"] == 150.5
        assert log_entry.metadata["tokens_used"] == 45
        assert log_entry.metadata["model"] == "gpt-4"
    
    def test_sensitive_data_sanitization(self, production_logger):
        """Test sanitization of sensitive data."""
        production_logger.info(
            LogCategory.SECURITY,
            "User authentication",
            "auth_service",
            user_id="child_123",
            password="secret123",
            api_key="sk-1234567890",
            token="bearer_token_xyz",
            safe_data="this_is_ok"
        )
        
        # Verify sensitive data redacted
        log_entry = production_logger.log_entries[0]
        assert log_entry.metadata["password"] == "[REDACTED]"
        assert log_entry.metadata["api_key"] == "[REDACTED]"
        assert log_entry.metadata["token"] == "[REDACTED]"
        assert log_entry.metadata["safe_data"] == "this_is_ok"
    
    def test_coppa_compliance_filtering(self, production_logger):
        """Test COPPA compliance filtering for child users."""
        # Log for child user (under 13)
        production_logger.info(
            LogCategory.CHILD_SAFETY,
            "Child interaction logged",
            "interaction_service",
            user_id="child_123",
            user_age=7,
            full_name="Johnny Doe",
            interaction_type="voice_chat",
            response_time=200
        )
        
        # Verify COPPA filtering applied
        log_entry = production_logger.log_entries[0]
        
        # User ID should be hashed
        assert log_entry.user_id != "child_123"
        assert len(log_entry.user_id) == 8  # Truncated hash
        
        # Only safe metadata should remain
        assert "interaction_type" in log_entry.metadata
        assert "response_time" in log_entry.metadata
        assert "full_name" not in log_entry.metadata
        assert "user_age" not in log_entry.metadata
    
    def test_child_interaction_logging(self, production_logger):
        """Test specialized child interaction logging."""
        production_logger.log_child_interaction(
            "Child asked about bedtime story",
            user_id="child_123",
            interaction_type="story_request",
            success=True,
            story_category="fairy_tale",
            duration_seconds=45
        )
        
        # Verify child interaction log
        log_entry = production_logger.log_entries[0]
        assert log_entry.category == LogCategory.CHILD_SAFETY
        assert log_entry.component == "child_interaction"
        assert log_entry.metadata["interaction_type"] == "story_request"
        assert log_entry.metadata["success"] is True
    
    def test_security_event_logging(self, production_logger):
        """Test security event logging."""
        production_logger.log_security_event(
            "Multiple failed login attempts detected",
            event_type="brute_force_attempt",
            severity="high",
            ip_address="192.168.1.100",
            attempt_count=5,
            user_id="child_123"
        )
        
        # Verify security log
        log_entry = production_logger.log_entries[0]
        assert log_entry.category == LogCategory.SECURITY
        assert log_entry.level == LogLevel.CRITICAL  # High severity
        assert log_entry.metadata["event_type"] == "brute_force_attempt"
        assert log_entry.metadata["attempt_count"] == 5
    
    def test_esp32_event_logging(self, production_logger):
        """Test ESP32 device event logging."""
        production_logger.log_esp32_event(
            "ESP32 device connected",
            device_id="esp32_teddy_001",
            event_type="device_connection",
            battery_level=85,
            wifi_strength=-45,
            firmware_version="1.2.3"
        )
        
        # Verify ESP32 log
        log_entry = production_logger.log_entries[0]
        assert log_entry.category == LogCategory.ESP32_DEVICE
        assert log_entry.device_id == "esp32_teddy_001"
        assert log_entry.metadata["event_type"] == "device_connection"
        assert log_entry.metadata["battery_level"] == 85
    
    def test_log_filtering_and_retrieval(self, production_logger):
        """Test log filtering and retrieval."""
        # Add various logs
        production_logger.info(LogCategory.SYSTEM, "System message", "system")
        production_logger.error(LogCategory.SECURITY, "Security error", "security")
        production_logger.warning(LogCategory.CHILD_SAFETY, "Child safety warning", "safety")
        production_logger.debug(LogCategory.ESP32_DEVICE, "ESP32 debug", "esp32")
        
        # Test category filtering
        security_logs = production_logger.get_logs(category=LogCategory.SECURITY)
        assert len(security_logs) == 1
        assert security_logs[0].category == LogCategory.SECURITY
        
        # Test level filtering
        error_logs = production_logger.get_logs(level=LogLevel.ERROR)
        assert len(error_logs) == 1
        assert error_logs[0].level == LogLevel.ERROR
        
        # Test component filtering
        system_logs = production_logger.get_logs(component="system")
        assert len(system_logs) == 1
        assert system_logs[0].component == "system"
    
    def test_log_export(self, production_logger, temp_log_file):
        """Test log export functionality."""
        # Add some logs
        production_logger.info(LogCategory.SYSTEM, "Test message 1", "component1")
        production_logger.error(LogCategory.SECURITY, "Test message 2", "component2")
        
        # Export to JSON
        json_file = temp_log_file + ".json"
        production_logger.export_logs(json_file, format="json")
        
        # Verify JSON export
        assert os.path.exists(json_file)
        
        with open(json_file, 'r') as f:
            exported_data = json.load(f)
        
        assert len(exported_data) == 2
        assert exported_data[0]["message"] == "Test message 1"
        assert exported_data[1]["message"] == "Test message 2"
        
        # Cleanup
        os.unlink(json_file)
    
    def test_metrics_collection(self, production_logger):
        """Test logging metrics collection."""
        # Add various logs
        production_logger.info(LogCategory.SYSTEM, "Info message", "component1")
        production_logger.error(LogCategory.SECURITY, "Error message", "component2")
        production_logger.warning(LogCategory.CHILD_SAFETY, "Warning message", "component1")
        production_logger.debug(LogCategory.ESP32_DEVICE, "Debug message", "component3")
        
        # Get metrics
        metrics = production_logger.get_metrics()
        
        # Verify metrics
        assert metrics["total_logs"] == 4
        assert metrics["level_distribution"]["INFO"] == 1
        assert metrics["level_distribution"]["ERROR"] == 1
        assert metrics["level_distribution"]["WARNING"] == 1
        assert metrics["level_distribution"]["DEBUG"] == 1
        
        assert metrics["category_distribution"]["system"] == 1
        assert metrics["category_distribution"]["security"] == 1
        assert metrics["category_distribution"]["child_safety"] == 1
        assert metrics["category_distribution"]["esp32_device"] == 1
        
        assert metrics["component_distribution"]["component1"] == 2
        assert metrics["component_distribution"]["component2"] == 1
        assert metrics["component_distribution"]["component3"] == 1
    
    def test_nested_data_sanitization(self, production_logger):
        """Test sanitization of nested sensitive data."""
        production_logger.info(
            LogCategory.SYSTEM,
            "Complex data logging",
            "test_component",
            user_data={
                "username": "child_user",
                "password": "secret123",
                "preferences": {
                    "api_key": "sk-abcdef",
                    "theme": "dark"
                },
                "tokens": ["token1", "token2"]
            }
        )
        
        # Verify nested sanitization
        log_entry = production_logger.log_entries[0]
        user_data = log_entry.metadata["user_data"]
        
        assert user_data["username"] == "child_user"
        assert user_data["password"] == "[REDACTED]"
        assert user_data["preferences"]["api_key"] == "[REDACTED]"
        assert user_data["preferences"]["theme"] == "dark"
        assert user_data["tokens"] == ["token1", "token2"]  # Not in sensitive fields
    
    @patch.dict(os.environ, {"COPPA_COMPLIANCE_MODE": "false"})
    def test_coppa_mode_disabled(self):
        """Test logger behavior when COPPA mode is disabled."""
        logger = ProductionLogger(enable_console=False)
        
        # Log child interaction without COPPA filtering
        logger.info(
            LogCategory.CHILD_SAFETY,
            "Child interaction",
            "test_component",
            user_id="child_123",
            user_age=7,
            full_name="Johnny Doe"
        )
        
        # Verify no COPPA filtering applied
        log_entry = logger.log_entries[0]
        assert log_entry.user_id == "child_123"  # Not hashed
        assert "full_name" in log_entry.metadata  # Not removed
        assert log_entry.metadata["user_age"] == 7  # Not removed
    
    def test_concurrent_logging(self, production_logger):
        """Test concurrent logging operations."""
        import threading
        import time
        
        def log_messages(thread_id: int):
            for i in range(10):
                production_logger.info(
                    LogCategory.SYSTEM,
                    f"Message from thread {thread_id}",
                    f"component_{thread_id}",
                    message_number=i
                )
                time.sleep(0.001)  # Small delay
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_messages, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all messages logged
        assert len(production_logger.log_entries) == 50
        
        # Verify messages from all threads present
        thread_messages = {}
        for log in production_logger.log_entries:
            component = log.component
            if component not in thread_messages:
                thread_messages[component] = 0
            thread_messages[component] += 1
        
        assert len(thread_messages) == 5  # 5 threads
        for count in thread_messages.values():
            assert count == 10  # 10 messages per thread