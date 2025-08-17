"""
Enhanced Configuration for Premium Features and WebSocket
========================================================
Configuration settings for premium subscriptions and real-time notifications.
"""

# Premium Subscription Configuration
PREMIUM_CONFIG = {
    # Subscription Pricing (in USD)
    "PRICING": {
        "FREE": {
            "monthly_price": 0.0,
            "children_limit": 1,
            "history_days": 7,
            "reports_per_month": 1,
            "features": ["basic_monitoring"],
        },
        "BASIC": {
            "monthly_price": 9.99,
            "children_limit": 3,
            "history_days": 90,
            "reports_per_month": 5,
            "features": [
                "advanced_analytics",
                "export_data",
                "real_time_alerts",
                "extended_history",
            ],
        },
        "PREMIUM": {
            "monthly_price": 19.99,
            "children_limit": -1,  # Unlimited
            "history_days": -1,  # Unlimited
            "reports_per_month": -1,
            "features": [
                "custom_reports",
                "priority_support",
                "unlimited_children",
                "ai_insights",
            ],
        },
        "ENTERPRISE": {
            "monthly_price": 49.99,
            "children_limit": -1,
            "history_days": -1,
            "reports_per_month": -1,
            "features": [
                "all_premium_features",
                "custom_integrations",
                "dedicated_support",
            ],
        },
    },
    # Payment Configuration
    "PAYMENT": {
        "STRIPE_PUBLISHABLE_KEY": "pk_test_...",  # Set in environment
        "STRIPE_SECRET_KEY": "sk_test_...",  # Set in environment
        "STRIPE_WEBHOOK_SECRET": "whsec_...",  # Set in environment
        "DEFAULT_CURRENCY": "USD",
        "TRIAL_DAYS": 7,
        "BILLING_CYCLE_DAYS": 30,
    },
    # Feature Limits
    "FEATURE_LIMITS": {
        "CUSTOM_REPORTS_PREMIUM": 10,
        "AI_INSIGHTS_PREMIUM": 20,
        "EXPORT_DATA_BASIC": 5,
        "MAX_CHILDREN_BASIC": 3,
    },
}

# WebSocket Configuration
WEBSOCKET_CONFIG = {
    # Connection Settings
    "MAX_CONNECTIONS_PER_USER": 5,
    "HEARTBEAT_INTERVAL": 30,
    "CONNECTION_TIMEOUT": 300,
    "MESSAGE_RATE_LIMIT": 100,  # per minute
    "MAX_MESSAGE_SIZE": 10240,  # 10KB
    # Real-time Notification Settings
    "NOTIFICATION_PRIORITIES": {
        "LOW": {"retry_attempts": 1, "escalation_delay": 0, "fallback_enabled": False},
        "MEDIUM": {
            "retry_attempts": 2,
            "escalation_delay": 60,
            "fallback_enabled": True,
        },
        "HIGH": {"retry_attempts": 3, "escalation_delay": 30, "fallback_enabled": True},
        "CRITICAL": {
            "retry_attempts": 5,
            "escalation_delay": 10,
            "fallback_enabled": True,
            "emergency_escalation": True,
        },
    },
    # Emergency Settings
    "EMERGENCY_ESCALATION_DELAY": 300,  # 5 minutes
    "EMERGENCY_CONTACT_AUTHORITIES": True,
    "EMERGENCY_BROADCAST_ALL_ADMINS": True,
    # Subscription Topics
    "SUBSCRIPTION_TOPICS": {
        "SAFETY_ALERTS": "safety:alerts",
        "BEHAVIOR_CONCERNS": "behavior:concerns",
        "USAGE_LIMITS": "usage:limits",
        "PREMIUM_FEATURES": "premium:features",
        "SYSTEM_ALERTS": "system:alerts",
        "EMERGENCY": "emergency:all",
    },
}

# Real-time Alert Configuration
ALERT_CONFIG = {
    # Alert Types and Their Requirements
    "ALERT_TYPES": {
        "SAFETY_ALERT": {
            "required_subscription": "FREE",
            "max_per_hour": 10,
            "auto_escalate_threshold": 3,
            "notification_channels": ["websocket", "email", "sms"],
        },
        "BEHAVIOR_CONCERN": {
            "required_subscription": "BASIC",
            "max_per_hour": 5,
            "auto_escalate_threshold": 5,
            "notification_channels": ["websocket", "email"],
        },
        "USAGE_LIMIT": {
            "required_subscription": "FREE",
            "max_per_hour": 20,
            "auto_escalate_threshold": 0,
            "notification_channels": ["websocket", "in_app"],
        },
        "PREMIUM_FEATURE": {
            "required_subscription": "FREE",
            "max_per_hour": 10,
            "auto_escalate_threshold": 0,
            "notification_channels": ["websocket", "in_app"],
        },
        "EMERGENCY": {
            "required_subscription": "FREE",
            "max_per_hour": 2,
            "auto_escalate_threshold": 1,
            "notification_channels": [
                "websocket",
                "email",
                "sms",
                "push",
                "phone_call",
            ],
        },
    },
    # Safety Score Thresholds
    "SAFETY_THRESHOLDS": {
        "CRITICAL": 30,  # Below 30% = Emergency
        "HIGH": 50,  # Below 50% = High priority alert
        "MEDIUM": 70,  # Below 70% = Medium priority alert
        "LOW": 85,  # Below 85% = Low priority alert
    },
    # Behavioral Pattern Thresholds
    "BEHAVIOR_THRESHOLDS": {
        "CONCERNING_PATTERN_CONFIDENCE": 0.8,
        "TRENDING_NEGATIVE_THRESHOLD": 3,  # 3 consecutive negative interactions
        "EMOTIONAL_DISTRESS_INDICATORS": ["sad", "angry", "frustrated", "scared"],
        "LANGUAGE_CONCERN_KEYWORDS": ["hate", "hurt", "scary", "angry", "mean"],
    },
}

# Mobile App Configuration
MOBILE_APP_CONFIG = {
    # Push Notification Settings
    "PUSH_NOTIFICATIONS": {
        "FCM_SERVER_KEY": "",  # Set in environment
        "APNS_CERTIFICATE": "",  # Set in environment
        "BADGE_COUNT_ENABLED": True,
        "SOUND_ENABLED": True,
        "VIBRATION_ENABLED": True,
    },
    # App Features by Subscription
    "FEATURES_BY_TIER": {
        "FREE": [
            "basic_monitoring",
            "single_child_profile",
            "weekly_reports",
            "basic_alerts",
        ],
        "BASIC": [
            "advanced_analytics",
            "multiple_children",
            "daily_reports",
            "real_time_alerts",
            "export_basic_data",
            "extended_history",
        ],
        "PREMIUM": [
            "custom_reports",
            "ai_insights",
            "unlimited_children",
            "priority_support",
            "advanced_export",
            "behavioral_analysis",
        ],
        "ENTERPRISE": [
            "all_premium_features",
            "custom_integrations",
            "dedicated_support",
            "white_labeling",
            "api_access",
        ],
    },
    # UI Configuration
    "UI_SETTINGS": {
        "THEME_COLORS": {
            "PRIMARY": "#8B4513",  # Brown (teddy bear)
            "SECONDARY": "#FFE4E1",  # Light pink
            "ACCENT": "#FF6B6B",  # Coral red
            "SUCCESS": "#4ECDC4",  # Teal
            "WARNING": "#FFD93D",  # Yellow
            "DANGER": "#FF6B6B",  # Red
            "INFO": "#45B7D1",  # Blue
        },
        "REFRESH_INTERVALS": {
            "DASHBOARD": 30,  # seconds
            "NOTIFICATIONS": 10,  # seconds
            "ANALYTICS": 300,  # 5 minutes
            "DEVICE_STATUS": 60,  # 1 minute
        },
    },
}

# Development and Testing Configuration
DEVELOPMENT_CONFIG = {
    # Data Settings
    "USE_MOCK_PAYMENTS": True,
    "USE_MOCK_NOTIFICATIONS": True,
    "ENABLE_TEST_ENDPOINTS": True,
    # Debug Settings
    "LOG_WEBSOCKET_MESSAGES": True,
    "LOG_PAYMENT_EVENTS": True,
    "LOG_NOTIFICATION_DELIVERY": True,
    # Test User Settings
    "TEST_USERS": {
        "FREE_USER": {
            "user_id": "test_free_user",
            "subscription_tier": "FREE",
            "children": ["test_child_1"],
        },
        "PREMIUM_USER": {
            "user_id": "test_premium_user",
            "subscription_tier": "PREMIUM",
            "children": ["test_child_1", "test_child_2", "test_child_3"],
        },
    },
}

# Export all configurations
__all__ = [
    "PREMIUM_CONFIG",
    "WEBSOCKET_CONFIG",
    "ALERT_CONFIG",
    "MOBILE_APP_CONFIG",
    "DEVELOPMENT_CONFIG",
]
