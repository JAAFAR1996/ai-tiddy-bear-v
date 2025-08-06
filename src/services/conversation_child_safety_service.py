"""Advanced Conversation-Specific Child Safety Service - نظام السلامة المتقدم للمحادثات

يعتمد على ChildSafetyService العام ويوسعه بميزات متخصصة للمحادثات:
- تحليل الأنماط السلوكية في المحادثات
- كشف محاولات التلاعب والاستدراج
- تتبع تطور السلوك المشبوه عبر الوقت
- نظام إنذار مبكر للمخاطر
- تحليل السياق الذكي للمحادثات
- تكامل مع Redis Cache للأداء العالي
"""

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# الاعتماد على الخدمة العامة
from src.application.services.child_safety_service import ChildSafetyService
from src.core.entities import Message, Conversation
from src.infrastructure.caching.conversation_cache import ConversationCacheService


# =========================================================================
# Additional Enums for Conversation-Specific Safety
# =========================================================================


class ConversationThreatType(Enum):
    """أنواع التهديدات المخصصة للمحادثات"""

    GROOMING_PATTERN = "grooming_pattern"
    TRUST_BUILDING_MANIPULATION = "trust_building_manipulation"
    CONVERSATION_ESCALATION = "conversation_escalation"
    ISOLATION_ATTEMPT = "isolation_attempt"
    REPETITIVE_PROBING = "repetitive_probing"
    BOUNDARY_TESTING = "boundary_testing"
    EMOTIONAL_MANIPULATION = "emotional_manipulation"
    TIME_PRESSURE = "time_pressure"


class ConversationRiskLevel(Enum):
    """مستويات الخطر للمحادثات"""

    NORMAL = "normal"  # محادثة عادية
    MONITORING = "monitoring"  # تحتاج مراقبة
    ELEVATED = "elevated"  # خطر متزايد
    HIGH_RISK = "high_risk"  # خطر عالي
    CRITICAL = "critical"  # تدخل فوري مطلوب


@dataclass
class ConversationSafetyMetrics:
    """مقاييس السلامة للمحادثة"""

    conversation_id: str
    total_messages: int
    risk_progression_score: float  # 0-1
    trust_building_score: float  # 0-1
    isolation_attempts: int
    personal_info_requests: int
    escalation_indicators: List[str]
    last_risk_assessment: datetime
    cumulative_risk_score: float  # 0-100


@dataclass
class ConversationAlert:
    """تنبيه مخصص للمحادثات"""

    alert_id: str
    conversation_id: str
    child_id: str
    threat_type: ConversationThreatType
    severity: ConversationRiskLevel
    description: str
    evidence_patterns: List[str]
    context_messages: List[str]  # آخر رسائل للسياق
    recommended_action: str
    timestamp: datetime
    requires_immediate_action: bool = False


# =========================================================================
# Main Conversation Safety Service
# =========================================================================


class ConversationChildSafetyService:
    """خدمة السلامة المتخصصة للمحادثات

    تعتمد على ChildSafetyService العام وتضيف:
    - تحليل الأنماط السلوكية المعقدة
    - كشف محاولات الاستدراج والتلاعب
    - تتبع تطور المخاطر عبر الوقت
    - نظام إنذار مبكر متقدم
    """

    def __init__(
        self,
        base_safety_service: ChildSafetyService,
        conversation_cache: Optional[ConversationCacheService] = None,
        logger: Optional[logging.Logger] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """تهيئة خدمة السلامة المتخصصة للمحادثات

        Args:
            base_safety_service: الخدمة العامة للسلامة
            conversation_cache: خدمة الكاش للمحادثات
            logger: أداة التسجيل
            config: إعدادات مخصصة
        """
        self.base_safety = base_safety_service
        self.conversation_cache = conversation_cache
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or {}

        # إعدادات المحادثات المتخصصة
        self.risk_threshold_warning = 0.6
        self.risk_threshold_critical = 0.8
        self.max_personal_info_attempts = 3
        self.escalation_window_minutes = 30
        self.trust_building_indicators_threshold = 5

        # ذاكرة مؤقتة للتحليلات
        self._conversation_metrics: Dict[str, ConversationSafetyMetrics] = {}
        self._conversation_alerts: List[ConversationAlert] = []
        self._recent_patterns: Dict[str, List[Dict]] = {}  # patterns per conversation

        # أنماط الاستدراج والتلاعب
        self._initialize_conversation_patterns()

        # إحصائيات متخصصة
        self.conversations_analyzed = 0
        self.high_risk_conversations_detected = 0
        self.grooming_attempts_blocked = 0

        self.logger.info("ConversationChildSafetyService initialized successfully")

    def _initialize_conversation_patterns(self):
        """تهيئة أنماط التهديدات المخصصة للمحادثات"""

        # أنماط الاستدراج (Grooming)
        self.grooming_patterns = [
            r"\b(you\'re so mature|mature for your age|special|different from others)\b",
            r"\b(our secret|don\'t tell|between us|keep this private)\b",
            r"\b(trust me|you can trust me|i understand you|nobody understands)\b",
            r"\b(meet|see you|visit|come over|in person|real life)\b",
            r"\b(parents don\'t understand|they wouldn\'t get it|adults don\'t know)\b",
        ]

        # أنماط بناء الثقة المشبوهة
        self.trust_building_patterns = [
            r"\b(you\'re my favorite|you\'re special to me|we have a connection)\b",
            r"\b(i care about you|i love you|you mean a lot to me)\b",
            r"\b(we\'re friends|best friends|close friends|special friends)\b",
            r"\b(only you understand|you get me|we think alike)\b",
        ]

        # أنماط محاولات العزل
        self.isolation_patterns = [
            r"\b(don\'t tell anyone|keep it secret|just between us)\b",
            r"\b(they wouldn\'t understand|they\'d be jealous|they\'d be mad)\b",
            r"\b(our special relationship|what we have is special)\b",
        ]

        # أنماط التصعيد العاطفي
        self.escalation_patterns = [
            r"\b(i miss you|can\'t wait to see you|thinking about you)\b",
            r"\b(send me|show me|picture|photo|video)\b",
            r"\b(what are you wearing|describe yourself|how do you look)\b",
        ]

        # أنماط الضغط الزمني
        self.pressure_patterns = [
            r"\b(right now|quickly|hurry|before someone comes|limited time)\b",
            r"\b(delete this|clear history|erase|don\'t save)\b",
        ]

    # =========================================================================
    # التحليل المتقدم للمحادثات
    # =========================================================================

    async def analyze_conversation_safety(
        self,
        message: Message,
        conversation: Conversation,
        child_age: int,
        context_messages: Optional[List[Message]] = None,
    ) -> Tuple[bool, ConversationRiskLevel, List[ConversationAlert]]:
        """التحليل الشامل لسلامة المحادثة

        Args:
            message: الرسالة الحالية
            conversation: المحادثة الكاملة
            child_age: عمر الطفل
            context_messages: رسائل السياق

        Returns:
            (is_safe, risk_level, alerts)
        """
        self.conversations_analyzed += 1

        # 1. التحليل الأساسي باستخدام الخدمة العامة
        base_validation = await self.base_safety.validate_content(
            message.content, child_age
        )

        # 2. التحليل المتخصص للمحادثات
        conversation_metrics = await self._analyze_conversation_patterns(
            message, conversation, context_messages or []
        )

        # 3. تحديث مقاييس المحادثة
        await self._update_conversation_metrics(conversation.id, conversation_metrics)

        # 4. تحليل تطور المخاطر
        risk_progression = await self._analyze_risk_progression(conversation.id)

        # 5. تحديد مستوى المخاطر الإجمالي
        overall_risk_level = self._calculate_overall_risk_level(
            base_validation, conversation_metrics, risk_progression
        )

        # 6. توليد التنبيهات إذا لزم الأمر
        alerts = await self._generate_conversation_alerts(
            message, conversation, overall_risk_level, conversation_metrics
        )

        # 7. تسجيل النتائج
        if overall_risk_level in [
            ConversationRiskLevel.HIGH_RISK,
            ConversationRiskLevel.CRITICAL,
        ]:
            self.high_risk_conversations_detected += 1

            if any(
                alert.threat_type == ConversationThreatType.GROOMING_PATTERN
                for alert in alerts
            ):
                self.grooming_attempts_blocked += 1

        is_safe = overall_risk_level in [
            ConversationRiskLevel.NORMAL,
            ConversationRiskLevel.MONITORING,
        ]

        return is_safe, overall_risk_level, alerts

    async def _analyze_conversation_patterns(
        self,
        message: Message,
        conversation: Conversation,
        context_messages: List[Message],
    ) -> Dict[str, Any]:
        """تحليل الأنماط المتخصصة في المحادثة"""
        content_lower = message.content.lower()

        analysis_result = {
            "grooming_indicators": 0,
            "trust_building_score": 0.0,
            "isolation_attempts": 0,
            "escalation_score": 0.0,
            "pressure_indicators": 0,
            "boundary_testing": 0,
            "detected_patterns": [],
        }

        # تحليل أنماط الاستدراج
        for pattern in self.grooming_patterns:
            import re

            if re.search(pattern, content_lower, re.IGNORECASE):
                analysis_result["grooming_indicators"] += 1
                analysis_result["detected_patterns"].append(f"grooming: {pattern}")

        # تحليل بناء الثقة المشبوه
        trust_indicators = 0
        for pattern in self.trust_building_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                trust_indicators += 1
                analysis_result["detected_patterns"].append(
                    f"trust_building: {pattern}"
                )

        analysis_result["trust_building_score"] = min(trust_indicators / 5.0, 1.0)

        # تحليل محاولات العزل
        for pattern in self.isolation_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                analysis_result["isolation_attempts"] += 1
                analysis_result["detected_patterns"].append(f"isolation: {pattern}")

        # تحليل التصعيد
        escalation_indicators = 0
        for pattern in self.escalation_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                escalation_indicators += 1
                analysis_result["detected_patterns"].append(f"escalation: {pattern}")

        analysis_result["escalation_score"] = min(escalation_indicators / 3.0, 1.0)

        # تحليل الضغط الزمني
        for pattern in self.pressure_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                analysis_result["pressure_indicators"] += 1
                analysis_result["detected_patterns"].append(f"pressure: {pattern}")

        # تحليل اختبار الحدود مع السياق
        if context_messages:
            boundary_score = await self._analyze_boundary_testing(
                message, context_messages
            )
            analysis_result["boundary_testing"] = boundary_score

        return analysis_result

    async def _analyze_boundary_testing(
        self, message: Message, context_messages: List[Message]
    ) -> float:
        """تحليل محاولات اختبار حدود الطفل"""
        boundary_keywords = [
            "secret",
            "private",
            "personal",
            "don't tell",
            "just us",
            "between friends",
            "special",
        ]

        # حساب تكرار كلمات اختبار الحدود
        current_content = message.content.lower()
        current_boundary_count = sum(
            1 for keyword in boundary_keywords if keyword in current_content
        )

        # تحليل السياق - هل هناك تصاعد؟
        context_boundary_counts = []
        for msg in context_messages[-5:]:  # آخر 5 رسائل
            count = sum(
                1 for keyword in boundary_keywords if keyword in msg.content.lower()
            )
            context_boundary_counts.append(count)

        # حساب التصاعد
        if len(context_boundary_counts) >= 2:
            recent_avg = sum(context_boundary_counts[-2:]) / 2
            earlier_avg = sum(context_boundary_counts[:-2]) / max(
                len(context_boundary_counts) - 2, 1
            )
            escalation = max(0, recent_avg - earlier_avg)
        else:
            escalation = 0

        boundary_score = min((current_boundary_count + escalation) / 5.0, 1.0)
        return boundary_score

    async def _update_conversation_metrics(
        self, conversation_id: UUID, analysis_result: Dict[str, Any]
    ):
        """تحديث مقاييس السلامة للمحادثة"""
        conv_id_str = str(conversation_id)

        if conv_id_str not in self._conversation_metrics:
            # إنشاء مقاييس جديدة
            self._conversation_metrics[conv_id_str] = ConversationSafetyMetrics(
                conversation_id=conv_id_str,
                total_messages=0,
                risk_progression_score=0.0,
                trust_building_score=0.0,
                isolation_attempts=0,
                personal_info_requests=0,
                escalation_indicators=[],
                last_risk_assessment=datetime.now(),
                cumulative_risk_score=0.0,
            )

        metrics = self._conversation_metrics[conv_id_str]

        # تحديث المقاييس
        metrics.total_messages += 1
        metrics.trust_building_score = max(
            metrics.trust_building_score, analysis_result["trust_building_score"]
        )
        metrics.isolation_attempts += analysis_result["isolation_attempts"]

        # إضافة مؤشرات التصعيد
        if analysis_result["escalation_score"] > 0.5:
            timestamp = datetime.now().isoformat()
            metrics.escalation_indicators.append(f"escalation_{timestamp}")

            # الاحتفاظ بآخر 10 مؤشرات فقط
            metrics.escalation_indicators = metrics.escalation_indicators[-10:]

        # حساب نقاط المخاطر التراكمية
        risk_factors = [
            analysis_result["grooming_indicators"] * 20,
            analysis_result["trust_building_score"] * 25,
            analysis_result["isolation_attempts"] * 15,
            analysis_result["escalation_score"] * 20,
            analysis_result["pressure_indicators"] * 10,
            analysis_result["boundary_testing"] * 10,
        ]

        current_risk = sum(risk_factors)
        metrics.cumulative_risk_score = min(
            (metrics.cumulative_risk_score * 0.8) + (current_risk * 0.2), 100.0
        )

        metrics.last_risk_assessment = datetime.now()

    async def _analyze_risk_progression(
        self, conversation_id: UUID
    ) -> Dict[str, float]:
        """تحليل تطور المخاطر عبر الوقت"""
        conv_id_str = str(conversation_id)

        if conv_id_str not in self._conversation_metrics:
            return {"progression_rate": 0.0, "trend": 0.0}

        metrics = self._conversation_metrics[conv_id_str]

        # تحليل معدل التطور
        time_since_start = (
            datetime.now() - metrics.last_risk_assessment
        ).total_seconds() / 3600  # hours
        progression_rate = metrics.cumulative_risk_score / max(time_since_start, 1)

        # تحليل الاتجاه من خلال مؤشرات التصعيد
        recent_escalations = len(
            [
                indicator
                for indicator in metrics.escalation_indicators
                if datetime.fromisoformat(indicator.split("_")[1])
                > datetime.now() - timedelta(hours=2)
            ]
        )

        trend = min(recent_escalations / 5.0, 1.0)

        return {"progression_rate": min(progression_rate, 1.0), "trend": trend}

    def _calculate_overall_risk_level(
        self,
        base_validation: Dict[str, Any],
        conversation_analysis: Dict[str, Any],
        risk_progression: Dict[str, float],
    ) -> ConversationRiskLevel:
        """حساب مستوى المخاطر الإجمالي"""

        # نقاط المخاطر من التحليل الأساسي
        base_risk = 0.0 if base_validation.get("is_safe", True) else 0.5

        # نقاط المخاطر من تحليل المحادثة
        conversation_risk = (
            conversation_analysis["grooming_indicators"] * 0.3
            + conversation_analysis["trust_building_score"] * 0.25
            + conversation_analysis["isolation_attempts"] * 0.2
            + conversation_analysis["escalation_score"] * 0.15
            + conversation_analysis["pressure_indicators"] * 0.1
        ) / 5.0

        # نقاط المخاطر من التطور
        progression_risk = (
            risk_progression["progression_rate"] * 0.3 + risk_progression["trend"] * 0.7
        )

        # المخاطر الإجمالية
        total_risk = base_risk * 0.3 + conversation_risk * 0.5 + progression_risk * 0.2

        # تحديد المستوى
        if total_risk >= 0.8:
            return ConversationRiskLevel.CRITICAL
        elif total_risk >= 0.6:
            return ConversationRiskLevel.HIGH_RISK
        elif total_risk >= 0.4:
            return ConversationRiskLevel.ELEVATED
        elif total_risk >= 0.2:
            return ConversationRiskLevel.MONITORING
        else:
            return ConversationRiskLevel.NORMAL

    # =========================================================================
    # نظام التنبيهات المتقدم
    # =========================================================================

    async def _generate_conversation_alerts(
        self,
        message: Message,
        conversation: Conversation,
        risk_level: ConversationRiskLevel,
        analysis_result: Dict[str, Any],
    ) -> List[ConversationAlert]:
        """توليد تنبيهات مخصصة للمحادثات"""
        alerts = []

        # تنبيه الاستدراج
        if analysis_result["grooming_indicators"] >= 2:
            alerts.append(
                ConversationAlert(
                    alert_id=str(uuid4()),
                    conversation_id=str(conversation.id),
                    child_id=str(conversation.child_id),
                    threat_type=ConversationThreatType.GROOMING_PATTERN,
                    severity=ConversationRiskLevel.HIGH_RISK,
                    description="Multiple grooming indicators detected in conversation",
                    evidence_patterns=analysis_result["detected_patterns"],
                    context_messages=[message.content],
                    recommended_action="Immediate review and potential conversation termination",
                    timestamp=datetime.now(),
                    requires_immediate_action=True,
                )
            )

        # تنبيه بناء الثقة المشبوه
        if analysis_result["trust_building_score"] > 0.6:
            alerts.append(
                ConversationAlert(
                    alert_id=str(uuid4()),
                    conversation_id=str(conversation.id),
                    child_id=str(conversation.child_id),
                    threat_type=ConversationThreatType.TRUST_BUILDING_MANIPULATION,
                    severity=ConversationRiskLevel.ELEVATED,
                    description="Suspicious trust-building patterns detected",
                    evidence_patterns=analysis_result["detected_patterns"],
                    context_messages=[message.content],
                    recommended_action="Monitor conversation closely and educate child about online safety",
                    timestamp=datetime.now(),
                    requires_immediate_action=False,
                )
            )

        # تنبيه محاولات العزل
        if analysis_result["isolation_attempts"] > 0:
            alerts.append(
                ConversationAlert(
                    alert_id=str(uuid4()),
                    conversation_id=str(conversation.id),
                    child_id=str(conversation.child_id),
                    threat_type=ConversationThreatType.ISOLATION_ATTEMPT,
                    severity=ConversationRiskLevel.HIGH_RISK,
                    description="Attempt to isolate child from parents/guardians detected",
                    evidence_patterns=analysis_result["detected_patterns"],
                    context_messages=[message.content],
                    recommended_action="Immediate intervention recommended",
                    timestamp=datetime.now(),
                    requires_immediate_action=True,
                )
            )

        # تنبيه التصعيد
        if analysis_result["escalation_score"] > 0.7:
            alerts.append(
                ConversationAlert(
                    alert_id=str(uuid4()),
                    conversation_id=str(conversation.id),
                    child_id=str(conversation.child_id),
                    threat_type=ConversationThreatType.CONVERSATION_ESCALATION,
                    severity=ConversationRiskLevel.ELEVATED,
                    description="Conversation escalation pattern detected",
                    evidence_patterns=analysis_result["detected_patterns"],
                    context_messages=[message.content],
                    recommended_action="Review conversation history and consider limitations",
                    timestamp=datetime.now(),
                    requires_immediate_action=False,
                )
            )

        # حفظ التنبيهات
        self._conversation_alerts.extend(alerts)

        # تسجيل التنبيهات
        for alert in alerts:
            # Sanitize alert data for logging
            safe_threat_type = alert.threat_type.value.replace('\n', '').replace('\r', '')[:50]
            safe_alert_id = alert.alert_id.replace('\n', '').replace('\r', '')[:50]
            safe_conv_id = alert.conversation_id.replace('\n', '').replace('\r', '')[:50]
            self.logger.warning(
                f"Conversation safety alert: {safe_threat_type}",
                extra={
                    "alert_id": safe_alert_id,
                    "conversation_id": safe_conv_id,
                    "severity": alert.severity.value,
                    "requires_immediate_action": alert.requires_immediate_action,
                },
            )

        return alerts

    # =========================================================================
    # واجهة التكامل المبسطة
    # =========================================================================

    async def validate_conversation_message(
        self, message: Message, conversation: Conversation, child_age: int
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """واجهة مبسطة للتكامل مع خدمة المحادثات

        Returns:
            (is_safe, filtered_content, safety_details)
        """
        # الحصول على السياق من الكاش
        context_messages = []
        if self.conversation_cache:
            try:
                cached_messages = (
                    await self.conversation_cache.get_conversation_messages(
                        conversation.id, limit=10
                    )
                )
                context_messages = [
                    Message(
                        id=UUID(m.message_id),
                        conversation_id=UUID(m.conversation_id),
                        message_type=m.message_type,
                        content=m.content,
                        sender_id=UUID(m.sender_id) if m.sender_id else None,
                        timestamp=datetime.fromisoformat(m.timestamp),
                        metadata=m.metadata,
                    )
                    for m in cached_messages
                ]
            except Exception as e:
                self.logger.warning(f"Failed to get conversation context: {e}")

        # التحليل الشامل
        is_safe, risk_level, alerts = await self.analyze_conversation_safety(
            message, conversation, child_age, context_messages
        )

        # تصفية المحتوى إذا لزم الأمر
        filtered_content = None
        if not is_safe:
            filtered_content = await self.base_safety.filter_content(message.content)

        # تفاصيل السلامة
        safety_details = {
            "is_safe": is_safe,
            "risk_level": risk_level.value,
            "alerts_count": len(alerts),
            "immediate_action_required": any(
                alert.requires_immediate_action for alert in alerts
            ),
            "conversation_metrics": self._conversation_metrics.get(
                str(conversation.id)
            ),
            "analysis_timestamp": datetime.now().isoformat(),
        }

        return is_safe, filtered_content, safety_details

    # =========================================================================
    # إدارة البيانات والتقارير
    # =========================================================================

    async def get_conversation_safety_report(
        self, conversation_id: UUID
    ) -> Dict[str, Any]:
        """تقرير السلامة الشامل للمحادثة"""
        conv_id_str = str(conversation_id)
        metrics = self._conversation_metrics.get(conv_id_str)

        if not metrics:
            return {"error": "No safety data found for conversation"}

        # التنبيهات المرتبطة بالمحادثة
        conversation_alerts = [
            asdict(alert)
            for alert in self._conversation_alerts
            if alert.conversation_id == conv_id_str
        ]

        # تحليل الاتجاهات
        risk_progression = await self._analyze_risk_progression(conversation_id)

        return {
            "conversation_id": conv_id_str,
            "metrics": asdict(metrics),
            "alerts": conversation_alerts,
            "risk_progression": risk_progression,
            "recommendations": self._generate_safety_recommendations(
                metrics, conversation_alerts
            ),
            "overall_assessment": self._get_overall_assessment(metrics),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_safety_recommendations(
        self, metrics: ConversationSafetyMetrics, alerts: List[Dict[str, Any]]
    ) -> List[str]:
        """توليد توصيات السلامة"""
        recommendations = []

        if metrics.cumulative_risk_score > 70:
            recommendations.append("Consider immediate conversation termination")
            recommendations.append("Review child's online activities closely")
        elif metrics.cumulative_risk_score > 40:
            recommendations.append("Increase monitoring of this conversation")
            recommendations.append("Discuss online safety with child")

        if metrics.isolation_attempts > 0:
            recommendations.append("Educate child about manipulation tactics")
            recommendations.append("Ensure child knows they can talk to trusted adults")

        if any(alert["requires_immediate_action"] for alert in alerts):
            recommendations.append("Seek immediate professional guidance")

        if len(alerts) > 5:
            recommendations.append("Consider limiting unsupervised online interactions")

        return recommendations

    def _get_overall_assessment(self, metrics: ConversationSafetyMetrics) -> str:
        """تقييم عام لحالة السلامة"""
        if metrics.cumulative_risk_score >= 80:
            return "CRITICAL - Immediate intervention required"
        elif metrics.cumulative_risk_score >= 60:
            return "HIGH RISK - Close monitoring needed"
        elif metrics.cumulative_risk_score >= 30:
            return "MODERATE RISK - Regular monitoring recommended"
        else:
            return "LOW RISK - Normal monitoring sufficient"

    async def cleanup_old_data(self, retention_hours: int = 72):
        """تنظيف البيانات القديمة"""
        cutoff_time = datetime.now() - timedelta(hours=retention_hours)

        # تنظيف التنبيهات القديمة
        self._conversation_alerts = [
            alert
            for alert in self._conversation_alerts
            if alert.timestamp > cutoff_time
        ]

        # تنظيف المقاييس للمحادثات غير النشطة
        inactive_conversations = []
        for conv_id, metrics in self._conversation_metrics.items():
            if metrics.last_risk_assessment < cutoff_time:
                inactive_conversations.append(conv_id)

        for conv_id in inactive_conversations:
            del self._conversation_metrics[conv_id]

        self.logger.info(
            f"Cleanup completed: {len(self._conversation_alerts)} alerts, {len(self._conversation_metrics)} active conversations"
        )

    async def get_service_statistics(self) -> Dict[str, Any]:
        """إحصائيات الخدمة"""
        return {
            "service": "ConversationChildSafetyService",
            "statistics": {
                "conversations_analyzed": self.conversations_analyzed,
                "high_risk_conversations_detected": self.high_risk_conversations_detected,
                "grooming_attempts_blocked": self.grooming_attempts_blocked,
                "active_conversation_metrics": len(self._conversation_metrics),
                "total_alerts_generated": len(self._conversation_alerts),
                "immediate_action_alerts": len(
                    [
                        alert
                        for alert in self._conversation_alerts
                        if alert.requires_immediate_action
                    ]
                ),
            },
            "health": {
                "base_safety_service": "connected",
                "conversation_cache": (
                    "connected" if self.conversation_cache else "not available"
                ),
                "last_analysis": datetime.now().isoformat(),
            },
        }


# =========================================================================
# Factory Function
# =========================================================================


def create_conversation_child_safety_service(
    base_safety_service: ChildSafetyService,
    conversation_cache: Optional[ConversationCacheService] = None,
    logger: Optional[logging.Logger] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ConversationChildSafetyService:
    """إنشاء خدمة السلامة المتخصصة للمحادثات

    Args:
        base_safety_service: الخدمة العامة للسلامة (مطلوبة)
        conversation_cache: خدمة الكاش للمحادثات
        logger: أداة التسجيل
        config: إعدادات مخصصة

    Returns:
        خدمة السلامة المتخصصة للمحادثات
    """
    return ConversationChildSafetyService(
        base_safety_service, conversation_cache, logger, config
    )


if __name__ == "__main__":
    # مثال على الاستخدام
    import asyncio

    async def demo_conversation_safety():
        # إنشاء الخدمة العامة أولاً
        base_safety = ChildSafetyService()

        # إنشاء الخدمة المتخصصة للمحادثات
        conv_safety = create_conversation_child_safety_service(base_safety)

        # محادثة تجريبية
        conversation = Conversation(
            id=uuid4(),
            child_id=uuid4(),
            status="active",
            interaction_type="chat",
            message_count=5,
        )

        # رسالة مشبوهة
        suspicious_message = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            message_type="user_input",
            content="You're so mature for your age. This will be our secret, don't tell your parents.",
            sender_id=uuid4(),
            timestamp=datetime.now(),
            metadata={},
        )

        # التحليل
        is_safe, filtered, details = await conv_safety.validate_conversation_message(
            suspicious_message, conversation, child_age=10
        )

        print(f"Is Safe: {is_safe}")
        print(f"Risk Level: {details['risk_level']}")
        print(f"Alerts: {details['alerts_count']}")
        print(f"Immediate Action Required: {details['immediate_action_required']}")

        if filtered:
            print(f"Filtered Content: {filtered}")

        # إحصائيات
        stats = await conv_safety.get_service_statistics()
        print(f"Service Statistics: {stats}")

    asyncio.run(demo_conversation_safety())
