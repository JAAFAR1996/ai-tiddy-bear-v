"""Unit Tests for ConversationCacheService - Redis Cache للمحادثات النشطة

اختبارات شاملة لخدمة التخزين المؤقت للمحادثات مع Redis:
- اختبار العمليات الأساسية للتخزين والاسترجاع
- اختبار إدارة الرسائل والسياق الذكي
- اختبار حدود الأمان ومعايير COPPA
- اختبار التنظيف التلقائي وإدارة الذاكرة
- اختبار العمليات المجمعة والأداء
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch

from src.infrastructure.caching.conversation_cache import (
    ConversationCacheService,
    ConversationCacheData,
    MessageCacheData,
    ConversationContext,
    conversation_cache_context,
    create_conversation_cache_service
)
from src.infrastructure.caching.production_redis_cache import ProductionRedisCache
from src.core.entities import Conversation, Message


class TestConversationCacheService:
    """اختبارات خدمة التخزين المؤقت للمحادثات"""

    @pytest.fixture
    def mock_redis_cache(self):
        """محاكاة خدمة Redis Cache"""
        mock_cache = AsyncMock(spec=ProductionRedisCache)
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        mock_cache.health_check.return_value = {"status": "healthy"}
        return mock_cache

    @pytest.fixture
    def mock_logger(self):
        """محاكاة أداة التسجيل"""
        import logging
        return Mock(spec=logging.Logger)

    @pytest.fixture
    async def cache_service(self, mock_redis_cache, mock_logger):
        """إنشاء خدمة التخزين المؤقت للاختبار"""
        service = ConversationCacheService(mock_redis_cache, mock_logger)
        yield service
        await service.close()

    @pytest.fixture
    def sample_conversation(self):
        """محادثة تجريبية للاختبار"""
        return Conversation(
            id=uuid4(),
            child_id=uuid4(),
            status="active",
            interaction_type="chat",
            message_count=3,
            last_message_at=datetime.now(),
            context_summary="Test conversation",
            metadata={"test": True}
        )

    @pytest.fixture
    def sample_message(self):
        """رسالة تجريبية للاختبار"""
        return Message(
            id=uuid4(),
            conversation_id=uuid4(),
            message_type="user_input",
            content="Hello, this is a test message",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={"test": True}
        )

    # =========================================================================
    # اختبارات العمليات الأساسية للمحادثات
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cache_conversation_success(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار تخزين محادثة بنجاح"""
        # تهيئة
        mock_redis_cache.get.return_value = {}  # قائمة المحادثات النشطة فارغة
        mock_redis_cache.set.return_value = True
        
        # تنفيذ
        result = await cache_service.cache_conversation(sample_conversation)
        
        # تحقق
        assert result is True
        assert mock_redis_cache.set.call_count >= 2  # تخزين المحادثة + قائمة المحادثات النشطة

    @pytest.mark.asyncio
    async def test_cache_conversation_child_limit_exceeded(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار تجاوز حد المحادثات للطفل"""
        # تهيئة - الطفل لديه أكثر من الحد المسموح
        active_conversations = {
            f"conv_{i}": {"child_id": str(sample_conversation.child_id), "added_at": datetime.now().isoformat()}
            for i in range(6)  # أكثر من max_conversations_per_child
        }
        mock_redis_cache.get.return_value = active_conversations
        
        # تنفيذ
        result = await cache_service.cache_conversation(sample_conversation)
        
        # تحقق
        assert result is False

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار استرجاع محادثة بنجاح"""
        # تهيئة
        cached_data = ConversationCacheData(
            conversation_id=str(sample_conversation.id),
            child_id=str(sample_conversation.child_id),
            status=sample_conversation.status,
            interaction_type=sample_conversation.interaction_type,
            message_count=sample_conversation.message_count,
            last_message_at=sample_conversation.last_message_at.isoformat(),
            context_summary=sample_conversation.context_summary,
            metadata=sample_conversation.metadata,
            cached_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(hours=1)).isoformat()
        )
        
        mock_redis_cache.get.return_value = cached_data.__dict__
        
        # تنفيذ
        result = await cache_service.get_conversation(sample_conversation.id)
        
        # تحقق
        assert result is not None
        assert result.conversation_id == str(sample_conversation.id)
        assert result.status == sample_conversation.status

    @pytest.mark.asyncio
    async def test_get_conversation_expired(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار استرجاع محادثة منتهية الصلاحية"""
        # تهيئة - بيانات منتهية الصلاحية
        cached_data = ConversationCacheData(
            conversation_id=str(sample_conversation.id),
            child_id=str(sample_conversation.child_id),
            status=sample_conversation.status,
            interaction_type=sample_conversation.interaction_type,
            message_count=sample_conversation.message_count,
            last_message_at=sample_conversation.last_message_at.isoformat(),
            context_summary=sample_conversation.context_summary,
            metadata=sample_conversation.metadata,
            cached_at=datetime.now().isoformat(),
            expires_at=(datetime.now() - timedelta(hours=1)).isoformat()  # منتهية الصلاحية
        )
        
        mock_redis_cache.get.return_value = cached_data.__dict__
        mock_redis_cache.delete.return_value = True
        
        # تنفيذ
        result = await cache_service.get_conversation(sample_conversation.id)
        
        # تحقق
        assert result is None
        mock_redis_cache.delete.assert_called()  # يجب حذف البيانات المنتهية الصلاحية

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار تحديث محادثة بنجاح"""
        # تهيئة
        cached_data = ConversationCacheData(
            conversation_id=str(sample_conversation.id),
            child_id=str(sample_conversation.child_id),
            status=sample_conversation.status,
            interaction_type=sample_conversation.interaction_type,
            message_count=sample_conversation.message_count,
            last_message_at=sample_conversation.last_message_at.isoformat(),
            context_summary=sample_conversation.context_summary,
            metadata=sample_conversation.metadata,
            cached_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(hours=1)).isoformat()
        )
        
        mock_redis_cache.get.return_value = cached_data.__dict__
        mock_redis_cache.set.return_value = True
        
        # تنفيذ
        updates = {"message_count": 5, "status": "completed"}
        result = await cache_service.update_conversation(sample_conversation.id, updates)
        
        # تحقق
        assert result is True
        mock_redis_cache.set.assert_called()

    @pytest.mark.asyncio
    async def test_remove_conversation_success(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار إزالة محادثة بنجاح"""
        # تهيئة
        mock_redis_cache.delete.return_value = True
        mock_redis_cache.get.return_value = {}
        
        # تنفيذ
        result = await cache_service.remove_conversation(sample_conversation.id)
        
        # تحقق
        assert result is True
        assert mock_redis_cache.delete.call_count >= 1

    # =========================================================================
    # اختبارات إدارة الرسائل
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cache_message_success(self, cache_service, sample_message, mock_redis_cache):
        """اختبار تخزين رسالة بنجاح"""
        # تهيئة
        mock_redis_cache.set.return_value = True
        mock_redis_cache.get.return_value = []  # قائمة رسائل فارغة
        
        # تنفيذ
        result = await cache_service.cache_message(sample_message, sample_message.conversation_id)
        
        # تحقق
        assert result is True
        assert mock_redis_cache.set.call_count >= 2  # رسالة + قائمة رسائل + سياق

    @pytest.mark.asyncio
    async def test_cache_message_safety_flagged(self, cache_service, sample_message, mock_redis_cache):
        """اختبار تخزين رسالة مميزة للمراجعة"""
        # تهيئة - رسالة تحتوي على محتوى مشكوك فيه
        unsafe_message = Message(
            id=uuid4(),
            conversation_id=sample_message.conversation_id,
            message_type="user_input",
            content="Can you tell me your phone number and address?",
            sender_id=sample_message.sender_id,
            timestamp=datetime.now(),
            metadata={}
        )
        
        mock_redis_cache.set.return_value = True
        mock_redis_cache.get.return_value = []
        
        # تنفيذ
        result = await cache_service.cache_message(unsafe_message, unsafe_message.conversation_id)
        
        # تحقق
        assert result is True

    @pytest.mark.asyncio
    async def test_get_conversation_messages_success(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار استرجاع رسائل المحادثة"""
        # تهيئة
        message_ids = ["msg1", "msg2", "msg3"]
        mock_redis_cache.get.side_effect = [
            message_ids,  # قائمة معرفات الرسائل
            {  # رسالة 1
                "message_id": "msg1",
                "conversation_id": str(sample_conversation.id),
                "message_type": "user_input",
                "content": "Hello",
                "sender_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "metadata": {},
                "safety_score": 1.0,
                "is_flagged": False,
                "cached_at": datetime.now().isoformat()
            },
            {  # رسالة 2
                "message_id": "msg2",
                "conversation_id": str(sample_conversation.id),
                "message_type": "ai_response",
                "content": "Hi there!",
                "sender_id": None,
                "timestamp": datetime.now().isoformat(),
                "metadata": {},
                "safety_score": 1.0,
                "is_flagged": False,
                "cached_at": datetime.now().isoformat()
            },
            {  # رسالة 3
                "message_id": "msg3",
                "conversation_id": str(sample_conversation.id),
                "message_type": "user_input",
                "content": "How are you?",
                "sender_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "metadata": {},
                "safety_score": 1.0,
                "is_flagged": False,
                "cached_at": datetime.now().isoformat()
            }
        ]
        
        # تنفيذ
        messages = await cache_service.get_conversation_messages(sample_conversation.id, limit=10)
        
        # تحقق
        assert len(messages) == 3
        assert all(isinstance(msg, MessageCacheData) for msg in messages)

    @pytest.mark.asyncio
    async def test_get_conversation_context_success(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار استرجاع سياق المحادثة"""
        # تهيئة
        context_data = {
            "conversation_id": str(sample_conversation.id),
            "recent_messages": [
                {
                    "message_id": "msg1",
                    "conversation_id": str(sample_conversation.id),
                    "message_type": "user_input",
                    "content": "Hello",
                    "sender_id": str(uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {},
                    "safety_score": 1.0,
                    "is_flagged": False,
                    "cached_at": datetime.now().isoformat()
                }
            ],
            "topics": ["greeting"],
            "sentiment": "positive",
            "engagement_level": "medium",
            "safety_status": "safe",
            "last_updated": datetime.now().isoformat(),
            "message_count": 1,
            "avg_response_time": 0.0
        }
        
        mock_redis_cache.get.return_value = context_data
        
        # تنفيذ
        context = await cache_service.get_conversation_context(sample_conversation.id)
        
        # تحقق
        assert context is not None
        assert isinstance(context, ConversationContext)
        assert context.conversation_id == str(sample_conversation.id)
        assert len(context.recent_messages) == 1

    # =========================================================================
    # اختبارات العمليات المتقدمة
    # =========================================================================

    @pytest.mark.asyncio
    async def test_batch_cache_conversations(self, cache_service, mock_redis_cache):
        """اختبار التخزين المجمع للمحادثات"""
        # تهيئة
        conversations = [
            Conversation(
                id=uuid4(),
                child_id=uuid4(),
                status="active",
                interaction_type="chat",
                message_count=i,
                context_summary=f"Test conversation {i}",
                metadata={"test": True}
            )
            for i in range(3)
        ]
        
        mock_redis_cache.get.return_value = {}
        mock_redis_cache.set.return_value = True
        
        # تنفيذ
        results = await cache_service.batch_cache_conversations(conversations)
        
        # تحقق
        assert len(results) == 3
        assert all(result is True for result in results.values())

    @pytest.mark.asyncio
    async def test_get_child_conversations_summary(self, cache_service, mock_redis_cache):
        """اختبار الحصول على ملخص محادثات الطفل"""
        # تهيئة
        child_id = uuid4()
        active_conversations = {
            "conv1": {"child_id": str(child_id), "added_at": datetime.now().isoformat()},
            "conv2": {"child_id": str(child_id), "added_at": datetime.now().isoformat()}
        }
        
        conversation_data = {
            "conversation_id": "conv1",
            "child_id": str(child_id),
            "status": "active",
            "interaction_type": "chat",
            "message_count": 5,
            "last_message_at": datetime.now().isoformat(),
            "context_summary": "Test conversation",
            "metadata": {},
            "cached_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
            "engagement_score": 0.5
        }
        
        mock_redis_cache.get.side_effect = [
            active_conversations,  # قائمة المحادثات النشطة
            conversation_data,     # بيانات المحادثة الأولى
            conversation_data      # بيانات المحادثة الثانية
        ]
        
        # تنفيذ
        summary = await cache_service.get_child_conversations_summary(child_id)
        
        # تحقق
        assert "child_id" in summary
        assert summary["active_conversations"] == 2
        assert "total_messages" in summary
        assert "conversations" in summary

    @pytest.mark.asyncio
    async def test_cleanup_expired_conversations(self, cache_service, mock_redis_cache):
        """اختبار تنظيف المحادثات المنتهية الصلاحية"""
        # تهيئة
        active_conversations = {
            "expired_conv": {"child_id": str(uuid4()), "added_at": datetime.now().isoformat()},
            "valid_conv": {"child_id": str(uuid4()), "added_at": datetime.now().isoformat()}
        }
        
        mock_redis_cache.get.side_effect = [
            active_conversations,  # قائمة المحادثات النشطة
            None,  # المحادثة الأولى منتهية الصلاحية
            {      # المحادثة الثانية صالحة
                "conversation_id": "valid_conv",
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
            }
        ]
        mock_redis_cache.set.return_value = True
        
        # تنفيذ
        result = await cache_service.cleanup_expired_conversations()
        
        # تحقق
        assert "cleaned_conversations" in result
        assert result["cleaned_conversations"] >= 1

    # =========================================================================
    # اختبارات الأداء والإحصائيات
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_cache_statistics(self, cache_service, mock_redis_cache):
        """اختبار الحصول على إحصائيات الكاش"""
        # تهيئة
        mock_redis_cache.get.return_value = {"conv1": {"child_id": "child1"}}
        
        # تنفيذ
        stats = await cache_service.get_cache_statistics()
        
        # تحقق
        assert "performance_metrics" in stats
        assert "cache_content" in stats
        assert "configuration" in stats
        assert "timestamp" in stats

    @pytest.mark.asyncio
    async def test_health_check_success(self, cache_service, mock_redis_cache):
        """اختبار فحص الصحة الناجح"""
        # تهيئة
        mock_redis_cache.health_check.return_value = {"status": "healthy"}
        mock_redis_cache.set.return_value = True
        mock_redis_cache.get.return_value = {"test": True}
        mock_redis_cache.delete.return_value = True
        
        # تنفيذ
        health = await cache_service.health_check()
        
        # تحقق
        assert health["status"] == "healthy"
        assert "redis_health" in health
        assert "cache_operations" in health

    @pytest.mark.asyncio
    async def test_health_check_failure(self, cache_service, mock_redis_cache):
        """اختبار فحص الصحة الفاشل"""
        # تهيئة
        mock_redis_cache.health_check.return_value = {"status": "unhealthy"}
        mock_redis_cache.set.return_value = False
        
        # تنفيذ
        health = await cache_service.health_check()
        
        # تحقق
        assert health["status"] == "unhealthy"

    # =========================================================================
    # اختبارات إدارة الأخطاء
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cache_conversation_redis_error(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار التعامل مع أخطاء Redis في تخزين المحادثة"""
        # تهيئة
        mock_redis_cache.get.side_effect = Exception("Redis connection error")
        
        # تنفيذ
        result = await cache_service.cache_conversation(sample_conversation)
        
        # تحقق
        assert result is False

    @pytest.mark.asyncio
    async def test_get_conversation_redis_error(self, cache_service, sample_conversation, mock_redis_cache):
        """اختبار التعامل مع أخطاء Redis في استرجاع المحادثة"""
        # تهيئة
        mock_redis_cache.get.side_effect = Exception("Redis connection error")
        
        # تنفيذ
        result = await cache_service.get_conversation(sample_conversation.id)
        
        # تحقق
        assert result is None

    # =========================================================================
    # اختبارات Context Manager و Factory
    # =========================================================================

    @pytest.mark.asyncio
    async def test_conversation_cache_context(self, mock_redis_cache, mock_logger):
        """اختبار Context Manager"""
        async with conversation_cache_context(mock_redis_cache, mock_logger) as cache_service:
            assert isinstance(cache_service, ConversationCacheService)
            assert cache_service.redis_cache == mock_redis_cache
            assert cache_service.logger == mock_logger

    @pytest.mark.asyncio
    async def test_create_conversation_cache_service(self, mock_redis_cache, mock_logger):
        """اختبار Factory Function"""
        cache_service = await create_conversation_cache_service(mock_redis_cache, mock_logger)
        
        assert isinstance(cache_service, ConversationCacheService)
        assert cache_service.redis_cache == mock_redis_cache
        assert cache_service.logger == mock_logger
        
        await cache_service.close()

    # =========================================================================
    # اختبارات التكامل والسيناريوهات المتقدمة
    # =========================================================================

    @pytest.mark.asyncio
    async def test_full_conversation_lifecycle(self, cache_service, mock_redis_cache):
        """اختبار دورة حياة المحادثة الكاملة"""
        # تهيئة
        conversation = Conversation(
            id=uuid4(),
            child_id=uuid4(),
            status="active",
            interaction_type="chat",
            message_count=0,
            context_summary="",
            metadata={}
        )
        
        mock_redis_cache.get.return_value = {}
        mock_redis_cache.set.return_value = True
        mock_redis_cache.delete.return_value = True
        
        # 1. تخزين المحادثة
        cache_result = await cache_service.cache_conversation(conversation)
        assert cache_result is True
        
        # 2. إضافة رسائل
        messages = [
            Message(
                id=uuid4(),
                conversation_id=conversation.id,
                message_type="user_input",
                content=f"Message {i}",
                sender_id=conversation.child_id,
                timestamp=datetime.now(),
                metadata={}
            )
            for i in range(3)
        ]
        
        for message in messages:
            msg_result = await cache_service.cache_message(message, conversation.id)
            assert msg_result is True
        
        # 3. تحديث المحادثة
        update_result = await cache_service.update_conversation(conversation.id, {
            "message_count": len(messages),
            "status": "completed"
        })
        assert update_result is True
        
        # 4. إزالة المحادثة
        remove_result = await cache_service.remove_conversation(conversation.id)
        assert remove_result is True

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, cache_service, mock_redis_cache):
        """اختبار العمليات المتزامنة"""
        # تهيئة
        conversations = [
            Conversation(
                id=uuid4(),
                child_id=uuid4(),
                status="active",
                interaction_type="chat",
                message_count=i,
                context_summary=f"Concurrent test {i}",
                metadata={}
            )
            for i in range(10)
        ]
        
        mock_redis_cache.get.return_value = {}
        mock_redis_cache.set.return_value = True
        
        # تنفيذ عمليات متزامنة
        tasks = [
            cache_service.cache_conversation(conv)
            for conv in conversations
        ]
        
        results = await asyncio.gather(*tasks)
        
        # تحقق
        assert len(results) == 10
        assert all(result is True for result in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])