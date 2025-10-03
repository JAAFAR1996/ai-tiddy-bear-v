-- ===========================================
-- AI TEDDY BEAR V5 - COMPLETE DATABASE SCHEMA
-- ===========================================
-- Complete database schema with all required tables
-- Includes: Core tables, Payment system, COPPA compliance, Audit trails

-- Create additional ENUMs
CREATE TYPE user_role AS ENUM ('child', 'parent', 'admin', 'support');
CREATE TYPE conversation_status AS ENUM ('active', 'paused', 'completed', 'archived');
CREATE TYPE content_type AS ENUM ('story', 'conversation', 'game', 'educational');
CREATE TYPE message_type AS ENUM ('text', 'audio', 'image', 'system');
CREATE TYPE safety_level AS ENUM ('safe', 'caution', 'warning', 'danger');
CREATE TYPE interaction_type AS ENUM ('voice', 'touch', 'gesture', 'button');
CREATE TYPE device_status AS ENUM ('pending', 'active', 'inactive', 'error', 'maintenance');
CREATE TYPE session_status AS ENUM ('active', 'expired', 'terminated');

-- ===========================================
-- CORE TABLES
-- ===========================================

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255),
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    display_name VARCHAR(100),
    avatar_url VARCHAR(500),
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    settings JSONB NOT NULL DEFAULT '{}',
    last_login_at TIMESTAMP WITH TIME ZONE,
    login_count INTEGER NOT NULL DEFAULT 0,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Children table (COPPA compliant)
CREATE TABLE children (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID REFERENCES users(id) NOT NULL,
    name VARCHAR(100) NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 3 AND age <= 13),
    avatar_url VARCHAR(500),
    preferences JSONB NOT NULL DEFAULT '{}',
    safety_settings JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    parental_consent_verified BOOLEAN NOT NULL DEFAULT false,
    consent_timestamp TIMESTAMP WITH TIME ZONE,
    consent_ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    child_id UUID REFERENCES children(id) NOT NULL,
    title VARCHAR(255),
    status conversation_status NOT NULL DEFAULT 'active',
    content_type content_type NOT NULL DEFAULT 'conversation',
    context JSONB NOT NULL DEFAULT '{}',
    safety_score INTEGER CHECK (safety_score >= 0 AND safety_score <= 100),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) NOT NULL,
    sender_type VARCHAR(20) NOT NULL CHECK (sender_type IN ('child', 'ai', 'system')),
    content TEXT NOT NULL,
    message_type message_type NOT NULL DEFAULT 'text',
    audio_url VARCHAR(500),
    image_url VARCHAR(500),
    safety_level safety_level NOT NULL DEFAULT 'safe',
    safety_score INTEGER CHECK (safety_score >= 0 AND safety_score <= 100),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Safety Reports table
CREATE TABLE safety_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    child_id UUID REFERENCES children(id) NOT NULL,
    conversation_id UUID REFERENCES conversations(id),
    message_id UUID REFERENCES messages(id),
    report_type VARCHAR(50) NOT NULL,
    severity safety_level NOT NULL,
    description TEXT NOT NULL,
    action_taken TEXT,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Audit Logs table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Interactions table
CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    child_id UUID REFERENCES children(id) NOT NULL,
    device_id UUID,
    interaction_type interaction_type NOT NULL,
    duration_seconds INTEGER,
    success BOOLEAN NOT NULL DEFAULT true,
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Devices table (ESP32)
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id VARCHAR(64) UNIQUE NOT NULL,
    device_type VARCHAR(32) NOT NULL DEFAULT 'ESP32_TEDDY',
    hardware_version VARCHAR(16),
    firmware_version VARCHAR(16),
    status device_status NOT NULL DEFAULT 'pending',
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    ip_address VARCHAR(45),
    oob_secret_hash VARCHAR(64),
    device_fingerprint VARCHAR(128),
    mac_address VARCHAR(17),
    paired_at TIMESTAMP WITH TIME ZONE,
    parent_id UUID REFERENCES users(id),
    configuration JSONB NOT NULL DEFAULT '{}',
    capabilities JSONB NOT NULL DEFAULT '[]',
    total_uptime_hours FLOAT NOT NULL DEFAULT 0.0,
    interaction_count INTEGER NOT NULL DEFAULT 0,
    last_interaction_at TIMESTAMP WITH TIME ZONE,
    registration_source VARCHAR(32) NOT NULL DEFAULT 'auto',
    compliance_flags JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    read BOOLEAN NOT NULL DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,
    action_url VARCHAR(500),
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    retention_status VARCHAR(20) NOT NULL DEFAULT 'active',
    scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    updated_by UUID,
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

-- Delivery Records table
CREATE TABLE delivery_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID REFERENCES notifications(id) NOT NULL,
    delivery_method VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- ===========================================
-- PAYMENT SYSTEM TABLES (ADVANCED)
-- ===========================================

-- Refund Transactions table
CREATE TABLE refund_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_transaction_id UUID REFERENCES payment_transactions(id) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Subscription Payments table
CREATE TABLE subscription_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID REFERENCES user_subscriptions(id) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Subscription Payment Attempts table
CREATE TABLE subscription_payment_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_payment_id UUID REFERENCES subscription_payments(id) NOT NULL,
    attempt_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    attempted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Payment Audit Logs table
CREATE TABLE payment_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID,
    action VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    user_id VARCHAR(255),
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Webhook Events table
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    signature VARCHAR(500),
    processed BOOLEAN NOT NULL DEFAULT false,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Payment Providers table
CREATE TABLE payment_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    provider_type VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    configuration JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Payment Fraud Checks table
CREATE TABLE payment_fraud_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID REFERENCES payment_transactions(id) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    risk_score INTEGER CHECK (risk_score >= 0 AND risk_score <= 100),
    result VARCHAR(20) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- ===========================================
-- PRODUCTION TABLES
-- ===========================================

-- Parental Consents table (COPPA)
CREATE TABLE parental_consents (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    parent_email VARCHAR(255) NOT NULL,
    child_id VARCHAR(255) REFERENCES children(id) NOT NULL,
    consent_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    ip_address VARCHAR(45),
    extra JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    status session_status NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Audit Events table
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id),
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- ===========================================
-- INDEXES FOR PERFORMANCE
-- ===========================================

-- Users indexes
CREATE INDEX idx_users_username ON users (username);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_is_active ON users (is_active);
CREATE INDEX idx_users_created_at ON users (created_at);

-- Children indexes
CREATE INDEX idx_children_parent_id ON children (parent_id);
CREATE INDEX idx_children_age ON children (age);
CREATE INDEX idx_children_is_active ON children (is_active);
CREATE INDEX idx_children_consent_verified ON children (parental_consent_verified);

-- Conversations indexes
CREATE INDEX idx_conversations_user_id ON conversations (user_id);
CREATE INDEX idx_conversations_child_id ON conversations (child_id);
CREATE INDEX idx_conversations_status ON conversations (status);
CREATE INDEX idx_conversations_started_at ON conversations (started_at);

-- Messages indexes
CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_messages_sender_type ON messages (sender_type);
CREATE INDEX idx_messages_created_at ON messages (created_at);
CREATE INDEX idx_messages_safety_level ON messages (safety_level);

-- Safety Reports indexes
CREATE INDEX idx_safety_reports_child_id ON safety_reports (child_id);
CREATE INDEX idx_safety_reports_severity ON safety_reports (severity);
CREATE INDEX idx_safety_reports_resolved ON safety_reports (resolved);
CREATE INDEX idx_safety_reports_created_at ON safety_reports (created_at);

-- Audit Logs indexes
CREATE INDEX idx_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs (action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at);

-- Interactions indexes
CREATE INDEX idx_interactions_child_id ON interactions (child_id);
CREATE INDEX idx_interactions_device_id ON interactions (device_id);
CREATE INDEX idx_interactions_type ON interactions (interaction_type);
CREATE INDEX idx_interactions_created_at ON interactions (created_at);

-- Devices indexes
CREATE INDEX idx_devices_device_id ON devices (device_id);
CREATE INDEX idx_devices_parent_id ON devices (parent_id);
CREATE INDEX idx_devices_status ON devices (status);
CREATE INDEX idx_devices_last_seen ON devices (last_seen_at);

-- Notifications indexes
CREATE INDEX idx_notifications_user_id ON notifications (user_id);
CREATE INDEX idx_notifications_type ON notifications (notification_type);
CREATE INDEX idx_notifications_read ON notifications (read);
CREATE INDEX idx_notifications_created_at ON notifications (created_at);

-- Delivery Records indexes
CREATE INDEX idx_delivery_records_notification_id ON delivery_records (notification_id);
CREATE INDEX idx_delivery_records_status ON delivery_records (status);
CREATE INDEX idx_delivery_records_created_at ON delivery_records (created_at);

-- Payment system indexes
CREATE INDEX idx_refund_transactions_original ON refund_transactions (original_transaction_id);
CREATE INDEX idx_subscription_payments_subscription ON subscription_payments (subscription_id);
CREATE INDEX idx_payment_audit_logs_transaction ON payment_audit_logs (transaction_id);
CREATE INDEX idx_webhook_events_processed ON webhook_events (processed);
CREATE INDEX idx_payment_fraud_checks_transaction ON payment_fraud_checks (transaction_id);

-- Production indexes
CREATE INDEX idx_parental_consents_email ON parental_consents (parent_email);
CREATE INDEX idx_parental_consents_child_id ON parental_consents (child_id);
CREATE INDEX idx_sessions_user_id ON sessions (user_id);
CREATE INDEX idx_sessions_token ON sessions (session_token);
CREATE INDEX idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX idx_audit_events_type ON audit_events (event_type);
CREATE INDEX idx_audit_events_user_id ON audit_events (user_id);

-- ===========================================
-- CONSTRAINTS
-- ===========================================

-- Unique constraints
ALTER TABLE parental_consents ADD CONSTRAINT uq_parent_child_consent UNIQUE (parent_email, child_id);
ALTER TABLE sessions ADD CONSTRAINT uq_session_token UNIQUE (session_token);

-- Check constraints
ALTER TABLE children ADD CONSTRAINT chk_child_age CHECK (age >= 3 AND age <= 13);
ALTER TABLE messages ADD CONSTRAINT chk_safety_score CHECK (safety_score >= 0 AND safety_score <= 100);
ALTER TABLE safety_reports ADD CONSTRAINT chk_safety_score_range CHECK (safety_score >= 0 AND safety_score <= 100);
ALTER TABLE payment_fraud_checks ADD CONSTRAINT chk_risk_score CHECK (risk_score >= 0 AND risk_score <= 100);

-- ===========================================
-- COMMENTS
-- ===========================================

COMMENT ON TABLE users IS 'User accounts for parents, children, admins, and support staff';
COMMENT ON TABLE children IS 'Child profiles with COPPA compliance and parental consent';
COMMENT ON TABLE conversations IS 'Conversation sessions between children and AI teddy bear';
COMMENT ON TABLE messages IS 'Individual messages within conversations with safety scoring';
COMMENT ON TABLE safety_reports IS 'Safety incident reports and resolutions';
COMMENT ON TABLE audit_logs IS 'Comprehensive audit trail for all system actions';
COMMENT ON TABLE interactions IS 'Device interaction tracking and analytics';
COMMENT ON TABLE devices IS 'ESP32 teddy bear device management and pairing';
COMMENT ON TABLE notifications IS 'User notifications and alerts';
COMMENT ON TABLE delivery_records IS 'Notification delivery tracking and status';
COMMENT ON TABLE refund_transactions IS 'Payment refund processing and tracking';
COMMENT ON TABLE subscription_payments IS 'Recurring subscription payment management';
COMMENT ON TABLE subscription_payment_attempts IS 'Payment retry attempts and failures';
COMMENT ON TABLE payment_audit_logs IS 'Payment system audit trail';
COMMENT ON TABLE webhook_events IS 'Payment provider webhook event processing';
COMMENT ON TABLE payment_providers IS 'Payment provider configuration and management';
COMMENT ON TABLE payment_fraud_checks IS 'Fraud detection and risk assessment';
COMMENT ON TABLE parental_consents IS 'COPPA-compliant parental consent records';
COMMENT ON TABLE sessions IS 'User session management and security';
COMMENT ON TABLE audit_events IS 'System-wide audit event tracking';
