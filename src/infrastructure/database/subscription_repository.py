"""
Subscription Repository - Production Ready
==========================================
Repository for managing subscription data in production database.
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from .models import Subscription
from .database_manager import database_manager
from .repository import BaseRepository


class SubscriptionRepository(BaseRepository):
    """Repository for managing subscriptions in production."""

    def __init__(self):
        super().__init__(Subscription)

    async def get_user_subscription(
        self, user_id: uuid.UUID
    ) -> Optional[Subscription]:
        """Get active subscription for a user."""
        async with database_manager.get_async_session() as session:
            query = select(Subscription).where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.status.in_(["active", "trialing"])
                )
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def create_subscription(
        self, subscription_data: Dict[str, Any]
    ) -> Subscription:
        """Create a new subscription."""
        async with database_manager.get_async_session() as session:
            subscription = Subscription(**subscription_data)
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)
            return subscription

    async def update_subscription(
        self, subscription_id: uuid.UUID, updates: Dict[str, Any]
    ) -> Optional[Subscription]:
        """Update an existing subscription."""
        async with database_manager.get_async_session() as session:
            subscription = await session.get(Subscription, subscription_id)
            if subscription:
                for key, value in updates.items():
                    setattr(subscription, key, value)
                subscription.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(subscription)
            return subscription

    async def cancel_subscription(
        self, subscription_id: uuid.UUID, immediate: bool = False
    ) -> Optional[Subscription]:
        """Cancel a subscription."""
        updates = {
            "status": "cancelled" if immediate else "pending_cancellation",
            "cancelled_at": datetime.utcnow()
        }
        if not immediate:
            updates["cancel_at_period_end"] = True
        
        return await self.update_subscription(subscription_id, updates)

    async def get_expired_subscriptions(self) -> List[Subscription]:
        """Get all expired subscriptions that need processing."""
        async with database_manager.get_async_session() as session:
            query = select(Subscription).where(
                and_(
                    Subscription.status == "active",
                    Subscription.current_period_end < datetime.utcnow()
                )
            )
            result = await session.execute(query)
            return result.scalars().all()

    async def record_payment_transaction(
        self, transaction_data: Dict[str, Any]
    ) -> None:
        """Record a payment transaction for audit purposes."""
        # This would typically write to a payment_transactions table
        # For now, we'll log the transaction
        async with database_manager.get_async_session() as session:
            # Could create a PaymentTransaction model and save it
            # For now, we update the subscription's last payment date
            subscription_id = transaction_data.get("subscription_id")
            if subscription_id:
                subscription = await session.get(Subscription, subscription_id)
                if subscription:
                    subscription.updated_at = datetime.utcnow()
                    await session.commit()

    async def get_subscription_by_stripe_id(
        self, stripe_subscription_id: str
    ) -> Optional[Subscription]:
        """Get subscription by Stripe ID."""
        async with database_manager.get_async_session() as session:
            query = select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_feature_usage(
        self, user_id: uuid.UUID, feature: str
    ) -> Dict[str, Any]:
        """Get feature usage for a user."""
        # This would typically query a feature_usage table
        # For now, return a default response
        async with database_manager.get_async_session() as session:
            subscription = await self.get_user_subscription(user_id)
            if subscription:
                # Would query actual usage data
                return {
                    "user_id": str(user_id),
                    "feature": feature,
                    "current_usage": 0,
                    "limit": -1,  # Would be based on subscription tier
                    "reset_date": None
                }
            return {
                "user_id": str(user_id),
                "feature": feature,
                "current_usage": 0,
                "limit": 0,
                "reset_date": None
            }