"""
🗺️ AI TEDDY BEAR - خريطة رحلة المستخدم
==========================================
نظام شامل لإدارة تجربة المستخدم من البداية للنهاية
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class JourneyStage(Enum):
    """مراحل رحلة المستخدم"""

    APP_DOWNLOAD = "app_download"
    PARENT_REGISTRATION = "parent_registration"
    CHILD_PROFILE_CREATION = "child_profile_creation"
    DEVICE_PAIRING = "device_pairing"
    FIRST_INTERACTION = "first_interaction"
    REGULAR_USAGE = "regular_usage"
    ISSUE_RESOLUTION = "issue_resolution"
    ACCOUNT_MANAGEMENT = "account_management"


class UserType(Enum):
    """نوع المستخدم"""

    PARENT = "parent"
    CHILD = "child"
    ADMIN = "admin"


@dataclass
class JourneyStep:
    """خطوة في رحلة المستخدم"""

    id: str
    stage: JourneyStage
    title: str
    description: str
    expected_duration: int  # بالدقائق
    difficulty_level: int  # 1-5 (1=سهل جداً, 5=معقد)
    user_type: UserType
    prerequisites: List[str]
    success_criteria: List[str]
    common_issues: List[str]
    help_resources: List[str]


@dataclass
class UserJourneyState:
    """حالة رحلة المستخدم الحالية"""

    user_id: str
    current_stage: JourneyStage
    current_step: str
    started_at: datetime
    last_activity: datetime
    completed_steps: List[str]
    failed_attempts: Dict[str, int]
    help_requests: List[str]
    satisfaction_score: Optional[int]  # 1-10


class UserJourneyManager:
    """مدير رحلة المستخدم"""

    def __init__(self):
        self.journey_map = self._create_journey_map()
        self.active_journeys: Dict[str, UserJourneyState] = {}

    def _create_journey_map(self) -> Dict[str, JourneyStep]:
        """إنشاء خريطة رحلة المستخدم الكاملة"""
        steps = {
            # 1. تحميل التطبيق
            "download_app": JourneyStep(
                id="download_app",
                stage=JourneyStage.APP_DOWNLOAD,
                title="تحميل تطبيق AI Teddy Bear",
                description="تحميل وتثبيت التطبيق من متجر التطبيقات",
                expected_duration=5,
                difficulty_level=1,
                user_type=UserType.PARENT,
                prerequisites=[],
                success_criteria=[
                    "تم تحميل التطبيق بنجاح",
                    "تم فتح التطبيق لأول مرة",
                    "ظهور شاشة الترحيب",
                ],
                common_issues=[
                    "مساحة تخزين غير كافية",
                    "مشاكل في الاتصال بالإنترنت",
                    "التطبيق غير متوافق مع الجهاز",
                ],
                help_resources=[
                    "دليل التحميل والتثبيت",
                    "متطلبات النظام",
                    "حل مشاكل التحميل",
                ],
            ),
            # 2. تسجيل ولي الأمر
            "parent_registration": JourneyStep(
                id="parent_registration",
                stage=JourneyStage.PARENT_REGISTRATION,
                title="تسجيل حساب ولي الأمر",
                description="إنشاء حساب آمن لولي الأمر مع التحقق من الهوية",
                expected_duration=10,
                difficulty_level=2,
                user_type=UserType.PARENT,
                prerequisites=["download_app"],
                success_criteria=[
                    "تم إدخال بيانات صحيحة",
                    "تم التحقق من البريد الإلكتروني",
                    "تم قبول شروط الاستخدام",
                    "تم إنشاء الحساب بنجاح",
                ],
                common_issues=[
                    "بريد إلكتروني مستخدم مسبقاً",
                    "كلمة مرور ضعيفة",
                    "عدم وصول رسالة التحقق",
                    "مشاكل في التحقق من الهوية",
                ],
                help_resources=[
                    "دليل إنشاء حساب آمن",
                    "نصائح كلمة المرور القوية",
                    "حل مشاكل التحقق من البريد",
                ],
            ),
            # 3. إنشاء ملف الطفل
            "create_child_profile": JourneyStep(
                id="create_child_profile",
                stage=JourneyStage.CHILD_PROFILE_CREATION,
                title="إنشاء ملف الطفل",
                description="إضافة معلومات الطفل وتخصيص تجربته",
                expected_duration=15,
                difficulty_level=2,
                user_type=UserType.PARENT,
                prerequisites=["parent_registration"],
                success_criteria=[
                    "تم إدخال اسم الطفل وعمره",
                    "تم اختيار التفضيلات المناسبة",
                    "تم ضبط إعدادات الأمان",
                    "تم حفظ الملف الشخصي",
                ],
                common_issues=[
                    "عمر الطفل خارج النطاق المسموح (3-13)",
                    "عدم فهم إعدادات الأمان",
                    "مشاكل في حفظ البيانات",
                ],
                help_resources=[
                    "دليل إعدادات الأمان للأطفال",
                    "نصائح التخصيص حسب العمر",
                    "شرح ميزات الحماية",
                ],
            ),
            # 4. ربط الجهاز
            "device_pairing": JourneyStep(
                id="device_pairing",
                stage=JourneyStage.DEVICE_PAIRING,
                title="ربط جهاز AI Teddy Bear",
                description="ربط جهاز ESP32 بحساب الطفل",
                expected_duration=20,
                difficulty_level=4,
                user_type=UserType.PARENT,
                prerequisites=["create_child_profile"],
                success_criteria=[
                    "تم توصيل الجهاز بالواي فاي",
                    "تم مسح QR code بنجاح",
                    "تم التحقق من اتصال الجهاز",
                    "تم ربط الجهاز بملف الطفل",
                ],
                common_issues=[
                    "مشاكل في الاتصال بالواي فاي",
                    "QR code غير واضح أو تالف",
                    "الجهاز مربوط مسبقاً",
                    "مشاكل في الشبكة المحلية",
                ],
                help_resources=[
                    "دليل إعداد الواي فاي",
                    "فيديو ربط الجهاز",
                    "حل مشاكل الاتصال",
                    "دليل استكشاف الأخطاء",
                ],
            ),
            # 5. أول تفاعل
            "first_interaction": JourneyStep(
                id="first_interaction",
                stage=JourneyStage.FIRST_INTERACTION,
                title="أول تفاعل صوتي",
                description="اختبار الصوت وأول محادثة مع الطفل",
                expected_duration=10,
                difficulty_level=2,
                user_type=UserType.CHILD,
                prerequisites=["device_pairing"],
                success_criteria=[
                    "تم اختبار المايكروفون",
                    "تم اختبار السماعة",
                    "نجح الطفل في التحدث مع AI Teddy",
                    "تم تلقي رد مناسب وآمن",
                ],
                common_issues=[
                    "مشاكل في جودة الصوت",
                    "عدم فهم صوت الطفل",
                    "تأخير في الاستجابة",
                    "خجل الطفل من التحدث",
                ],
                help_resources=[
                    "دليل ضبط الصوت",
                    "نصائح لتشجيع الطفل",
                    "أمثلة على المحادثات الأولى",
                ],
            ),
            # 6. الاستخدام المنتظم
            "regular_usage": JourneyStep(
                id="regular_usage",
                stage=JourneyStage.REGULAR_USAGE,
                title="الاستخدام اليومي",
                description="استخدام منتظم وآمن للجهاز",
                expected_duration=0,  # مستمر
                difficulty_level=1,
                user_type=UserType.CHILD,
                prerequisites=["first_interaction"],
                success_criteria=[
                    "تفاعل يومي منتظم",
                    "محادثات آمنة ومفيدة",
                    "عدم وجود مشاكل تقنية",
                    "رضا الطفل والوالد",
                ],
                common_issues=[
                    "تكرار نفس الأسئلة",
                    "انقطاع الاتصال المؤقت",
                    "بطء في الاستجابة",
                    "محتوى غير مناسب",
                ],
                help_resources=[
                    "دليل الاستخدام اليومي",
                    "أفكار للمحادثات",
                    "مراقبة أداء الجهاز",
                ],
            ),
            # 7. حل المشاكل
            "issue_resolution": JourneyStep(
                id="issue_resolution",
                stage=JourneyStage.ISSUE_RESOLUTION,
                title="حل المشاكل التقنية",
                description="التعامل مع المشاكل والأخطاء",
                expected_duration=30,
                difficulty_level=3,
                user_type=UserType.PARENT,
                prerequisites=["regular_usage"],
                success_criteria=[
                    "تم تحديد المشكلة بدقة",
                    "تم تطبيق الحل المناسب",
                    "عودة الجهاز للعمل الطبيعي",
                    "منع تكرار المشكلة",
                ],
                common_issues=[
                    "انقطاع الإنترنت المطول",
                    "مشاكل في التحديثات",
                    "أخطاء في النظام",
                    "مشاكل في الأجهزة",
                ],
                help_resources=[
                    "دليل استكشاف الأخطاء",
                    "قاعدة بيانات المشاكل الشائعة",
                    "التواصل مع الدعم الفني",
                    "فيديوهات الإصلاح",
                ],
            ),
            # 8. إدارة الحساب
            "account_management": JourneyStep(
                id="account_management",
                stage=JourneyStage.ACCOUNT_MANAGEMENT,
                title="إدارة الحساب والبيانات",
                description="تعديل الإعدادات وإدارة البيانات",
                expected_duration=15,
                difficulty_level=2,
                user_type=UserType.PARENT,
                prerequisites=["parent_registration"],
                success_criteria=[
                    "تم الوصول لإعدادات الحساب",
                    "تم تعديل البيانات بنجاح",
                    "تم حفظ التغييرات",
                    "تم التأكيد على الإجراءات الحساسة",
                ],
                common_issues=[
                    "نسيان كلمة المرور",
                    "صعوبة في الوصول للإعدادات",
                    "عدم فهم خيارات الحذف",
                    "مخاوف من فقدان البيانات",
                ],
                help_resources=[
                    "دليل إدارة الحساب",
                    "شرح سياسة البيانات",
                    "خطوات الحذف الآمن",
                    "استرداد كلمة المرور",
                ],
            ),
        }

        return steps

    async def start_journey(
        self, user_id: str, user_type: UserType
    ) -> UserJourneyState:
        """بدء رحلة مستخدم جديد"""
        journey_state = UserJourneyState(
            user_id=user_id,
            current_stage=JourneyStage.APP_DOWNLOAD,
            current_step="download_app",
            started_at=datetime.now(),
            last_activity=datetime.now(),
            completed_steps=[],
            failed_attempts={},
            help_requests=[],
            satisfaction_score=None,
        )

        self.active_journeys[user_id] = journey_state
        logger.info(f"Started journey for user {user_id}")

        return journey_state

    async def complete_step(
        self, user_id: str, step_id: str, success: bool = True
    ) -> bool:
        """تسجيل إكمال خطوة"""
        if user_id not in self.active_journeys:
            logger.error(f"No active journey for user {user_id}")
            return False

        journey = self.active_journeys[user_id]
        journey.last_activity = datetime.now()

        if success:
            journey.completed_steps.append(step_id)
            logger.info(f"User {user_id} completed step {step_id}")

            # الانتقال للخطوة التالية
            next_step = self._get_next_step(step_id)
            if next_step:
                journey.current_step = next_step.id
                journey.current_stage = next_step.stage
        else:
            # تسجيل المحاولة الفاشلة
            if step_id not in journey.failed_attempts:
                journey.failed_attempts[step_id] = 0
            journey.failed_attempts[step_id] += 1

            logger.warning(
                f"User {user_id} failed step {step_id} (attempt {journey.failed_attempts[step_id]})"
            )

        return True

    def _get_next_step(self, current_step_id: str) -> Optional[JourneyStep]:
        """الحصول على الخطوة التالية"""
        step_order = [
            "download_app",
            "parent_registration",
            "create_child_profile",
            "device_pairing",
            "first_interaction",
            "regular_usage",
        ]

        try:
            current_index = step_order.index(current_step_id)
            if current_index < len(step_order) - 1:
                next_step_id = step_order[current_index + 1]
                return self.journey_map[next_step_id]
        except (ValueError, IndexError):
            pass

        return None

    async def request_help(
        self, user_id: str, step_id: str, issue_type: str
    ) -> Dict[str, Any]:
        """طلب المساعدة في خطوة معينة"""
        if user_id not in self.active_journeys:
            return {"error": "No active journey found"}

        journey = self.active_journeys[user_id]
        journey.help_requests.append(f"{step_id}:{issue_type}")

        step = self.journey_map.get(step_id)
        if not step:
            return {"error": "Step not found"}

        # تحديد المساعدة المناسبة
        help_response = {
            "step": step.title,
            "issue": issue_type,
            "solutions": [],
            "resources": step.help_resources,
            "contact_support": False,
        }

        # إذا فشل المستخدم عدة مرات، اقترح التواصل مع الدعم
        if journey.failed_attempts.get(step_id, 0) >= 3:
            help_response["contact_support"] = True
            help_response["solutions"].append(
                "يبدو أنك تواجه صعوبة في هذه الخطوة. ننصح بالتواصل مع فريق الدعم للمساعدة."
            )

        return help_response

    async def get_progress_summary(self, user_id: str) -> Dict[str, Any]:
        """الحصول على ملخص تقدم المستخدم"""
        if user_id not in self.active_journeys:
            return {"error": "No active journey found"}

        journey = self.active_journeys[user_id]
        total_steps = len(self.journey_map)
        completed_steps = len(journey.completed_steps)

        return {
            "user_id": user_id,
            "current_stage": journey.current_stage.value,
            "current_step": journey.current_step,
            "progress_percentage": (completed_steps / total_steps) * 100,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "failed_attempts": journey.failed_attempts,
            "help_requests": len(journey.help_requests),
            "journey_duration": (datetime.now() - journey.started_at).total_seconds()
            / 60,  # بالدقائق
            "satisfaction_score": journey.satisfaction_score,
        }

    async def update_satisfaction(self, user_id: str, score: int) -> bool:
        """تحديث درجة رضا المستخدم"""
        if user_id not in self.active_journeys:
            return False

        if 1 <= score <= 10:
            self.active_journeys[user_id].satisfaction_score = score
            logger.info(f"User {user_id} satisfaction score: {score}/10")
            return True

        return False
