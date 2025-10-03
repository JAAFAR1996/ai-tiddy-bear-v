-- ===========================================
-- AI TEDDY BEAR V5 - PREMIUM SYSTEM MIGRATION
-- ===========================================

-- Create subscription tier enumeration
CREATE TYPE subscription_status AS ENUM ('ACTIVE', 'CANCELLED', 'EXPIRED', 'TRIAL', 'PAST_DUE');
CREATE TYPE transaction_type AS ENUM ('SUBSCRIPTION', 'UPGRADE', 'DOWNGRADE', 'CANCELLATION', 'REFUND');
CREATE TYPE payment_status AS ENUM ('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REFUNDED');
CREATE TYPE websocket_status AS ENUM ('CONNECTING', 'CONNECTED', 'DISCONNECTED', 'ERROR');
CREATE TYPE notification_type AS ENUM ('SAFETY_ALERT', 'BEHAVIOR_CONCERN', 'USAGE_LIMIT', 'PREMIUM_FEATURE', 'EMERGENCY');
CREATE TYPE notification_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
CREATE TYPE delivery_status AS ENUM ('PENDING', 'PARTIAL', 'DELIVERED', 'FAILED');

-- Create subscription tiers table
CREATE TABLE subscription_tiers (
    id SERIAL PRIMARY KEY,
    tier_name VARCHAR(50) UNIQUE NOT NULL,
    monthly_price FLOAT NOT NULL DEFAULT 0.0,
    children_limit INTEGER NOT NULL DEFAULT 1,
    history_days INTEGER NOT NULL DEFAULT 7,
    reports_per_month INTEGER NOT NULL DEFAULT 1,
    features_json TEXT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create user subscriptions table
CREATE TABLE user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    tier_id INTEGER REFERENCES subscription_tiers(id) NOT NULL,
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),
    status subscription_status NOT NULL DEFAULT 'TRIAL',
    start_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,
    trial_end_date TIMESTAMP,
    next_billing_date TIMESTAMP,
    cancelled_at TIMESTAMP,
    billing_cycle_days INTEGER NOT NULL DEFAULT 30,
    last_payment_amount FLOAT,
    last_payment_date TIMESTAMP,
    subscription_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create payment transactions table
CREATE TABLE payment_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES user_subscriptions(id) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    transaction_type transaction_type NOT NULL,
    amount FLOAT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    provider VARCHAR(50) NOT NULL DEFAULT 'stripe',
    provider_transaction_id VARCHAR(255),
    provider_customer_id VARCHAR(255),
    status payment_status NOT NULL DEFAULT 'PENDING',
    transaction_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_date TIMESTAMP,
    description TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create websocket connections table
CREATE TABLE websocket_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    connection_id VARCHAR(255) UNIQUE NOT NULL,
    client_ip VARCHAR(45),
    user_agent TEXT,
    room_id VARCHAR(255),
    status websocket_status NOT NULL DEFAULT 'CONNECTING',
    connected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP,
    messages_sent INTEGER DEFAULT 0 NOT NULL,
    messages_received INTEGER DEFAULT 0 NOT NULL,
    connection_metadata TEXT
);

-- Create notification deliveries table
CREATE TABLE notification_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    notification_type notification_type NOT NULL,
    priority notification_priority NOT NULL DEFAULT 'MEDIUM',
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    action_url VARCHAR(500),
    websocket_delivered BOOLEAN DEFAULT FALSE NOT NULL,
    email_delivered BOOLEAN DEFAULT FALSE NOT NULL,
    sms_delivered BOOLEAN DEFAULT FALSE NOT NULL,
    push_delivered BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    websocket_sent_at TIMESTAMP,
    email_sent_at TIMESTAMP,
    sms_sent_at TIMESTAMP,
    push_sent_at TIMESTAMP,
    websocket_attempts INTEGER DEFAULT 0 NOT NULL,
    email_attempts INTEGER DEFAULT 0 NOT NULL,
    sms_attempts INTEGER DEFAULT 0 NOT NULL,
    push_attempts INTEGER DEFAULT 0 NOT NULL,
    overall_status delivery_status NOT NULL DEFAULT 'PENDING',
    last_error TEXT,
    retry_after TIMESTAMP,
    related_child_id VARCHAR(255),
    safety_score INTEGER,
    metadata TEXT
);

-- Create feature usage table
CREATE TABLE feature_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    subscription_id UUID REFERENCES user_subscriptions(id),
    feature_name VARCHAR(100) NOT NULL,
    feature_category VARCHAR(50) NOT NULL,
    usage_count INTEGER DEFAULT 1 NOT NULL,
    usage_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usage_month VARCHAR(7) NOT NULL,
    is_billable BOOLEAN DEFAULT TRUE NOT NULL,
    tier_required VARCHAR(50) NOT NULL,
    usage_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes
CREATE INDEX idx_subscription_tier_name ON subscription_tiers (tier_name);
CREATE INDEX idx_subscription_tier_active ON subscription_tiers (is_active);
CREATE INDEX idx_user_subscription_user_id ON user_subscriptions (user_id);
CREATE INDEX idx_user_subscription_status ON user_subscriptions (status);
CREATE INDEX idx_user_subscription_stripe_id ON user_subscriptions (stripe_subscription_id);
CREATE INDEX idx_user_subscription_end_date ON user_subscriptions (end_date);
CREATE INDEX idx_payment_transaction_subscription ON payment_transactions (subscription_id);
CREATE INDEX idx_payment_transaction_user ON payment_transactions (user_id);
CREATE INDEX idx_payment_transaction_status ON payment_transactions (status);
CREATE INDEX idx_payment_transaction_date ON payment_transactions (transaction_date);
CREATE INDEX idx_payment_transaction_provider_id ON payment_transactions (provider_transaction_id);
CREATE INDEX idx_websocket_user_id ON websocket_connections (user_id);
CREATE INDEX idx_websocket_connection_id ON websocket_connections (connection_id);
CREATE INDEX idx_websocket_status ON websocket_connections (status);
CREATE INDEX idx_websocket_room_id ON websocket_connections (room_id);
CREATE INDEX idx_websocket_last_activity ON websocket_connections (last_activity_at);
CREATE INDEX idx_notification_user_id ON notification_deliveries (user_id);
CREATE INDEX idx_notification_type ON notification_deliveries (notification_type);
CREATE INDEX idx_notification_priority ON notification_deliveries (priority);
CREATE INDEX idx_notification_status ON notification_deliveries (overall_status);
CREATE INDEX idx_notification_created ON notification_deliveries (created_at);
CREATE INDEX idx_notification_child_id ON notification_deliveries (related_child_id);
CREATE INDEX idx_feature_usage_user_id ON feature_usage (user_id);
CREATE INDEX idx_feature_usage_feature ON feature_usage (feature_name);
CREATE INDEX idx_feature_usage_month ON feature_usage (usage_month);
CREATE INDEX idx_feature_usage_date ON feature_usage (usage_date);
CREATE INDEX idx_feature_usage_subscription ON feature_usage (subscription_id);

-- Add constraints
ALTER TABLE user_subscriptions ADD CONSTRAINT uq_user_subscription_user_id UNIQUE (user_id);
ALTER TABLE user_subscriptions ADD CONSTRAINT chk_subscription_dates CHECK (end_date IS NULL OR end_date > start_date);
ALTER TABLE payment_transactions ADD CONSTRAINT chk_payment_amount CHECK (amount >= 0);
ALTER TABLE feature_usage ADD CONSTRAINT chk_usage_count CHECK (usage_count > 0);
ALTER TABLE feature_usage ADD CONSTRAINT uq_daily_feature_usage UNIQUE (user_id, feature_name, usage_date);

-- Insert default subscription tiers
INSERT INTO subscription_tiers (tier_name, monthly_price, children_limit, history_days, reports_per_month, features_json) VALUES 
('FREE', 0.0, 1, 7, 1, '["basic_monitoring"]'),
('BASIC', 9.99, 3, 90, 5, '["advanced_analytics", "export_data", "real_time_alerts", "extended_history"]'),
('PREMIUM', 19.99, -1, -1, -1, '["custom_reports", "priority_support", "unlimited_children", "ai_insights"]'),
('ENTERPRISE', 49.99, -1, -1, -1, '["all_premium_features", "custom_integrations", "dedicated_support"]');

-- Add comments
COMMENT ON TABLE subscription_tiers IS 'Premium subscription tier configuration';
COMMENT ON TABLE user_subscriptions IS 'User premium subscription records with Stripe integration';
COMMENT ON TABLE payment_transactions IS 'Payment transaction audit trail';
COMMENT ON TABLE websocket_connections IS 'Active WebSocket connection tracking';
COMMENT ON TABLE notification_deliveries IS 'Real-time notification delivery tracking';
COMMENT ON TABLE feature_usage IS 'Premium feature usage tracking for billing';
