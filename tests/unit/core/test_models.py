"""Comprehensive unit tests for core models with 100% coverage."""
import pytest
from datetime import datetime, UTC, timedelta
from dataclasses import FrozenInstanceError
import json
from uuid import UUID

from src.core.models import (
    ConversationEntity,
    MessageEntity,
    RiskLevel,
    SafetyAnalysisResult
)


class TestConversationEntity:
    """Test suite for ConversationEntity model."""
    
    def test_create_new_conversation(self):
        """Test creating a new conversation with factory method."""
        child_id = "child-123"
        summary = "Initial conversation"
        emotion = "happy"
        sentiment = 0.8
        
        conv = ConversationEntity.create_new(
            child_id=child_id,
            summary=summary,
            emotion_analysis=emotion,
            sentiment_score=sentiment
        )
        
        assert conv.child_id == child_id
        assert conv.summary == summary
        assert conv.emotion_analysis == emotion
        assert conv.sentiment_score == sentiment
        assert conv.message_count == 0
        assert conv.safety_score == 1.0
        assert conv.engagement_level == "medium"
        assert conv.end_time is None
        assert conv.metadata == {}
        
        # Check UUIDs are valid
        UUID(conv.id)
        UUID(conv.session_id)
        
        # Check timestamps
        assert isinstance(conv.start_time, datetime)
        assert conv.created_at == conv.start_time
        assert isinstance(conv.updated_at, datetime)
    
    def test_create_new_defaults(self):
        """Test create_new with default values."""
        conv = ConversationEntity.create_new(child_id="child-456")
        
        assert conv.summary == ""
        assert conv.emotion_analysis == "neutral"
        assert conv.sentiment_score == 0.0
    
    def test_direct_instantiation(self):
        """Test direct instantiation of ConversationEntity."""
        now = datetime.now(UTC)
        conv = ConversationEntity(
            id="conv-123",
            child_id="child-789",
            session_id="session-123",
            start_time=now,
            end_time=now + timedelta(hours=1),
            summary="Test summary",
            emotion_analysis="sad",
            sentiment_score=-0.5,
            message_count=10,
            safety_score=0.9,
            engagement_level="high",
            created_at=now,
            updated_at=now,
            metadata={"key": "value"}
        )
        
        assert conv.id == "conv-123"
        assert conv.message_count == 10
        assert conv.engagement_level == "high"
        assert conv.metadata == {"key": "value"}
    
    def test_post_init_defaults(self):
        """Test __post_init__ sets default timestamps."""
        start = datetime.now(UTC)
        conv = ConversationEntity(
            id="test",
            child_id="child",
            session_id="session",
            start_time=start
        )
        
        assert conv.created_at == start
        assert conv.updated_at is not None
        assert isinstance(conv.updated_at, datetime)
    
    def test_post_init_preserves_provided_values(self):
        """Test __post_init__ preserves explicitly provided values."""
        start = datetime.now(UTC)
        created = start - timedelta(days=1)
        updated = start - timedelta(hours=1)
        
        conv = ConversationEntity(
            id="test",
            child_id="child",
            session_id="session",
            start_time=start,
            created_at=created,
            updated_at=updated
        )
        
        assert conv.created_at == created
        assert conv.updated_at == updated
    
    def test_end_conversation(self):
        """Test ending a conversation."""
        conv = ConversationEntity.create_new(child_id="child-123")
        original_updated = conv.updated_at
        
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        conv.end_conversation(
            summary="Great conversation about dinosaurs",
            emotion_analysis="excited",
            sentiment_score=0.9
        )
        
        assert conv.end_time is not None
        assert isinstance(conv.end_time, datetime)
        assert conv.summary == "Great conversation about dinosaurs"
        assert conv.emotion_analysis == "excited"
        assert conv.sentiment_score == 0.9
        assert conv.updated_at > original_updated
    
    def test_add_message(self):
        """Test adding messages to conversation."""
        conv = ConversationEntity.create_new(child_id="child-123")
        original_updated = conv.updated_at
        
        # Small delay
        import time
        time.sleep(0.01)
        
        conv.add_message()
        assert conv.message_count == 1
        assert conv.updated_at > original_updated
        
        conv.add_message()
        conv.add_message()
        assert conv.message_count == 3
    
    def test_update_safety_score(self):
        """Test updating safety score."""
        conv = ConversationEntity.create_new(child_id="child-123")
        original_updated = conv.updated_at
        
        # Small delay
        import time
        time.sleep(0.01)
        
        conv.update_safety_score(0.7)
        assert conv.safety_score == 0.7
        assert conv.updated_at > original_updated
    
    def test_update_safety_score_bounds(self):
        """Test safety score is bounded between 0 and 1."""
        conv = ConversationEntity.create_new(child_id="child-123")
        
        conv.update_safety_score(1.5)
        assert conv.safety_score == 1.0
        
        conv.update_safety_score(-0.5)
        assert conv.safety_score == 0.0
        
        conv.update_safety_score(0.5)
        assert conv.safety_score == 0.5
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        now = datetime.now(UTC)
        conv = ConversationEntity(
            id="conv-123",
            child_id="child-456",
            session_id="session-789",
            start_time=now,
            end_time=now + timedelta(hours=1),
            summary="Test",
            emotion_analysis="happy",
            sentiment_score=0.8,
            message_count=5,
            safety_score=0.95,
            engagement_level="high",
            created_at=now,
            updated_at=now + timedelta(minutes=30),
            metadata={"test": True}
        )
        
        data = conv.to_dict()
        
        assert data["id"] == "conv-123"
        assert data["child_id"] == "child-456"
        assert data["session_id"] == "session-789"
        assert data["start_time"] == now.isoformat()
        assert data["end_time"] == (now + timedelta(hours=1)).isoformat()
        assert data["summary"] == "Test"
        assert data["emotion_analysis"] == "happy"
        assert data["sentiment_score"] == 0.8
        assert data["message_count"] == 5
        assert data["safety_score"] == 0.95
        assert data["engagement_level"] == "high"
        assert data["created_at"] == now.isoformat()
        assert data["updated_at"] == (now + timedelta(minutes=30)).isoformat()
        assert data["metadata"] == {"test": True}
    
    def test_to_dict_with_none_values(self):
        """Test to_dict with None values."""
        conv = ConversationEntity(
            id="test",
            child_id="child",
            session_id="session",
            start_time=datetime.now(UTC),
            created_at=None,
            updated_at=None
        )
        
        data = conv.to_dict()
        assert data["end_time"] is None
        assert data["created_at"] is None
        assert data["updated_at"] is None
    
    def test_from_dict(self):
        """Test creating entity from dictionary."""
        now = datetime.now(UTC)
        data = {
            "id": "conv-123",
            "child_id": "child-456",
            "session_id": "session-789",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
            "summary": "Test summary",
            "emotion_analysis": "neutral",
            "sentiment_score": 0.0,
            "message_count": 10,
            "safety_score": 0.85,
            "engagement_level": "low",
            "created_at": now.isoformat(),
            "updated_at": (now + timedelta(minutes=10)).isoformat(),
            "metadata": {"key": "value"}
        }
        
        conv = ConversationEntity.from_dict(data)
        
        assert conv.id == "conv-123"
        assert conv.child_id == "child-456"
        assert conv.session_id == "session-789"
        assert conv.summary == "Test summary"
        assert conv.message_count == 10
        assert conv.safety_score == 0.85
        assert conv.metadata == {"key": "value"}
    
    def test_from_dict_minimal(self):
        """Test from_dict with minimal data."""
        data = {
            "id": "test",
            "child_id": "child",
            "session_id": "session",
            "start_time": datetime.now(UTC).isoformat()
        }
        
        conv = ConversationEntity.from_dict(data)
        
        assert conv.summary == ""
        assert conv.emotion_analysis == "neutral"
        assert conv.sentiment_score == 0.0
        assert conv.message_count == 0
        assert conv.safety_score == 1.0
        assert conv.engagement_level == "medium"
        assert conv.metadata == {}
        assert conv.end_time is None
        assert conv.created_at is None
        assert conv.updated_at is None
    
    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = ConversationEntity.create_new(
            child_id="child-123",
            summary="Round trip test",
            emotion_analysis="happy",
            sentiment_score=0.7
        )
        
        # Add some changes
        original.add_message()
        original.update_safety_score(0.9)
        original.metadata = {"test": "data"}
        
        # Round trip
        data = original.to_dict()
        restored = ConversationEntity.from_dict(data)
        
        assert restored.id == original.id
        assert restored.child_id == original.child_id
        assert restored.message_count == original.message_count
        assert restored.safety_score == original.safety_score
        assert restored.metadata == original.metadata


class TestMessageEntity:
    """Test suite for MessageEntity model."""
    
    def test_create_message(self):
        """Test creating a new message with factory method."""
        conv_id = "conv-123"
        sender = "child"
        content = "encrypted_content_here"
        seq_num = 1
        
        msg = MessageEntity.create_message(
            conversation_id=conv_id,
            sender=sender,
            content_encrypted=content,
            sequence_number=seq_num,
            content_type="text"
        )
        
        assert msg.conversation_id == conv_id
        assert msg.sender == sender
        assert msg.content_encrypted == content
        assert msg.sequence_number == seq_num
        assert msg.content_type == "text"
        assert msg.emotion == "neutral"
        assert msg.sentiment == 0.0
        assert msg.safety_score == 1.0
        assert msg.metadata == {}
        
        # Check UUID is valid
        UUID(msg.id)
        
        # Check timestamps
        assert isinstance(msg.timestamp, datetime)
        assert msg.created_at == msg.timestamp
    
    def test_create_message_defaults(self):
        """Test create_message with default values."""
        msg = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="teddy",
            content_encrypted="encrypted"
        )
        
        assert msg.sequence_number == 0
        assert msg.content_type == "text"
    
    def test_direct_instantiation(self):
        """Test direct instantiation of MessageEntity."""
        now = datetime.now(UTC)
        msg = MessageEntity(
            id="msg-123",
            conversation_id="conv-456",
            sender="child",
            content_encrypted="encrypted_data",
            timestamp=now,
            emotion="excited",
            sentiment=0.9,
            content_type="audio",
            sequence_number=5,
            safety_score=0.95,
            created_at=now - timedelta(minutes=1),
            metadata={"duration": 30}
        )
        
        assert msg.id == "msg-123"
        assert msg.emotion == "excited"
        assert msg.content_type == "audio"
        assert msg.metadata == {"duration": 30}
        assert msg.created_at == now - timedelta(minutes=1)
    
    def test_post_init_defaults(self):
        """Test __post_init__ sets default created_at."""
        timestamp = datetime.now(UTC)
        msg = MessageEntity(
            id="test",
            conversation_id="conv",
            sender="child",
            content_encrypted="data",
            timestamp=timestamp
        )
        
        assert msg.created_at == timestamp
    
    def test_post_init_preserves_created_at(self):
        """Test __post_init__ preserves provided created_at."""
        timestamp = datetime.now(UTC)
        created = timestamp - timedelta(hours=1)
        
        msg = MessageEntity(
            id="test",
            conversation_id="conv",
            sender="teddy",
            content_encrypted="data",
            timestamp=timestamp,
            created_at=created
        )
        
        assert msg.created_at == created
    
    def test_update_analysis(self):
        """Test updating emotion analysis."""
        msg = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="child",
            content_encrypted="data"
        )
        
        msg.update_analysis(emotion="sad", sentiment=-0.6)
        
        assert msg.emotion == "sad"
        assert msg.sentiment == -0.6
    
    def test_update_safety_score(self):
        """Test updating safety score."""
        msg = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="teddy",
            content_encrypted="data"
        )
        
        msg.update_safety_score(0.8)
        assert msg.safety_score == 0.8
    
    def test_update_safety_score_bounds(self):
        """Test safety score is bounded between 0 and 1."""
        msg = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="child",
            content_encrypted="data"
        )
        
        msg.update_safety_score(2.0)
        assert msg.safety_score == 1.0
        
        msg.update_safety_score(-1.0)
        assert msg.safety_score == 0.0
        
        msg.update_safety_score(0.3)
        assert msg.safety_score == 0.3
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        now = datetime.now(UTC)
        msg = MessageEntity(
            id="msg-123",
            conversation_id="conv-456",
            sender="child",
            content_encrypted="encrypted_content",
            timestamp=now,
            emotion="happy",
            sentiment=0.7,
            content_type="text",
            sequence_number=3,
            safety_score=0.9,
            created_at=now - timedelta(seconds=10),
            metadata={"processed": True}
        )
        
        data = msg.to_dict()
        
        assert data["id"] == "msg-123"
        assert data["conversation_id"] == "conv-456"
        assert data["sender"] == "child"
        assert data["content_encrypted"] == "encrypted_content"
        assert data["timestamp"] == now.isoformat()
        assert data["emotion"] == "happy"
        assert data["sentiment"] == 0.7
        assert data["content_type"] == "text"
        assert data["sequence_number"] == 3
        assert data["safety_score"] == 0.9
        assert data["created_at"] == (now - timedelta(seconds=10)).isoformat()
        assert data["metadata"] == {"processed": True}
    
    def test_to_dict_with_none_created_at(self):
        """Test to_dict when created_at is None."""
        msg = MessageEntity(
            id="test",
            conversation_id="conv",
            sender="teddy",
            content_encrypted="data",
            timestamp=datetime.now(UTC),
            created_at=None
        )
        
        data = msg.to_dict()
        assert data["created_at"] is None
    
    def test_from_dict(self):
        """Test creating entity from dictionary."""
        now = datetime.now(UTC)
        data = {
            "id": "msg-789",
            "conversation_id": "conv-123",
            "sender": "teddy",
            "content_encrypted": "encrypted_response",
            "timestamp": now.isoformat(),
            "emotion": "neutral",
            "sentiment": 0.1,
            "content_type": "audio",
            "sequence_number": 7,
            "safety_score": 0.99,
            "created_at": (now - timedelta(milliseconds=100)).isoformat(),
            "metadata": {"model": "gpt-4"}
        }
        
        msg = MessageEntity.from_dict(data)
        
        assert msg.id == "msg-789"
        assert msg.sender == "teddy"
        assert msg.content_type == "audio"
        assert msg.sequence_number == 7
        assert msg.metadata == {"model": "gpt-4"}
    
    def test_from_dict_minimal(self):
        """Test from_dict with minimal data."""
        data = {
            "id": "test",
            "conversation_id": "conv",
            "sender": "child",
            "content_encrypted": "data",
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        msg = MessageEntity.from_dict(data)
        
        assert msg.emotion == "neutral"
        assert msg.sentiment == 0.0
        assert msg.content_type == "text"
        assert msg.sequence_number == 0
        assert msg.safety_score == 1.0
        assert msg.created_at is None
        assert msg.metadata == {}
    
    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="child",
            content_encrypted="test_content",
            sequence_number=5,
            content_type="text"
        )
        
        # Make some changes
        original.update_analysis("happy", 0.8)
        original.update_safety_score(0.85)
        original.metadata = {"length": 50}
        
        # Round trip
        data = original.to_dict()
        restored = MessageEntity.from_dict(data)
        
        assert restored.id == original.id
        assert restored.conversation_id == original.conversation_id
        assert restored.emotion == original.emotion
        assert restored.sentiment == original.sentiment
        assert restored.safety_score == original.safety_score
        assert restored.metadata == original.metadata


class TestRiskLevel:
    """Test suite for RiskLevel enum."""
    
    def test_risk_level_values(self):
        """Test all risk level values."""
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.DANGEROUS.value == "dangerous"
    
    def test_risk_level_comparison(self):
        """Test risk level comparisons."""
        assert RiskLevel.SAFE != RiskLevel.HIGH
        assert RiskLevel.MEDIUM == RiskLevel.MEDIUM
    
    def test_risk_level_membership(self):
        """Test enum membership."""
        all_levels = list(RiskLevel)
        assert len(all_levels) == 5
        assert RiskLevel.SAFE in RiskLevel
        assert RiskLevel.DANGEROUS in RiskLevel
    
    def test_risk_level_string_conversion(self):
        """Test string representation."""
        assert str(RiskLevel.SAFE) == "RiskLevel.SAFE"
        assert RiskLevel.SAFE.name == "SAFE"
        assert RiskLevel.SAFE.value == "safe"


class TestSafetyAnalysisResult:
    """Test suite for SafetyAnalysisResult."""
    
    def test_create_safe_result(self):
        """Test creating a safe analysis result."""
        result = SafetyAnalysisResult(
            is_safe=True,
            risk_level=RiskLevel.SAFE,
            issues=[],
            reason="Content is appropriate for children"
        )
        
        assert result.is_safe is True
        assert result.risk_level == RiskLevel.SAFE
        assert result.issues == []
        assert result.reason == "Content is appropriate for children"
    
    def test_create_unsafe_result(self):
        """Test creating an unsafe analysis result."""
        issues = ["violence", "inappropriate language"]
        result = SafetyAnalysisResult(
            is_safe=False,
            risk_level=RiskLevel.HIGH,
            issues=issues,
            reason="Multiple safety violations detected"
        )
        
        assert result.is_safe is False
        assert result.risk_level == RiskLevel.HIGH
        assert result.issues == issues
        assert len(result.issues) == 2
    
    def test_default_issues_list(self):
        """Test default empty issues list."""
        result = SafetyAnalysisResult(
            is_safe=True,
            risk_level=RiskLevel.LOW,
            reason="Minor concerns"
        )
        
        assert result.issues == []
    
    def test_none_issues_becomes_empty_list(self):
        """Test None issues becomes empty list."""
        result = SafetyAnalysisResult(
            is_safe=True,
            risk_level=RiskLevel.SAFE,
            issues=None,
            reason="All good"
        )
        
        assert result.issues == []
    
    def test_repr(self):
        """Test string representation."""
        result = SafetyAnalysisResult(
            is_safe=False,
            risk_level=RiskLevel.MEDIUM,
            issues=["test1", "test2"],
            reason="Test reason"
        )
        
        repr_str = repr(result)
        assert "SafetyAnalysisResult" in repr_str
        assert "is_safe=False" in repr_str
        assert "risk_level=RiskLevel.MEDIUM" in repr_str
        assert "issues=['test1', 'test2']" in repr_str
        assert "reason='Test reason'" in repr_str
    
    def test_repr_empty_reason(self):
        """Test repr with empty reason."""
        result = SafetyAnalysisResult(
            is_safe=True,
            risk_level=RiskLevel.SAFE,
            reason=""
        )
        
        repr_str = repr(result)
        assert "reason=''" in repr_str
    
    def test_different_risk_levels(self):
        """Test creating results with different risk levels."""
        for level in RiskLevel:
            result = SafetyAnalysisResult(
                is_safe=(level == RiskLevel.SAFE),
                risk_level=level,
                reason=f"Risk level: {level.value}"
            )
            assert result.risk_level == level


class TestModelIntegration:
    """Integration tests for model interactions."""
    
    def test_conversation_and_messages(self):
        """Test conversation with multiple messages."""
        # Create conversation
        conv = ConversationEntity.create_new(
            child_id="child-123",
            summary="Test conversation"
        )
        
        # Create messages
        messages = []
        for i in range(5):
            sender = "child" if i % 2 == 0 else "teddy"
            msg = MessageEntity.create_message(
                conversation_id=conv.id,
                sender=sender,
                content_encrypted=f"message_{i}",
                sequence_number=i
            )
            messages.append(msg)
            conv.add_message()
        
        assert conv.message_count == 5
        assert all(msg.conversation_id == conv.id for msg in messages)
    
    def test_safety_analysis_workflow(self):
        """Test typical safety analysis workflow."""
        # Create message
        msg = MessageEntity.create_message(
            conversation_id="conv-123",
            sender="child",
            content_encrypted="encrypted_content"
        )
        
        # Perform safety analysis
        analysis = SafetyAnalysisResult(
            is_safe=True,
            risk_level=RiskLevel.LOW,
            issues=["mild_concern"],
            reason="Generally safe with minor concern"
        )
        
        # Update message based on analysis
        if analysis.risk_level in [RiskLevel.SAFE, RiskLevel.LOW]:
            msg.update_safety_score(0.9)
        else:
            msg.update_safety_score(0.5)
        
        assert msg.safety_score == 0.9
    
    def test_full_conversation_lifecycle(self):
        """Test complete conversation lifecycle."""
        # Start conversation
        conv = ConversationEntity.create_new(
            child_id="child-456",
            emotion_analysis="curious"
        )
        
        # Exchange messages
        for i in range(3):
            # Child message
            child_msg = MessageEntity.create_message(
                conversation_id=conv.id,
                sender="child",
                content_encrypted=f"child_msg_{i}",
                sequence_number=i*2
            )
            child_msg.update_analysis("happy", 0.7)
            conv.add_message()
            
            # Teddy response
            teddy_msg = MessageEntity.create_message(
                conversation_id=conv.id,
                sender="teddy",
                content_encrypted=f"teddy_msg_{i}",
                sequence_number=i*2+1
            )
            teddy_msg.update_analysis("friendly", 0.8)
            conv.add_message()
        
        # End conversation
        conv.end_conversation(
            summary="Enjoyable conversation about toys",
            emotion_analysis="happy",
            sentiment_score=0.75
        )
        
        assert conv.message_count == 6
        assert conv.end_time is not None
        assert conv.emotion_analysis == "happy"


class TestModuleExports:
    """Test module exports."""
    
    def test_all_exports(self):
        """Test __all__ exports correct models."""
        from src.core import models
        
        assert hasattr(models, '__all__')
        assert "ConversationEntity" in models.__all__
        assert "MessageEntity" in models.__all__
        assert len(models.__all__) == 2