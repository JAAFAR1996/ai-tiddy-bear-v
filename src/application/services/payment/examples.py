"""
Iraqi Payment System Examples and Testing
==========================================
Complete examples and test cases for the Iraqi payment system.
Demonstrates all payment operations with realistic scenarios.
"""

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from .interfaces import (
    PaymentRequest,
    PaymentMethod,
    RefundRequest,
    SubscriptionRequest,
)
from .payment_service import IraqiPaymentService
from .config import get_payment_config, configure_for_environment, Environment


class PaymentExamples:
    """Examples and test scenarios for Iraqi payment system."""

    def __init__(self):
        self.service = IraqiPaymentService()
        self.config = get_payment_config()

    async def example_zaincash_payment(self) -> Dict[str, Any]:
        """Example: ZainCash mobile payment."""
        print("🔄 Testing ZainCash Payment...")

        request = PaymentRequest(
            amount=Decimal("50000"),  # 50,000 IQD
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="07901234567",
            customer_name="أحمد محمد علي",
            description="اشتراك شهري في تطبيق الدب الذكي",
            reference_id="TEDDY_SUB_001",
        )

        try:
            # Initiate payment
            response = await self.service.initiate_payment(request)
            print(f"✅ Payment initiated: {response.payment_id}")
            print(f"   Status: {response.status.value}")
            print(f"   USSD Code: {response.payment_code}")
            print(f"   Payment URL: {response.payment_url}")

            # Simulate user completing payment after 2 seconds
            await asyncio.sleep(2)

            # Check status
            status = await self.service.get_payment_status(response.payment_id)
            print(f"✅ Final Status: {status.status.value}")
            print(f"   Amount Paid: {status.amount_paid} {status.currency}")

            return {
                "success": True,
                "payment_id": response.payment_id,
                "status": status.status.value,
                "amount": float(status.amount_paid),
            }

        except Exception as e:
            print(f"❌ ZainCash payment failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def example_fastpay_qr_payment(self) -> Dict[str, Any]:
        """Example: FastPay QR code payment."""
        print("\n🔄 Testing FastPay QR Payment...")

        request = PaymentRequest(
            amount=Decimal("25000"),  # 25,000 IQD
            currency="IQD",
            payment_method=PaymentMethod.FAST_PAY,
            customer_phone="07801234567",
            customer_name="فاطمة حسن",
            description="شراء محتوى تعليمي للأطفال",
            reference_id="CONTENT_001",
        )

        try:
            response = await self.service.initiate_payment(request)
            print(f"✅ Payment initiated: {response.payment_id}")
            print(f"   QR Code: {response.qr_code}")
            print(f"   Expires at: {response.expires_at}")

            await asyncio.sleep(1.5)

            status = await self.service.get_payment_status(response.payment_id)
            print(f"✅ Final Status: {status.status.value}")

            return {
                "success": True,
                "payment_id": response.payment_id,
                "qr_code": response.qr_code,
                "status": status.status.value,
            }

        except Exception as e:
            print(f"❌ FastPay payment failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def example_subscription_creation(self) -> Dict[str, Any]:
        """Example: Monthly subscription setup."""
        print("\n🔄 Testing Subscription Creation...")

        request = SubscriptionRequest(
            customer_id="CUST_12345",
            plan_id="PREMIUM_MONTHLY",
            amount=Decimal("75000"),  # 75,000 IQD/month
            currency="IQD",
            payment_method=PaymentMethod.SWITCH,
            billing_cycle="monthly",
            customer_phone="07701234567",
            customer_name="محمد عبدالله",
        )

        try:
            response = await self.service.create_subscription(request)
            print(f"✅ Subscription created: {response.subscription_id}")
            print(f"   Status: {response.status.value}")
            print(f"   Next billing: {response.next_billing_date}")

            return {
                "success": True,
                "subscription_id": response.subscription_id,
                "status": response.status.value,
                "next_billing": response.next_billing_date.isoformat(),
            }

        except Exception as e:
            print(f"❌ Subscription creation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def example_payment_refund(self) -> Dict[str, Any]:
        """Example: Processing payment refund."""
        print("\n🔄 Testing Payment Refund...")

        # First create a payment
        payment_request = PaymentRequest(
            amount=Decimal("30000"),
            currency="IQD",
            payment_method=PaymentMethod.ASIACELL_CASH,
            customer_phone="07601234567",
            customer_name="علياء حسين",
            description="شراء ألعاب تفاعلية",
        )

        try:
            # Complete payment
            payment_response = await self.service.initiate_payment(payment_request)
            await asyncio.sleep(1)

            # Request partial refund
            refund_request = RefundRequest(
                payment_id=payment_response.payment_id,
                amount=Decimal("15000"),  # Partial refund
                reason="العميل طلب إلغاء جزء من الطلب",
            )

            refund_response = await self.service.request_refund(refund_request)
            print(f"✅ Refund processed: {refund_response.refund_id}")
            print(f"   Status: {refund_response.status.value}")
            print(f"   Refund amount: {refund_response.amount}")

            return {
                "success": True,
                "refund_id": refund_response.refund_id,
                "amount_refunded": float(refund_response.amount),
                "status": refund_response.status.value,
            }

        except Exception as e:
            print(f"❌ Refund failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def example_failed_payment_handling(self) -> Dict[str, Any]:
        """Example: Handling failed payments."""
        print("\n🔄 Testing Failed Payment Handling...")

        # Create a payment that will fail (mock provider simulates failures)
        request = PaymentRequest(
            amount=Decimal("999999999"),  # Very large amount to trigger failure
            currency="IQD",
            payment_method=PaymentMethod.KOREK_PAY,
            customer_phone="07501234567",
            customer_name="تجربة فشل الدفع",
            description="اختبار فشل الدفع",
        )

        try:
            response = await self.service.initiate_payment(request)
            print(f"⚠️  Payment initiated but will fail: {response.payment_id}")

            await asyncio.sleep(1)

            status = await self.service.get_payment_status(response.payment_id)
            print(f"❌ Payment failed as expected: {status.status.value}")
            print(f"   Error: {status.error_message}")

            return {
                "success": True,  # Success in handling failure
                "payment_id": response.payment_id,
                "status": status.status.value,
                "error_handled": True,
            }

        except Exception as e:
            print(f"✅ Failed payment handled correctly: {str(e)}")
            return {"success": True, "error_handled": True, "error": str(e)}

    async def example_multiple_providers_comparison(self) -> Dict[str, Any]:
        """Example: Compare different providers for same transaction."""
        print("\n🔄 Testing Multiple Providers...")

        base_request = PaymentRequest(
            amount=Decimal("40000"),
            currency="IQD",
            customer_phone="07401234567",
            customer_name="مقارنة المزودين",
            description="اختبار مقارنة المزودين",
        )

        providers_to_test = [
            PaymentMethod.ZAIN_CASH,
            PaymentMethod.FAST_PAY,
            PaymentMethod.SWITCH,
            PaymentMethod.BANK_TRANSFER,
        ]

        results = {}

        for provider in providers_to_test:
            try:
                request = PaymentRequest(
                    amount=base_request.amount,
                    currency=base_request.currency,
                    payment_method=provider,
                    customer_phone=base_request.customer_phone,
                    customer_name=base_request.customer_name,
                    description=f"{base_request.description} - {provider.value}",
                )

                start_time = datetime.utcnow()
                response = await self.service.initiate_payment(request)
                end_time = datetime.utcnow()

                processing_time = (end_time - start_time).total_seconds()

                results[provider.value] = {
                    "payment_id": response.payment_id,
                    "status": response.status.value,
                    "processing_time": processing_time,
                    "payment_url": response.payment_url,
                    "payment_code": response.payment_code,
                    "qr_code": response.qr_code,
                }

                print(
                    f"✅ {provider.value}: {processing_time:.2f}s - {response.status.value}"
                )

            except Exception as e:
                results[provider.value] = {"error": str(e), "processing_time": None}
                print(f"❌ {provider.value}: Failed - {str(e)}")

        return results

    async def example_rate_limiting_test(self) -> Dict[str, Any]:
        """Example: Test rate limiting behavior."""
        print("\n🔄 Testing Rate Limiting...")

        request = PaymentRequest(
            amount=Decimal("1000"),
            currency="IQD",
            payment_method=PaymentMethod.ZAIN_CASH,
            customer_phone="07301234567",
            customer_name="اختبار الحد الأقصى",
            description="اختبار الحد الأقصى للطلبات",
        )

        success_count = 0
        rate_limited_count = 0

        # Try to make many rapid requests
        for i in range(10):
            try:
                await self.service.initiate_payment(request)
                success_count += 1
                print(f"✅ Request {i+1}: Success")

            except Exception as e:
                if "rate" in str(e).lower() or "limit" in str(e).lower():
                    rate_limited_count += 1
                    print(f"⚠️  Request {i+1}: Rate limited")
                else:
                    print(f"❌ Request {i+1}: Error - {str(e)}")

        return {
            "total_requests": 10,
            "successful": success_count,
            "rate_limited": rate_limited_count,
            "rate_limiting_working": rate_limited_count > 0,
        }

    async def run_all_examples(self) -> Dict[str, Any]:
        """Run all payment examples."""
        print("🚀 Starting Iraqi Payment System Examples\n")
        print("=" * 50)

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": self.config.environment.value,
            "examples": {},
        }

        examples = [
            ("zaincash_payment", self.example_zaincash_payment),
            ("fastpay_payment", self.example_fastpay_qr_payment),
            ("subscription_creation", self.example_subscription_creation),
            ("payment_refund", self.example_payment_refund),
            ("failed_payment", self.example_failed_payment_handling),
            ("multiple_providers", self.example_multiple_providers_comparison),
            ("rate_limiting", self.example_rate_limiting_test),
        ]

        for name, example_func in examples:
            try:
                result = await example_func()
                results["examples"][name] = result
                await asyncio.sleep(0.5)  # Brief pause between examples

            except Exception as e:
                results["examples"][name] = {"success": False, "error": str(e)}
                print(f"❌ Example {name} failed: {str(e)}")

        print("\n" + "=" * 50)
        print("🎉 All examples completed!")

        # Summary
        total_examples = len(results["examples"])
        successful_examples = sum(
            1 for r in results["examples"].values() if r.get("success", False)
        )

        results["summary"] = {
            "total_examples": total_examples,
            "successful": successful_examples,
            "failed": total_examples - successful_examples,
            "success_rate": f"{(successful_examples/total_examples)*100:.1f}%",
        }

        print("\n📊 Summary:")
        print(f"   Total Examples: {total_examples}")
        print(f"   Successful: {successful_examples}")
        print(f"   Success Rate: {results['summary']['success_rate']}")

        return results


class PaymentSystemTester:
    """Comprehensive testing utilities for payment system."""

    def __init__(self):
        self.service = IraqiPaymentService()

    async def test_all_payment_methods(self) -> Dict[str, Any]:
        """Test all available payment methods."""
        methods = await self.service.get_supported_methods()
        results = {}

        for method in methods:
            request = PaymentRequest(
                amount=Decimal("10000"),
                currency="IQD",
                payment_method=method,
                customer_phone="07001234567",
                customer_name=f"Test {method.value}",
                description=f"Testing {method.value}",
            )

            try:
                response = await self.service.initiate_payment(request)
                results[method.value] = {
                    "success": True,
                    "payment_id": response.payment_id,
                    "status": response.status.value,
                }
            except Exception as e:
                results[method.value] = {"success": False, "error": str(e)}

        return results

    async def test_amount_validations(self) -> Dict[str, Any]:
        """Test amount validation across providers."""
        test_amounts = [
            Decimal("100"),  # Too small
            Decimal("1000"),  # Valid minimum
            Decimal("1000000"),  # Valid medium
            Decimal("999999999"),  # Too large
        ]

        results = {}

        for amount in test_amounts:
            request = PaymentRequest(
                amount=amount,
                currency="IQD",
                payment_method=PaymentMethod.ZAIN_CASH,
                customer_phone="07001234567",
                customer_name="Amount Test",
                description=f"Testing amount {amount}",
            )

            try:
                response = await self.service.initiate_payment(request)
                results[str(amount)] = {
                    "success": True,
                    "payment_id": response.payment_id,
                }
            except Exception as e:
                results[str(amount)] = {
                    "success": False,
                    "error": str(e),
                    "expected": "validation_error" in str(e).lower(),
                }

        return results

    async def performance_test(self, num_requests: int = 50) -> Dict[str, Any]:
        """Performance test with multiple concurrent requests."""
        import time

        start_time = time.time()

        tasks = []
        for i in range(num_requests):
            request = PaymentRequest(
                amount=Decimal("5000"),
                currency="IQD",
                payment_method=PaymentMethod.FAST_PAY,
                customer_phone=f"0700123{i:04d}",
                customer_name=f"Performance Test {i}",
                description=f"Performance test request {i}",
            )

            task = self.service.initiate_payment(request)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful

        return {
            "total_requests": num_requests,
            "successful": successful,
            "failed": failed,
            "total_time": total_time,
            "requests_per_second": num_requests / total_time,
            "average_response_time": total_time / num_requests,
        }


# CLI interface for running examples
async def main():
    """Main function to run payment examples."""

    # Configure for testing
    configure_for_environment(Environment.TESTING)

    examples = PaymentExamples()

    print("🇮🇶 Iraqi Payment System Examples")
    print("=" * 40)

    choice = input(
        """
Choose an option:
1. Run all examples
2. Test ZainCash payment
3. Test FastPay payment
4. Test subscription
5. Test refund
6. Test multiple providers
7. Performance test
8. Exit

Enter your choice (1-8): """
    )

    if choice == "1":
        results = await examples.run_all_examples()
        print("\n💾 Results saved to: payment_examples_results.json")
        with open("payment_examples_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    elif choice == "2":
        await examples.example_zaincash_payment()

    elif choice == "3":
        await examples.example_fastpay_qr_payment()

    elif choice == "4":
        await examples.example_subscription_creation()

    elif choice == "5":
        await examples.example_payment_refund()

    elif choice == "6":
        await examples.example_multiple_providers_comparison()

    elif choice == "7":
        tester = PaymentSystemTester()
        result = await tester.performance_test(25)
        print("\n⚡ Performance Results:")
        print(f"   Requests/second: {result['requests_per_second']:.2f}")
        print(f"   Average response: {result['average_response_time']:.3f}s")
        print(
            f"   Success rate: {(result['successful']/result['total_requests'])*100:.1f}%"
        )

    elif choice == "8":
        print("👋 Goodbye!")
        return

    else:
        print("❌ Invalid choice!")


if __name__ == "__main__":
    asyncio.run(main())
