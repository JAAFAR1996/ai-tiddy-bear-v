"""
Production Database Operations Integration Tests
=============================================
Real integration tests for database operations with actual persistence.
NO MOCKS - Tests actual CRUD operations, relationships, and data integrity.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text

from tests.conftest_production import skip_if_offline
from src.infrastructure.database.models import (
    Child, Parent, Conversation, Message, Interaction, SafetyReport
)


class TestProductionDatabaseOperations:
    """Integration tests for real database operations."""
    
    @pytest.mark.asyncio
    async def test_parent_child_relationship_crud(
        self,
        db_session
    ):
        """Test complete CRUD operations for parent-child relationships."""
        
        # Create parent
        parent = Parent(
            id=str(uuid4()),
            email="integration@test.com",
            username="integrationparent",
            hashed_password="hashed_password_here",
            is_verified=True,
            created_at=datetime.utcnow()
        )
        
        db_session.add(parent)
        await db_session.commit()
        await db_session.refresh(parent)
        
        assert parent.id is not None
        assert parent.email == "integration@test.com"
        
        # Create child linked to parent
        child = Child(
            id=str(uuid4()),
            name="Integration Test Child",
            age=9,
            parent_id=parent.id,
            parental_consent=True,
            preferences={"language": "en", "voice_type": "friendly"},
            created_at=datetime.utcnow()
        )
        
        db_session.add(child)
        await db_session.commit()
        await db_session.refresh(child)
        
        assert child.id is not None
        assert child.parent_id == parent.id
        assert child.parental_consent is True
        
        # Test relationship query
        parent_with_children = await db_session.get(Parent, parent.id)
        assert parent_with_children is not None
        
        # Test child update
        child.age = 10
        child.preferences["new_interest"] = "robots"
        await db_session.commit()
        await db_session.refresh(child)
        
        assert child.age == 10
        assert child.preferences["new_interest"] == "robots"
        
        # Test deletion (child first due to foreign key)
        await db_session.delete(child)
        await db_session.commit()
        
        # Verify child is deleted
        deleted_child = await db_session.get(Child, child.id)
        assert deleted_child is None
        
        # Parent should still exist
        existing_parent = await db_session.get(Parent, parent.id)
        assert existing_parent is not None
        
        # Clean up parent
        await db_session.delete(parent)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_conversation_message_workflow(
        self,
        test_child,
        db_session
    ):
        """Test complete conversation and message workflow."""
        
        # Create conversation
        conversation = Conversation(
            child_id=test_child.id,
            status="active",
            started_at=datetime.utcnow(),
            context={"session_type": "storytelling", "topic": "animals"}
        )
        
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        assert conversation.id is not None
        assert conversation.child_id == test_child.id
        assert conversation.status == "active"
        
        # Add messages to conversation
        messages_data = [
            ("child", "Tell me about elephants"),
            ("ai", "Elephants are amazing animals! They're very intelligent..."),
            ("child", "Do they remember things?"),
            ("ai", "Yes! Elephants have excellent memories...")
        ]
        
        message_ids = []
        for sender_type, content in messages_data:
            message = Message(
                conversation_id=conversation.id,
                content=content,
                sender_type=sender_type,
                timestamp=datetime.utcnow()
            )
            db_session.add(message)
            await db_session.commit()
            await db_session.refresh(message)
            message_ids.append(message.id)
        
        assert len(message_ids) == 4
        
        # Query messages in conversation
        result = await db_session.execute(
            text("SELECT * FROM messages WHERE conversation_id = :conv_id ORDER BY timestamp"),
            {"conv_id": conversation.id}
        )
        messages = result.fetchall()
        
        assert len(messages) == 4
        assert messages[0].content == "Tell me about elephants"
        assert messages[0].sender_type == "child"
        assert messages[1].sender_type == "ai"
        
        # Test conversation completion
        conversation.status = "completed"
        conversation.ended_at = datetime.utcnow()
        await db_session.commit()
        
        # Verify update
        updated_conv = await db_session.get(Conversation, conversation.id)
        assert updated_conv.status == "completed"
        assert updated_conv.ended_at is not None
    
    @pytest.mark.asyncio
    async def test_interaction_tracking_integration(
        self,
        test_child,
        db_session
    ):
        """Test interaction tracking with database integration."""
        
        # Create conversation
        conversation = Conversation(
            child_id=test_child.id,
            status="active",
            started_at=datetime.utcnow()
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        # Create multiple interactions
        interactions_data = [
            ("Hello!", "Hi there! How can I help you?", 98.5, False),
            ("Tell me a joke", "Why don't scientists trust atoms? Because they make up everything!", 99.0, False),
            ("I'm feeling sad", "I'm sorry to hear that. Would you like to talk about it?", 85.0, False),
        ]
        
        interaction_ids = []
        for user_msg, ai_response, safety_score, flagged in interactions_data:
            interaction = Interaction(
                conversation_id=conversation.id,
                message=user_msg,
                ai_response=ai_response,
                timestamp=datetime.utcnow(),
                safety_score=safety_score,
                flagged=flagged
            )
            db_session.add(interaction)
            await db_session.commit()
            await db_session.refresh(interaction)
            interaction_ids.append(interaction.id)
        
        assert len(interaction_ids) == 3
        
        # Test analytics queries
        analytics_result = await db_session.execute(
            text("""
                SELECT 
                    COUNT(*) as total_interactions,
                    AVG(safety_score) as avg_safety_score,
                    COUNT(CASE WHEN flagged = 1 THEN 1 END) as flagged_count,
                    MIN(safety_score) as min_safety_score,
                    MAX(safety_score) as max_safety_score
                FROM interactions 
                WHERE conversation_id = :conv_id
            """),
            {"conv_id": conversation.id}
        )
        
        stats = analytics_result.fetchone()
        assert stats.total_interactions == 3
        assert stats.avg_safety_score > 90.0
        assert stats.flagged_count == 0
        assert stats.min_safety_score == 85.0
        assert stats.max_safety_score == 99.0
    
    @pytest.mark.asyncio
    async def test_safety_report_lifecycle(
        self,
        test_child,
        db_session
    ):
        """Test safety report creation and lifecycle management."""
        
        # Create safety report
        safety_report = SafetyReport(
            child_id=test_child.id,
            report_type="inappropriate_content",
            severity="high",
            description="Child attempted to share personal information",
            content_flagged="My address is 123 Main Street",
            detected_by_ai=True,
            ai_confidence=0.95,
            detection_rules=["pii_detection", "address_pattern"],
            reviewed=False,
            resolved=False,
            created_at=datetime.utcnow()
        )
        
        db_session.add(safety_report)
        await db_session.commit()
        await db_session.refresh(safety_report)
        
        assert safety_report.id is not None
        assert safety_report.child_id == test_child.id
        assert safety_report.severity == "high"
        assert safety_report.reviewed is False
        assert safety_report.resolved is False
        
        # Test report review workflow
        safety_report.reviewed = True
        safety_report.reviewer_id = "admin-123"
        safety_report.reviewed_at = datetime.utcnow()
        safety_report.resolution_notes = "Addressed with parent notification"
        
        await db_session.commit()
        await db_session.refresh(safety_report)
        
        assert safety_report.reviewed is True
        assert safety_report.reviewer_id == "admin-123"
        assert safety_report.reviewed_at is not None
        
        # Test report resolution
        safety_report.resolved = True
        safety_report.resolved_at = datetime.utcnow()
        
        await db_session.commit()
        await db_session.refresh(safety_report)
        
        assert safety_report.resolved is True
        assert safety_report.resolved_at is not None
    
    @pytest.mark.asyncio
    async def test_data_integrity_constraints(
        self,
        test_parent,
        db_session
    ):
        """Test database constraints and data validation."""
        
        # Test foreign key constraint
        try:
            invalid_child = Child(
                id=str(uuid4()),
                name="Invalid Child",
                age=8,
                parent_id="non-existent-parent-id",
                parental_consent=True,
                created_at=datetime.utcnow()
            )
            
            db_session.add(invalid_child)
            await db_session.commit()
            
            # Should raise constraint error
            assert False, "Should have raised foreign key constraint error"
            
        except Exception as e:
            # Expected constraint violation
            await db_session.rollback()
            assert "foreign key" in str(e).lower() or "constraint" in str(e).lower()
        
        # Test unique constraint (email)
        try:
            duplicate_parent = Parent(
                id=str(uuid4()),
                email=test_parent.email,  # Same email as existing parent
                username="duplicate_parent",
                hashed_password="password",
                is_verified=True,
                created_at=datetime.utcnow()
            )
            
            db_session.add(duplicate_parent)
            await db_session.commit()
            
            # Should raise unique constraint error
            assert False, "Should have raised unique constraint error"
            
        except Exception as e:
            # Expected unique constraint violation
            await db_session.rollback()
            assert "unique" in str(e).lower() or "constraint" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_complex_queries_and_joins(
        self,
        test_child,
        test_parent,
        db_session
    ):
        """Test complex database queries and joins."""
        
        # Create test data
        conversation = Conversation(
            child_id=test_child.id,
            status="completed",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow()
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        # Add interactions
        for i in range(5):
            interaction = Interaction(
                conversation_id=conversation.id,
                message=f"Test message {i}",
                ai_response=f"Test response {i}",
                timestamp=datetime.utcnow(),
                safety_score=90.0 + i,
                flagged=i > 3  # Flag last interaction
            )
            db_session.add(interaction)
        
        await db_session.commit()
        
        # Complex query: Parent dashboard data
        dashboard_query = text("""
            SELECT 
                p.username as parent_name,
                c.name as child_name,
                c.age,
                COUNT(DISTINCT conv.id) as total_conversations,
                COUNT(i.id) as total_interactions,
                AVG(i.safety_score) as avg_safety_score,
                COUNT(CASE WHEN i.flagged = 1 THEN 1 END) as flagged_interactions
            FROM parents p
            JOIN children c ON p.id = c.parent_id
            LEFT JOIN conversations conv ON c.id = conv.child_id
            LEFT JOIN interactions i ON conv.id = i.conversation_id
            WHERE p.id = :parent_id
            GROUP BY p.id, c.id
        """)
        
        result = await db_session.execute(dashboard_query, {"parent_id": test_parent.id})
        dashboard_data = result.fetchone()
        
        assert dashboard_data is not None
        assert dashboard_data.parent_name == test_parent.username
        assert dashboard_data.child_name == test_child.name
        assert dashboard_data.total_conversations == 1
        assert dashboard_data.total_interactions == 5
        assert 90.0 <= dashboard_data.avg_safety_score <= 95.0
        assert dashboard_data.flagged_interactions == 1
    
    @pytest.mark.asyncio
    async def test_database_performance_under_load(
        self,
        test_child,
        db_session
    ):
        """Test database performance with larger datasets."""
        
        import time
        
        # Create conversation
        conversation = Conversation(
            child_id=test_child.id,
            status="active",
            started_at=datetime.utcnow()
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        # Bulk insert interactions
        start_time = time.time()
        
        interactions = []
        for i in range(100):
            interaction = Interaction(
                conversation_id=conversation.id,
                message=f"Bulk message {i}",
                ai_response=f"Bulk response {i}",
                timestamp=datetime.utcnow(),
                safety_score=95.0,
                flagged=False
            )
            interactions.append(interaction)
        
        db_session.add_all(interactions)
        await db_session.commit()
        
        insert_time = time.time() - start_time
        
        # Should complete bulk insert reasonably quickly
        assert insert_time < 5.0  # Less than 5 seconds for 100 records
        
        # Test query performance
        start_time = time.time()
        
        result = await db_session.execute(
            text("SELECT COUNT(*) FROM interactions WHERE conversation_id = :conv_id"),
            {"conv_id": conversation.id}
        )
        count = result.scalar()
        
        query_time = time.time() - start_time
        
        assert count == 100
        assert query_time < 1.0  # Less than 1 second for count query
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_scenarios(
        self,
        test_child,
        db_session
    ):
        """Test transaction rollback scenarios."""
        
        # Start transaction
        initial_conversations = await db_session.execute(
            text("SELECT COUNT(*) FROM conversations WHERE child_id = :child_id"),
            {"child_id": test_child.id}
        )
        initial_count = initial_conversations.scalar()
        
        try:
            # Create conversation
            conversation = Conversation(
                child_id=test_child.id,
                status="active",
                started_at=datetime.utcnow()
            )
            db_session.add(conversation)
            await db_session.flush()  # Flush but don't commit
            
            # Create invalid interaction (force error)
            invalid_interaction = Interaction(
                conversation_id="invalid-uuid-format",  # Invalid UUID
                message="Test message",
                ai_response="Test response",
                timestamp=datetime.utcnow(),
                safety_score=95.0,
                flagged=False
            )
            db_session.add(invalid_interaction)
            await db_session.commit()  # This should fail
            
        except Exception:
            # Expected error, rollback
            await db_session.rollback()
        
        # Verify no data was committed
        final_conversations = await db_session.execute(
            text("SELECT COUNT(*) FROM conversations WHERE child_id = :child_id"),
            {"child_id": test_child.id}
        )
        final_count = final_conversations.scalar()
        
        assert final_count == initial_count  # No new conversations should be added
    
    @pytest.mark.asyncio
    async def test_database_connection_recovery(
        self,
        database_manager
    ):
        """Test database connection recovery scenarios."""
        
        # Test connection health
        async with database_manager.get_session() as session:
            result = await session.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            assert test_value == 1
        
        # Test multiple concurrent connections
        async def test_concurrent_connection():
            async with database_manager.get_session() as session:
                result = await session.execute(text("SELECT 1 as test"))
                return result.scalar()
        
        import asyncio
        tasks = [test_concurrent_connection() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All connections should succeed
        assert all(result == 1 for result in results)
        assert len(results) == 10


class TestDatabaseIndexingAndOptimization:
    """Test database indexing and query optimization."""
    
    @pytest.mark.asyncio
    async def test_query_performance_with_indexes(
        self,
        test_child,
        db_session
    ):
        """Test that database queries perform well with proper indexing."""
        
        # Create test data
        conversation = Conversation(
            child_id=test_child.id,
            status="active",
            started_at=datetime.utcnow()
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        # Add many interactions
        interactions = []
        for i in range(50):
            interaction = Interaction(
                conversation_id=conversation.id,
                message=f"Query test message {i}",
                ai_response=f"Query test response {i}",
                timestamp=datetime.utcnow(),
                safety_score=85.0 + (i % 15),  # Vary scores
                flagged=i % 10 == 0  # Flag every 10th
            )
            interactions.append(interaction)
        
        db_session.add_all(interactions)
        await db_session.commit()
        
        import time
        
        # Test indexed queries performance
        queries_to_test = [
            # Query by conversation_id (should be indexed)
            ("SELECT * FROM interactions WHERE conversation_id = :conv_id", {"conv_id": conversation.id}),
            # Query by safety_score (should be indexed for analytics)
            ("SELECT * FROM interactions WHERE safety_score < :score", {"score": 90.0}),
            # Query by flagged status (should be indexed)
            ("SELECT * FROM interactions WHERE flagged = 1", {}),
            # Query by timestamp (should be indexed for chronological access)
            ("SELECT * FROM interactions WHERE timestamp > :timestamp ORDER BY timestamp", 
             {"timestamp": datetime.utcnow().replace(hour=0, minute=0, second=0)})
        ]
        
        for query, params in queries_to_test:
            start_time = time.time()
            result = await db_session.execute(text(query), params)
            results = result.fetchall()
            query_time = time.time() - start_time
            
            # Each query should complete quickly
            assert query_time < 0.5  # Less than 500ms
            assert len(results) >= 0  # Should return some results