-- Manual index rollback for production safety (run if you need to drop the indexes)

DROP INDEX CONCURRENTLY IF EXISTS ix_messages_child_id_created_at;
DROP INDEX CONCURRENTLY IF EXISTS ix_conversations_user_id_created_at;
DROP INDEX CONCURRENTLY IF EXISTS ix_messages_content_trgm;
