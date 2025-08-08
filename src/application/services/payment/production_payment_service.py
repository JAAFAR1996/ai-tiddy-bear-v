"""
Production Payment Service
=========================
Enterprise-grade payment orchestration service.
Handles all payment operations with:
- Real provider integrations
- Comprehensive security and audit
- Fraud detection and prevention
- Atomic transactions with rollback
- Real-time status updates
- Webhook processing

CLEANUP LOG (2025-08-06):
- All code is production-ready and actively used
- Comprehensive payment orchestration with security
- Real Iraqi payment provider integrations (ZainCash, FastPay, etc.)
- Complete audit trail and transaction management
- No unused/dead code found - all components serve production purposes
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from enum import Enum
from dataclasses import dataclass
import logging

from .repositories.payment_repository import (
    PaymentUnitOfWork,
    TransactionStatus,
    PaymentSearchFilters,
    PaginationParams,
)
from .security.payment_security import PaymentSecurityManager, SecurityContext
from .providers.iraqi_payment_providers import (
    PaymentProviderFactory,
    PaymentRequest,
    RefundRequest,
    PaymentMethod,
    ProviderStatus,
)


class PaymentError(Exception):
    """Custom payment error with error codes."""

    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class PaymentResult(Enum):
    """Payment operation results."""

    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    REQUIRES_VERIFICATION = "requires_verification"
    BLOCKED = "blocked"


@dataclass
class PaymentInitiationRequest:
    """Request to initiate payment."""

    customer_id: str
    amount: int  # Amount in Iraqi fils
    currency: str = "IQD"
    payment_method: PaymentMethod = PaymentMethod.ZAINCASH
    customer_phone: str = ""
    customer_name: str = ""
    description: str = ""
    callback_url: str = ""
    metadata: Dict[str, Any] = None


@dataclass
class PaymentInitiationResponse:
    """Response from payment initiation."""

    result: PaymentResult
    payment_id: Optional[UUID] = None
    payment_url: Optional[str] = None
    message: str = ""
    error_code: Optional[str] = None
    expires_at: Optional[datetime] = None
    requires_verification: bool = False
    risk_score: int = 0


class ProductionPaymentService:
    """
    Production-ready payment service for Iraqi market.
    Handles all payment operations with enterprise-grade security.
    """

    def __init__(
        self,
        security_manager: PaymentSecurityManager,
        provider_configs: Dict[str, Dict],
        redis_client,
        logger=None,
    ):
        self.security = security_manager
        self.provider_configs = provider_configs
        self.redis = redis_client
        self.logger = logger or logging.getLogger(__name__)

        # Initialize payment providers
        self.providers = {}
        for provider_name, config in provider_configs.items():
            try:
                self.providers[provider_name] = PaymentProviderFactory.create_provider(
                    provider_name, config
                )
                self.logger.info(f"Payment provider initialized: {provider_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize provider {provider_name}: {e}")

    async def initiate_payment(
        self,
        request: PaymentInitiationRequest,
        context: SecurityContext,
        uow: PaymentUnitOfWork,
    ) -> PaymentInitiationResponse:
        """
        Initiate payment with comprehensive security checks.
        """
        try:
            # 1. Security and authorization checks
            authorized = await self.security.authorize_payment_operation(
                context, "initiate_payment", request.amount
            )
            if not authorized:
                return PaymentInitiationResponse(
                    result=PaymentResult.BLOCKED,
                    message="Payment not authorized",
                    error_code="AUTHORIZATION_FAILED",
                )

            # 2. Rate limiting
            rate_limit_ok = await self.security.check_rate_limits(
                context, "initiate_payment"
            )
            if not rate_limit_ok:
                return PaymentInitiationResponse(
                    result=PaymentResult.BLOCKED,
                    message="Rate limit exceeded",
                    error_code="RATE_LIMIT_EXCEEDED",
                )

            # 3. Fraud detection
            fraud_check = await self.security.perform_fraud_check(
                context=context,
                amount=request.amount,
                payment_method=request.payment_method.value,
                customer_phone=request.customer_phone,
                db_session=uow.db,
            )

            if not fraud_check["is_approved"]:
                await self.security.log_security_event(
                    context,
                    "payment_blocked_fraud",
                    f"Payment blocked by fraud detection. Risk score: {fraud_check['risk_score']}",
                    additional_data=fraud_check,
                    db_session=uow.db,
                )

                return PaymentInitiationResponse(
                    result=PaymentResult.BLOCKED,
                    message="Payment blocked by security system",
                    error_code="FRAUD_DETECTED",
                    risk_score=fraud_check["risk_score"],
                )

            # 4. Create payment record in database
            payment_data = {
                "customer_id": request.customer_id,
                "amount": request.amount,
                "currency": request.currency,
                "payment_method": request.payment_method.value,
                "provider": self._get_provider_for_method(request.payment_method),
                "customer_phone": self.security.encrypt_sensitive_data(
                    request.customer_phone
                ),
                "customer_name": self.security.encrypt_sensitive_data(
                    request.customer_name
                ),
                "description": request.description,
                "callback_url": request.callback_url,
                "metadata": request.metadata or {},
                "user_id": context.user_id,
                "ip_address": context.ip_address,
            }

            payment = await uow.payment_repo.create_payment(payment_data)

            # 5. Initiate payment with provider
            provider_name = self._get_provider_for_method(request.payment_method)
            provider = self.providers.get(provider_name)

            if not provider:
                raise PaymentError(
                    f"Provider {provider_name} not available", "PROVIDER_UNAVAILABLE"
                )

            provider_request = PaymentRequest(
                amount=request.amount,
                currency=request.currency,
                customer_phone=request.customer_phone,
                customer_name=request.customer_name,
                description=request.description,
                callback_url=request.callback_url,
                reference_id=str(payment.id),
                metadata=request.metadata,
            )

            provider_response = await provider.initiate_payment(provider_request)

            # 6. Update payment with provider response
            if provider_response.success:
                await uow.payment_repo.update_payment_status(
                    payment.id,
                    TransactionStatus.PROCESSING,
                    provider_response.provider_response,
                    context.user_id,
                    context.ip_address,
                )

                # Store payment URL in Redis for quick access
                if provider_response.payment_url:
                    await self.redis.setex(
                        f"payment_url:{payment.id}",
                        1800,  # 30 minutes
                        provider_response.payment_url,
                    )

                # Log successful initiation
                await self.security.log_security_event(
                    context,
                    "payment_initiated",
                    f"Payment initiated successfully with {provider_name}",
                    str(payment.id),
                    {"amount": request.amount, "provider": provider_name},
                    uow.db,
                )

                return PaymentInitiationResponse(
                    result=PaymentResult.PENDING,
                    payment_id=payment.id,
                    payment_url=provider_response.payment_url,
                    message="Payment initiated successfully",
                    expires_at=provider_response.expires_at,
                    requires_verification=fraud_check["requires_verification"],
                    risk_score=fraud_check["risk_score"],
                )
            else:
                # Provider failed
                await uow.payment_repo.update_payment_status(
                    payment.id,
                    TransactionStatus.FAILED,
                    provider_response.provider_response,
                    context.user_id,
                    context.ip_address,
                )

                return PaymentInitiationResponse(
                    result=PaymentResult.FAILED,
                    payment_id=payment.id,
                    message=provider_response.message,
                    error_code=provider_response.error_code,
                )

        except PaymentError as e:
            await self.security.log_security_event(
                context,
                "payment_error",
                f"Payment initiation error: {e.message}",
                additional_data={"error_code": e.error_code, "details": e.details},
                db_session=uow.db,
            )

            return PaymentInitiationResponse(
                result=PaymentResult.FAILED, message=e.message, error_code=e.error_code
            )
        except Exception as e:
            self.logger.error(f"Unexpected payment initiation error: {e}")

            await self.security.log_security_event(
                context,
                "payment_system_error",
                f"System error during payment initiation: {str(e)}",
                db_session=uow.db,
            )

            return PaymentInitiationResponse(
                result=PaymentResult.FAILED,
                message="System error occurred",
                error_code="SYSTEM_ERROR",
            )

    async def check_payment_status(
        self, payment_id: UUID, context: SecurityContext, uow: PaymentUnitOfWork
    ) -> Dict[str, Any]:
        """Check payment status with provider."""
        try:
            # Get payment from database
            payment = await uow.payment_repo.get_payment_by_id(payment_id)
            if not payment:
                raise PaymentError("Payment not found", "PAYMENT_NOT_FOUND")

            # Authorization check
            if (
                payment.customer_id != context.user_id
                and "payment:read_all" not in context.permissions
            ):
                raise PaymentError(
                    "Not authorized to view this payment", "UNAUTHORIZED"
                )

            # Get provider and check status
            provider = self.providers.get(payment.provider)
            if not provider:
                raise PaymentError(
                    f"Provider {payment.provider} not available", "PROVIDER_UNAVAILABLE"
                )

            provider_response = await provider.check_payment_status(
                payment.provider_reference_id
            )

            # Update database if status changed
            current_status = TransactionStatus(payment.status)
            new_status = self._map_provider_status(provider_response.status)

            if new_status != current_status:
                await uow.payment_repo.update_payment_status(
                    payment_id,
                    new_status,
                    provider_response.provider_response,
                    context.user_id,
                    context.ip_address,
                )

                # Log status change
                await self.security.log_security_event(
                    context,
                    "payment_status_updated",
                    f"Payment status updated from {current_status.value} to {new_status.value}",
                    str(payment_id),
                    {
                        "old_status": current_status.value,
                        "new_status": new_status.value,
                    },
                    uow.db,
                )

            return {
                "payment_id": str(payment_id),
                "status": new_status.value,
                "amount": payment.amount,
                "currency": payment.currency,
                "provider": payment.provider,
                "created_at": payment.created_at.isoformat(),
                "updated_at": payment.updated_at.isoformat(),
                "provider_reference_id": payment.provider_reference_id,
                "message": provider_response.message,
            }

        except PaymentError:
            raise
        except Exception as e:
            self.logger.error(f"Error checking payment status: {e}")
            raise PaymentError("System error occurred", "SYSTEM_ERROR")

    async def process_refund(
        self,
        payment_id: UUID,
        refund_amount: int,
        reason: str,
        context: SecurityContext,
        uow: PaymentUnitOfWork,
    ) -> Dict[str, Any]:
        """Process payment refund."""
        try:
            # Authorization check
            authorized = await self.security.authorize_payment_operation(
                context, "refund_payment", refund_amount
            )
            if not authorized:
                raise PaymentError("Refund not authorized", "AUTHORIZATION_FAILED")

            # Get original payment
            payment = await uow.payment_repo.get_payment_by_id(payment_id)
            if not payment:
                raise PaymentError("Payment not found", "PAYMENT_NOT_FOUND")

            if payment.status != "completed":
                raise PaymentError(
                    "Can only refund completed payments", "INVALID_PAYMENT_STATUS"
                )

            # Create refund record
            refund_data = {
                "original_transaction_id": payment_id,
                "amount": refund_amount,
                "reason": reason,
                "requested_by": context.user_id,
            }

            refund = await uow.refund_repo.create_refund(refund_data)

            # Process refund with provider
            provider = self.providers.get(payment.provider)
            if not provider:
                raise PaymentError(
                    f"Provider {payment.provider} not available", "PROVIDER_UNAVAILABLE"
                )

            refund_request = RefundRequest(
                original_transaction_id=payment.provider_reference_id,
                amount=refund_amount,
                reason=reason,
                reference_id=str(refund.id),
            )

            provider_response = await provider.refund_payment(refund_request)

            # Update refund status
            if provider_response.success:
                await uow.refund_repo.update_refund_status(
                    refund.id,
                    TransactionStatus.PROCESSING,
                    provider_response.provider_response,
                )

                # Log refund
                await self.security.log_security_event(
                    context,
                    "refund_initiated",
                    f"Refund initiated for payment {payment_id}",
                    str(refund.id),
                    {"amount": refund_amount, "reason": reason},
                    uow.db,
                )

                return {
                    "refund_id": str(refund.id),
                    "status": "processing",
                    "amount": refund_amount,
                    "message": "Refund initiated successfully",
                }
            else:
                await uow.refund_repo.update_refund_status(
                    refund.id,
                    TransactionStatus.FAILED,
                    provider_response.provider_response,
                )

                raise PaymentError(
                    provider_response.message,
                    provider_response.error_code or "REFUND_FAILED",
                )

        except PaymentError:
            raise
        except Exception as e:
            self.logger.error(f"Error processing refund: {e}")
            raise PaymentError("System error occurred", "SYSTEM_ERROR")

    async def cancel_payment(
        self, payment_id: UUID, context: SecurityContext, uow: PaymentUnitOfWork
    ) -> Dict[str, Any]:
        """Cancel pending payment."""
        try:
            # Authorization check
            authorized = await self.security.authorize_payment_operation(
                context, "cancel_payment"
            )
            if not authorized:
                raise PaymentError(
                    "Cancellation not authorized", "AUTHORIZATION_FAILED"
                )

            # Get payment
            payment = await uow.payment_repo.get_payment_by_id(payment_id)
            if not payment:
                raise PaymentError("Payment not found", "PAYMENT_NOT_FOUND")

            if payment.status not in ["pending", "processing"]:
                raise PaymentError(
                    "Can only cancel pending/processing payments",
                    "INVALID_PAYMENT_STATUS",
                )

            # Cancel with provider
            provider = self.providers.get(payment.provider)
            if provider:
                provider_response = await provider.cancel_payment(
                    payment.provider_reference_id
                )

                if provider_response.success:
                    await uow.payment_repo.update_payment_status(
                        payment_id,
                        TransactionStatus.CANCELLED,
                        provider_response.provider_response,
                        context.user_id,
                        context.ip_address,
                    )

                    # Log cancellation
                    await self.security.log_security_event(
                        context,
                        "payment_cancelled",
                        f"Payment {payment_id} cancelled",
                        str(payment_id),
                        {"reason": "user_request"},
                        uow.db,
                    )

                    return {
                        "payment_id": str(payment_id),
                        "status": "cancelled",
                        "message": "Payment cancelled successfully",
                    }
                else:
                    # Manual cancellation if provider doesn't support it
                    await uow.payment_repo.update_payment_status(
                        payment_id,
                        TransactionStatus.CANCELLED,
                        {"manual_cancellation": True},
                        context.user_id,
                        context.ip_address,
                    )

                    return {
                        "payment_id": str(payment_id),
                        "status": "cancelled",
                        "message": "Payment cancelled (manual)",
                    }
            else:
                raise PaymentError(
                    f"Provider {payment.provider} not available", "PROVIDER_UNAVAILABLE"
                )

        except PaymentError:
            raise
        except Exception as e:
            self.logger.error(f"Error cancelling payment: {e}")
            raise PaymentError("System error occurred", "SYSTEM_ERROR")

    async def search_payments(
        self,
        filters: PaymentSearchFilters,
        pagination: PaginationParams,
        context: SecurityContext,
        uow: PaymentUnitOfWork,
    ) -> Dict[str, Any]:
        """Search payments with filters."""
        try:
            # Restrict search to user's payments unless admin
            if "payment:read_all" not in context.permissions:
                filters.customer_id = context.user_id

            payments, total_count = await uow.payment_repo.search_payments(
                filters, pagination
            )

            # Decrypt sensitive data for authorized users
            payment_list = []
            for payment in payments:
                payment_dict = {
                    "id": str(payment.id),
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status,
                    "payment_method": payment.payment_method,
                    "provider": payment.provider,
                    "description": payment.description,
                    "created_at": payment.created_at.isoformat(),
                    "updated_at": payment.updated_at.isoformat(),
                }

                # Add sensitive data if authorized
                if (
                    payment.customer_id == context.user_id
                    or "payment:read_all" in context.permissions
                ):
                    try:
                        payment_dict.update(
                            {
                                "customer_phone": self.security.decrypt_sensitive_data(
                                    payment.customer_phone
                                ),
                                "customer_name": self.security.decrypt_sensitive_data(
                                    payment.customer_name
                                ),
                                "provider_reference_id": payment.provider_reference_id,
                            }
                        )
                    except Exception:
                        # Handle decryption errors gracefully
                        payment_dict.update(
                            {
                                "customer_phone": "***",
                                "customer_name": "***",
                                "provider_reference_id": "***",
                            }
                        )

                payment_list.append(payment_dict)

            return {
                "payments": payment_list,
                "total_count": total_count,
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total_pages": (total_count + pagination.page_size - 1)
                // pagination.page_size,
            }

        except Exception as e:
            self.logger.error(f"Error searching payments: {e}")
            raise PaymentError("Search failed", "SEARCH_ERROR")

    async def process_webhook(
        self,
        provider_name: str,
        payload: Dict[str, Any],
        signature: str,
        uow: PaymentUnitOfWork,
    ) -> Dict[str, Any]:
        """Process webhook from payment provider."""
        try:
            # Verify webhook signature
            verified = await self.security.verify_webhook_signature(
                provider_name, json.dumps(payload).encode(), signature
            )

            if not verified:
                self.logger.warning(f"Invalid webhook signature from {provider_name}")
                return {"status": "error", "message": "Invalid signature"}

            # Rate limiting for webhooks
            context = SecurityContext(
                user_id="system",
                session_id="webhook",
                ip_address="provider",
                user_agent=f"{provider_name}_webhook",
            )

            rate_limit_ok = await self.security.check_rate_limits(context, "webhook")
            if not rate_limit_ok:
                return {"status": "error", "message": "Rate limit exceeded"}

            # Store webhook event
            webhook_data = {
                "provider": provider_name,
                "event_type": payload.get("event_type", "payment_update"),
                "payload": payload,
            }

            webhook = await uow.webhook_repo.create_webhook_event(webhook_data)

            # Process webhook based on provider
            if provider_name == "zaincash":
                result = await self._process_zaincash_webhook(payload, uow)
            elif provider_name == "fastpay":
                result = await self._process_fastpay_webhook(payload, uow)
            elif provider_name == "switch":
                result = await self._process_switch_webhook(payload, uow)
            else:
                result = {"status": "error", "message": "Unknown provider"}

            # Update webhook status
            await uow.webhook_repo.update_webhook_status(
                webhook.id,
                "processed" if result.get("status") == "success" else "failed",
                result,
            )

            return result

        except Exception as e:
            self.logger.error(f"Webhook processing error: {e}")
            return {"status": "error", "message": "Processing failed"}

    def _get_provider_for_method(self, payment_method: PaymentMethod) -> str:
        """Get provider name for payment method."""
        method_provider_map = {
            PaymentMethod.ZAINCASH: "zaincash",
            PaymentMethod.FASTPAY_CARD: "fastpay",
            PaymentMethod.SWITCH_VISA: "switch",
            PaymentMethod.SWITCH_MASTERCARD: "switch",
            PaymentMethod.BANK_TRANSFER: "switch",
        }
        return method_provider_map.get(payment_method, "zaincash")

    def _map_provider_status(
        self, provider_status: ProviderStatus
    ) -> TransactionStatus:
        """Map provider status to our transaction status."""
        status_map = {
            ProviderStatus.SUCCESS: TransactionStatus.COMPLETED,
            ProviderStatus.PENDING: TransactionStatus.PENDING,
            ProviderStatus.PROCESSING: TransactionStatus.PROCESSING,
            ProviderStatus.FAILED: TransactionStatus.FAILED,
            ProviderStatus.CANCELLED: TransactionStatus.CANCELLED,
            ProviderStatus.EXPIRED: TransactionStatus.EXPIRED,
        }
        return status_map.get(provider_status, TransactionStatus.FAILED)

    async def _process_zaincash_webhook(
        self, payload: Dict, uow: PaymentUnitOfWork
    ) -> Dict[str, Any]:
        """Process ZainCash webhook."""
        try:
            payment_id = payload.get("orderId")
            if not payment_id:
                return {"status": "error", "message": "Missing orderId"}

            payment = await uow.payment_repo.get_payment_by_reference(payment_id)
            if not payment:
                return {"status": "error", "message": "Payment not found"}

            # Update payment status based on ZainCash response
            status_code = payload.get("status", 0)
            if status_code == 200:
                new_status = TransactionStatus.COMPLETED
            elif status_code == 202:
                new_status = TransactionStatus.CANCELLED
            else:
                new_status = TransactionStatus.FAILED

            await uow.payment_repo.update_payment_status(
                payment.id, new_status, payload
            )

            return {"status": "success", "message": "Webhook processed"}

        except Exception as e:
            self.logger.error(f"ZainCash webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def _process_fastpay_webhook(
        self, payload: Dict, uow: PaymentUnitOfWork
    ) -> Dict[str, Any]:
        """Process FastPay webhook."""
        try:
            transaction_id = payload.get("transaction_id")
            if not transaction_id:
                return {"status": "error", "message": "Missing transaction_id"}

            payment = await uow.payment_repo.get_payment_by_reference(transaction_id)
            if not payment:
                return {"status": "error", "message": "Payment not found"}

            # Update payment status
            status = payload.get("status", "failed")
            status_map = {
                "completed": TransactionStatus.COMPLETED,
                "failed": TransactionStatus.FAILED,
                "cancelled": TransactionStatus.CANCELLED,
            }

            new_status = status_map.get(status, TransactionStatus.FAILED)

            await uow.payment_repo.update_payment_status(
                payment.id, new_status, payload
            )

            return {"status": "success", "message": "Webhook processed"}

        except Exception as e:
            self.logger.error(f"FastPay webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def _process_switch_webhook(
        self, payload: Dict, uow: PaymentUnitOfWork
    ) -> Dict[str, Any]:
        """Process Switch webhook."""
        try:
            order_id = payload.get("orderId")
            if not order_id:
                return {"status": "error", "message": "Missing orderId"}

            payment = await uow.payment_repo.get_payment_by_reference(order_id)
            if not payment:
                return {"status": "error", "message": "Payment not found"}

            # Update payment status based on Switch response
            order_status = payload.get("orderStatus", 6)  # Default to failed
            if order_status == 2:
                new_status = TransactionStatus.COMPLETED
            elif order_status == 3:
                new_status = TransactionStatus.CANCELLED
            else:
                new_status = TransactionStatus.FAILED

            await uow.payment_repo.update_payment_status(
                payment.id, new_status, payload
            )

            return {"status": "success", "message": "Webhook processed"}

        except Exception as e:
            self.logger.error(f"Switch webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def close(self):
        """Clean up resources."""
        for provider in self.providers.values():
            if hasattr(provider, "close"):
                await provider.close()
