"""
ESP32 Production Runner - Complete Production Setup
==================================================
Production-ready runner for ESP32 Chat Server with all services configured.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from src.services.esp32_service_factory import esp32_service_factory
from src.services.service_registry import ServiceRegistry


class ESP32ProductionRunner:
    """Production runner for ESP32 Chat Server."""

    def __init__(self):
        self.logger = self._setup_logging()
        self.chat_server = None
        self.service_registry = None

    def _setup_logging(self) -> logging.Logger:
        """Setup production logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('esp32_chat_server.log')
            ]
        )
        return logging.getLogger(__name__)

    async def initialize_services(self) -> None:
        """Initialize all required services."""
        try:
            self.logger.info("Initializing ESP32 Chat Server services...")

            # Initialize service registry
            self.service_registry = ServiceRegistry()

            # Get services from registry
            ai_service = await self.service_registry.get_ai_service()
            
            # Get TTS service from audio service
            audio_service = await self.service_registry.get_audio_service()
            tts_service = getattr(audio_service, 'tts_service', None)

            # Configuration
            stt_model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

            # Create production server with all services
            self.chat_server = await esp32_service_factory.create_production_server(
                stt_model_size=stt_model_size,
                ai_provider=ai_service,  # This will be the ConsolidatedAIService
                tts_service=tts_service,
                redis_url=redis_url,
            )

            self.logger.info("ESP32 Chat Server services initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}", exc_info=True)
            raise

    async def start_server(self) -> None:
        """Start the ESP32 Chat Server."""
        try:
            if not self.chat_server:
                await self.initialize_services()

            self.logger.info("ESP32 Chat Server is ready for connections")
            
            # The server is now ready to handle WebSocket connections
            # In a real deployment, this would be integrated with FastAPI
            
            # Keep the server running
            while True:
                # Perform health checks
                health_status = await self.chat_server.health_check()
                
                if health_status["status"] != "healthy":
                    self.logger.warning(f"Server health check failed: {health_status}")
                
                # Log metrics every 5 minutes
                metrics = self.chat_server.get_session_metrics()
                self.logger.info(f"Server metrics: {metrics}")
                
                await asyncio.sleep(300)  # 5 minutes

        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
            await self.shutdown()
        except Exception as e:
            self.logger.error(f"Server error: {e}", exc_info=True)
            await self.shutdown()
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        try:
            self.logger.info("Shutting down ESP32 Chat Server...")
            
            if self.chat_server:
                await self.chat_server.shutdown()
            
            self.logger.info("ESP32 Chat Server shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)

    async def health_check(self) -> dict:
        """Get server health status."""
        if not self.chat_server:
            return {"status": "not_initialized"}
        
        return await self.chat_server.health_check()

    def get_chat_server(self):
        """Get the chat server instance for integration with FastAPI."""
        return self.chat_server


# Global production runner instance
esp32_production_runner = ESP32ProductionRunner()


async def main():
    """Main entry point for standalone server."""
    try:
        await esp32_production_runner.start_server()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())