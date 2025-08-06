"""Adapter interfaces for dependency inversion.

All adapter contracts are defined here to eliminate circular dependencies
and ensure proper integration layer separation.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Union
from uuid import UUID
from datetime import datetime


class IDatabaseAdapter(ABC):
    """Interface for database connectivity."""

    @abstractmethod
    async def connect(self, connection_string: str) -> bool:
        """Connect to database."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from database."""
        pass

    @abstractmethod
    async def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> Any:
        """Execute database query."""
        pass

    @abstractmethod
    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple queries in transaction."""
        pass

    @abstractmethod
    async def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check database health."""
        pass


class IWebAdapter(ABC):
    """Interface for web request/response handling."""

    @abstractmethod
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming web request."""
        pass

    @abstractmethod
    async def create_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Create web response."""
        pass

    @abstractmethod
    async def handle_websocket_connection(self, connection_data: Dict[str, Any]) -> bool:
        """Handle websocket connection."""
        pass

    @abstractmethod
    async def send_websocket_message(self, connection_id: str, message: str) -> bool:
        """Send websocket message."""
        pass

    @abstractmethod
    async def validate_request_data(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate request data against schema."""
        pass


class ICacheAdapter(ABC):
    """Interface for caching services."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def clear_pattern(self, pattern: str) -> int:
        """Clear keys matching pattern."""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class IEmailAdapter(ABC):
    """Interface for email services."""

    @abstractmethod
    async def send_email(
        self, 
        to: Union[str, List[str]], 
        subject: str, 
        body: str, 
        html_body: Optional[str] = None
    ) -> bool:
        """Send email."""
        pass

    @abstractmethod
    async def send_template_email(
        self, 
        to: Union[str, List[str]], 
        template_id: str, 
        variables: Dict[str, Any]
    ) -> bool:
        """Send email using template."""
        pass

    @abstractmethod
    async def validate_email_address(self, email: str) -> bool:
        """Validate email address format."""
        pass

    @abstractmethod
    async def get_delivery_status(self, message_id: str) -> Dict[str, Any]:
        """Get email delivery status."""
        pass


class IStorageAdapter(ABC):
    """Interface for file storage services."""

    @abstractmethod
    async def upload_file(self, file_path: str, file_data: bytes) -> str:
        """Upload file and return URL."""
        pass

    @abstractmethod
    async def download_file(self, file_url: str) -> bytes:
        """Download file by URL."""
        pass

    @abstractmethod
    async def delete_file(self, file_url: str) -> bool:
        """Delete file by URL."""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_url: str) -> Dict[str, Any]:
        """Get file metadata."""
        pass

    @abstractmethod
    async def generate_presigned_url(self, file_path: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for file access."""
        pass


class IExternalAPIAdapter(ABC):
    """Interface for external API integrations."""

    @abstractmethod
    async def make_request(
        self, 
        method: str, 
        url: str, 
        headers: Dict[str, str] = None,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to external API."""
        pass

    @abstractmethod
    async def authenticate_api(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with external API."""
        pass

    @abstractmethod
    async def handle_rate_limiting(self, response: Dict[str, Any]) -> bool:
        """Handle API rate limiting."""
        pass

    @abstractmethod
    async def validate_api_response(self, response: Dict[str, Any]) -> bool:
        """Validate API response."""
        pass

    @abstractmethod
    async def get_api_status(self) -> Dict[str, Any]:
        """Get external API status."""
        pass


class IMessageQueueAdapter(ABC):
    """Interface for message queue services."""

    @abstractmethod
    async def publish_message(
        self, 
        queue_name: str, 
        message: Dict[str, Any], 
        priority: int = 0
    ) -> bool:
        """Publish message to queue."""
        pass

    @abstractmethod
    async def consume_message(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Consume message from queue."""
        pass

    @abstractmethod
    async def acknowledge_message(self, message_id: str) -> bool:
        """Acknowledge message processing."""
        pass

    @abstractmethod
    async def create_queue(self, queue_name: str, config: Dict[str, Any]) -> bool:
        """Create new queue."""
        pass

    @abstractmethod
    async def delete_queue(self, queue_name: str) -> bool:
        """Delete queue."""
        pass

    @abstractmethod
    async def get_queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """Get queue statistics."""
        pass


class ILoggingAdapter(ABC):
    """Interface for logging services."""

    @abstractmethod
    async def log_info(self, message: str, context: Dict[str, Any] = None) -> None:
        """Log info message."""
        pass

    @abstractmethod
    async def log_warning(self, message: str, context: Dict[str, Any] = None) -> None:
        """Log warning message."""
        pass

    @abstractmethod
    async def log_error(self, message: str, error: Exception = None, context: Dict[str, Any] = None) -> None:
        """Log error message."""
        pass

    @abstractmethod
    async def log_debug(self, message: str, context: Dict[str, Any] = None) -> None:
        """Log debug message."""
        pass

    @abstractmethod
    async def create_correlation_id(self) -> str:
        """Create correlation ID for request tracking."""
        pass


class IMonitoringAdapter(ABC):
    """Interface for monitoring and metrics services."""

    @abstractmethod
    async def record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record metric value."""
        pass

    @abstractmethod
    async def increment_counter(self, counter_name: str, tags: Dict[str, str] = None) -> None:
        """Increment counter metric."""
        pass

    @abstractmethod
    async def record_histogram(self, histogram_name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record histogram value."""
        pass

    @abstractmethod
    async def create_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Create monitoring alert."""
        pass

    @abstractmethod
    async def get_metrics(self, metric_names: List[str], time_range: Dict[str, Any]) -> Dict[str, Any]:
        """Get metrics data."""
        pass


# Protocol for adapter factory
class AdapterFactory(Protocol):
    """Protocol for adapter factory implementations."""

    def create_database_adapter(self) -> IDatabaseAdapter:
        """Create database adapter instance."""
        ...

    def create_web_adapter(self) -> IWebAdapter:
        """Create web adapter instance."""
        ...

    def create_cache_adapter(self) -> ICacheAdapter:
        """Create cache adapter instance."""
        ...

    def create_email_adapter(self) -> IEmailAdapter:
        """Create email adapter instance."""
        ...

    def create_storage_adapter(self) -> IStorageAdapter:
        """Create storage adapter instance."""
        ...

    def create_external_api_adapter(self) -> IExternalAPIAdapter:
        """Create external API adapter instance."""
        ...

    def create_message_queue_adapter(self) -> IMessageQueueAdapter:
        """Create message queue adapter instance."""
        ...

    def create_logging_adapter(self) -> ILoggingAdapter:
        """Create logging adapter instance."""
        ...

    def create_monitoring_adapter(self) -> IMonitoringAdapter:
        """Create monitoring adapter instance."""
        ...


class IAdapter(ABC):
    """Base adapter interface."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to external system."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to external system."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        pass


# Additional adapter interfaces extending base IAdapter class
class IFileStorageAdapter(IAdapter):
    """Interface for file storage systems."""

    @abstractmethod
    async def upload(self, file_path: str, content: bytes) -> str:
        """Upload file and return storage URL."""
        pass

    @abstractmethod
    async def download(self, file_path: str) -> bytes:
        """Download file content."""
        pass

    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """Delete file from storage."""
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "") -> List[str]:
        """List files with optional prefix filter."""
        pass


class IWebSocketAdapter(IAdapter):
    """Interface for WebSocket connections."""

    @abstractmethod
    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific WebSocket connection."""
        pass

    @abstractmethod
    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all connections. Returns count of recipients."""
        pass

    @abstractmethod
    async def disconnect_client(self, connection_id: str) -> bool:
        """Disconnect specific client."""
        pass
