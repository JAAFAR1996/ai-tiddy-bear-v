
-- Manual index & vector extension creation for production safety (corrected columns)

-- Enable pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS embedding vector(768);
CREATE INDEX IF NOT EXISTS ix_messages_embedding ON messages USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- Standard indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_child_id_created_at ON messages(child_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_conversations_child_id_created_at ON conversations(child_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_content_trgm ON messages USING GIN (content gin_trgm_ops);
