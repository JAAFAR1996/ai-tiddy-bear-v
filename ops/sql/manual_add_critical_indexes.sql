

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS embedding vector(768);
CREATE INDEX IF NOT EXISTS ix_messages_embedding ON messages USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_child_id_created_at ON messages(child_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversations_child_id_created_at ON conversations(child_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_content_trgm ON messages USING GIN (content gin_trgm_ops);

-- Premium system indexes (migrated from 002_add_premium_system.py)
-- These should be executed manually in production as per the deployment runbook

-- User subscriptions: active status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_active ON user_subscriptions (user_id) WHERE status = 'ACTIVE';

-- Payment transactions: recent year
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_transactions_recent ON payment_transactions (transaction_date) WHERE transaction_date > NOW() - INTERVAL '1 year';

-- WebSocket connections: active
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_active ON websocket_connections (user_id) WHERE status = 'CONNECTED';

-- Notification deliveries: pending/partial
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_deliveries_pending ON notification_deliveries (created_at) WHERE overall_status IN ('PENDING', 'PARTIAL');
