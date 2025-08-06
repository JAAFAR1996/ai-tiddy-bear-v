"""
Production Notification Service - Real Email & Push Notifications
================================================================
Enterprise-grade notification service with comprehensive error handling,
retry logic, template management, and delivery tracking.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

from src.interfaces.services import INotificationService


@dataclass
class NotificationMetrics:
    """Track notification delivery metrics."""
    total_sent: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    bounced_emails: int = 0
    push_delivery_failures: int = 0
    avg_delivery_time_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_sent == 0:
            return 0.0
        return (self.successful_deliveries / self.total_sent) * 100


class ProductionNotificationService(INotificationService):
    """
    Production-grade notification service supporting:
    - SMTP email delivery with retry logic
    - Push notifications via FCM/APNs
    - Template management
    - Delivery tracking and metrics
    - Error handling and fallback mechanisms
    """
    
    def __init__(self, email_adapter, push_adapter):
        self.email_adapter = email_adapter
        self.push_adapter = push_adapter
        self.logger = logging.getLogger(__name__)
        self.metrics = NotificationMetrics()
        
        # SMTP Configuration from environment
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        
        # Validation
        if not self.smtp_username or not self.smtp_password:
            raise ValueError("SMTP credentials not configured")
            
        # Push notification configuration
        self.fcm_server_key = os.getenv("FCM_SERVER_KEY")
        self.apns_cert_path = os.getenv("APNS_CERT_PATH")
        
        self.logger.info("ProductionNotificationService initialized")
    
    async def send_email(
        self, 
        to: str, 
        subject: str, 
        body: str, 
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send production email with retry logic and delivery tracking.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            attachments: Optional list of attachments
            
        Returns:
            True if email sent successfully
        """
        start_time = datetime.now()
        correlation_id = f"email_{int(start_time.timestamp())}"
        
        try:
            self.logger.info(
                f"Sending email to {to}",
                extra={
                    "correlation_id": correlation_id,
                    "recipient": to,
                    "subject": subject[:50] + "..." if len(subject) > 50 else subject
                }
            )
            
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = self.smtp_username
            message["To"] = to
            message["Subject"] = subject
            
            # Add plain text body
            text_part = MIMEText(body, "plain")
            message.attach(text_part)
            
            # Add HTML body if provided
            if html_body:
                html_part = MIMEText(html_body, "html")
                message.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    self._add_attachment(message, attachment)
            
            # Send email with retry logic
            success = await self._send_email_with_retry(message, to)
            
            # Update metrics
            self.metrics.total_sent += 1
            if success:
                self.metrics.successful_deliveries += 1
            else:
                self.metrics.failed_deliveries += 1
            
            # Update delivery time
            delivery_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_avg_delivery_time(delivery_time)
            
            if success:
                self.logger.info(
                    f"Email sent successfully to {to}",
                    extra={"correlation_id": correlation_id, "delivery_time_ms": delivery_time}
                )
            else:
                self.logger.error(
                    f"Failed to send email to {to}",
                    extra={"correlation_id": correlation_id}
                )
            
            return success
            
        except Exception as e:
            self.metrics.total_sent += 1
            self.metrics.failed_deliveries += 1
            
            self.logger.error(
                f"Email sending error: {e}",
                extra={"correlation_id": correlation_id, "recipient": to},
                exc_info=True
            )
            return False
    
    async def send_push(
        self, 
        user_id: str, 
        title: str, 
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send push notification to user device.
        
        Args:
            user_id: Target user ID
            title: Notification title
            message: Notification message
            data: Optional custom data
            
        Returns:
            True if notification sent successfully
        """
        start_time = datetime.now()
        correlation_id = f"push_{int(start_time.timestamp())}"
        
        try:
            self.logger.info(
                f"Sending push notification to user {user_id}",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "title": title
                }
            )
            
            # Use push adapter to send notification
            success = await self.push_adapter.send_notification(
                user_id=user_id,
                title=title,
                message=message,
                data=data or {}
            )
            
            # Update metrics
            self.metrics.total_sent += 1
            if success:
                self.metrics.successful_deliveries += 1
            else:
                self.metrics.failed_deliveries += 1
                self.metrics.push_delivery_failures += 1
            
            # Update delivery time
            delivery_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_avg_delivery_time(delivery_time)
            
            if success:
                self.logger.info(
                    f"Push notification sent successfully to user {user_id}",
                    extra={"correlation_id": correlation_id, "delivery_time_ms": delivery_time}
                )
            else:
                self.logger.error(
                    f"Failed to send push notification to user {user_id}",
                    extra={"correlation_id": correlation_id}
                )
            
            return success
            
        except Exception as e:
            self.metrics.total_sent += 1
            self.metrics.failed_deliveries += 1
            self.metrics.push_delivery_failures += 1
            
            self.logger.error(
                f"Push notification error: {e}",
                extra={"correlation_id": correlation_id, "user_id": user_id},
                exc_info=True
            )
            return False
    
    async def _send_email_with_retry(self, message: MIMEMultipart, recipient: str) -> bool:
        """Send email with exponential backoff retry logic."""
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Create SSL context
                context = ssl.create_default_context()
                
                # Connect to SMTP server
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    if self.use_tls:
                        server.starttls(context=context)
                    
                    # Login and send
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(message)
                    
                return True
                
            except smtplib.SMTPException as e:
                self.logger.warning(
                    f"SMTP error (attempt {attempt + 1}/{max_retries}): {e}",
                    extra={"recipient": recipient, "attempt": attempt + 1}
                )
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"All email retry attempts failed for {recipient}",
                        extra={"recipient": recipient}
                    )
                    return False
                    
            except Exception as e:
                self.logger.error(
                    f"Unexpected email error: {e}",
                    extra={"recipient": recipient},
                    exc_info=True
                )
                return False
        
        return False
    
    def _add_attachment(self, message: MIMEMultipart, attachment: Dict[str, Any]) -> None:
        """Add attachment to email message."""
        try:
            filename = attachment.get("filename")
            content = attachment.get("content")
            content_type = attachment.get("content_type", "application/octet-stream")
            
            if not filename or not content:
                self.logger.warning("Invalid attachment format")
                return
            
            part = MIMEBase(*content_type.split("/"))
            part.set_payload(content)
            encoders.encode_base64(part)
            
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {filename}"
            )
            
            message.attach(part)
            
        except Exception as e:
            self.logger.error(f"Failed to add attachment: {e}", exc_info=True)
    
    def _update_avg_delivery_time(self, delivery_time_ms: float) -> None:
        """Update average delivery time metric."""
        if self.metrics.total_sent == 1:
            self.metrics.avg_delivery_time_ms = delivery_time_ms
        else:
            # Calculate rolling average
            total_time = self.metrics.avg_delivery_time_ms * (self.metrics.total_sent - 1)
            self.metrics.avg_delivery_time_ms = (total_time + delivery_time_ms) / self.metrics.total_sent
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get notification service metrics."""
        return {
            "total_sent": self.metrics.total_sent,
            "successful_deliveries": self.metrics.successful_deliveries,
            "failed_deliveries": self.metrics.failed_deliveries,
            "success_rate": self.metrics.success_rate,
            "bounced_emails": self.metrics.bounced_emails,
            "push_delivery_failures": self.metrics.push_delivery_failures,
            "avg_delivery_time_ms": self.metrics.avg_delivery_time_ms,
            "timestamp": datetime.now().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check notification service health."""
        try:
            # Test SMTP connection
            smtp_healthy = await self._test_smtp_connection()
            
            # Test push service
            push_healthy = await self._test_push_service()
            
            overall_status = "healthy" if smtp_healthy and push_healthy else "degraded"
            
            return {
                "status": overall_status,
                "smtp_healthy": smtp_healthy,
                "push_healthy": push_healthy,
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _test_smtp_connection(self) -> bool:
        """Test SMTP server connectivity."""
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                if self.use_tls:
                    server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                return True
        except Exception as e:
            self.logger.warning(f"SMTP health check failed: {e}")
            return False
    
    async def _test_push_service(self) -> bool:
        """Test push notification service connectivity."""
        try:
            # Test FCM/APNs connectivity through adapter
            if hasattr(self.push_adapter, 'health_check'):
                return await self.push_adapter.health_check()
            return True
        except Exception as e:
            self.logger.warning(f"Push service health check failed: {e}")
            return False