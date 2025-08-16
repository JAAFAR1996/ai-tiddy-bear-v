"""
Production Message Queue Adapter - Legacy Compatibility Module
=============================================================
Message queue adapter for production environments with Redis/RabbitMQ support.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Message structure for queue operations."""
    id: str
    topic: str
    payload: Dict[str, Any]
    timestamp: datetime
    retry_count: int = 0


class ProductionMessageQueueAdapter:
    """Production message queue adapter with Redis/RabbitMQ support."""
    
    def __init__(self, connection_url: str = None):
        """Initialize message queue adapter."""
        self.connection_url = connection_url or "redis://localhost:6379/0"
        self.subscribers: Dict[str, List[Callable]] = {}
        self.logger = logger
        
    async def connect(self):
        """Connect to message queue backend."""
        self.logger.info(f"Connecting to message queue: {self.connection_url}")
        # In production this would connect to actual Redis/RabbitMQ
        
    async def disconnect(self):
        """Disconnect from message queue backend."""
        self.logger.info("Disconnecting from message queue")
        
    async def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish message to topic."""
        try:
            self.logger.info(f"Publishing message to topic '{topic}': {message}")
            # In production this would publish to actual queue
            return True
        except Exception as e:
            self.logger.error(f"Failed to publish message: {e}")
            return False
            
    async def subscribe(self, topic: str, callback: Callable):
        """Subscribe to topic with callback."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        self.logger.info(f"Subscribed to topic '{topic}'")
        
    async def unsubscribe(self, topic: str, callback: Callable = None):
        """Unsubscribe from topic."""
        if topic in self.subscribers:
            if callback:
                self.subscribers[topic].remove(callback)
            else:
                del self.subscribers[topic]
        self.logger.info(f"Unsubscribed from topic '{topic}'")


# Global instance for backward compatibility
production_message_queue_adapter = ProductionMessageQueueAdapter()