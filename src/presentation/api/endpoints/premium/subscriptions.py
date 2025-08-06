"""
Premium Subscription API Endpoints
=================================
RESTful API for managing premium subscriptions and billing.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.application.services.premium.subscription_service import (
    PremiumSubscriptionService,
    get_premium_subscription_service,
    InsufficientPermissionsError,
    SubscriptionExpiredError,
    FeatureLimitExceededError,
)
from src.core.entities.subscription import SubscriptionTier, SubscriptionStatus
from src.infrastructure.security.auth import get_current_user
from src.core.entities import User

router = APIRouter(prefix="/api/v1/premium", tags=["Premium"])


# Request/Response Models
class CreateSubscriptionRequest(BaseModel):
    """Request to create new subscription."""

    tier: SubscriptionTier
    payment_method_id: Optional[str] = None
    trial_days: int = Field(default=7, ge=0, le=30)


class UpgradeSubscriptionRequest(BaseModel):
    """Request to upgrade subscription."""

    new_tier: SubscriptionTier
    payment_method_id: Optional[str] = None


class FeatureUsageRequest(BaseModel):
    """Request to use premium feature."""

    feature_id: str
    amount: int = Field(default=1, ge=1)
    metadata: Optional[Dict[str, Any]] = None


class SubscriptionResponse(BaseModel):
    """Subscription response model."""

    id: str
    user_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    monthly_price: float
    currency: str
    created_at: datetime
    expires_at: Optional[datetime]
    trial_ends_at: Optional[datetime]
    is_active: bool
    is_trial: bool
    days_until_expiry: Optional[int]
    feature_limits: Dict[str, int]
    usage_counters: Dict[str, int]


class SubscriptionAnalyticsResponse(BaseModel):
    """Subscription analytics response."""

    subscription: Dict[str, Any]
    usage: Dict[str, Any]
    billing: Dict[str, Any]


class FeatureAccessResponse(BaseModel):
    """Feature access check response."""

    can_access: bool
    error_message: Optional[str] = None
    remaining_usage: Optional[int] = None


class PricingResponse(BaseModel):
    """Pricing information response."""

    tiers: Dict[str, Dict[str, Any]]
    features: List[Dict[str, Any]]


# API Endpoints
@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> SubscriptionResponse:
    """
    Create new premium subscription for user.

    Requires:
    - Valid user authentication
    - Payment method for paid tiers (except during trial)

    Returns:
    - Created subscription details
    """
    try:
        subscription = await subscription_service.create_subscription(
            user_id=UUID(current_user.id),
            tier=request.tier,
            payment_method_id=request.payment_method_id,
            trial_days=request.trial_days,
        )

        return SubscriptionResponse(
            id=str(subscription.id),
            user_id=str(subscription.user_id),
            tier=subscription.tier,
            status=subscription.status,
            monthly_price=subscription.monthly_price,
            currency=subscription.currency,
            created_at=subscription.created_at,
            expires_at=subscription.expires_at,
            trial_ends_at=subscription.trial_ends_at,
            is_active=subscription.is_active(),
            is_trial=subscription.is_trial(),
            days_until_expiry=subscription.days_until_expiry(),
            feature_limits=subscription.feature_limits,
            usage_counters=subscription.usage_counters,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create subscription: {str(e)}",
        )


@router.get("/subscriptions/current", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> Optional[SubscriptionResponse]:
    """
    Get current user's subscription details.

    Returns:
    - Current subscription or null if no subscription exists
    """
    try:
        subscription = await subscription_service.get_user_subscription(
            UUID(current_user.id)
        )

        if not subscription:
            return None

        return SubscriptionResponse(
            id=str(subscription.id),
            user_id=str(subscription.user_id),
            tier=subscription.tier,
            status=subscription.status,
            monthly_price=subscription.monthly_price,
            currency=subscription.currency,
            created_at=subscription.created_at,
            expires_at=subscription.expires_at,
            trial_ends_at=subscription.trial_ends_at,
            is_active=subscription.is_active(),
            is_trial=subscription.is_trial(),
            days_until_expiry=subscription.days_until_expiry(),
            feature_limits=subscription.feature_limits,
            usage_counters=subscription.usage_counters,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription: {str(e)}",
        )


@router.put("/subscriptions/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    request: UpgradeSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> SubscriptionResponse:
    """
    Upgrade user's subscription to higher tier.

    Requires:
    - Existing subscription
    - Valid upgrade path (can only upgrade to higher tiers)
    - Payment method for paid tiers

    Returns:
    - Updated subscription details
    """
    try:
        subscription = await subscription_service.upgrade_subscription(
            user_id=UUID(current_user.id),
            new_tier=request.new_tier,
            payment_method_id=request.payment_method_id,
        )

        return SubscriptionResponse(
            id=str(subscription.id),
            user_id=str(subscription.user_id),
            tier=subscription.tier,
            status=subscription.status,
            monthly_price=subscription.monthly_price,
            currency=subscription.currency,
            created_at=subscription.created_at,
            expires_at=subscription.expires_at,
            trial_ends_at=subscription.trial_ends_at,
            is_active=subscription.is_active(),
            is_trial=subscription.is_trial(),
            days_until_expiry=subscription.days_until_expiry(),
            feature_limits=subscription.feature_limits,
            usage_counters=subscription.usage_counters,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to upgrade subscription: {str(e)}",
        )


@router.delete("/subscriptions/cancel")
async def cancel_subscription(
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> Dict[str, Any]:
    """
    Cancel user's subscription.

    Note: Subscription remains active until end of billing period.

    Returns:
    - Cancellation confirmation
    """
    try:
        success = await subscription_service.cancel_subscription(
            user_id=UUID(current_user.id),
            reason=reason or "User requested cancellation",
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found",
            )

        return {
            "success": True,
            "message": "Subscription cancelled successfully",
            "cancelled_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )


@router.get("/features/{feature_id}/access", response_model=FeatureAccessResponse)
async def check_feature_access(
    feature_id: str,
    amount: int = 1,
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> FeatureAccessResponse:
    """
    Check if user can access specific premium feature.

    Args:
    - feature_id: Feature identifier
    - amount: Requested usage amount (default: 1)

    Returns:
    - Access permission and details
    """
    try:
        can_access, error_message = await subscription_service.check_feature_access(
            user_id=UUID(current_user.id),
            feature_id=feature_id,
            requested_amount=amount,
        )

        # Calculate remaining usage if applicable
        remaining_usage = None
        if can_access:
            subscription = await subscription_service.get_user_subscription(
                UUID(current_user.id)
            )
            if subscription and feature_id in subscription.feature_limits:
                limit = subscription.feature_limits[feature_id]
                used = subscription.usage_counters.get(feature_id, 0)
                remaining_usage = (
                    max(0, limit - used) if limit >= 0 else -1
                )  # -1 = unlimited

        return FeatureAccessResponse(
            can_access=can_access,
            error_message=error_message,
            remaining_usage=remaining_usage,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check feature access: {str(e)}",
        )


@router.post("/features/use")
async def use_premium_feature(
    request: FeatureUsageRequest,
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> Dict[str, Any]:
    """
    Record usage of premium feature.

    This endpoint should be called when user actually uses a premium feature
    to track usage against their subscription limits.

    Returns:
    - Usage confirmation and remaining quota
    """
    try:
        success = await subscription_service.use_premium_feature(
            user_id=UUID(current_user.id),
            feature_id=request.feature_id,
            amount=request.amount,
            metadata=request.metadata,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Feature usage not allowed",
            )

        # Get updated usage info
        subscription = await subscription_service.get_user_subscription(
            UUID(current_user.id)
        )
        remaining = None
        if subscription and request.feature_id in subscription.feature_limits:
            limit = subscription.feature_limits[request.feature_id]
            used = subscription.usage_counters.get(request.feature_id, 0)
            remaining = max(0, limit - used) if limit >= 0 else -1

        return {
            "success": True,
            "feature_id": request.feature_id,
            "amount_used": request.amount,
            "remaining_usage": remaining,
            "timestamp": datetime.now().isoformat(),
        }

    except (
        InsufficientPermissionsError,
        SubscriptionExpiredError,
        FeatureLimitExceededError,
    ) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record feature usage: {str(e)}",
        )


@router.get("/analytics", response_model=SubscriptionAnalyticsResponse)
async def get_subscription_analytics(
    current_user: User = Depends(get_current_user),
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> SubscriptionAnalyticsResponse:
    """
    Get comprehensive subscription analytics for user.

    Includes:
    - Subscription details and status
    - Feature usage statistics
    - Billing information

    Returns:
    - Complete analytics data
    """
    try:
        analytics = await subscription_service.get_subscription_analytics(
            UUID(current_user.id)
        )

        if "error" in analytics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=analytics["error"]
            )

        return SubscriptionAnalyticsResponse(**analytics)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}",
        )


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing_information() -> PricingResponse:
    """
    Get current pricing information and feature details.

    Public endpoint - no authentication required.

    Returns:
    - All subscription tiers with pricing
    - Available features and requirements
    """
    try:
        from src.core.entities.subscription import (
            SUBSCRIPTION_PRICING,
            PREMIUM_FEATURES,
        )

        # Format features for response
        features_list = []
        for feature in PREMIUM_FEATURES:
            features_list.append(
                {
                    "feature_id": feature.feature_id,
                    "name": feature.name,
                    "description": feature.description,
                    "required_tier": feature.required_tier.value,
                    "monthly_limit": feature.monthly_limit,
                    "enabled": feature.enabled,
                }
            )

        return PricingResponse(tiers=SUBSCRIPTION_PRICING, features=features_list)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pricing information: {str(e)}",
        )


# Webhook endpoints for payment processing (Stripe, PayPal, etc.)
@router.post("/webhooks/stripe")
async def stripe_webhook(
    # TODO: Add Stripe webhook signature verification
    # TODO: Handle Stripe events (payment success, failure, subscription updates)
    subscription_service: PremiumSubscriptionService = Depends(
        get_premium_subscription_service
    ),
) -> Dict[str, str]:
    """
    Handle Stripe webhook events.

    Events handled:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    # TODO: Implement Stripe webhook handling
    return {"status": "webhook_received"}
