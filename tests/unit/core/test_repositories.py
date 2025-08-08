"""Comprehensive unit tests for core repositories with 100% coverage."""
import pytest
import asyncio
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import tempfile
import aiosqlite

from src.core.repositories import (
    ConversationRepository,
    MessageRepository,
    IConversationRepository,
    IMessageRepository,
    create_conversation_repository,
    create_message_repository,
    DatabaseConnectionError,
    ConversationNotFoundError,
    MessageNotFoundError
)
from src.core.models import ConversationEntity, MessageEntity


class TestDatabaseExceptions:
    """Test custom database exceptions."""
    
    def test_database_connection_error(self):
        """Test DatabaseConnectionError exception."""
        exc = DatabaseConnectionError("Connection failed")
        assert str(exc) == "Connection failed"
        assert isinstance(exc, Exception)
    
    def test_conversation_not_found_error(self):
        """Test ConversationNotFoundError exception."""
        exc = ConversationNotFoundError("Conversation not found")
        assert str(exc) == "Conversation not found"
        assert isinstance(exc, Exception)
    
    def test_message_not_found_error(self):
        """Test MessageNotFoundError exception."""
        exc = MessageNotFoundError("Message not found")
        assert str(exc) == "Message not found"
        assert isinstance(exc, Exception)


class TestConversationRepository:
    """Test suite for ConversationRepository."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name
    
    @pytest.fixture
    def repo(self, temp_db_path):
        """Create ConversationRepository instance for testing."""
        return ConversationRepository(temp_db_path)
    
    @pytest.fixture
    def sample_conversation(self):
        """Create sample conversation for testing."""
        return ConversationEntity.create_new(
            child_id="child-123",
            summary="Test conversation",
            emotion_analysis="happy",
            sentiment_score=0.8
        )
    
    def test_init(self, temp_db_path):
        """Test repository initialization."""
        repo = ConversationRepository(temp_db_path)
        assert repo.db_path == Path(temp_db_path)
    
    def test_init_creates_parent_directories(self):
        """Test initialization creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "nested" / "dir" / "test.db"
            repo = ConversationRepository(str(db_path))
            assert repo.db_path.parent.exists()
    
    @pytest.mark.asyncio
    async def test_create_tables_success(self, repo):
        """Test successful table creation."""
        await repo.create_tables()
        
        # Verify table exists by trying to query it
        async with aiosqlite.connect(repo.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
            )
            result = await cursor.fetchone()
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_create_tables_creates_indexes(self, repo):
        """Test that indexes are created."""
        await repo.create_tables()
        
        async with aiosqlite.connect(repo.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_conversations_%'"
            )
            indexes = await cursor.fetchall()
            assert len(indexes) >= 3  # child_id, start_time, session_id indexes
    
    @pytest.mark.asyncio
    async def test_create_tables_database_error(self, repo):
        """Test table creation with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Database error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Table creation failed"):
                await repo.create_tables()
    
    @pytest.mark.asyncio
    async def test_save_conversation_new(self, repo, sample_conversation):
        """Test saving a new conversation."""
        await repo.create_tables()
        
        result = await repo.save(sample_conversation)
        
        assert result.id == sample_conversation.id
        assert result.child_id == sample_conversation.child_id
        assert result.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_save_conversation_update(self, repo, sample_conversation):
        """Test updating existing conversation."""
        await repo.create_tables()
        
        # Save initial conversation
        await repo.save(sample_conversation)
        
        # Update conversation
        sample_conversation.summary = "Updated summary"
        sample_conversation.message_count = 5
        
        result = await repo.save(sample_conversation)
        
        assert result.summary == "Updated summary"
        assert result.message_count == 5
    
    @pytest.mark.asyncio
    async def test_save_conversation_with_metadata(self, repo):
        """Test saving conversation with metadata."""
        await repo.create_tables()
        
        conv = ConversationEntity.create_new(child_id="child-123")
        conv.metadata = {"key": "value", "number": 42}
        
        await repo.save(conv)
        
        # Retrieve and verify
        retrieved = await repo.get_by_id(conv.id)
        assert retrieved.metadata == {"key": "value", "number": 42}
    
    @pytest.mark.asyncio
    async def test_save_conversation_with_end_time(self, repo, sample_conversation):
        """Test saving conversation with end time."""
        await repo.create_tables()
        
        sample_conversation.end_conversation(
            summary="Final summary",
            emotion_analysis="satisfied",
            sentiment_score=0.9
        )
        
        result = await repo.save(sample_conversation)
        assert result.end_time is not None
    
    @pytest.mark.asyncio
    async def test_save_conversation_database_error(self, repo, sample_conversation):
        """Test save with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Save error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Save operation failed"):
                await repo.save(sample_conversation)
    
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repo, sample_conversation):
        """Test getting conversation by ID when it exists."""
        await repo.create_tables()
        await repo.save(sample_conversation)
        
        result = await repo.get_by_id(sample_conversation.id)
        
        assert result is not None
        assert result.id == sample_conversation.id
        assert result.child_id == sample_conversation.child_id
        assert result.summary == sample_conversation.summary
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo):
        """Test getting conversation by ID when it doesn't exist."""
        await repo.create_tables()
        
        result = await repo.get_by_id("nonexistent-id")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_by_id_database_error(self, repo):
        """Test get_by_id with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Get error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Get operation failed"):
                await repo.get_by_id("test-id")
    
    @pytest.mark.asyncio
    async def test_get_by_child_id(self, repo):
        """Test getting conversations by child ID."""
        await repo.create_tables()
        
        # Create multiple conversations for same child
        child_id = "child-123"
        conv1 = ConversationEntity.create_new(child_id=child_id, summary="First")
        conv2 = ConversationEntity.create_new(child_id=child_id, summary="Second")
        conv3 = ConversationEntity.create_new(child_id="other-child", summary="Other")
        
        await repo.save(conv1)
        await repo.save(conv2)
        await repo.save(conv3)
        
        results = await repo.get_by_child_id(child_id)
        
        assert len(results) == 2
        assert all(conv.child_id == child_id for conv in results)
        # Should be ordered by start_time DESC
        summaries = [conv.summary for conv in results]
        assert "Second" in summaries
        assert "First" in summaries
    
    @pytest.mark.asyncio
    async def test_get_by_child_id_empty(self, repo):
        """Test getting conversations for child with no conversations."""
        await repo.create_tables()
        
        results = await repo.get_by_child_id("nonexistent-child")
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_get_by_child_id_database_error(self, repo):
        """Test get_by_child_id with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Get error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Get operation failed"):
                await repo.get_by_child_id("child-123")
    
    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, repo, sample_conversation):
        """Test successful conversation deletion."""
        await repo.create_tables()
        await repo.save(sample_conversation)
        
        await repo.delete(sample_conversation.id)
        
        # Verify deletion
        result = await repo.get_by_id(sample_conversation.id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, repo):
        """Test deleting non-existent conversation."""
        await repo.create_tables()
        
        with pytest.raises(ConversationNotFoundError):
            await repo.delete("nonexistent-id")
    
    @pytest.mark.asyncio
    async def test_delete_conversation_database_error(self, repo):
        """Test delete with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.rowcount = 1
            mock_db.execute.return_value = mock_cursor
            mock_db.commit.side_effect = aiosqlite.Error("Delete error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Delete operation failed"):
                await repo.delete("test-id")
    
    @pytest.mark.asyncio
    async def test_cleanup_old_conversations(self, repo):
        """Test cleaning up old conversations."""
        await repo.create_tables()
        
        # Create old and new conversations
        old_conv = ConversationEntity.create_new(child_id="child-123")
        old_conv.start_time = datetime.now(UTC) - timedelta(days=100)
        
        new_conv = ConversationEntity.create_new(child_id="child-456")
        new_conv.start_time = datetime.now(UTC) - timedelta(days=10)
        
        await repo.save(old_conv)
        await repo.save(new_conv)
        
        # Cleanup with 30 day retention
        deleted_count = await repo.cleanup_old_conversations(retention_days=30)
        
        assert deleted_count == 1
        
        # Verify old conversation is deleted, new one remains
        assert await repo.get_by_id(old_conv.id) is None
        assert await repo.get_by_id(new_conv.id) is not None
    
    @pytest.mark.asyncio
    async def test_cleanup_old_conversations_database_error(self, repo):
        """Test cleanup with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Cleanup error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Cleanup operation failed"):
                await repo.cleanup_old_conversations()
    
    def test_row_to_conversation_full_data(self, repo):
        """Test converting database row to ConversationEntity with full data."""
        now = datetime.now(UTC)
        row = {
            "id": "conv-123",
            "child_id": "child-456",
            "session_id": "session-789",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "summary": "Test summary",
            "emotion_analysis": "happy",
            "sentiment_score": 0.8,
            "message_count": 5,
            "safety_score": 0.9,
            "engagement_level": "high",
            "created_at": now.isoformat(),
            "updated_at": (now + timedelta(minutes=30)).isoformat(),
            "metadata": '{"key": "value", "number": 42}'
        }
        
        conv = repo._row_to_conversation(row)
        
        assert conv.id == "conv-123"
        assert conv.child_id == "child-456"
        assert conv.emotion_analysis == "happy"
        assert conv.sentiment_score == 0.8
        assert conv.metadata == {"key": "value", "number": 42}
    
    def test_row_to_conversation_minimal_data(self, repo):
        """Test converting row with minimal data."""
        now = datetime.now(UTC)
        row = {
            "id": "conv-123",
            "child_id": "child-456",
            "session_id": "session-789",
            "start_time": now.isoformat()
        }
        
        conv = repo._row_to_conversation(row)
        
        assert conv.id == "conv-123"
        assert conv.summary == ""
        assert conv.emotion_analysis == "neutral"
        assert conv.sentiment_score == 0.0
        assert conv.message_count == 0
        assert conv.safety_score == 1.0
        assert conv.engagement_level == "medium"
        assert conv.metadata == {}
    
    def test_row_to_conversation_invalid_metadata(self, repo):
        """Test handling invalid metadata JSON."""
        now = datetime.now(UTC)
        row = {
            "id": "conv-123",
            "child_id": "child-456",
            "session_id": "session-789",
            "start_time": now.isoformat(),
            "metadata": "invalid json{"
        }
        
        with patch('src.core.repositories.logger') as mock_logger:
            conv = repo._row_to_conversation(row)
            
            assert conv.metadata == {}
            mock_logger.warning.assert_called_once()
    
    def test_row_to_conversation_none_metadata(self, repo):
        """Test handling None metadata."""
        now = datetime.now(UTC)
        row = {
            "id": "conv-123",
            "child_id": "child-456", 
            "session_id": "session-789",
            "start_time": now.isoformat(),
            "metadata": None
        }
        
        conv = repo._row_to_conversation(row)
        assert conv.metadata == {}


class TestMessageRepository:
    """Test suite for MessageRepository."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name
    
    @pytest.fixture
    def repo(self, temp_db_path):
        """Create MessageRepository instance for testing."""
        return MessageRepository(temp_db_path)
    
    @pytest.fixture
    def sample_message(self):
        """Create sample message for testing."""
        return MessageEntity.create_message(
            conversation_id="conv-123",
            sender="child",
            content_encrypted="encrypted_content",
            sequence_number=1
        )
    
    def test_init(self, temp_db_path):
        """Test repository initialization."""
        repo = MessageRepository(temp_db_path)
        assert repo.db_path == Path(temp_db_path)
    
    def test_init_creates_parent_directories(self):
        """Test initialization creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "nested" / "messages.db"
            repo = MessageRepository(str(db_path))
            assert repo.db_path.parent.exists()
    
    @pytest.mark.asyncio
    async def test_create_tables_success(self, repo):
        """Test successful table creation."""
        await repo.create_tables()
        
        # Verify table exists
        async with aiosqlite.connect(repo.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            )
            result = await cursor.fetchone()
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_create_tables_creates_indexes(self, repo):
        """Test that indexes are created."""
        await repo.create_tables()
        
        async with aiosqlite.connect(repo.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_messages_%'"
            )
            indexes = await cursor.fetchall()
            assert len(indexes) >= 3  # conversation_id, timestamp, sequence indexes
    
    @pytest.mark.asyncio
    async def test_create_tables_database_error(self, repo):
        """Test table creation with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Database error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Table creation failed"):
                await repo.create_tables()
    
    @pytest.mark.asyncio
    async def test_save_message_success(self, repo, sample_message):
        """Test saving a message successfully."""
        await repo.create_tables()
        
        result = await repo.save_message(sample_message)
        
        assert result.id == sample_message.id
        assert result.conversation_id == sample_message.conversation_id
        assert result.sender == sample_message.sender
    
    @pytest.mark.asyncio
    async def test_save_message_with_metadata(self, repo):
        """Test saving message with metadata."""
        await repo.create_tables()
        
        msg = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="teddy",
            content_encrypted="encrypted"
        )
        msg.metadata = {"type": "response", "length": 100}
        
        await repo.save_message(msg)
        
        # Retrieve and verify metadata
        messages = await repo.get_conversation_messages("conv-123")
        assert len(messages) == 1
        assert messages[0].metadata == {"type": "response", "length": 100}
    
    @pytest.mark.asyncio
    async def test_save_message_database_error(self, repo, sample_message):
        """Test save with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Save error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Save operation failed"):
                await repo.save_message(sample_message)
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, repo):
        """Test getting messages for a conversation."""
        await repo.create_tables()
        
        conv_id = "conv-123"
        
        # Create multiple messages
        msg1 = MessageEntity.create_message(conv_id, "child", "msg1", sequence_number=1)
        msg2 = MessageEntity.create_message(conv_id, "teddy", "msg2", sequence_number=2)
        msg3 = MessageEntity.create_message(conv_id, "child", "msg3", sequence_number=3)
        
        await repo.save_message(msg1)
        await repo.save_message(msg2)
        await repo.save_message(msg3)
        
        messages = await repo.get_conversation_messages(conv_id)
        
        assert len(messages) == 3
        # Should be ordered by sequence number
        assert messages[0].sequence_number == 1
        assert messages[1].sequence_number == 2
        assert messages[2].sequence_number == 3
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_with_limit(self, repo):
        """Test getting messages with limit and offset."""
        await repo.create_tables()
        
        conv_id = "conv-123"
        
        # Create 5 messages
        for i in range(5):
            msg = MessageEntity.create_message(
                conv_id, "child", f"msg{i}", sequence_number=i
            )
            await repo.save_message(msg)
        
        # Get 2 messages with offset 1
        messages = await repo.get_conversation_messages(conv_id, limit=2, offset=1)
        
        assert len(messages) == 2
        assert messages[0].sequence_number == 1
        assert messages[1].sequence_number == 2
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_empty(self, repo):
        """Test getting messages for conversation with no messages."""
        await repo.create_tables()
        
        messages = await repo.get_conversation_messages("empty-conv")
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_database_error(self, repo):
        """Test get_conversation_messages with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Get error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Get operation failed"):
                await repo.get_conversation_messages("conv-123")
    
    @pytest.mark.asyncio
    async def test_delete_conversation_messages(self, repo):
        """Test deleting all messages for a conversation."""
        await repo.create_tables()
        
        conv_id = "conv-123"
        other_conv_id = "conv-456"
        
        # Create messages for both conversations
        msg1 = MessageEntity.create_message(conv_id, "child", "msg1")
        msg2 = MessageEntity.create_message(conv_id, "teddy", "msg2")
        msg3 = MessageEntity.create_message(other_conv_id, "child", "msg3")
        
        await repo.save_message(msg1)
        await repo.save_message(msg2)
        await repo.save_message(msg3)
        
        # Delete messages for conv_id only
        deleted_count = await repo.delete_conversation_messages(conv_id)
        
        assert deleted_count == 2
        
        # Verify deletion
        messages_conv = await repo.get_conversation_messages(conv_id)
        messages_other = await repo.get_conversation_messages(other_conv_id)
        
        assert len(messages_conv) == 0
        assert len(messages_other) == 1
    
    @pytest.mark.asyncio
    async def test_delete_conversation_messages_empty(self, repo):
        """Test deleting messages for conversation with no messages."""
        await repo.create_tables()
        
        deleted_count = await repo.delete_conversation_messages("empty-conv")
        assert deleted_count == 0
    
    @pytest.mark.asyncio
    async def test_delete_conversation_messages_database_error(self, repo):
        """Test delete_conversation_messages with database error."""
        with patch('aiosqlite.connect') as mock_connect:
            mock_db = AsyncMock()
            mock_db.execute.side_effect = aiosqlite.Error("Delete error")
            mock_connect.return_value.__aenter__.return_value = mock_db
            
            with pytest.raises(DatabaseConnectionError, match="Delete operation failed"):
                await repo.delete_conversation_messages("conv-123")
    
    def test_row_to_message_full_data(self, repo):
        """Test converting database row to MessageEntity with full data."""
        now = datetime.now(UTC)
        row = {
            "id": "msg-123",
            "conversation_id": "conv-456",
            "sender": "child",
            "content_encrypted": "encrypted_content",
            "timestamp": now.isoformat(),
            "emotion": "happy",
            "sentiment": 0.7,
            "content_type": "text",
            "sequence_number": 5,
            "safety_score": 0.95,
            "created_at": (now - timedelta(seconds=10)).isoformat(),
            "metadata": '{"processed": true, "tokens": 50}'
        }
        
        msg = repo._row_to_message(row)
        
        assert msg.id == "msg-123"
        assert msg.conversation_id == "conv-456"
        assert msg.sender == "child"
        assert msg.emotion == "happy"
        assert msg.sentiment == 0.7
        assert msg.sequence_number == 5
        assert msg.metadata == {"processed": True, "tokens": 50}
    
    def test_row_to_message_minimal_data(self, repo):
        """Test converting row with minimal data."""
        now = datetime.now(UTC)
        row = {
            "id": "msg-123",
            "conversation_id": "conv-456",
            "sender": "teddy",
            "content_encrypted": "encrypted",
            "timestamp": now.isoformat()
        }
        
        msg = repo._row_to_message(row)
        
        assert msg.id == "msg-123"
        assert msg.emotion == "neutral"
        assert msg.sentiment == 0.0
        assert msg.content_type == "text"
        assert msg.sequence_number == 0
        assert msg.safety_score == 1.0
        assert msg.metadata == {}
        assert msg.created_at is None
    
    def test_row_to_message_invalid_metadata(self, repo):
        """Test handling invalid metadata JSON."""
        now = datetime.now(UTC)
        row = {
            "id": "msg-123",
            "conversation_id": "conv-456",
            "sender": "child",
            "content_encrypted": "encrypted",
            "timestamp": now.isoformat(),
            "metadata": "invalid json{"
        }
        
        with patch('src.core.repositories.logger') as mock_logger:
            msg = repo._row_to_message(row)
            
            assert msg.metadata == {}
            mock_logger.warning.assert_called_once()


class TestRepositoryInterfaces:
    """Test repository interfaces."""
    
    def test_iconversation_repository_is_abstract(self):
        """Test that IConversationRepository is abstract."""
        with pytest.raises(TypeError):
            IConversationRepository()
    
    def test_imessage_repository_is_abstract(self):
        """Test that IMessageRepository is abstract."""
        with pytest.raises(TypeError):
            IMessageRepository()
    
    def test_conversation_repository_implements_interface(self):
        """Test ConversationRepository implements interface."""
        repo = ConversationRepository(":memory:")
        assert isinstance(repo, IConversationRepository)
    
    def test_message_repository_implements_interface(self):
        """Test MessageRepository implements interface."""
        repo = MessageRepository(":memory:")
        assert isinstance(repo, IMessageRepository)


class TestFactoryFunctions:
    """Test factory functions."""
    
    def test_create_conversation_repository_default(self):
        """Test creating conversation repository with default path."""
        repo = create_conversation_repository()
        assert isinstance(repo, ConversationRepository)
        assert repo.db_path.name == "conversations.db"
    
    def test_create_conversation_repository_custom_path(self):
        """Test creating conversation repository with custom path."""
        custom_path = "custom_conversations.db"
        repo = create_conversation_repository(custom_path)
        assert isinstance(repo, ConversationRepository)
        assert repo.db_path.name == custom_path
    
    def test_create_message_repository_default(self):
        """Test creating message repository with default path."""
        repo = create_message_repository()
        assert isinstance(repo, MessageRepository)
        assert repo.db_path.name == "conversations.db"
    
    def test_create_message_repository_custom_path(self):
        """Test creating message repository with custom path."""
        custom_path = "custom_messages.db"
        repo = create_message_repository(custom_path)
        assert isinstance(repo, MessageRepository)
        assert repo.db_path.name == custom_path


class TestRepositoryIntegration:
    """Integration tests for repositories."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield f.name
    
    @pytest.mark.asyncio
    async def test_conversation_and_message_repositories_together(self, temp_db_path):
        """Test using both repositories with same database."""
        conv_repo = ConversationRepository(temp_db_path)
        msg_repo = MessageRepository(temp_db_path)
        
        # Create tables
        await conv_repo.create_tables()
        await msg_repo.create_tables()
        
        # Create and save conversation
        conv = ConversationEntity.create_new(child_id="child-123")
        await conv_repo.save(conv)
        
        # Create and save messages
        msg1 = MessageEntity.create_message(conv.id, "child", "Hello", sequence_number=1)
        msg2 = MessageEntity.create_message(conv.id, "teddy", "Hi there!", sequence_number=2)
        
        await msg_repo.save_message(msg1)
        await msg_repo.save_message(msg2)
        
        # Update conversation message count
        conv.add_message()
        conv.add_message()
        await conv_repo.save(conv)
        
        # Verify integration
        retrieved_conv = await conv_repo.get_by_id(conv.id)
        messages = await msg_repo.get_conversation_messages(conv.id)
        
        assert retrieved_conv.message_count == 2
        assert len(messages) == 2
        assert all(msg.conversation_id == conv.id for msg in messages)
    
    @pytest.mark.asyncio
    async def test_cascade_delete_simulation(self, temp_db_path):
        """Test simulating cascade delete behavior."""
        conv_repo = ConversationRepository(temp_db_path)
        msg_repo = MessageRepository(temp_db_path)
        
        await conv_repo.create_tables()
        await msg_repo.create_tables()
        
        # Create conversation with messages
        conv = ConversationEntity.create_new(child_id="child-123")
        await conv_repo.save(conv)
        
        msg = MessageEntity.create_message(conv.id, "child", "Test message")
        await msg_repo.save_message(msg)
        
        # Delete messages first, then conversation
        deleted_msg_count = await msg_repo.delete_conversation_messages(conv.id)
        await conv_repo.delete(conv.id)
        
        assert deleted_msg_count == 1
        assert await conv_repo.get_by_id(conv.id) is None
        assert len(await msg_repo.get_conversation_messages(conv.id)) == 0


class TestModuleExports:
    """Test module exports."""
    
    def test_all_exports(self):
        """Test __all__ contains expected exports."""
        from src.core import repositories
        
        expected_exports = [
            "IConversationRepository",
            "IMessageRepository", 
            "ConversationRepository",
            "MessageRepository",
            "create_conversation_repository",
            "create_message_repository",
            "DatabaseConnectionError",
            "ConversationNotFoundError",
            "MessageNotFoundError"
        ]
        
        assert hasattr(repositories, '__all__')
        for export in expected_exports:
            assert export in repositories.__all__
            assert hasattr(repositories, export)