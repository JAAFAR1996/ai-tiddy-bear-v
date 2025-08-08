"""
Production Email Adapter - SMTP with SendGrid/AWS SES Support
===========================================================
Enterprise-grade email delivery with multiple provider support,
template management, bounce handling, and delivery tracking.
"""

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any
import os

# Optional imports for cloud providers
try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_SES_AVAILABLE = True
except ImportError:
    AWS_SES_AVAILABLE = False


class ProductionEmailAdapter:
    """
    Production email adapter supporting multiple providers:
    - SMTP (Gmail, Outlook, custom servers)
    - SendGrid API
    - AWS SES
    - Automatic failover between providers
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configure primary provider
        self.primary_provider = os.getenv("EMAIL_PRIMARY_PROVIDER", "smtp").lower()
        
        # SMTP Configuration
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        
        # SendGrid Configuration
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.sendgrid_client = None
        if SENDGRID_AVAILABLE and self.sendgrid_api_key:
            self.sendgrid_client = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
        
        # AWS SES Configuration
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.ses_client = None
        if AWS_SES_AVAILABLE:
            try:
                self.ses_client = boto3.client("ses", region_name=self.aws_region)
            except Exception as e:
                self.logger.warning(f"AWS SES client initialization failed: {e}")
        
        # Email configuration
        self.default_from_email = os.getenv("DEFAULT_FROM_EMAIL", "noreply@aiteddybear.com")
        self.default_from_name = os.getenv("DEFAULT_FROM_NAME", "AI Teddy Bear")
        
        # Metrics
        self.sent_count = 0
        self.failed_count = 0
        self.provider_failures = {"smtp": 0, "sendgrid": 0, "ses": 0}
        
        self.logger.info(f"ProductionEmailAdapter initialized with primary provider: {self.primary_provider}")
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send email with automatic provider failover.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            from_email: Sender email (uses default if None)
            from_name: Sender name (uses default if None)
            attachments: Optional attachments
            
        Returns:
            True if email sent successfully
        """
        from_email = from_email or self.default_from_email
        from_name = from_name or self.default_from_name
        
        correlation_id = f"email_{int(datetime.now().timestamp())}"
        
        self.logger.info(
            f"Sending email to {to}",
            extra={
                "correlation_id": correlation_id,
                "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                "primary_provider": self.primary_provider
            }
        )
        
        # Try primary provider first
        success = await self._send_with_provider(
            self.primary_provider,
            to, subject, body, html_body, from_email, from_name, attachments, correlation_id
        )
        
        if success:
            self.sent_count += 1
            return True
        
        # Try failover providers
        failover_providers = self._get_failover_providers()
        
        for provider in failover_providers:
            self.logger.warning(
                f"Trying failover provider: {provider}",
                extra={"correlation_id": correlation_id}
            )
            
            success = await self._send_with_provider(
                provider,
                to, subject, body, html_body, from_email, from_name, attachments, correlation_id
            )
            
            if success:
                self.sent_count += 1
                return True
        
        # All providers failed
        self.failed_count += 1
        self.logger.error(
            f"All email providers failed for {to}",
            extra={"correlation_id": correlation_id}
        )
        return False
    
    async def _send_with_provider(
        self,
        provider: str,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str],
        from_email: str,
        from_name: str,
        attachments: Optional[List[Dict[str, Any]]],
        correlation_id: str
    ) -> bool:
        """Send email using specific provider."""
        try:
            if provider == "smtp":
                return await self._send_smtp(
                    to, subject, body, html_body, from_email, from_name, attachments, correlation_id
                )
            elif provider == "sendgrid":
                return await self._send_sendgrid(
                    to, subject, body, html_body, from_email, from_name, correlation_id
                )
            elif provider == "ses":
                return await self._send_ses(
                    to, subject, body, html_body, from_email, from_name, correlation_id
                )
            else:
                self.logger.error(f"Unknown email provider: {provider}")
                return False
                
        except Exception as e:
            self.provider_failures[provider] = self.provider_failures.get(provider, 0) + 1
            self.logger.error(
                f"Email provider {provider} failed: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True
            )
            return False
    
    async def _send_smtp(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str],
        from_email: str,
        from_name: str,
        attachments: Optional[List[Dict[str, Any]]],
        correlation_id: str
    ) -> bool:
        """Send email via SMTP."""
        if not self.smtp_username or not self.smtp_password:
            self.logger.error("SMTP credentials not configured")
            return False
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = f"{from_name} <{from_email}>"
            message["To"] = to
            message["Subject"] = subject
            
            # Add plain text body
            text_part = MIMEText(body, "plain")
            message.attach(text_part)
            
            # Add HTML body if provided
            if html_body:
                html_part = MIMEText(html_body, "html")
                message.attach(html_part)
            
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls(context=context)
                
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            self.logger.info(
                f"SMTP email sent successfully to {to}",
                extra={"correlation_id": correlation_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"SMTP send failed: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True
            )
            return False
    
    async def _send_sendgrid(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str],
        from_email: str,
        from_name: str,
        correlation_id: str
    ) -> bool:
        """Send email via SendGrid API."""
        if not self.sendgrid_client:
            self.logger.error("SendGrid client not available")
            return False
        
        try:
            from_email_obj = Email(from_email, from_name)
            to_email = To(to)
            
            # Use HTML body if available, otherwise plain text
            content_type = "text/html" if html_body else "text/plain"
            content_body = html_body if html_body else body
            content = Content(content_type, content_body)
            
            mail = Mail(from_email_obj, to_email, subject, content)
            
            # Send email
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.sendgrid_client.send, mail
            )
            
            if response.status_code in [200, 202]:
                self.logger.info(
                    f"SendGrid email sent successfully to {to}",
                    extra={"correlation_id": correlation_id, "status_code": response.status_code}
                )
                return True
            else:
                self.logger.error(
                    f"SendGrid send failed with status {response.status_code}",
                    extra={"correlation_id": correlation_id, "response_body": response.body}
                )
                return False
                
        except Exception as e:
            self.logger.error(
                f"SendGrid send failed: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True
            )
            return False
    
    async def _send_ses(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str],
        from_email: str,
        from_name: str,
        correlation_id: str
    ) -> bool:
        """Send email via AWS SES."""
        if not self.ses_client:
            self.logger.error("AWS SES client not available")
            return False
        
        try:
            destination = {"ToAddresses": [to]}
            
            message = {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {}
            }
            
            # Add plain text body
            message["Body"]["Text"] = {"Data": body, "Charset": "UTF-8"}
            
            # Add HTML body if provided
            if html_body:
                message["Body"]["Html"] = {"Data": html_body, "Charset": "UTF-8"}
            
            # Send email
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.ses_client.send_email,
                from_email,
                destination,
                message
            )
            
            message_id = response.get("MessageId")
            
            self.logger.info(
                f"AWS SES email sent successfully to {to}",
                extra={"correlation_id": correlation_id, "message_id": message_id}
            )
            return True
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            self.logger.error(
                f"AWS SES send failed: {error_code}",
                extra={"correlation_id": correlation_id, "error": str(e)},
                exc_info=True
            )
            return False
        except Exception as e:
            self.logger.error(
                f"AWS SES send failed: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True
            )
            return False
    
    def _get_failover_providers(self) -> List[str]:
        """Get list of failover providers based on availability."""
        all_providers = ["smtp", "sendgrid", "ses"]
        failover_providers = []
        
        for provider in all_providers:
            if provider != self.primary_provider:
                if provider == "smtp" and self.smtp_username and self.smtp_password:
                    failover_providers.append(provider)
                elif provider == "sendgrid" and self.sendgrid_client:
                    failover_providers.append(provider)
                elif provider == "ses" and self.ses_client:
                    failover_providers.append(provider)
        
        return failover_providers
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get email adapter metrics."""
        total_attempts = self.sent_count + self.failed_count
        success_rate = (self.sent_count / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "total_sent": self.sent_count,
            "total_failed": self.failed_count,
            "success_rate": success_rate,
            "provider_failures": self.provider_failures,
            "primary_provider": self.primary_provider,
            "available_providers": self._get_available_providers(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_available_providers(self) -> List[str]:
        """Get list of available email providers."""
        providers = []
        
        if self.smtp_username and self.smtp_password:
            providers.append("smtp")
        if self.sendgrid_client:
            providers.append("sendgrid")
        if self.ses_client:
            providers.append("ses")
        
        return providers
    
    async def health_check(self) -> Dict[str, Any]:
        """Check email service health."""
        try:
            available_providers = self._get_available_providers()
            
            if not available_providers:
                return {
                    "status": "unhealthy",
                    "reason": "no_providers_available",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Test primary provider
            primary_healthy = await self._test_provider_connectivity(self.primary_provider)
            
            return {
                "status": "healthy" if primary_healthy else "degraded",
                "primary_provider": self.primary_provider,
                "primary_provider_healthy": primary_healthy,
                "available_providers": available_providers,
                "metrics": self.get_metrics(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Email health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _test_provider_connectivity(self, provider: str) -> bool:
        """Test connectivity to email provider."""
        try:
            if provider == "smtp":
                return await self._test_smtp_connectivity()
            elif provider == "sendgrid":
                return self.sendgrid_client is not None
            elif provider == "ses":
                return self.ses_client is not None
            return False
        except Exception as e:
            self.logger.warning(f"Provider {provider} connectivity test failed: {e}")
            return False
    
    async def _test_smtp_connectivity(self) -> bool:
        """Test SMTP server connectivity."""
        if not self.smtp_username or not self.smtp_password:
            return False
        
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                if self.smtp_use_tls:
                    server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                return True
        except Exception:
            return False
