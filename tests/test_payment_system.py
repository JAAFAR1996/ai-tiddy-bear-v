"""
Iraqi Payment System Tests
==========================
Comprehensive test suite for the Iraqi payment system.
Tests all payment operations, providers, and edge cases.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime

from ..interfaces import (
    PaymentRequest,
    PaymentMethod,
    PaymentStatus,
    RefundRequest,
    SubscriptionRequest,
    PaymentProviderError
)
from ..payment_service import IraqiPaymentService
from ..mock_provider import MockIraqiPaymentProvider
from ..config import get_payment_config, configure_for_environment, Environment


class TestPaymentInterfaces:
    """Test payment interfaces and data models."""
    
    def test_payment_request_validation(self):
        """Test PaymentRequest validation."""
        # Valid request
        request = PaymentRequest(
            amount=Decimal("50000"),
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="07901234567",
            customer_name="أحمد محمد"
        )
        assert request.amount == Decimal("50000")
        assert request.currency == "IQD"
        assert request.payment_method == PaymentMethod.ZAIN_CASH
    
    def test_payment_method_enum(self):
        """Test PaymentMethod enum values."""
        assert PaymentMethod.ZAIN_CASH.value == "zain_cash"
        assert PaymentMethod.FAST_PAY.value == "fast_pay"
        assert PaymentMethod.SWITCH.value == "switch"
        assert PaymentMethod.ASIACELL_CASH.value == "asiacell_cash"
        assert PaymentMethod.KOREK_PAY.value == "korek_pay"
        assert PaymentMethod.BANK_TRANSFER.value == "bank_transfer"
        assert PaymentMethod.CREDIT_CARD.value == "credit_card"
    
    def test_payment_status_enum(self):
        """Test PaymentStatus enum values."""
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.COMPLETED.value == "completed"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.CANCELLED.value == "cancelled"
        assert PaymentStatus.REFUNDED.value == "refunded"


class TestMockProvider:
    """Test mock Iraqi payment provider."""
    
    def setUp(self):
        """Set up test environment."""
        self.provider = MockIraqiPaymentProvider()
    
    @pytest.mark.asyncio
    async def test_zaincash_payment_success(self):
        """Test successful ZainCash payment."""
        request = PaymentRequest(
            amount=Decimal("50000"),
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="07901234567",
            customer_name="أحمد محمد"
        )
        
        response = await self.provider.initiate_payment(request)
        
        assert response.payment_id.startswith("zaincash_")
        assert response.status in [PaymentStatus.PENDING, PaymentStatus.COMPLETED]
        assert response.payment_code is not None
        assert response.payment_url is not None
    
    @pytest.mark.asyncio
    async def test_fastpay_payment_with_qr(self):
        """Test FastPay payment with QR code."""
        request = PaymentRequest(
            amount=Decimal("25000"),
            currency="IQD",
            payment_method=PaymentMethod.FAST_PAY,
            customer_phone="07801234567",
            customer_name="فاطمة علي"
        )
        
        response = await self.provider.initiate_payment(request)
        
        assert response.payment_id.startswith("fastpay_")
        assert response.qr_code is not None
        assert "fastpay.iq" in response.qr_code
    
    @pytest.mark.asyncio
    async def test_payment_status_check(self):
        """Test payment status checking."""
        # Create payment first
        request = PaymentRequest(
            amount=Decimal("30000"),
            currency="IQD",
            payment_method=PaymentMethod.SWITCH,
            customer_phone="07701234567",
            customer_name="محمد حسن"
        )
        
        payment_response = await self.provider.initiate_payment(request)
        
        # Check status
        status_response = await self.provider.get_payment_status(
            payment_response.payment_id, 
            PaymentMethod.SWITCH
        )
        
        assert status_response.payment_id == payment_response.payment_id
        assert status_response.status in [PaymentStatus.PENDING, PaymentStatus.COMPLETED, PaymentStatus.FAILED]
        assert status_response.amount == Decimal("30000")
    
    @pytest.mark.asyncio
    async def test_refund_processing(self):
        """Test refund processing."""
        # Create and complete payment first
        request = PaymentRequest(
            amount=Decimal("40000"),
            currency="IQD",
            payment_method=PaymentMethod.ASIACELL_CASH,
            customer_phone="07601234567",
            customer_name="علياء حسين"
        )
        
        payment_response = await self.provider.initiate_payment(request)
        
        # Request refund
        refund_request = RefundRequest(
            payment_id=payment_response.payment_id,
            amount=Decimal("20000"),  # Partial refund
            reason="العميل طلب استرداد جزئي"
        )
        
        refund_response = await self.provider.request_refund(refund_request)
        
        assert refund_response.refund_id is not None
        assert refund_response.amount == Decimal("20000")
        assert refund_response.status in [PaymentStatus.PENDING, PaymentStatus.COMPLETED]
    
    @pytest.mark.asyncio
    async def test_subscription_creation(self):
        """Test subscription creation."""
        request = SubscriptionRequest(
            customer_id="CUST_TEST_001",
            plan_id="MONTHLY_PREMIUM",
            amount=Decimal("75000"),
            currency="IQD",
            payment_method=PaymentMethod.KOREK_PAY,
            billing_cycle="monthly",
            customer_phone="07501234567",
            customer_name="حسام عبدالله"
        )
        
        response = await self.provider.create_subscription(request)
        
        assert response.subscription_id is not None
        assert response.status in [PaymentStatus.PENDING, PaymentStatus.COMPLETED]
        assert response.next_billing_date is not None
    
    @pytest.mark.asyncio
    async def test_large_amount_failure(self):
        """Test that very large amounts fail appropriately."""
        request = PaymentRequest(
            amount=Decimal("999999999"),  # Very large amount
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="07901234567",
            customer_name="اختبار مبلغ كبير"
        )
        
        with pytest.raises(PaymentProviderError) as exc_info:
            await self.provider.initiate_payment(request)
        
        assert "amount" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()


class TestPaymentService:
    """Test main payment service."""
    
    def setUp(self):
        """Set up test environment."""
        configure_for_environment(Environment.TESTING)
        self.service = IraqiPaymentService()
    
    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization."""
        assert self.service is not None
        
        # Test getting supported methods
        methods = await self.service.get_supported_methods()
        assert len(methods) > 0
        assert PaymentMethod.ZAIN_CASH in methods
    
    @pytest.mark.asyncio
    async def test_provider_status_check(self):
        """Test provider status checking."""
        status = await self.service.get_provider_status()
        
        assert isinstance(status, dict)
        assert len(status) > 0
        
        for provider_name, provider_status in status.items():
            assert "available" in provider_status
            assert "last_check" in provider_status
    
    @pytest.mark.asyncio
    async def test_payment_flow_integration(self):
        """Test complete payment flow integration."""
        # Initiate payment
        request = PaymentRequest(
            amount=Decimal("35000"),
            currency="IQD",
            payment_method=PaymentMethod.FAST_PAY,
            customer_phone="07801234567",
            customer_name="سارة أحمد",
            description="اختبار التكامل الكامل"
        )
        
        payment_response = await self.service.initiate_payment(request)
        assert payment_response.payment_id is not None
        
        # Check status
        status_response = await self.service.get_payment_status(payment_response.payment_id)
        assert status_response.payment_id == payment_response.payment_id
        
        # If payment is completed, test refund
        if status_response.status == PaymentStatus.COMPLETED:
            refund_request = RefundRequest(
                payment_id=payment_response.payment_id,
                amount=Decimal("10000"),
                reason="اختبار الاسترداد"
            )
            
            refund_response = await self.service.request_refund(refund_request)
            assert refund_response.refund_id is not None
    
    @pytest.mark.asyncio
    async def test_transaction_history(self):
        """Test transaction history retrieval."""
        # Create a few test transactions
        for i in range(3):
            payment_request = PaymentRequest(
                amount=Decimal("15000"),
                currency="IQD",
                payment_method=PaymentMethod.SWITCH,
                customer_phone=f"0770123456{i}",
                customer_name=f"عميل اختبار {i}",
                description=f"معاملة اختبار {i}"
            )
            
            await self.service.initiate_payment(payment_request)
        
        # Get transaction history
        history = await self.service.get_transaction_history(limit=10)
        
        assert isinstance(history, list)
        # Note: Mock provider doesn't persist data, so this tests the interface


class TestConfiguration:
    """Test payment system configuration."""
    
    def test_config_initialization(self):
        """Test configuration initialization."""
        config = get_payment_config()
        
        assert config is not None
        assert config.default_currency == "IQD"
        assert len(config.providers) > 0
    
    def test_provider_config(self):
        """Test provider-specific configuration."""
        config = get_payment_config()
        
        # Test ZainCash config
        zaincash_config = config.get_provider_config("zain_cash")
        assert zaincash_config is not None
        assert zaincash_config.name == "ZainCash"
        assert zaincash_config.min_amount >= Decimal("1000")
        assert zaincash_config.max_amount <= Decimal("50000000")
    
    def test_environment_configuration(self):
        """Test environment-specific configuration."""
        # Test development environment
        dev_config = configure_for_environment(Environment.DEVELOPMENT)
        assert dev_config.environment == Environment.DEVELOPMENT
        assert dev_config.debug_mode is True
        
        # Test production environment
        prod_config = configure_for_environment(Environment.PRODUCTION)
        assert prod_config.environment == Environment.PRODUCTION
        assert prod_config.debug_mode is False
    
    def test_amount_validation(self):
        """Test amount validation for providers."""
        config = get_payment_config()
        
        # Valid amount
        assert config.validate_amount("zain_cash", Decimal("50000")) is True
        
        # Too small amount
        assert config.validate_amount("zain_cash", Decimal("100")) is False
        
        # Too large amount  
        assert config.validate_amount("zain_cash", Decimal("999999999")) is False


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        self.service = IraqiPaymentService()
    
    @pytest.mark.asyncio
    async def test_invalid_payment_method(self):
        """Test handling of invalid payment method."""
        with pytest.raises((ValueError, PaymentProviderError)):
            request = PaymentRequest(
                amount=Decimal("50000"),
                currency="IQD",
                payment_method="invalid_method",  # This should cause an error
                customer_phone="07901234567",
                customer_name="اختبار خطأ"
            )
    
    @pytest.mark.asyncio
    async def test_payment_not_found(self):
        """Test payment not found scenario."""
        with pytest.raises(PaymentProviderError) as exc_info:
            await self.service.get_payment_status("nonexistent_payment_id")
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_invalid_phone_number(self):
        """Test invalid phone number handling."""
        request = PaymentRequest(
            amount=Decimal("50000"),
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="invalid_phone",  # Invalid phone
            customer_name="اختبار رقم خاطئ"
        )
        
        with pytest.raises(PaymentProviderError) as exc_info:
            await self.service.initiate_payment(request)
        
        assert "phone" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


class TestPerformance:
    """Test performance scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        self.service = IraqiPaymentService()
    
    @pytest.mark.asyncio
    async def test_concurrent_payments(self):
        """Test handling multiple concurrent payments."""
        tasks = []
        
        for i in range(10):
            request = PaymentRequest(
                amount=Decimal("10000"),
                currency="IQD",
                payment_method=PaymentMethod.FAST_PAY,
                customer_phone=f"0780123456{i}",
                customer_name=f"عميل متزامن {i}",
                description=f"دفعة متزامنة {i}"
            )
            
            task = self.service.initiate_payment(request)
            tasks.append(task)
        
        # Execute all payments concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that most payments succeeded
        successful = sum(1 for r in results if not isinstance(r, Exception))
        assert successful >= 7  # Allow for some failures due to rate limiting
    
    @pytest.mark.asyncio
    async def test_response_time(self):
        """Test payment response time."""
        request = PaymentRequest(
            amount=Decimal("25000"),
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="07901234567",
            customer_name="اختبار السرعة"
        )
        
        start_time = datetime.utcnow()
        response = await self.service.initiate_payment(request)
        end_time = datetime.utcnow()
        
        response_time = (end_time - start_time).total_seconds()
        
        # Payment should complete within 5 seconds for mock provider
        assert response_time < 5.0
        assert response.payment_id is not None


# Test fixtures and utilities
@pytest.fixture
def sample_payment_request():
    """Create a sample payment request for testing."""
    return PaymentRequest(
        amount=Decimal("50000"),
        currency="IQD",
        payment_method=PaymentMethod.ZAIN_CASH,
        customer_phone="07901234567",
        customer_name="عميل اختبار",
        description="دفعة اختبار"
    )


@pytest.fixture
def sample_refund_request():
    """Create a sample refund request for testing."""
    return RefundRequest(
        payment_id="test_payment_123",
        amount=Decimal("25000"),
        reason="اختبار الاسترداد"
    )


@pytest.fixture
def sample_subscription_request():
    """Create a sample subscription request for testing."""
    return SubscriptionRequest(
        customer_id="TEST_CUSTOMER",
        plan_id="TEST_PLAN",
        amount=Decimal("75000"),
        currency="IQD",
        payment_method=PaymentMethod.SWITCH,
        billing_cycle="monthly",
        customer_phone="07701234567",
        customer_name="عميل اشتراك اختبار"
    )


# Integration test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
