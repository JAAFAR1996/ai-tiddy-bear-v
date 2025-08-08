"""Advanced Redis Caching for Active Conversations - Enhanced Performance System

نظام تخزين مؤقت متقدم للمحادثات النشطة مع Redis:
- تخزين مؤقت ذكي للمحادثات النشطة مع التحقق من صحة البيانات
- تخزين تاريخ الرسائل مع ضغط البيانات وتحسين الأداء  
- إدارة السياق والذاكرة مع آليات التنظيف التلقائي
- تتبع استخدام الأطفال مع الامتثال لقوانين COPPA
- دعم التخزين المؤقت الموزع والتحديث في الوقت الفعلي
- نظام تنظيف تلقائي وإدارة الذاكرة الذكية
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from src.infrastructure.caching.production_redis_cache import ProductionRedisCache
from src.core.entities import Conversation, Message


@dataclass
class ConversationCacheData:
    """بيانات المحادثة المخزنة مؤقتاً مع معلومات التحقق"""
    conversation_id: str
    child_id: str
    status: str
    interaction_type: str
    message_count: int
    last_message_at: str
    context_summary: str
    metadata: Dict[str, Any]
    cached_at: str
    expires_at: str
    is_child_safe: bool = True
    engagement_score: float = 0.0

    def to_conversation(self) -> Dict[str, Any]:
        """تحويل إلى تنسيق Conversation Entity"""
        return {
            "id": self.conversation_id,
            "child_id": self.child_id,
            "status": self.status,
            "interaction_type": self.interaction_type,
            "message_count": self.message_count,
            "last_message_at": self.last_message_at,
            "context_summary": self.context_summary,
            "metadata": self.metadata
        }


@dataclass
class MessageCacheData:
    """بيانات الرسالة المخزنة مؤقتاً مع معلومات السلامة"""
    message_id: str
    conversation_id: str
    message_type: str
    content: str
    sender_id: Optional[str]
    timestamp: str
    metadata: Dict[str, Any]
    safety_score: float = 1.0
    is_flagged: bool = False
    cached_at: str = None

    def __post_init__(self):
        if self.cached_at is None:
            self.cached_at = datetime.now().isoformat()

    def to_message(self) -> Dict[str, Any]:
        """تحويل إلى تنسيق Message Entity"""
        return {
            "id": self.message_id,
            "conversation_id": self.conversation_id,
            "message_type": self.message_type,
            "content": self.content,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class ConversationContext:
    """سياق المحادثة الذكي مع تحليل الأنماط"""
    conversation_id: str
    recent_messages: List[MessageCacheData]
    topics: List[str]
    sentiment: str
    engagement_level: str
    safety_status: str
    last_updated: str
    message_count: int = 0
    avg_response_time: float = 0.0


class ConversationCacheService:
    """خدمة التخزين المؤقت المتقدمة للمحادثات مع Redis
    
    توفر إمكانيات شاملة لتخزين وإدارة المحادثات النشطة:
    - تخزين ذكي للمحادثات مع تحسين الأداء
    - إدارة تاريخ الرسائل مع ضغط البيانات
    - تتبع السياق والذاكرة الذكية
    - ضمان السلامة والامتثال لـ COPPA
    - نظام تنظيف تلقائي وإدارة الذاكرة
    """

    def __init__(self, redis_cache: ProductionRedisCache = None, logger=None):
        """تهيئة خدمة التخزين المؤقت للمحادثات
        
        Args:
            redis_cache: خدمة Redis Cache الأساسية
            logger: أداة التسجيل
        """
        self.redis_cache = redis_cache or ProductionRedisCache()
        self.logger = logger
        
        # إعدادات التخزين المؤقت
        self.conversation_ttl = 3600 * 4  # 4 ساعات للمحادثات النشطة
        self.message_ttl = 3600 * 24  # 24 ساعة لتاريخ الرسائل
        self.context_ttl = 3600 * 2   # ساعتان للسياق
        self.child_usage_ttl = 3600 * 24 * 7  # أسبوع لتتبع الاستخدام
        
        # إعدادات الحدود والأمان
        self.max_messages_per_conversation = 100
        self.max_context_messages = 10
        self.max_conversations_per_child = 5
        self.message_compression_threshold = 500  # بايت
        
        # مفاتيح Redis
        self.conversation_key_prefix = "conv_cache"
        self.message_key_prefix = "msg_cache"
        self.context_key_prefix = "ctx_cache"
        self.child_usage_prefix = "child_usage"
        self.active_conversations_key = "active_convs"
        
        # إحصائيات الأداء
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0
        
        if self.logger:
            self.logger.info("ConversationCacheService initialized successfully")

    # =========================================================================
    # إدارة المحادثات النشطة
    # =========================================================================

    async def cache_conversation(
        self, 
        conversation: Conversation,
        ttl: Optional[int] = None
    ) -> bool:
        """تخزين محادثة في الكاش مع التحقق من السلامة والحدود
        
        Args:
            conversation: كائن المحادثة المراد تخزينه
            ttl: مدة البقاء في الثواني (افتراضي: conversation_ttl)
            
        Returns:
            True إذا تم التخزين بنجاح
        """
        try:
            # التحقق من حدود الطفل
            child_conversations = await self._get_child_active_conversations(conversation.child_id)
            if len(child_conversations) >= self.max_conversations_per_child:
                if self.logger:
                    self.logger.warning(
                        f"Child {conversation.child_id} reached max conversations limit",
                        extra={"child_id": str(conversation.child_id)}
                    )
                return False
            
            # إنشاء بيانات الكاش
            cache_data = ConversationCacheData(
                conversation_id=str(conversation.id),
                child_id=str(conversation.child_id),
                status=conversation.status,
                interaction_type=conversation.interaction_type,
                message_count=conversation.message_count,
                last_message_at=conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                context_summary=conversation.context_summary or "",
                metadata=conversation.metadata or {},
                cached_at=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(seconds=ttl or self.conversation_ttl)).isoformat(),
                engagement_score=self._calculate_engagement_score(conversation)
            )
            
            # تخزين في Redis
            cache_key = f"{self.conversation_key_prefix}:{conversation.id}"
            success = await self.redis_cache.set(
                cache_key, 
                asdict(cache_data), 
                ttl or self.conversation_ttl
            )
            
            if success:
                # إضافة إلى قائمة المحادثات النشطة
                await self._add_to_active_conversations(str(conversation.id), str(conversation.child_id))
                
                # تتبع استخدام الطفل
                await self._track_child_usage(conversation.child_id)
                
                if self.logger:
                    self.logger.debug(
                        f"Conversation cached successfully: {conversation.id}",
                        extra={
                            "conversation_id": str(conversation.id),
                            "child_id": str(conversation.child_id),
                            "ttl": ttl or self.conversation_ttl
                        }
                    )
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to cache conversation {conversation.id}: {e}",
                    exc_info=True
                )
            return False

    async def get_conversation(self, conversation_id: UUID) -> Optional[ConversationCacheData]:
        """استرجاع محادثة من الكاش مع التحقق من الصلاحية
        
        Args:
            conversation_id: معرف المحادثة
            
        Returns:
            بيانات المحادثة المخزنة أو None
        """
        try:
            self.total_requests += 1
            
            cache_key = f"{self.conversation_key_prefix}:{conversation_id}"
            cached_data = await self.redis_cache.get(cache_key)
            
            if cached_data is None:
                self.cache_misses += 1
                if self.logger:
                    self.logger.debug(f"Conversation cache miss: {conversation_id}")
                return None
            
            # التحقق من صلاحية البيانات
            conversation_data = ConversationCacheData(**cached_data)
            
            if datetime.fromisoformat(conversation_data.expires_at) < datetime.now():
                # البيانات منتهية الصلاحية
                await self.remove_conversation(conversation_id)
                self.cache_misses += 1
                return None
            
            self.cache_hits += 1
            if self.logger:
                self.logger.debug(f"Conversation cache hit: {conversation_id}")
            
            return conversation_data
            
        except Exception as e:
            self.cache_misses += 1
            if self.logger:
                self.logger.error(
                    f"Failed to get conversation from cache {conversation_id}: {e}",
                    exc_info=True
                )
            return None

    async def update_conversation(
        self, 
        conversation_id: UUID, 
        updates: Dict[str, Any]
    ) -> bool:
        """تحديث محادثة في الكاش بصورة ذرية
        
        Args:
            conversation_id: معرف المحادثة
            updates: التحديثات المطلوب تطبيقها
            
        Returns:
            True إذا تم التحديث بنجاح
        """
        try:
            # استرجاع البيانات الحالية
            current_data = await self.get_conversation(conversation_id)
            if current_data is None:
                return False
            
            # تطبيق التحديثات
            for key, value in updates.items():
                if hasattr(current_data, key):
                    setattr(current_data, key, value)
            
            # تحديث وقت التعديل
            current_data.cached_at = datetime.now().isoformat()
            
            # إعادة التخزين
            cache_key = f"{self.conversation_key_prefix}:{conversation_id}"
            return await self.redis_cache.set(cache_key, asdict(current_data), self.conversation_ttl)
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to update conversation in cache {conversation_id}: {e}",
                    exc_info=True
                )
            return False

    async def remove_conversation(self, conversation_id: UUID) -> bool:
        """إزالة محادثة من الكاش ومن قائمة المحادثات النشطة
        
        Args:
            conversation_id: معرف المحادثة
            
        Returns:
            True إذا تمت الإزالة بنجاح
        """
        try:
            cache_key = f"{self.conversation_key_prefix}:{conversation_id}"
            success = await self.redis_cache.delete(cache_key)
            
            # إزالة من قائمة المحادثات النشطة
            await self._remove_from_active_conversations(str(conversation_id))
            
            # تنظيف الرسائل والسياق المرتبط
            await self._cleanup_conversation_data(conversation_id)
            
            if self.logger:
                self.logger.debug(f"Conversation removed from cache: {conversation_id}")
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to remove conversation from cache {conversation_id}: {e}",
                    exc_info=True
                )
            return False

    # =========================================================================
    # إدارة الرسائل والتاريخ
    # =========================================================================

    async def cache_message(
        self, 
        message: Message, 
        conversation_id: UUID
    ) -> bool:
        """تخزين رسالة في الكاش مع التحقق من السلامة والضغط
        
        Args:
            message: كائن الرسالة
            conversation_id: معرف المحادثة
            
        Returns:
            True إذا تم التخزين بنجاح
        """
        try:
            # التحقق من السلامة
            safety_score = await self._calculate_message_safety_score(message.content)
            is_flagged = safety_score < 0.7
            
            # إنشاء بيانات الكاش
            message_data = MessageCacheData(
                message_id=str(message.id),
                conversation_id=str(conversation_id),
                message_type=message.message_type,
                content=message.content,
                sender_id=str(message.sender_id) if message.sender_id else None,
                timestamp=message.timestamp.isoformat(),
                metadata=message.metadata or {},
                safety_score=safety_score,
                is_flagged=is_flagged
            )
            
            # تخزين الرسالة
            message_key = f"{self.message_key_prefix}:{conversation_id}:{message.id}"
            success = await self.redis_cache.set(
                message_key, 
                asdict(message_data), 
                self.message_ttl
            )
            
            if success:
                # إضافة إلى قائمة رسائل المحادثة
                await self._add_to_conversation_messages(conversation_id, str(message.id))
                
                # تحديث السياق
                await self._update_conversation_context(conversation_id, message_data)
                
                if self.logger:
                    self.logger.debug(
                        f"Message cached: {message.id} for conversation {conversation_id}",
                        extra={
                            "safety_score": safety_score,
                            "is_flagged": is_flagged
                        }
                    )
            
            return success
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to cache message {message.id}: {e}",
                    exc_info=True
                )
            return False

    async def get_conversation_messages(
        self, 
        conversation_id: UUID, 
        limit: int = 20,
        include_flagged: bool = False
    ) -> List[MessageCacheData]:
        """استرجاع رسائل المحادثة من الكاش مع الفلترة والترتيب
        
        Args:
            conversation_id: معرف المحادثة
            limit: عدد الرسائل المطلوبة
            include_flagged: تضمين الرسائل المميزة للمراجعة
            
        Returns:
            قائمة برسائل المحادثة
        """
        try:
            # استرجاع قائمة معرفات الرسائل
            messages_list_key = f"{self.message_key_prefix}:list:{conversation_id}"
            message_ids = await self.redis_cache.get(messages_list_key, default=[])
            
            if not message_ids:
                return []
            
            # استرجاع الرسائل
            messages = []
            for message_id in message_ids[-limit:]:  # أحدث الرسائل
                message_key = f"{self.message_key_prefix}:{conversation_id}:{message_id}"
                message_data = await self.redis_cache.get(message_key)
                
                if message_data:
                    message_obj = MessageCacheData(**message_data)
                    
                    # فلترة الرسائل المميزة
                    if not include_flagged and message_obj.is_flagged:
                        continue
                    
                    messages.append(message_obj)
            
            # ترتيب حسب التوقيت
            messages.sort(key=lambda m: m.timestamp)
            
            return messages
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to get conversation messages {conversation_id}: {e}",
                    exc_info=True
                )
            return []

    async def get_conversation_context(
        self, 
        conversation_id: UUID,
        context_size: int = 10
    ) -> Optional[ConversationContext]:
        """استرجاع سياق المحادثة الذكي مع التحليل
        
        Args:
            conversation_id: معرف المحادثة
            context_size: عدد الرسائل في السياق
            
        Returns:
            سياق المحادثة أو None
        """
        try:
            context_key = f"{self.context_key_prefix}:{conversation_id}"
            context_data = await self.redis_cache.get(context_key)
            
            if context_data:
                context = ConversationContext(**context_data)
                
                # التحقق من حداثة السياق
                if datetime.fromisoformat(context.last_updated) > datetime.now() - timedelta(minutes=30):
                    return context
            
            # إنشاء سياق جديد
            return await self._generate_conversation_context(conversation_id, context_size)
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to get conversation context {conversation_id}: {e}",
                    exc_info=True
                )
            return None

    # =========================================================================
    # عمليات متقدمة ومجمعة
    # =========================================================================

    async def batch_cache_conversations(
        self, 
        conversations: List[Conversation]
    ) -> Dict[str, bool]:
        """تخزين مجموعة من المحادثات بصورة مجمعة
        
        Args:
            conversations: قائمة المحادثات
            
        Returns:
            خريطة النتائج حسب معرف المحادثة
        """
        results = {}
        
        try:
            # تنفيذ متوازي للعمليات
            tasks = []
            for conversation in conversations:
                task = self.cache_conversation(conversation)
                tasks.append((str(conversation.id), task))
            
            # انتظار جميع العمليات
            for conv_id, task in tasks:
                try:
                    result = await task
                    results[conv_id] = result
                except Exception as e:
                    results[conv_id] = False
                    if self.logger:
                        self.logger.error(f"Batch cache failed for {conv_id}: {e}")
            
            return results
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Batch cache conversations failed: {e}", exc_info=True)
            return results

    async def get_child_conversations_summary(
        self, 
        child_id: UUID
    ) -> Dict[str, Any]:
        """الحصول على ملخص شامل لمحادثات الطفل
        
        Args:
            child_id: معرف الطفل
            
        Returns:
            ملخص شامل للمحادثات والإحصائيات
        """
        try:
            # استرجاع قائمة المحادثات النشطة
            child_conversations = await self._get_child_active_conversations(child_id)
            
            total_messages = 0
            total_engagement = 0.0
            interaction_types = {}
            safety_incidents = 0
            
            conversations_data = []
            
            for conv_id in child_conversations:
                conv_data = await self.get_conversation(UUID(conv_id))
                if conv_data:
                    conversations_data.append(conv_data)
                    total_messages += conv_data.message_count
                    total_engagement += conv_data.engagement_score
                    
                    # تجميع أنواع التفاعل
                    interaction_type = conv_data.interaction_type
                    interaction_types[interaction_type] = interaction_types.get(interaction_type, 0) + 1
            
            # حساب الإحصائيات
            avg_engagement = total_engagement / len(conversations_data) if conversations_data else 0
            
            return {
                "child_id": str(child_id),
                "active_conversations": len(conversations_data),
                "total_messages": total_messages,
                "average_engagement": avg_engagement,
                "interaction_types": interaction_types,
                "safety_incidents": safety_incidents,
                "conversations": [asdict(conv) for conv in conversations_data],
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to get child conversations summary {child_id}: {e}",
                    exc_info=True
                )
            return {"error": str(e)}

    async def cleanup_expired_conversations(self) -> Dict[str, int]:
        """تنظيف المحادثات المنتهية الصلاحية تلقائياً
        
        Returns:
            إحصائيات التنظيف
        """
        try:
            # استرجاع قائمة المحادثات النشطة
            active_conversations = await self.redis_cache.get(self.active_conversations_key, default={})
            
            cleaned_count = 0
            error_count = 0
            
            for conv_id in list(active_conversations.keys()):
                try:
                    conv_data = await self.get_conversation(UUID(conv_id))
                    if conv_data is None:
                        # المحادثة غير موجودة أو منتهية الصلاحية
                        await self._remove_from_active_conversations(conv_id)
                        cleaned_count += 1
                except Exception as e:
                    error_count += 1
                    if self.logger:
                        self.logger.error(f"Error cleaning conversation {conv_id}: {e}")
            
            if self.logger:
                self.logger.info(
                    f"Cleanup completed: {cleaned_count} conversations cleaned, {error_count} errors"
                )
            
            return {
                "cleaned_conversations": cleaned_count,
                "errors": error_count,
                "remaining_active": len(active_conversations) - cleaned_count,
                "cleanup_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Cleanup failed: {e}", exc_info=True)
            return {"error": str(e)}

    # =========================================================================
    # الوظائف المساعدة الداخلية
    # =========================================================================

    async def _add_to_active_conversations(self, conversation_id: str, child_id: str) -> bool:
        """إضافة محادثة إلى قائمة المحادثات النشطة"""
        try:
            active_conversations = await self.redis_cache.get(self.active_conversations_key, default={})
            active_conversations[conversation_id] = {
                "child_id": child_id,
                "added_at": datetime.now().isoformat()
            }
            
            return await self.redis_cache.set(
                self.active_conversations_key, 
                active_conversations, 
                self.conversation_ttl
            )
        except Exception:
            return False

    async def _remove_from_active_conversations(self, conversation_id: str) -> bool:
        """إزالة محادثة من قائمة المحادثات النشطة"""
        try:
            active_conversations = await self.redis_cache.get(self.active_conversations_key, default={})
            active_conversations.pop(conversation_id, None)
            
            return await self.redis_cache.set(
                self.active_conversations_key, 
                active_conversations, 
                self.conversation_ttl
            )
        except Exception:
            return False

    async def _get_child_active_conversations(self, child_id: UUID) -> List[str]:
        """استرجاع قائمة المحادthات النشطة للطفل"""
        try:
            active_conversations = await self.redis_cache.get(self.active_conversations_key, default={})
            
            child_conversations = []
            for conv_id, conv_info in active_conversations.items():
                if conv_info.get("child_id") == str(child_id):
                    child_conversations.append(conv_id)
            
            return child_conversations
        except Exception:
            return []

    async def _add_to_conversation_messages(self, conversation_id: UUID, message_id: str) -> bool:
        """إضافة رسالة إلى قائمة رسائل المحادثة"""
        try:
            messages_list_key = f"{self.message_key_prefix}:list:{conversation_id}"
            message_list = await self.redis_cache.get(messages_list_key, default=[])
            
            message_list.append(message_id)
            
            # الحفاظ على الحد الأقصى للرسائل
            if len(message_list) > self.max_messages_per_conversation:
                message_list = message_list[-self.max_messages_per_conversation:]
            
            return await self.redis_cache.set(messages_list_key, message_list, self.message_ttl)
        except Exception:
            return False

    async def _update_conversation_context(
        self, 
        conversation_id: UUID, 
        message_data: MessageCacheData
    ) -> bool:
        """تحديث سياق المحادثة بناءً على الرسالة الجديدة"""
        try:
            context_key = f"{self.context_key_prefix}:{conversation_id}"
            current_context = await self.redis_cache.get(context_key)
            
            if current_context:
                context = ConversationContext(**current_context)
            else:
                context = ConversationContext(
                    conversation_id=str(conversation_id),
                    recent_messages=[],
                    topics=[],
                    sentiment="neutral",
                    engagement_level="medium",
                    safety_status="safe",
                    last_updated=datetime.now().isoformat()
                )
            
            # إضافة الرسالة الجديدة
            context.recent_messages.append(message_data)
            context.message_count += 1
            context.last_updated = datetime.now().isoformat()
            
            # الحفاظ على حجم السياق
            if len(context.recent_messages) > self.max_context_messages:
                context.recent_messages = context.recent_messages[-self.max_context_messages:]
            
            # تحديث التحليل
            context.topics = await self._extract_topics(context.recent_messages)
            context.sentiment = await self._analyze_sentiment(context.recent_messages)
            context.engagement_level = await self._calculate_engagement_level(context.recent_messages)
            context.safety_status = "flagged" if message_data.is_flagged else "safe"
            
            return await self.redis_cache.set(context_key, asdict(context), self.context_ttl)
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to update conversation context: {e}")
            return False

    async def _generate_conversation_context(
        self, 
        conversation_id: UUID, 
        context_size: int
    ) -> Optional[ConversationContext]:
        """إنشاء سياق جديد للمحادثة"""
        try:
            messages = await self.get_conversation_messages(conversation_id, limit=context_size)
            
            if not messages:
                return None
            
            context = ConversationContext(
                conversation_id=str(conversation_id),
                recent_messages=messages,
                topics=await self._extract_topics(messages),
                sentiment=await self._analyze_sentiment(messages),
                engagement_level=await self._calculate_engagement_level(messages),
                safety_status="safe" if not any(m.is_flagged for m in messages) else "flagged",
                last_updated=datetime.now().isoformat(),
                message_count=len(messages)
            )
            
            # تخزين السياق
            context_key = f"{self.context_key_prefix}:{conversation_id}"
            await self.redis_cache.set(context_key, asdict(context), self.context_ttl)
            
            return context
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to generate conversation context: {e}")
            return None

    async def _track_child_usage(self, child_id: UUID) -> bool:
        """تتبع استخدام الطفل للخدمة"""
        try:
            usage_key = f"{self.child_usage_prefix}:{child_id}"
            usage_data = await self.redis_cache.get(usage_key, default={
                "daily_conversations": 0,
                "total_messages": 0,
                "last_activity": None,
                "week_start": datetime.now().strftime("%Y-%W")
            })
            
            # تحديث الإحصائيات
            current_week = datetime.now().strftime("%Y-%W")
            if usage_data.get("week_start") != current_week:
                # أسبوع جديد - إعادة تعيين
                usage_data = {
                    "daily_conversations": 1,
                    "total_messages": 0,
                    "last_activity": datetime.now().isoformat(),
                    "week_start": current_week
                }
            else:
                usage_data["daily_conversations"] += 1
                usage_data["last_activity"] = datetime.now().isoformat()
            
            return await self.redis_cache.set(usage_key, usage_data, self.child_usage_ttl)
            
        except Exception:
            return False

    async def _cleanup_conversation_data(self, conversation_id: UUID) -> bool:
        """تنظيف جميع البيانات المرتبطة بالمحادثة"""
        try:
            # تنظيف قائمة الرسائل
            messages_list_key = f"{self.message_key_prefix}:list:{conversation_id}"
            message_ids = await self.redis_cache.get(messages_list_key, default=[])
            
            # حذف الرسائل
            for message_id in message_ids:
                message_key = f"{self.message_key_prefix}:{conversation_id}:{message_id}"
                await self.redis_cache.delete(message_key)
            
            # حذف قائمة الرسائل
            await self.redis_cache.delete(messages_list_key)
            
            # حذف السياق
            context_key = f"{self.context_key_prefix}:{conversation_id}"
            await self.redis_cache.delete(context_key)
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to cleanup conversation data: {e}")
            return False

    def _calculate_engagement_score(self, conversation: Conversation) -> float:
        """حساب نقاط التفاعل للمحادثة"""
        try:
            base_score = min(conversation.message_count * 0.1, 1.0)
            
            # مكافآت إضافية
            if conversation.interaction_type == "story":
                base_score *= 1.2
            elif conversation.interaction_type == "learning":
                base_score *= 1.1
            
            return min(base_score, 1.0)
        except Exception:
            return 0.0

    async def _calculate_message_safety_score(self, content: str) -> float:
        """حساب نقاط السلامة للرسالة"""
        try:
            # تحليل بسيط للسلامة (يمكن تطويره أكثر)
            unsafe_keywords = [
                "personal information", "address", "phone", "email",
                "scared", "uncomfortable", "inappropriate"
            ]
            
            content_lower = content.lower()
            safety_violations = sum(1 for keyword in unsafe_keywords if keyword in content_lower)
            
            # نقاط السلامة من 0 إلى 1
            safety_score = max(0.0, 1.0 - (safety_violations * 0.3))
            
            return safety_score
        except Exception:
            return 1.0  # افتراض السلامة في حالة الخطأ

    async def _extract_topics(self, messages: List[MessageCacheData]) -> List[str]:
        """استخراج المواضيع من الرسائل"""
        try:
            # تحليل بسيط للمواضيع
            common_topics = {
                "animals": ["dog", "cat", "lion", "elephant", "animal"],
                "science": ["space", "star", "planet", "science", "experiment"],
                "games": ["play", "game", "fun", "toy"],
                "stories": ["story", "tale", "adventure", "character"],
                "learning": ["learn", "teach", "school", "homework"]
            }
            
            found_topics = []
            for message in messages:
                content_lower = message.content.lower()
                for topic, keywords in common_topics.items():
                    if any(keyword in content_lower for keyword in keywords):
                        if topic not in found_topics:
                            found_topics.append(topic)
            
            return found_topics
        except Exception:
            return []

    async def _analyze_sentiment(self, messages: List[MessageCacheData]) -> str:
        """تحليل المشاعر في الرسائل"""
        try:
            positive_words = ["happy", "good", "great", "love", "fun", "excited"]
            negative_words = ["sad", "bad", "angry", "scared", "worried"]
            
            positive_count = 0
            negative_count = 0
            
            for message in messages:
                content_lower = message.content.lower()
                positive_count += sum(1 for word in positive_words if word in content_lower)
                negative_count += sum(1 for word in negative_words if word in content_lower)
            
            if positive_count > negative_count:
                return "positive"
            elif negative_count > positive_count:
                return "negative"
            else:
                return "neutral"
        except Exception:
            return "neutral"

    async def _calculate_engagement_level(self, messages: List[MessageCacheData]) -> str:
        """حساب مستوى التفاعل"""
        try:
            if len(messages) >= 10:
                return "high"
            elif len(messages) >= 5:
                return "medium"
            else:
                return "low"
        except Exception:
            return "medium"

    # =========================================================================
    # الإحصائيات والمراقبة
    # =========================================================================

    async def get_cache_statistics(self) -> Dict[str, Any]:
        """الحصول على إحصائيات الكاش والأداء"""
        try:
            active_conversations = await self.redis_cache.get(self.active_conversations_key, default={})
            
            # إحصائيات الأداء
            hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0
            
            return {
                "performance_metrics": {
                    "total_requests": self.total_requests,
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses,
                    "hit_rate_percentage": hit_rate
                },
                "cache_content": {
                    "active_conversations": len(active_conversations),
                    "conversations_by_type": await self._get_conversation_type_distribution()
                },
                "configuration": {
                    "conversation_ttl": self.conversation_ttl,
                    "message_ttl": self.message_ttl,
                    "max_conversations_per_child": self.max_conversations_per_child,
                    "max_messages_per_conversation": self.max_messages_per_conversation
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}

    async def _get_conversation_type_distribution(self) -> Dict[str, int]:
        """توزيع أنواع المحادثات"""
        try:
            active_conversations = await self.redis_cache.get(self.active_conversations_key, default={})
            distribution = {}
            
            for conv_id in active_conversations.keys():
                conv_data = await self.get_conversation(UUID(conv_id))
                if conv_data:
                    interaction_type = conv_data.interaction_type
                    distribution[interaction_type] = distribution.get(interaction_type, 0) + 1
            
            return distribution
        except Exception:
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """فحص صحة خدمة التخزين المؤقت"""
        try:
            # فحص اتصال Redis
            redis_health = await self.redis_cache.health_check()
            
            # فحص العمليات الأساسية
            test_conversation_id = UUID("12345678-1234-5678-9012-123456789012")
            test_data = ConversationCacheData(
                conversation_id=str(test_conversation_id),
                child_id="test-child",
                status="active",
                interaction_type="chat",
                message_count=1,
                last_message_at=datetime.now().isoformat(),
                context_summary="test",
                metadata={},
                cached_at=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(seconds=60)).isoformat()
            )
            
            # اختبار التخزين والاسترجاع
            cache_key = f"{self.conversation_key_prefix}:{test_conversation_id}"
            set_success = await self.redis_cache.set(cache_key, asdict(test_data), 60)
            
            if set_success:
                retrieved_data = await self.redis_cache.get(cache_key)
                get_success = retrieved_data is not None
                
                # تنظيف البيانات التجريبية
                await self.redis_cache.delete(cache_key)
            else:
                get_success = False
            
            return {
                "status": "healthy" if redis_health.get("status") == "healthy" and set_success and get_success else "unhealthy",
                "redis_health": redis_health,
                "cache_operations": {
                    "set_test": set_success,
                    "get_test": get_success
                },
                "statistics": await self.get_cache_statistics(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """إغلاق الاتصالات وتنظيف الموارد"""
        try:
            if self.redis_cache:
                await self.redis_cache.close()
            
            if self.logger:
                self.logger.info("ConversationCacheService closed successfully")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error closing ConversationCacheService: {e}")


# =========================================================================
# Context Manager للاستخدام الآمن
# =========================================================================

@asynccontextmanager
async def conversation_cache_context(redis_cache=None, logger=None):
    """Context manager للاستخدام الآمن لخدمة التخزين المؤقت"""
    cache_service = ConversationCacheService(redis_cache, logger)
    try:
        yield cache_service
    finally:
        await cache_service.close()


# =========================================================================
# Factory Function
# =========================================================================

async def create_conversation_cache_service(
    redis_cache: ProductionRedisCache = None,
    logger = None
) -> ConversationCacheService:
    """إنشاء وتكوين خدمة التخزين المؤقت للمحادثات
    
    Args:
        redis_cache: خدمة Redis Cache
        logger: أداة التسجيل
        
    Returns:
        خدمة التخزين المؤقت مُكونة ومجهزة
    """
    return ConversationCacheService(redis_cache, logger)


if __name__ == "__main__":
    import asyncio
    
    async def test_conversation_cache():
        """مثال على الاستخدام والاختبار"""
        async with conversation_cache_context() as cache_service:
            # فحص الصحة
            health = await cache_service.health_check()
            print("Health Check:", health)
            
            # اختبار العمليات الأساسية
            from src.core.entities import Conversation
            from uuid import uuid4
            
            # إنشاء محادثة تجريبية
            test_conversation = Conversation(
                id=uuid4(),
                child_id=uuid4(),
                status="active",
                interaction_type="chat",
                message_count=5,
                context_summary="Test conversation",
                metadata={"test": True}
            )
            
            # تخزين واسترجاع
            cache_success = await cache_service.cache_conversation(test_conversation)
            print(f"Cache Success: {cache_success}")
            
            if cache_success:
                retrieved = await cache_service.get_conversation(test_conversation.id)
                print(f"Retrieved: {retrieved is not None}")
                
                # الإحصائيات
                stats = await cache_service.get_cache_statistics()
                print("Statistics:", stats)
    
    # تشغيل الاختبار
    asyncio.run(test_conversation_cache())
