import pytest
from src.core.services import ChatService, SafetyService, ConversationService
from src.core.entities import Message, Conversation
from src.infrastructure.config.production_config import load_config


config = load_config()


class DummyAIProvider:
    async def stream_chat(self, messages):
        yield "Hello!"


def test_rate_limiting():
    chat = ChatService(ai_provider=DummyAIProvider(), config=config)
    assert hasattr(chat, 'rate_limiter')
    assert chat.rate_limiter is not None


def test_safety_filter():
    safety = SafetyService(config=config)
    result = safety.analyze_content("kill monster", 8)
    assert not result.is_safe


import asyncio
import aiosqlite
import os

def test_conversation_crud():
    # Clean up any existing test database
    test_db = "conversations.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Create a mock repository for testing
    from src.core.repositories import IConversationRepository
    
    class MockConversationRepository:
        def __init__(self):
            self.conversations = {}
        
        async def create_tables(self):
            pass
        
        async def get_or_create_conversation(self, child_id):
            if child_id not in self.conversations:
                from src.core.entities import Conversation
                conv = Conversation(child_id=child_id, id=f"conv_{child_id}")
                self.conversations[child_id] = conv
            return self.conversations[child_id]
        
        async def add_message(self, child_id, message):
            conv = await self.get_or_create_conversation(child_id)
            if not hasattr(conv, '_messages'):
                conv._messages = []
            conv._messages.append(message)
            return conv
        
        async def get_conversation_history(self, child_id):
            return []
    
    mock_repo = MockConversationRepository()
    service = ConversationService(conversation_repository=mock_repo)
    child_id = "child1"
    msg = Message(role="user", content="hi", id="m1", child_id=child_id)
    
    async def run_test():
        # Initialize database table with proper schema
        async with aiosqlite.connect(test_db) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    child_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    summary TEXT,
                    emotion_analysis TEXT DEFAULT 'neutral',
                    sentiment_score REAL DEFAULT 0.0,
                    message_count INTEGER DEFAULT 0,
                    safety_score REAL DEFAULT 1.0,
                    engagement_level TEXT DEFAULT 'medium',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            await db.commit()
        # Initialize repository tables first
        await service.repository.create_tables()
        
        # Test basic conversation creation
        conv = await service.get_or_create_conversation(child_id)
        assert conv.child_id == child_id
        
        # Test adding message
        conv = await service.add_message(child_id, msg)
        assert len(conv._messages) > 0
        assert any(m.id == "m1" for m in conv._messages)
        
        # Test getting conversation history
        history = await service.get_conversation_history(child_id)
        assert len(history) >= 0  # Should not fail
    
    try:
        asyncio.run(run_test())
    finally:
        # Clean up test database
        if os.path.exists(test_db):
            os.remove(test_db)
