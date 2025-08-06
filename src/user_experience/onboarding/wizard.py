"""
🧙‍♂️ AI TEDDY BEAR - معالج الإعداد الأولي
========================================
نظام شامل لإرشاد المستخدمين الجدد خطوة بخطوة
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
from src.shared.audio_types import VoiceGender, VoiceEmotion


class WizardStepType(Enum):
    """نوع خطوة المعالج"""

    WELCOME = "welcome"
    INFO_COLLECTION = "info_collection"
    DEVICE_SETUP = "device_setup"
    TESTING = "testing"
    COMPLETION = "completion"


class MediaType(Enum):
    """نوع الوسائط المساعدة"""

    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"
    AUDIO = "audio"
    PDF = "pdf"


@dataclass
class WizardStep:
    """خطوة في معالج الإعداد"""

    id: str
    type: WizardStepType
    title: str
    subtitle: str
    description: str
    instructions: List[str]
    media_files: List[Dict[str, str]]  # [{"type": "image", "url": "...", "alt": "..."}]
    input_fields: List[Dict[str, Any]]  # مطلوب إدخال من المستخدم
    validation_rules: Dict[str, Any]
    success_message: str
    error_messages: Dict[str, str]
    help_text: str
    estimated_time: int  # بالثواني
    can_skip: bool
    next_step: Optional[str]
    previous_step: Optional[str]


class OnboardingWizard:
    """معالج الإعداد الأولي"""

    def __init__(self):
        self.steps = self._create_wizard_steps()
        self.current_sessions: Dict[str, Dict[str, Any]] = {}

    def _create_wizard_steps(self) -> Dict[str, WizardStep]:
        """إنشاء خطوات المعالج"""
        return {
            # خطوة 1: الترحيب
            "welcome": WizardStep(
                id="welcome",
                type=WizardStepType.WELCOME,
                title="🎉 مرحباً بك في AI Teddy Bear!",
                subtitle="دعنا نساعدك في إعداد تجربة آمنة ومميزة لطفلك",
                description="سنقوم معاً بإعداد حسابك وربط جهاز AI Teddy Bear في خطوات بسيطة.",
                instructions=[
                    "هذا المعالج سيستغرق حوالي 10-15 دقيقة",
                    "تأكد من وجود جهاز AI Teddy Bear بجانبك",
                    "تأكد من اتصالك بشبكة الواي فاي",
                    "احتفظ بكود QR الموجود على الجهاز",
                ],
                media_files=[
                    {
                        "type": "image",
                        "url": "/static/images/onboarding/welcome_hero.png",
                        "alt": "AI Teddy Bear - الشاشة الترحيبية",
                    }
                ],
                input_fields=[],
                validation_rules={},
                success_message="ممتاز! لنبدأ رحلة الإعداد",
                error_messages={},
                help_text="يمكنك الخروج من المعالج في أي وقت والعودة لاحقاً",
                estimated_time=30,
                can_skip=False,
                next_step="parent_info",
                previous_step=None,
            ),
            # خطوة 2: معلومات ولي الأمر
            "parent_info": WizardStep(
                id="parent_info",
                type=WizardStepType.INFO_COLLECTION,
                title="👨‍👩‍👧‍👦 معلومات ولي الأمر",
                subtitle="نحتاج لبعض المعلومات الأساسية لإنشاء حساب آمن",
                description="هذه المعلومات ستستخدم لحماية حساب طفلك وضمان الاستخدام الآمن.",
                instructions=[
                    "أدخل اسمك الكامل كما هو في الهوية",
                    "استخدم بريد إلكتروني صحيح - ستحتاجه للتحقق",
                    "اختر كلمة مرور قوية (8 أحرف على الأقل)",
                    "أدخل رقم هاتف للطوارئ (اختياري)",
                ],
                media_files=[
                    {
                        "type": "image",
                        "url": "/static/images/onboarding/parent_info_form.png",
                        "alt": "نموذج معلومات ولي الأمر",
                    }
                ],
                input_fields=[
                    {
                        "id": "full_name",
                        "type": "text",
                        "label": "الاسم الكامل",
                        "placeholder": "أدخل اسمك الكامل",
                        "required": True,
                        "max_length": 100,
                    },
                    {
                        "id": "email",
                        "type": "email",
                        "label": "البريد الإلكتروني",
                        "placeholder": "example@email.com",
                        "required": True,
                    },
                    {
                        "id": "password",
                        "type": "password",
                        "label": "كلمة المرور",
                        "placeholder": "كلمة مرور قوية",
                        "required": True,
                        "min_length": 8,
                    },
                    {
                        "id": "password_confirm",
                        "type": "password",
                        "label": "تأكيد كلمة المرور",
                        "placeholder": "أعد كتابة كلمة المرور",
                        "required": True,
                    },
                    {
                        "id": "phone",
                        "type": "tel",
                        "label": "رقم الهاتف (اختياري)",
                        "placeholder": "+966 50 123 4567",
                        "required": False,
                    },
                ],
                validation_rules={
                    "email": {"format": "email"},
                    "password": {"min_length": 8, "require_special": True},
                    "password_confirm": {"must_match": "password"},
                    "phone": {"format": "international"},
                },
                success_message="تم حفظ معلوماتك بنجاح! سنرسل رابط التحقق لبريدك الإلكتروني",
                error_messages={
                    "email_exists": "هذا البريد الإلكتروني مستخدم بالفعل",
                    "weak_password": "كلمة المرور ضعيفة، استخدم أحرف وأرقام ورموز",
                    "password_mismatch": "كلمتا المرور غير متطابقتين",
                    "invalid_phone": "رقم الهاتف غير صحيح",
                },
                help_text="معلوماتك محمية وفقاً لقوانين COPPA وGDPR",
                estimated_time=300,
                can_skip=False,
                next_step="child_profile",
                previous_step="welcome",
            ),
            # خطوة 3: ملف الطفل
            "child_profile": WizardStep(
                id="child_profile",
                type=WizardStepType.INFO_COLLECTION,
                title="🧸 ملف الطفل الشخصي",
                subtitle="دعنا نتعرف على طفلك لنقدم تجربة مخصصة وآمنة",
                description="هذه المعلومات ستساعدنا في تخصيص المحادثات والمحتوى ليناسب عمر طفلك.",
                instructions=[
                    "أدخل اسم طفلك (يمكن استخدام اسم مستعار)",
                    "حدد العمر بدقة - مهم جداً للمحتوى الآمن",
                    "اختر الهوايات والاهتمامات",
                    "حدد مستوى التفاعل المناسب",
                ],
                media_files=[
                    {
                        "type": "image",
                        "url": "/static/images/onboarding/child_profile.png",
                        "alt": "إنشاء ملف الطفل",
                    },
                    {
                        "type": "video",
                        "url": "/static/videos/child_safety_explanation.mp4",
                        "alt": "شرح ميزات الأمان للأطفال",
                    },
                ],
                input_fields=[
                    {
                        "id": "child_name",
                        "type": "text",
                        "label": "اسم الطفل",
                        "placeholder": "مثال: أحمد أو سارة",
                        "required": True,
                        "max_length": 50,
                    },
                    {
                        "id": "child_age",
                        "type": "number",
                        "label": "عمر الطفل",
                        "placeholder": "من 3 إلى 13 سنة",
                        "required": True,
                        "min": 3,
                        "max": 13,
                    },
                    {
                        "id": "gender",
                        "type": "select",
                        "label": "الجنس (اختياري)",
                        "options": [
                            {"value": "", "label": "لا أرغب في التحديد"},
                            {"value": VoiceGender.MALE.value, "label": "ذكر"},
                            {"value": VoiceGender.FEMALE.value, "label": "أنثى"},
                        ],
                        "required": False,
                    },
                    {
                        "id": "interests",
                        "type": "checkbox",
                        "label": "الاهتمامات والهوايات",
                        "options": [
                            {"value": "stories", "label": "القصص والحكايات"},
                            {"value": "music", "label": "الموسيقى والأغاني"},
                            {"value": "games", "label": "الألعاب والألغاز"},
                            {"value": "science", "label": "العلوم والاكتشافات"},
                            {"value": "art", "label": "الفن والرسم"},
                            {"value": "sports", "label": "الرياضة والحركة"},
                        ],
                        "required": False,
                    },
                    {
                        "id": "interaction_level",
                        "type": "radio",
                        "label": "مستوى التفاعل",
                        "options": [
                            {"value": VoiceEmotion.GENTLE.value, "label": "هادئ ولطيف"},
                            {"value": "moderate", "label": "متوسط ومرح"},
                            {"value": "energetic", "label": "نشيط ومفعم بالحيوية"},
                        ],
                        "required": True,
                        "default": "moderate",
                    },
                ],
                validation_rules={
                    "child_age": {"min": 3, "max": 13},
                    "child_name": {"min_length": 2, "max_length": 50},
                },
                success_message="رائع! تم حفظ ملف طفلك بنجاح",
                error_messages={
                    "age_out_of_range": "عذراً، AI Teddy Bear مخصص للأطفال من 3 إلى 13 سنة",
                    "name_too_short": "اسم الطفل قصير جداً",
                    "name_too_long": "اسم الطفل طويل جداً",
                },
                help_text="يمكنك تعديل هذه المعلومات في أي وقت من الإعدادات",
                estimated_time=240,
                can_skip=False,
                next_step="device_preparation",
                previous_step="parent_info",
            ),
            # خطوة 4: تحضير الجهاز
            "device_preparation": WizardStep(
                id="device_preparation",
                type=WizardStepType.DEVICE_SETUP,
                title="📱 تحضير جهاز AI Teddy Bear",
                subtitle="الآن دعنا نحضر الجهاز للاستخدام",
                description="سنقوم بتوصيل الجهاز بالشبكة وربطه بحساب طفلك.",
                instructions=[
                    "تأكد من أن الجهاز متصل بالكهرباء ومضاء",
                    "تأكد من اتصالك بشبكة الواي فاي",
                    "احضر كود QR الموجود على ظهر الجهاز أو في العلبة",
                    "تأكد من أن جهازك متصل بنفس شبكة الواي فاي",
                ],
                media_files=[
                    {
                        "type": "image",
                        "url": "/static/images/onboarding/device_preparation.png",
                        "alt": "تحضير الجهاز للإعداد",
                    },
                    {
                        "type": "gif",
                        "url": "/static/images/onboarding/find_qr_code.gif",
                        "alt": "كيفية العثور على كود QR",
                    },
                    {
                        "type": "video",
                        "url": "/static/videos/device_setup_guide.mp4",
                        "alt": "دليل إعداد الجهاز بالفيديو",
                    },
                ],
                input_fields=[
                    {
                        "id": "device_ready",
                        "type": "checkbox",
                        "label": "تأكيدات الجاهزية",
                        "options": [
                            {
                                "value": "powered",
                                "label": "الجهاز متصل بالكهرباء ومضاء",
                            },
                            {
                                "value": "wifi_connected",
                                "label": "جهازي متصل بشبكة الواي فاي",
                            },
                            {"value": "qr_ready", "label": "كود QR جاهز ومرئي بوضوح"},
                            {
                                "value": "location_ready",
                                "label": "الجهاز في مكان مناسب للطفل",
                            },
                        ],
                        "required": True,
                        "min_selections": 4,
                    }
                ],
                validation_rules={"device_ready": {"min_selections": 4}},
                success_message="ممتاز! الجهاز جاهز للربط",
                error_messages={
                    "incomplete_preparation": "يرجى التأكد من جميع خطوات التحضير"
                },
                help_text="إذا واجهت مشكلة، راجع دليل الإعداد السريع في العلبة",
                estimated_time=180,
                can_skip=False,
                next_step="wifi_setup",
                previous_step="child_profile",
            ),
            # خطوة 5: إعداد الواي فاي
            "wifi_setup": WizardStep(
                id="wifi_setup",
                type=WizardStepType.DEVICE_SETUP,
                title="📶 ربط الجهاز بالواي فاي",
                subtitle="سنربط جهاز AI Teddy Bear بشبكة الواي فاي",
                description="هذه الخطوة ضرورية لتمكين الجهاز من التواصل مع خدمات AI الآمنة.",
                instructions=[
                    "اضغط على زر الإعداد في الجهاز لمدة 3 ثواني",
                    "انتظر حتى يضيء الضوء الأزرق",
                    "امسح كود QR الموجود على الجهاز",
                    "اتبع التعليمات التي ستظهر على الشاشة",
                ],
                media_files=[
                    {
                        "type": "gif",
                        "url": "/static/images/onboarding/wifi_setup.gif",
                        "alt": "خطوات ربط الواي فاي",
                    },
                    {
                        "type": "image",
                        "url": "/static/images/onboarding/qr_scanner.png",
                        "alt": "ماسح كود QR",
                    },
                ],
                input_fields=[
                    {
                        "id": "qr_code",
                        "type": "qr_scanner",
                        "label": "امسح كود QR",
                        "placeholder": "اضغط لفتح الكاميرا وامسح الكود",
                        "required": True,
                    },
                    {
                        "id": "manual_code",
                        "type": "text",
                        "label": "أو أدخل الكود يدوياً",
                        "placeholder": "TB-XXXX-XXXX-XXXX",
                        "required": False,
                        "pattern": "^TB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
                    },
                ],
                validation_rules={
                    "qr_code": {"format": "teddy_bear_device"},
                    "manual_code": {
                        "pattern": "^TB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
                    },
                },
                success_message="تم ربط الجهاز بنجاح! الآن يمكنه الاتصال بالإنترنت",
                error_messages={
                    "invalid_qr": "كود QR غير صحيح أو تالف",
                    "device_already_paired": "هذا الجهاز مربوط بحساب آخر",
                    "connection_failed": "فشل في الاتصال، تحقق من شبكة الواي فاي",
                    "invalid_manual_code": "الكود المدخل غير صحيح",
                },
                help_text="إذا لم تتمكن من مسح الكود، جرب تحسين الإضاءة أو استخدم الإدخال اليدوي",
                estimated_time=300,
                can_skip=False,
                next_step="audio_test",
                previous_step="device_preparation",
            ),
            # خطوة 6: اختبار الصوت
            "audio_test": WizardStep(
                id="audio_test",
                type=WizardStepType.TESTING,
                title="🎵 اختبار الصوت",
                subtitle="دعنا نتأكد من أن الصوت يعمل بشكل مثالي",
                description="سنختبر المايكروفون والسماعة للتأكد من جودة التفاعل الصوتي.",
                instructions=[
                    "ضع الجهاز على مسافة مناسبة من الطفل (1-2 متر)",
                    "تأكد من عدم وجود ضوضاء في الخلفية",
                    "اطلب من الطفل قول 'مرحبا' بصوت واضح",
                    "تأكد من سماع الرد من الجهاز",
                ],
                media_files=[
                    {
                        "type": "audio",
                        "url": "/static/audio/test_sound.mp3",
                        "alt": "صوت اختبار للتأكد من عمل السماعة",
                    },
                    {
                        "type": "gif",
                        "url": "/static/images/onboarding/audio_test.gif",
                        "alt": "اختبار الصوت خطوة بخطوة",
                    },
                ],
                input_fields=[
                    {
                        "id": "speaker_test",
                        "type": "button",
                        "label": "اختبار السماعة",
                        "action": "play_test_sound",
                        "text": "🔊 تشغيل صوت اختبار",
                    },
                    {
                        "id": "microphone_test",
                        "type": "voice_recorder",
                        "label": "اختبار المايكروفون",
                        "placeholder": "اضغط واتحدث",
                        "max_duration": 10,
                    },
                    {
                        "id": "audio_quality",
                        "type": "radio",
                        "label": "كيف تبدو جودة الصوت؟",
                        "options": [
                            {"value": "excellent", "label": "ممتازة - واضحة جداً"},
                            {"value": "good", "label": "جيدة - واضحة"},
                            {
                                "value": "acceptable",
                                "label": "مقبولة - بها بعض التشويش",
                            },
                            {"value": "poor", "label": "ضعيفة - غير واضحة"},
                        ],
                        "required": True,
                    },
                ],
                validation_rules={
                    "microphone_test": {"min_duration": 2},
                    "audio_quality": {"not_empty": True},
                },
                success_message="رائع! الصوت يعمل بشكل مثالي",
                error_messages={
                    "no_sound_detected": "لم يتم سماع أي صوت، تحقق من المايكروفون",
                    "poor_quality": "جودة الصوت ضعيفة، جرب تحسين الموقع أو تقليل الضوضاء",
                },
                help_text="للحصول على أفضل جودة صوت، ضع الجهاز في مكان هادئ",
                estimated_time=180,
                can_skip=True,
                next_step="first_conversation",
                previous_step="wifi_setup",
            ),
            # خطوة 7: أول محادثة
            "first_conversation": WizardStep(
                id="first_conversation",
                type=WizardStepType.TESTING,
                title="💬 أول محادثة مع AI Teddy",
                subtitle="حان الوقت لأول تفاعل حقيقي!",
                description="دع طفلك يجرب التحدث مع AI Teddy Bear لأول مرة.",
                instructions=[
                    "اطلب من الطفل قول: 'مرحبا، ما اسمك؟'",
                    "انتظر رد AI Teddy Bear",
                    "شجع الطفل على طرح سؤال آخر",
                    "تأكد من أن الردود مناسبة وآمنة",
                ],
                media_files=[
                    {
                        "type": "video",
                        "url": "/static/videos/first_conversation_example.mp4",
                        "alt": "مثال على أول محادثة",
                    }
                ],
                input_fields=[
                    {
                        "id": "conversation_started",
                        "type": "checkbox",
                        "label": "تأكيد المحادثة",
                        "options": [
                            {"value": "child_spoke", "label": "الطفل تحدث مع AI Teddy"},
                            {
                                "value": "teddy_responded",
                                "label": "AI Teddy رد بشكل مناسب",
                            },
                            {"value": "child_happy", "label": "الطفل مستمتع بالتفاعل"},
                            {
                                "value": "content_appropriate",
                                "label": "المحتوى مناسب وآمن",
                            },
                        ],
                        "required": True,
                        "min_selections": 3,
                    },
                    {
                        "id": "first_impression",
                        "type": "radio",
                        "label": "ما هو انطباع الطفل الأول؟",
                        "options": [
                            {"value": VoiceEmotion.EXCITED.value, "label": "متحمس ومتفاعل"},
                            {"value": "curious", "label": "فضولي ومهتم"},
                            {"value": "shy", "label": "خجول لكن مهتم"},
                            {"value": "confused", "label": "محتار أو غير متأكد"},
                        ],
                        "required": True,
                    },
                ],
                validation_rules={"conversation_started": {"min_selections": 3}},
                success_message="🎉 تهانينا! تم إعداد AI Teddy Bear بنجاح",
                error_messages={
                    "conversation_incomplete": "يبدو أن المحادثة لم تكتمل بنجاح"
                },
                help_text="إذا كان الطفل خجولاً، شجعه بلطف ولا تجبره على التحدث",
                estimated_time=300,
                can_skip=True,
                next_step="completion",
                previous_step="audio_test",
            ),
            # خطوة 8: إكمال الإعداد
            "completion": WizardStep(
                id="completion",
                type=WizardStepType.COMPLETION,
                title="🎊 تم إكمال الإعداد بنجاح!",
                subtitle="AI Teddy Bear جاهز الآن لمرافقة طفلك",
                description="تهانينا! لقد أكملت جميع خطوات الإعداد بنجاح. طفلك الآن يستطيع الاستمتاع بتجربة آمنة ومفيدة.",
                instructions=[
                    "يمكن لطفلك الآن التحدث مع AI Teddy في أي وقت",
                    "راجع إعدادات الأمان من حسابك كولي أمر",
                    "تذكر أنه يمكنك تعديل التفضيلات في أي وقت",
                    "احفظ معلومات الاتصال للدعم الفني",
                ],
                media_files=[
                    {
                        "type": "image",
                        "url": "/static/images/onboarding/completion_celebration.png",
                        "alt": "احتفال بإكمال الإعداد",
                    }
                ],
                input_fields=[
                    {
                        "id": "satisfaction_rating",
                        "type": "rating",
                        "label": "كيف تقيم تجربة الإعداد؟",
                        "min": 1,
                        "max": 5,
                        "required": False,
                    },
                    {
                        "id": "feedback",
                        "type": "textarea",
                        "label": "أي تعليقات أو اقتراحات؟",
                        "placeholder": "شاركنا رأيك لتحسين التجربة",
                        "required": False,
                        "max_length": 500,
                    },
                    {
                        "id": "notifications",
                        "type": "checkbox",
                        "label": "التنبيهات",
                        "options": [
                            {
                                "value": "safety_alerts",
                                "label": "تنبيهات الأمان المهمة",
                            },
                            {"value": "updates", "label": "إشعارات التحديثات"},
                            {"value": "tips", "label": "نصائح الاستخدام الأسبوعية"},
                        ],
                        "required": False,
                    },
                ],
                validation_rules={},
                success_message="شكراً لك! تم حفظ تقييمك وملاحظاتك",
                error_messages={},
                help_text="يمكنك الوصول لهذا المعالج مرة أخرى من الإعدادات",
                estimated_time=120,
                can_skip=True,
                next_step=None,
                previous_step="first_conversation",
            ),
        }

    async def start_wizard(self, user_id: str) -> Dict[str, Any]:
        """بدء معالج الإعداد"""
        session = {
            "user_id": user_id,
            "current_step": "welcome",
            "started_at": datetime.now().isoformat(),
            "completed_steps": [],
            "step_data": {},
            "total_time": 0,
        }

        self.current_sessions[user_id] = session

        return {
            "session_id": user_id,
            "current_step": self.steps["welcome"],
            "progress": {"current": 1, "total": len(self.steps)},
            "estimated_remaining_time": sum(
                step.estimated_time for step in self.steps.values()
            ),
        }

    async def process_step(
        self, user_id: str, step_id: str, step_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """معالجة خطوة في المعالج"""
        if user_id not in self.current_sessions:
            return {"error": "No active wizard session"}

        session = self.current_sessions[user_id]
        step = self.steps.get(step_id)

        if not step:
            return {"error": "Invalid step"}

        # التحقق من صحة البيانات
        validation_result = await self._validate_step_data(step, step_data)
        if not validation_result["valid"]:
            return {
                "success": False,
                "errors": validation_result["errors"],
                "current_step": step,
            }

        # حفظ بيانات الخطوة
        session["step_data"][step_id] = step_data
        session["completed_steps"].append(step_id)

        # الانتقال للخطوة التالية
        next_step_id = step.next_step
        if next_step_id and next_step_id in self.steps:
            session["current_step"] = next_step_id
            next_step = self.steps[next_step_id]

            return {
                "success": True,
                "message": step.success_message,
                "next_step": next_step,
                "progress": {
                    "current": len(session["completed_steps"]) + 1,
                    "total": len(self.steps),
                },
            }
        else:
            # إكمال المعالج
            return await self._complete_wizard(user_id)

    async def _validate_step_data(
        self, step: WizardStep, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """التحقق من صحة بيانات الخطوة"""
        errors = []

        for field in step.input_fields:
            field_id = field["id"]
            field_value = data.get(field_id)

            # التحقق من الحقول المطلوبة
            if field.get("required", False) and not field_value:
                errors.append(f"حقل '{field['label']}' مطلوب")
                continue

            # تطبيق قواعد التحقق المخصصة
            field_rules = step.validation_rules.get(field_id, {})

            if (
                "min_length" in field_rules
                and len(str(field_value)) < field_rules["min_length"]
            ):
                errors.append(f"'{field['label']}' قصير جداً")

            if (
                "max_length" in field_rules
                and len(str(field_value)) > field_rules["max_length"]
            ):
                errors.append(f"'{field['label']}' طويل جداً")

            if (
                "min" in field_rules
                and isinstance(field_value, (int, float))
                and field_value < field_rules["min"]
            ):
                errors.append(f"'{field['label']}' أقل من الحد المسموح")

            if (
                "max" in field_rules
                and isinstance(field_value, (int, float))
                and field_value > field_rules["max"]
            ):
                errors.append(f"'{field['label']}' أكبر من الحد المسموح")

        return {"valid": len(errors) == 0, "errors": errors}

    async def _complete_wizard(self, user_id: str) -> Dict[str, Any]:
        """إكمال المعالج"""
        session = self.current_sessions[user_id]

        # معالجة البيانات النهائية
        final_data = {
            "user_id": user_id,
            "completed_at": datetime.now().isoformat(),
            "total_time": session["total_time"],
            "all_step_data": session["step_data"],
        }

        # تنظيف الجلسة
        del self.current_sessions[user_id]

        return {
            "success": True,
            "message": "🎉 تم إكمال إعداد AI Teddy Bear بنجاح!",
            "wizard_completed": True,
            "final_data": final_data,
        }

    async def get_step(self, step_id: str) -> Optional[WizardStep]:
        """الحصول على خطوة معينة"""
        return self.steps.get(step_id)

    async def skip_step(self, user_id: str, step_id: str) -> Dict[str, Any]:
        """تخطي خطوة (إذا كان مسموحاً)"""
        step = self.steps.get(step_id)
        if not step or not step.can_skip:
            return {"error": "Cannot skip this step"}

        return await self.process_step(user_id, step_id, {"skipped": True})

    async def go_back(self, user_id: str) -> Dict[str, Any]:
        """العودة للخطوة السابقة"""
        if user_id not in self.current_sessions:
            return {"error": "No active session"}

        session = self.current_sessions[user_id]
        current_step = self.steps[session["current_step"]]

        if current_step.previous_step:
            session["current_step"] = current_step.previous_step
            # إزالة الخطوة الحالية من المكتملة إذا كانت موجودة
            if session["current_step"] in session["completed_steps"]:
                session["completed_steps"].remove(session["current_step"])

            return {
                "success": True,
                "current_step": self.steps[current_step.previous_step],
            }

        return {"error": "Cannot go back from this step"}
