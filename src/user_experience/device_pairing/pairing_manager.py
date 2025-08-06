"""
📱 AI TEDDY BEAR - نظام ربط الأجهزة الذكي
==========================================
نظام شامل لربط أجهزة ESP32 بحسابات الأطفال بطريقة آمنة وسهلة
"""

import uuid
import qrcode
import hashlib
import secrets
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import logging
import json
import re

logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    """حالة الجهاز"""

    UNREGISTERED = "unregistered"
    PAIRING_MODE = "pairing_mode"
    PAIRED = "paired"
    ACTIVE = "active"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class PairingMethod(Enum):
    """طريقة الربط"""

    QR_CODE = "qr_code"
    MANUAL_CODE = "manual_code"
    BLUETOOTH = "bluetooth"
    WIFI_DIRECT = "wifi_direct"


@dataclass
class DeviceInfo:
    """معلومات الجهاز"""

    device_id: str
    device_code: str  # الكود المطبوع على الجهاز
    mac_address: str
    model: str
    firmware_version: str
    manufacture_date: datetime
    qr_code_data: str
    security_key: str
    status: DeviceStatus
    paired_child_id: Optional[str] = None
    paired_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    wifi_ssid: Optional[str] = None
    ip_address: Optional[str] = None


@dataclass
class PairingSession:
    """جلسة ربط جهاز"""

    session_id: str
    parent_id: str
    child_id: str
    device_code: str
    method: PairingMethod
    started_at: datetime
    expires_at: datetime
    status: str  # pending, in_progress, success, failed, expired
    steps_completed: List[str]
    error_message: Optional[str] = None
    retry_count: int = 0


class DevicePairingManager:
    """مدير ربط الأجهزة"""

    def __init__(self):
        self.devices: Dict[str, DeviceInfo] = {}
        self.pairing_sessions: Dict[str, PairingSession] = {}
        self.pairing_codes: Dict[str, str] = {}  # temporary codes -> device_id
        self.max_pairing_time = 600  # 10 دقائق
        self.max_retry_attempts = 3

    def generate_device_code(self, device_id: str) -> str:
        """إنشاء كود فريد للجهاز"""
        # كود بصيغة TB-XXXX-XXXX-XXXX
        random_part = secrets.token_hex(6).upper()
        formatted_code = f"TB-{random_part[:4]}-{random_part[4:8]}-{random_part[8:12]}"

        # التأكد من عدم تكرار الكود
        while formatted_code in [
            device.device_code for device in self.devices.values()
        ]:
            random_part = secrets.token_hex(6).upper()
            formatted_code = (
                f"TB-{random_part[:4]}-{random_part[4:8]}-{random_part[8:12]}"
            )

        return formatted_code

    def generate_qr_code(self, device_info: DeviceInfo) -> str:
        """إنشاء QR code للجهاز"""
        qr_data = {
            "type": "ai_teddy_device",
            "device_id": device_info.device_id,
            "device_code": device_info.device_code,
            "security_key": device_info.security_key,
            "model": device_info.model,
            "version": "1.0",
        }

        qr_string = json.dumps(qr_data, separators=(",", ":"))

        # إنشاء QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)

        return qr_string

    async def register_device(
        self, mac_address: str, model: str, firmware_version: str
    ) -> DeviceInfo:
        """تسجيل جهاز جديد في النظام"""
        device_id = str(uuid.uuid4())
        device_code = self.generate_device_code(device_id)
        security_key = secrets.token_urlsafe(32)

        device_info = DeviceInfo(
            device_id=device_id,
            device_code=device_code,
            mac_address=mac_address,
            model=model,
            firmware_version=firmware_version,
            manufacture_date=datetime.now(),
            qr_code_data="",  # سيتم ملؤه
            security_key=security_key,
            status=DeviceStatus.UNREGISTERED,
        )

        # إنشاء QR code
        device_info.qr_code_data = self.generate_qr_code(device_info)

        self.devices[device_id] = device_info

        logger.info(f"Registered new device: {device_code}")

        return device_info

    async def start_pairing_session(
        self,
        parent_id: str,
        child_id: str,
        method: PairingMethod = PairingMethod.QR_CODE,
    ) -> PairingSession:
        """بدء جلسة ربط جديدة"""
        session_id = str(uuid.uuid4())

        session = PairingSession(
            session_id=session_id,
            parent_id=parent_id,
            child_id=child_id,
            device_code="",  # سيتم ملؤه عند مسح الكود
            method=method,
            started_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.max_pairing_time),
            status="pending",
            steps_completed=[],
        )

        self.pairing_sessions[session_id] = session

        logger.info(f"Started pairing session {session_id} for parent {parent_id}")

        return session

    async def process_device_code(
        self, session_id: str, device_code: str
    ) -> Dict[str, Any]:
        """معالجة كود الجهاز المدخل"""
        if session_id not in self.pairing_sessions:
            return {"success": False, "error": "جلسة ربط غير صحيحة"}

        session = self.pairing_sessions[session_id]

        # التحقق من انتهاء صلاحية الجلسة
        if datetime.now() > session.expires_at:
            session.status = "expired"
            return {"success": False, "error": "انتهت صلاحية جلسة الربط"}

        # التحقق من صيغة الكود
        if not self._validate_device_code_format(device_code):
            return {"success": False, "error": "صيغة كود الجهاز غير صحيحة"}

        # البحث عن الجهاز
        device = self._find_device_by_code(device_code)
        if not device:
            return {"success": False, "error": "كود الجهاز غير موجود"}

        # التحقق من حالة الجهاز
        if device.status == DeviceStatus.PAIRED:
            return {
                "success": False,
                "error": "هذا الجهاز مربوط بالفعل بحساب آخر",
                "action": "contact_support",
            }

        # تحديث جلسة الربط
        session.device_code = device_code
        session.status = "in_progress"
        session.steps_completed.append("device_code_verified")

        return {
            "success": True,
            "message": "تم التحقق من كود الجهاز بنجاح",
            "device_info": {
                "model": device.model,
                "firmware_version": device.firmware_version,
            },
            "next_step": "wifi_setup",
        }

    async def process_qr_code(self, session_id: str, qr_data: str) -> Dict[str, Any]:
        """معالجة QR code المممسوح"""
        try:
            qr_content = json.loads(qr_data)
        except json.JSONDecodeError:
            return {"success": False, "error": "QR code غير صحيح"}

        # التحقق من نوع QR code
        if qr_content.get("type") != "ai_teddy_device":
            return {
                "success": False,
                "error": "هذا ليس QR code صحيح لجهاز AI Teddy Bear",
            }

        device_code = qr_content.get("device_code")
        if not device_code:
            return {"success": False, "error": "QR code تالف أو غير مكتمل"}

        # معالجة الكود كما لو كان مُدخل يدوياً
        return await self.process_device_code(session_id, device_code)

    async def setup_wifi_connection(
        self, session_id: str, wifi_ssid: str, wifi_password: str
    ) -> Dict[str, Any]:
        """إعداد اتصال الواي فاي للجهاز"""
        if session_id not in self.pairing_sessions:
            return {"success": False, "error": "جلسة ربط غير صحيحة"}

        session = self.pairing_sessions[session_id]
        device = self._find_device_by_code(session.device_code)

        if not device:
            return {"success": False, "error": "جهاز غير موجود"}

        try:
            # محاكاة إرسال إعدادات الواي فاي للجهاز
            wifi_config = {
                "ssid": wifi_ssid,
                "password": wifi_password,
                "device_id": device.device_id,
                "security_key": device.security_key,
            }

            # في التطبيق الحقيقي، سنرسل هذه البيانات للجهاز عبر Bluetooth أو WiFi Direct
            success = await self._send_wifi_config_to_device(device, wifi_config)

            if success:
                device.wifi_ssid = wifi_ssid
                device.status = DeviceStatus.PAIRING_MODE
                session.steps_completed.append("wifi_configured")

                return {
                    "success": True,
                    "message": "تم إعداد الواي فاي بنجاح",
                    "next_step": "test_connection",
                }
            else:
                return {
                    "success": False,
                    "error": "فشل في إعداد الواي فاي. تحقق من صحة كلمة المرور والشبكة",
                }

        except Exception as e:
            logger.error(f"WiFi setup error: {e}")
            return {"success": False, "error": "خطأ في إعداد الواي فاي"}

    async def test_device_connection(self, session_id: str) -> Dict[str, Any]:
        """اختبار اتصال الجهاز"""
        if session_id not in self.pairing_sessions:
            return {"success": False, "error": "جلسة ربط غير صحيحة"}

        session = self.pairing_sessions[session_id]
        device = self._find_device_by_code(session.device_code)

        if not device:
            return {"success": False, "error": "جهاز غير موجود"}

        # محاكاة اختبار الاتصال
        connection_test = await self._test_device_connectivity(device)

        if connection_test["success"]:
            device.ip_address = connection_test.get("ip_address")
            device.last_seen = datetime.now()
            device.status = DeviceStatus.ACTIVE
            session.steps_completed.append("connection_tested")

            return {
                "success": True,
                "message": "تم اختبار الاتصال بنجاح",
                "device_ip": device.ip_address,
                "next_step": "finalize_pairing",
            }
        else:
            return {
                "success": False,
                "error": "فشل في الاتصال بالجهاز. تحقق من الشبكة وإعادة المحاولة",
                "troubleshooting": [
                    "تأكد من أن الجهاز قريب من الراوتر",
                    "تحقق من صحة كلمة مرور الواي فاي",
                    "أعد تشغيل الراوتر إذا لزم الأمر",
                ],
            }

    async def finalize_pairing(self, session_id: str) -> Dict[str, Any]:
        """إنهاء عملية الربط"""
        if session_id not in self.pairing_sessions:
            return {"success": False, "error": "جلسة ربط غير صحيحة"}

        session = self.pairing_sessions[session_id]
        device = self._find_device_by_code(session.device_code)

        if not device:
            return {"success": False, "error": "جهاز غير موجود"}

        try:
            # ربط الجهاز بالطفل
            device.paired_child_id = session.child_id
            device.paired_at = datetime.now()
            device.status = DeviceStatus.PAIRED

            # إكمال الجلسة
            session.status = "success"
            session.steps_completed.append("pairing_completed")

            # حفظ معلومات الربط في قاعدة البيانات
            await self._save_pairing_to_database(device, session)

            # إرسال إعدادات الطفل للجهاز
            await self._send_child_settings_to_device(device, session.child_id)

            logger.info(
                f"Device {device.device_code} successfully paired with child {session.child_id}"
            )

            return {
                "success": True,
                "message": "🎉 تم ربط الجهاز بنجاح!",
                "device_info": {
                    "device_code": device.device_code,
                    "model": device.model,
                    "paired_at": device.paired_at.isoformat(),
                },
                "next_steps": [
                    "يمكن لطفلك الآن التحدث مع AI Teddy",
                    "راجع إعدادات الأمان من حسابك",
                    "جرب أول محادثة مع طفلك",
                ],
            }

        except Exception as e:
            logger.error(f"Pairing finalization error: {e}")
            session.status = "failed"
            session.error_message = str(e)

            return {"success": False, "error": "خطأ في إكمال عملية الربط"}

    async def handle_pairing_error(
        self, session_id: str, error_type: str, error_details: str
    ) -> Dict[str, Any]:
        """معالجة أخطاء الربط"""
        if session_id not in self.pairing_sessions:
            return {"success": False, "error": "جلسة ربط غير صحيحة"}

        session = self.pairing_sessions[session_id]
        session.retry_count += 1

        # تحديد نوع الخطأ والحل المناسب
        error_solutions = {
            "wifi_connection_failed": {
                "message": "فشل في الاتصال بالواي فاي",
                "solutions": [
                    "تحقق من صحة اسم الشبكة وكلمة المرور",
                    "تأكد من أن الجهاز قريب من الراوتر",
                    "جرب إعادة تشغيل الراوتر",
                ],
                "can_retry": True,
            },
            "device_not_responding": {
                "message": "الجهاز لا يستجيب",
                "solutions": [
                    "تأكد من أن الجهاز مشحون ومضاء",
                    "اضغط على زر إعادة التشغيل",
                    "تحقق من اتصال الكابلات",
                ],
                "can_retry": True,
            },
            "qr_code_damaged": {
                "message": "QR code تالف أو غير واضح",
                "solutions": [
                    "نظف سطح QR code بقطعة قماش ناعمة",
                    "تأكد من وجود إضاءة كافية",
                    "جرب الإدخال اليدوي للكود",
                ],
                "can_retry": True,
            },
            "device_already_paired": {
                "message": "الجهاز مربوط بحساب آخر",
                "solutions": [
                    "تواصل مع الدعم الفني لإعادة تعيين الجهاز",
                    "تأكد من أنك تستخدم الجهاز الصحيح",
                ],
                "can_retry": False,
            },
        }

        error_info = error_solutions.get(
            error_type,
            {
                "message": "خطأ غير محدد",
                "solutions": ["تواصل مع الدعم الفني"],
                "can_retry": False,
            },
        )

        # إذا تجاوز عدد المحاولات المسموح
        if session.retry_count >= self.max_retry_attempts:
            session.status = "failed"
            session.error_message = f"تجاوز عدد المحاولات المسموح: {error_type}"

            return {
                "success": False,
                "error": "تجاوز عدد المحاولات المسموح",
                "message": "يرجى التواصل مع الدعم الفني للمساعدة",
                "support_contact": {
                    "email": "support@ai-teddy-bear.com",
                    "phone": "+966 11 123 4567",
                },
            }

        return {
            "success": False,
            "error": error_info["message"],
            "solutions": error_info["solutions"],
            "can_retry": error_info["can_retry"],
            "retry_count": session.retry_count,
            "max_retries": self.max_retry_attempts,
        }

    def _validate_device_code_format(self, device_code: str) -> bool:
        """التحقق من صيغة كود الجهاز"""
        pattern = r"^TB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
        return bool(re.match(pattern, device_code))

    def _find_device_by_code(self, device_code: str) -> Optional[DeviceInfo]:
        """البحث عن جهاز بالكود"""
        for device in self.devices.values():
            if device.device_code == device_code:
                return device
        return None

    async def _send_wifi_config_to_device(
        self, device: DeviceInfo, config: Dict[str, Any]
    ) -> bool:
        """إرسال إعدادات الواي فاي للجهاز"""
        # في التطبيق الحقيقي، سيتم إرسال البيانات عبر Bluetooth أو WiFi Direct
        # هنا نحاكي العملية
        await asyncio.sleep(2)  # محاكاة وقت الإرسال

        # محاكاة نجاح العملية (90% نجاح)
        import random

        return random.random() > 0.1

    async def _test_device_connectivity(self, device: DeviceInfo) -> Dict[str, Any]:
        """اختبار اتصال الجهاز"""
        # محاكاة اختبار الاتصال
        await asyncio.sleep(3)

        # محاكاة نتيجة الاختبار
        import random

        if random.random() > 0.2:  # 80% نجاح
            return {
                "success": True,
                "ip_address": f"192.168.1.{random.randint(100, 200)}",
                "latency": random.randint(10, 50),
                "signal_strength": random.randint(60, 100),
            }
        else:
            return {"success": False}

    async def _save_pairing_to_database(
        self, device: DeviceInfo, session: PairingSession
    ):
        """حفظ معلومات الربط في قاعدة البيانات"""
        # هنا سيتم حفظ البيانات في قاعدة البيانات الحقيقية
        pass

    async def _send_child_settings_to_device(self, device: DeviceInfo, child_id: str):
        """إرسال إعدادات الطفل للجهاز"""
        # هنا سيتم إرسال تفضيلات وإعدادات الطفل للجهاز
        pass

    async def get_pairing_session_status(self, session_id: str) -> Dict[str, Any]:
        """الحصول على حالة جلسة الربط"""
        if session_id not in self.pairing_sessions:
            return {"error": "جلسة غير موجودة"}

        session = self.pairing_sessions[session_id]

        return {
            "session_id": session_id,
            "status": session.status,
            "steps_completed": session.steps_completed,
            "retry_count": session.retry_count,
            "started_at": session.started_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "time_remaining": (session.expires_at - datetime.now()).total_seconds(),
            "error_message": session.error_message,
        }

    async def unpair_device(self, device_code: str, parent_id: str) -> Dict[str, Any]:
        """إلغاء ربط جهاز"""
        device = self._find_device_by_code(device_code)
        if not device:
            return {"success": False, "error": "جهاز غير موجود"}

        if device.status != DeviceStatus.PAIRED:
            return {"success": False, "error": "الجهاز غير مربوط"}

        # إعادة تعيين الجهاز
        device.paired_child_id = None
        device.paired_at = None
        device.status = DeviceStatus.UNREGISTERED
        device.wifi_ssid = None
        device.ip_address = None

        logger.info(f"Device {device_code} unpaired by parent {parent_id}")

        return {"success": True, "message": "تم إلغاء ربط الجهاز بنجاح"}
