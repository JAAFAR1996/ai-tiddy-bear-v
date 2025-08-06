"""
👥 AI TEDDY BEAR - إدارة الجلسات المتطورة
========================================
نظام شامل لإدارة جلسات المستخدمين مع ميزات الأمان والمراقبة
"""

import uuid
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import datetime, timedelta
import logging
from ipaddress import ip_address

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """حالة الجلسة"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    SUSPICIOUS = "suspicious"


class DeviceType(Enum):
    """نوع الجهاز"""

    ESP32_TEDDY = "esp32_teddy"
    MOBILE_APP = "mobile_app"
    WEB_BROWSER = "web_browser"
    ADMIN_PANEL = "admin_panel"


class SessionTerminationReason(Enum):
    """سبب إنهاء الجلسة"""

    USER_LOGOUT = "user_logout"
    PARENT_TERMINATED = "parent_terminated"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    ADMIN_TERMINATED = "admin_terminated"
    DEVICE_OFFLINE = "device_offline"


@dataclass
class SessionInfo:
    """معلومات الجلسة"""

    session_id: str
    user_id: str
    child_id: Optional[str]
    device_id: str
    device_type: DeviceType
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    status: SessionStatus
    is_child_session: bool
    security_flags: Set[str] = field(default_factory=set)
    activity_log: List[Dict[str, Any]] = field(default_factory=list)
    location_info: Optional[Dict[str, str]] = None
    permissions: Set[str] = field(default_factory=set)


@dataclass
class SessionActivity:
    """نشاط في الجلسة"""

    timestamp: datetime
    action: str
    details: Dict[str, Any]
    ip_address: str
    success: bool
    risk_score: int = 0  # 0-100


class SessionManager:
    """مدير الجلسات المتطور"""

    def __init__(self):
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.session_tokens: Dict[str, str] = {}  # token -> session_id
        self.user_sessions: Dict[str, Set[str]] = {}  # user_id -> {session_ids}
        self.device_sessions: Dict[str, str] = {}  # device_id -> session_id

        # إعدادات الأمان
        self.max_sessions_per_user = 5
        self.max_child_sessions = 1  # طفل واحد = جلسة واحدة
        self.session_timeout = 3600  # ساعة واحدة
        self.child_session_timeout = 7200  # ساعتان للأطفال
        self.max_inactive_time = 1800  # 30 دقيقة بدون نشاط

        # مراقبة الأمان
        self.suspicious_ips: Set[str] = set()
        self.failed_attempts: Dict[str, int] = {}
        self.security_alerts: List[Dict[str, Any]] = []

    async def create_session(
        self,
        user_id: str,
        device_id: str,
        device_type: DeviceType,
        ip_address: str,
        user_agent: str,
        child_id: Optional[str] = None,
        location_info: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """إنشاء جلسة جديدة"""

        # التحقق من صحة البيانات
        if not self._validate_ip_address(ip_address):
            return {"error": "عنوان IP غير صحيح"}

        # التحقق من الحد الأقصى للجلسات
        if user_id in self.user_sessions:
            if len(self.user_sessions[user_id]) >= self.max_sessions_per_user:
                return {"error": "تجاوز الحد الأقصى للجلسات المتزامنة"}

        # التحقق من جلسات الأطفال
        is_child_session = child_id is not None
        if is_child_session:
            # التأكد من عدم وجود جلسة أخرى للطفل
            existing_child_session = self._find_active_child_session(child_id)
            if existing_child_session:
                return {"error": "يوجد جلسة نشطة للطفل بالفعل"}

        # التحقق من الجهاز
        if device_id in self.device_sessions:
            # إنهاء الجلسة القديمة
            old_session_id = self.device_sessions[device_id]
            await self.terminate_session(
                old_session_id, SessionTerminationReason.DEVICE_OFFLINE
            )

        # إنشاء الجلسة
        session_id = str(uuid.uuid4())
        session_token = secrets.token_urlsafe(32)

        timeout = (
            self.child_session_timeout if is_child_session else self.session_timeout
        )

        session_info = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            child_id=child_id,
            device_id=device_id,
            device_type=device_type,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=timeout),
            status=SessionStatus.ACTIVE,
            is_child_session=is_child_session,
            location_info=location_info,
            permissions=self._get_default_permissions(device_type, is_child_session),
        )

        # حفظ الجلسة
        self.active_sessions[session_id] = session_info
        self.session_tokens[session_token] = session_id

        # ربط الجلسة بالمستخدم والجهاز
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)
        self.device_sessions[device_id] = session_id

        # تسجيل النشاط
        await self._log_session_activity(
            session_id,
            "session_created",
            {"device_type": device_type.value, "is_child": is_child_session},
            ip_address,
        )

        logger.info(f"Created session {session_id} for user {user_id}")

        return {
            "success": True,
            "session_id": session_id,
            "session_token": session_token,
            "expires_at": session_info.expires_at.isoformat(),
            "permissions": list(session_info.permissions),
        }

    async def validate_session(
        self, session_token: str, ip_address: str
    ) -> Dict[str, Any]:
        """التحقق من صحة الجلسة"""
        if session_token not in self.session_tokens:
            return {"valid": False, "error": "رمز الجلسة غير صحيح"}

        session_id = self.session_tokens[session_token]
        session = self.active_sessions.get(session_id)

        if not session:
            return {"valid": False, "error": "جلسة غير موجودة"}

        # التحقق من حالة الجلسة
        if session.status != SessionStatus.ACTIVE:
            return {"valid": False, "error": f"الجلسة غير نشطة: {session.status.value}"}

        # التحقق من انتهاء الصلاحية
        if datetime.now() > session.expires_at:
            session.status = SessionStatus.EXPIRED
            return {"valid": False, "error": "انتهت صلاحية الجلسة"}

        # التحقق من عدم النشاط
        inactive_time = (datetime.now() - session.last_activity).total_seconds()
        if inactive_time > self.max_inactive_time:
            session.status = SessionStatus.INACTIVE
            return {"valid": False, "error": "الجلسة غير نشطة لفترة طويلة"}

        # فحص أمني للـ IP
        if session.ip_address != ip_address:
            # تسجيل محاولة مشبوهة
            await self._log_security_alert(
                session_id,
                "ip_mismatch",
                {"original_ip": session.ip_address, "new_ip": ip_address},
            )

            session.security_flags.add("ip_changed")
            session.status = SessionStatus.SUSPICIOUS

            return {"valid": False, "error": "تغيير في عنوان IP"}

        # تحديث النشاط
        session.last_activity = datetime.now()

        return {
            "valid": True,
            "session": {
                "session_id": session_id,
                "user_id": session.user_id,
                "child_id": session.child_id,
                "device_type": session.device_type.value,
                "is_child_session": session.is_child_session,
                "permissions": list(session.permissions),
                "security_flags": list(session.security_flags),
            },
        }

    async def extend_session(
        self, session_id: str, additional_time: int = None
    ) -> Dict[str, Any]:
        """تمديد صلاحية الجلسة"""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"success": False, "error": "جلسة غير موجودة"}

        if session.status != SessionStatus.ACTIVE:
            return {"success": False, "error": "لا يمكن تمديد جلسة غير نشطة"}

        # تحديد وقت التمديد
        if additional_time is None:
            additional_time = (
                self.child_session_timeout
                if session.is_child_session
                else self.session_timeout
            )

        # تحديد الحد الأقصى للتمديد
        max_extension = 4 * 3600  # 4 ساعات
        if additional_time > max_extension:
            additional_time = max_extension

        session.expires_at = datetime.now() + timedelta(seconds=additional_time)

        await self._log_session_activity(
            session_id,
            "session_extended",
            {"additional_time": additional_time},
            session.ip_address,
        )

        return {
            "success": True,
            "new_expiry": session.expires_at.isoformat(),
            "extended_by": additional_time,
        }

    async def terminate_session(
        self,
        session_id: str,
        reason: SessionTerminationReason,
        terminated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """إنهاء جلسة"""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"success": False, "error": "جلسة غير موجودة"}

        # تحديث حالة الجلسة
        session.status = SessionStatus.TERMINATED

        # تنظيف المراجع
        if session.user_id in self.user_sessions:
            self.user_sessions[session.user_id].discard(session_id)

        if session.device_id in self.device_sessions:
            del self.device_sessions[session.device_id]

        # إزالة الرموز
        tokens_to_remove = [
            token for token, sid in self.session_tokens.items() if sid == session_id
        ]
        for token in tokens_to_remove:
            del self.session_tokens[token]

        # تسجيل الإنهاء
        await self._log_session_activity(
            session_id,
            "session_terminated",
            {"reason": reason.value, "terminated_by": terminated_by},
            session.ip_address,
        )

        logger.info(f"Terminated session {session_id} - reason: {reason.value}")

        return {"success": True, "message": "تم إنهاء الجلسة بنجاح"}

    async def terminate_all_user_sessions(
        self, user_id: str, except_session: Optional[str] = None
    ) -> Dict[str, Any]:
        """إنهاء جميع جلسات المستخدم"""
        if user_id not in self.user_sessions:
            return {"success": True, "terminated_count": 0}

        sessions_to_terminate = self.user_sessions[user_id].copy()
        if except_session:
            sessions_to_terminate.discard(except_session)

        terminated_count = 0
        for session_id in sessions_to_terminate:
            result = await self.terminate_session(
                session_id, SessionTerminationReason.PARENT_TERMINATED, user_id
            )
            if result.get("success"):
                terminated_count += 1

        return {
            "success": True,
            "terminated_count": terminated_count,
            "message": f"تم إنهاء {terminated_count} جلسة",
        }

    async def get_user_sessions(self, user_id: str) -> Dict[str, Any]:
        """الحصول على جلسات المستخدم"""
        if user_id not in self.user_sessions:
            return {"sessions": []}

        sessions = []
        for session_id in self.user_sessions[user_id]:
            session = self.active_sessions.get(session_id)
            if session:
                sessions.append(
                    {
                        "session_id": session_id,
                        "device_type": session.device_type.value,
                        "device_id": session.device_id,
                        "created_at": session.created_at.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                        "expires_at": session.expires_at.isoformat(),
                        "status": session.status.value,
                        "is_child_session": session.is_child_session,
                        "child_id": session.child_id,
                        "ip_address": session.ip_address,
                        "security_flags": list(session.security_flags),
                        "location": session.location_info,
                    }
                )

        return {"sessions": sessions}

    async def force_child_logout(self, child_id: str, parent_id: str) -> Dict[str, Any]:
        """إجبار الطفل على تسجيل الخروج"""
        child_session = self._find_active_child_session(child_id)
        if not child_session:
            return {"success": False, "error": "لا توجد جلسة نشطة للطفل"}

        # التحقق من صلاحية الوالد
        if not await self._verify_parent_authority(parent_id, child_id):
            return {"success": False, "error": "غير مصرح لك بإنهاء هذه الجلسة"}

        result = await self.terminate_session(
            child_session.session_id,
            SessionTerminationReason.PARENT_TERMINATED,
            parent_id,
        )

        if result.get("success"):
            # إرسال إشعار للجهاز
            await self._notify_device_session_ended(child_session.device_id)

            return {"success": True, "message": "تم إنهاء جلسة الطفل بنجاح"}

        return result

    async def get_session_activity_log(
        self, session_id: str, limit: int = 50
    ) -> Dict[str, Any]:
        """الحصول على سجل نشاط الجلسة"""
        session = self.active_sessions.get(session_id)
        if not session:
            return {"error": "جلسة غير موجودة"}

        # ترتيب الأنشطة حسب الوقت (الأحدث أولاً)
        sorted_activities = sorted(
            session.activity_log,
            key=lambda x: x.get("timestamp", datetime.min),
            reverse=True,
        )

        return {
            "session_id": session_id,
            "activities": sorted_activities[:limit],
            "total_activities": len(session.activity_log),
        }

    async def monitor_suspicious_activity(self) -> Dict[str, Any]:
        """مراقبة النشاطات المشبوهة"""
        suspicious_sessions = []
        security_issues = []

        for session_id, session in self.active_sessions.items():
            if session.status == SessionStatus.SUSPICIOUS or session.security_flags:
                suspicious_sessions.append(
                    {
                        "session_id": session_id,
                        "user_id": session.user_id,
                        "flags": list(session.security_flags),
                        "last_activity": session.last_activity.isoformat(),
                        "ip_address": session.ip_address,
                    }
                )

        # فحص محاولات الوصول الفاشلة
        for ip, attempts in self.failed_attempts.items():
            if attempts >= 5:  # 5 محاولات فاشلة
                security_issues.append(
                    {
                        "type": "multiple_failed_attempts",
                        "ip_address": ip,
                        "attempts": attempts,
                    }
                )

        return {
            "suspicious_sessions": suspicious_sessions,
            "security_issues": security_issues,
            "total_active_sessions": len(self.active_sessions),
            "suspicious_ips": list(self.suspicious_ips),
        }

    async def cleanup_expired_sessions(self) -> Dict[str, Any]:
        """تنظيف الجلسات المنتهية الصلاحية"""
        now = datetime.now()
        expired_sessions = []

        for session_id, session in list(self.active_sessions.items()):
            if now > session.expires_at or session.status in [
                SessionStatus.EXPIRED,
                SessionStatus.TERMINATED,
            ]:
                expired_sessions.append(session_id)

                # إزالة من جميع القوائم
                if session.user_id in self.user_sessions:
                    self.user_sessions[session.user_id].discard(session_id)

                if session.device_id in self.device_sessions:
                    del self.device_sessions[session.device_id]

                # إزالة الرموز
                tokens_to_remove = [
                    token
                    for token, sid in self.session_tokens.items()
                    if sid == session_id
                ]
                for token in tokens_to_remove:
                    del self.session_tokens[token]

                del self.active_sessions[session_id]

        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        return {
            "cleaned_sessions": len(expired_sessions),
            "remaining_active": len(self.active_sessions),
        }

    def _validate_ip_address(self, ip: str) -> bool:
        """التحقق من صحة عنوان IP"""
        try:
            ip_address(ip)
            return True
        except ValueError:
            return False

    def _find_active_child_session(self, child_id: str) -> Optional[SessionInfo]:
        """البحث عن جلسة نشطة للطفل"""
        for session in self.active_sessions.values():
            if (
                session.child_id == child_id
                and session.is_child_session
                and session.status == SessionStatus.ACTIVE
            ):
                return session
        return None

    def _get_default_permissions(
        self, device_type: DeviceType, is_child_session: bool
    ) -> Set[str]:
        """الحصول على الصلاحيات الافتراضية"""
        permissions = set()

        if device_type == DeviceType.ESP32_TEDDY:
            permissions.update(["voice_chat", "story_telling", "basic_questions"])
            if is_child_session:
                permissions.add("child_safe_content")
            else:
                permissions.update(["device_management", "child_monitoring"])

        elif device_type == DeviceType.MOBILE_APP:
            permissions.update(
                ["account_management", "child_profiles", "device_pairing"]
            )
            if not is_child_session:
                permissions.update(["parent_controls", "session_management"])

        elif device_type == DeviceType.WEB_BROWSER:
            permissions.update(["dashboard_access", "reports_viewing"])

        elif device_type == DeviceType.ADMIN_PANEL:
            permissions.update(["admin_access", "system_management", "user_management"])

        return permissions

    async def _log_session_activity(
        self,
        session_id: str,
        action: str,
        details: Dict[str, Any],
        ip_address: str,
        success: bool = True,
        risk_score: int = 0,
    ):
        """تسجيل نشاط الجلسة"""
        session = self.active_sessions.get(session_id)
        if not session:
            return

        activity = SessionActivity(
            timestamp=datetime.now(),
            action=action,
            details=details,
            ip_address=ip_address,
            success=success,
            risk_score=risk_score,
        )

        # تحويل إلى dictionary للحفظ
        activity_dict = {
            "timestamp": activity.timestamp.isoformat(),
            "action": activity.action,
            "details": activity.details,
            "ip_address": activity.ip_address,
            "success": activity.success,
            "risk_score": activity.risk_score,
        }

        session.activity_log.append(activity_dict)

        # الاحتفاظ بآخر 100 نشاط فقط
        if len(session.activity_log) > 100:
            session.activity_log = session.activity_log[-100:]

    async def _log_security_alert(
        self, session_id: str, alert_type: str, details: Dict[str, Any]
    ):
        """تسجيل تنبيه أمني"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "alert_type": alert_type,
            "details": details,
        }

        self.security_alerts.append(alert)
        logger.warning(f"Security alert: {alert_type} for session {session_id}")

    async def _verify_parent_authority(self, parent_id: str, child_id: str) -> bool:
        """التحقق من صلاحية الوالد على الطفل"""
        # هنا سيتم التحقق من قاعدة البيانات
        # حالياً نفترض أن التحقق صحيح
        return True

    async def _notify_device_session_ended(self, device_id: str):
        """إشعار الجهاز بانتهاء الجلسة"""
        # هنا سيتم إرسال إشعار للجهاز
        logger.info(f"Notified device {device_id} about session termination")
