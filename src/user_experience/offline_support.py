"""
🌐 AI TEDDY BEAR - نظام الدعم في وضع عدم الاتصال
==================================================
نظام شامل للعمل بدون إنترنت مع المزامنة التلقائية
"""

import os
import json
import sqlite3
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta
import logging
from pathlib import Path
import asyncio
import uuid

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """حالة المزامنة"""

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class ContentType(Enum):
    """نوع المحتوى القابل للتخزين"""

    CONVERSATION = "conversation"
    STORY = "story"
    VOICE_RESPONSE = "voice_response"
    CHILD_PROFILE = "child_profile"
    SETTINGS = "settings"
    MEDIA_FILE = "media_file"


class OfflineAction(Enum):
    """الإجراءات المتاحة في وضع عدم الاتصال"""

    VIEW_CONTENT = "view_content"
    BASIC_CHAT = "basic_chat"
    PLAY_STORIES = "play_stories"
    VOICE_INTERACTION = "voice_interaction"
    UPDATE_SETTINGS = "update_settings"
    CREATE_CONTENT = "create_content"


@dataclass
class OfflineContent:
    """محتوى مخزن للاستخدام بدون إنترنت"""

    content_id: str
    content_type: ContentType
    title: str
    description: str
    data: Dict[str, Any]
    file_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)
    sync_status: SyncStatus = SyncStatus.PENDING
    file_size: int = 0
    checksum: str = ""
    priority: int = 1  # 1=عالي، 5=منخفض
    expiry_date: Optional[datetime] = None


@dataclass
class SyncTask:
    """مهمة مزامنة"""

    task_id: str
    content_id: str
    action: str  # upload, download, update, delete
    data: Dict[str, Any]
    created_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    status: SyncStatus = SyncStatus.PENDING
    error_message: Optional[str] = None


class OfflineSupportManager:
    """مدير الدعم في وضع عدم الاتصال"""

    def __init__(self, storage_path: str = "./offline_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # مسارات التخزين
        self.db_path = self.storage_path / "offline_data.db"
        self.files_path = self.storage_path / "files"
        self.files_path.mkdir(exist_ok=True)

        # إعدادات التخزين
        self.max_storage_size = 500 * 1024 * 1024  # 500 MB
        self.max_content_age = 30  # 30 يوم
        self.auto_sync_interval = 300  # 5 دقائق

        # قوائم التتبع
        self.offline_content: Dict[str, OfflineContent] = {}
        self.sync_queue: List[SyncTask] = []
        self.offline_capabilities: Dict[OfflineAction, bool] = {}

        # حالة الاتصال
        self.is_online = True
        self.last_sync_time: Optional[datetime] = None
        self.sync_in_progress = False

        # إعداد قاعدة البيانات
        self._init_database()
        self._load_offline_content()
        self._setup_offline_capabilities()

    def _init_database(self):
        """إعداد قاعدة البيانات المحلية"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # جدول المحتوى
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_content (
                content_id TEXT PRIMARY KEY,
                content_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                data TEXT NOT NULL,
                file_path TEXT,
                created_at TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                sync_status TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                checksum TEXT,
                priority INTEGER DEFAULT 1,
                expiry_date TEXT
            )
        """
        )

        # جدول مهام المزامنة
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_tasks (
                task_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                action TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                status TEXT NOT NULL,
                error_message TEXT
            )
        """
        )

        # جدول الإعدادات
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

        conn.commit()
        conn.close()

    def _load_offline_content(self):
        """تحميل المحتوى المخزن محلياً"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM offline_content")
        rows = cursor.fetchall()

        for row in rows:
            content = OfflineContent(
                content_id=row[0],
                content_type=ContentType(row[1]),
                title=row[2],
                description=row[3],
                data=json.loads(row[4]),
                file_path=row[5],
                created_at=datetime.fromisoformat(row[6]),
                last_modified=datetime.fromisoformat(row[7]),
                sync_status=SyncStatus(row[8]),
                file_size=row[9],
                checksum=row[10],
                priority=row[11],
                expiry_date=datetime.fromisoformat(row[12]) if row[12] else None,
            )
            self.offline_content[content.content_id] = content

        # تحميل مهام المزامنة
        cursor.execute("SELECT * FROM sync_tasks")
        sync_rows = cursor.fetchall()

        for row in sync_rows:
            task = SyncTask(
                task_id=row[0],
                content_id=row[1],
                action=row[2],
                data=json.loads(row[3]),
                created_at=datetime.fromisoformat(row[4]),
                attempts=row[5],
                max_attempts=row[6],
                status=SyncStatus(row[7]),
                error_message=row[8],
            )
            self.sync_queue.append(task)

        conn.close()
        logger.info(f"Loaded {len(self.offline_content)} offline content items")

    def _setup_offline_capabilities(self):
        """إعداد الإمكانيات المتاحة بدون إنترنت"""
        self.offline_capabilities = {
            OfflineAction.VIEW_CONTENT: True,
            OfflineAction.BASIC_CHAT: True,  # ردود محدودة مخزنة
            OfflineAction.PLAY_STORIES: True,
            OfflineAction.VOICE_INTERACTION: True,  # ملفات صوتية مخزنة
            OfflineAction.UPDATE_SETTINGS: True,
            OfflineAction.CREATE_CONTENT: True,  # حفظ للمزامنة لاحقاً
        }

    async def download_content_for_offline(
        self, content_ids: List[str], priority: int = 1
    ) -> Dict[str, Any]:
        """تحميل محتوى للاستخدام بدون إنترنت"""
        if not self.is_online:
            return {"error": "يجب الاتصال بالإنترنت لتحميل المحتوى"}

        downloaded_count = 0
        failed_count = 0
        total_size = 0

        for content_id in content_ids:
            try:
                # محاكاة تحميل المحتوى من الخادم
                content_data = await self._fetch_content_from_server(content_id)

                if content_data:
                    # إنشاء محتوى غير متصل
                    offline_content = OfflineContent(
                        content_id=content_id,
                        content_type=ContentType(
                            content_data.get("type", "conversation")
                        ),
                        title=content_data.get("title", "محتوى بدون عنوان"),
                        description=content_data.get("description", ""),
                        data=content_data,
                        priority=priority,
                        sync_status=SyncStatus.SYNCED,
                    )

                    # حفظ الملفات إذا كانت موجودة
                    if "file_url" in content_data:
                        file_path = await self._download_media_file(
                            content_data["file_url"], content_id
                        )
                        offline_content.file_path = str(file_path)
                        offline_content.file_size = (
                            file_path.stat().st_size if file_path.exists() else 0
                        )
                        offline_content.checksum = self._calculate_file_checksum(
                            file_path
                        )

                    # حفظ في قاعدة البيانات
                    await self._save_offline_content(offline_content)
                    self.offline_content[content_id] = offline_content

                    total_size += offline_content.file_size
                    downloaded_count += 1

            except Exception as e:
                logger.error(f"Failed to download content {content_id}: {e}")
                failed_count += 1

        # تنظيف التخزين إذا تجاوز الحد الأقصى
        await self._cleanup_storage_if_needed()

        return {
            "success": True,
            "downloaded": downloaded_count,
            "failed": failed_count,
            "total_size": total_size,
            "storage_used": await self._get_storage_usage(),
        }

    async def get_offline_content(
        self,
        content_type: Optional[ContentType] = None,
        search_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """الحصول على المحتوى المتاح بدون إنترنت"""
        filtered_content = []

        for content in self.offline_content.values():
            # فلترة حسب النوع
            if content_type and content.content_type != content_type:
                continue

            # فلترة حسب البحث
            if search_query:
                search_lower = search_query.lower()
                if (
                    search_lower not in content.title.lower()
                    and search_lower not in content.description.lower()
                ):
                    continue

            # التحقق من انتهاء الصلاحية
            if content.expiry_date and datetime.now() > content.expiry_date:
                continue

            filtered_content.append(
                {
                    "content_id": content.content_id,
                    "type": content.content_type.value,
                    "title": content.title,
                    "description": content.description,
                    "file_path": content.file_path,
                    "created_at": content.created_at.isoformat(),
                    "sync_status": content.sync_status.value,
                    "file_size": content.file_size,
                }
            )

        # ترتيب حسب الأولوية والتاريخ
        filtered_content.sort(
            key=lambda x: (
                self.offline_content[x["content_id"]].priority,
                x["created_at"],
            )
        )

        return {
            "content": filtered_content,
            "total_count": len(filtered_content),
            "storage_usage": await self._get_storage_usage(),
            "offline_capabilities": {
                action.value: enabled
                for action, enabled in self.offline_capabilities.items()
            },
        }

    async def create_offline_content(
        self,
        content_type: ContentType,
        title: str,
        description: str,
        data: Dict[str, Any],
        file_data: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """إنشاء محتوى جديد للمزامنة لاحقاً"""
        content_id = str(uuid.uuid4())

        # إنشاء محتوى غير متصل
        offline_content = OfflineContent(
            content_id=content_id,
            content_type=content_type,
            title=title,
            description=description,
            data=data,
            sync_status=SyncStatus.PENDING,
        )

        # حفظ الملف إذا كان موجوداً
        if file_data:
            file_path = self.files_path / f"{content_id}.dat"
            with open(file_path, "wb") as f:
                f.write(file_data)

            offline_content.file_path = str(file_path)
            offline_content.file_size = len(file_data)
            offline_content.checksum = hashlib.md5(file_data).hexdigest()

        # حفظ المحتوى
        await self._save_offline_content(offline_content)
        self.offline_content[content_id] = offline_content

        # إضافة مهمة مزامنة
        sync_task = SyncTask(
            task_id=str(uuid.uuid4()),
            content_id=content_id,
            action="upload",
            data={"created_offline": True},
            created_at=datetime.now(),
        )
        await self._add_sync_task(sync_task)

        return {
            "success": True,
            "content_id": content_id,
            "message": "تم إنشاء المحتوى وسيتم رفعه عند الاتصال بالإنترنت",
        }

    async def sync_with_server(self, force: bool = False) -> Dict[str, Any]:
        """مزامنة البيانات مع الخادم"""
        if not self.is_online:
            return {"error": "غير متصل بالإنترنت"}

        if self.sync_in_progress and not force:
            return {"error": "المزامنة قيد التنفيذ بالفعل"}

        self.sync_in_progress = True
        sync_results = {"uploaded": 0, "downloaded": 0, "failed": 0, "conflicts": 0}

        try:
            # معالجة مهام المزامنة
            for task in self.sync_queue.copy():
                if task.status != SyncStatus.PENDING:
                    continue

                try:
                    task.status = SyncStatus.SYNCING

                    if task.action == "upload":
                        success = await self._upload_content_to_server(task.content_id)
                        if success:
                            sync_results["uploaded"] += 1
                            task.status = SyncStatus.SYNCED
                            # إزالة من قائمة المزامنة
                            self.sync_queue.remove(task)
                        else:
                            task.status = SyncStatus.FAILED
                            sync_results["failed"] += 1

                    elif task.action == "download":
                        success = await self._download_content_update(task.content_id)
                        if success:
                            sync_results["downloaded"] += 1
                            task.status = SyncStatus.SYNCED
                            self.sync_queue.remove(task)
                        else:
                            task.status = SyncStatus.FAILED
                            sync_results["failed"] += 1

                    # تحديث عدد المحاولات
                    task.attempts += 1

                    # إزالة المهام الفاشلة نهائياً
                    if (
                        task.attempts >= task.max_attempts
                        and task.status == SyncStatus.FAILED
                    ):
                        self.sync_queue.remove(task)
                        await self._delete_sync_task(task.task_id)
                    else:
                        await self._update_sync_task(task)

                except Exception as e:
                    task.status = SyncStatus.FAILED
                    task.error_message = str(e)
                    sync_results["failed"] += 1
                    logger.error(f"Sync task failed: {e}")

            self.last_sync_time = datetime.now()
            await self._save_setting("last_sync_time", self.last_sync_time.isoformat())

        finally:
            self.sync_in_progress = False

        return {
            "success": True,
            "sync_time": self.last_sync_time.isoformat(),
            "results": sync_results,
            "pending_tasks": len(
                [t for t in self.sync_queue if t.status == SyncStatus.PENDING]
            ),
        }

    async def set_offline_mode(self, offline: bool) -> Dict[str, Any]:
        """تغيير حالة الاتصال"""
        previous_state = self.is_online
        self.is_online = not offline

        if previous_state != self.is_online:
            if self.is_online:
                # العودة للاتصال - بدء المزامنة التلقائية
                logger.info("Device back online - starting sync")
                sync_result = await self.sync_with_server()
                return {
                    "success": True,
                    "message": "تم الاتصال بالإنترنت وبدء المزامنة",
                    "sync_result": sync_result,
                }
            else:
                # انقطاع الاتصال
                logger.info("Device went offline")
                return {
                    "success": True,
                    "message": "تم التبديل لوضع عدم الاتصال",
                    "offline_capabilities": list(self.offline_capabilities.keys()),
                }

        return {"success": True, "message": "لا تغيير في حالة الاتصال"}

    async def cleanup_offline_storage(
        self, max_age_days: Optional[int] = None, max_size_mb: Optional[int] = None
    ) -> Dict[str, Any]:
        """تنظيف التخزين المحلي"""
        if max_age_days is None:
            max_age_days = self.max_content_age

        if max_size_mb is None:
            max_size_mb = self.max_storage_size // (1024 * 1024)

        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        max_size_bytes = max_size_mb * 1024 * 1024

        removed_count = 0
        freed_space = 0

        # إزالة المحتوى القديم
        for content_id, content in list(self.offline_content.items()):
            should_remove = False

            # التحقق من العمر
            if content.created_at < cutoff_date:
                should_remove = True

            # التحقق من انتهاء الصلاحية
            if content.expiry_date and datetime.now() > content.expiry_date:
                should_remove = True

            if should_remove:
                freed_space += content.file_size
                await self._remove_offline_content(content_id)
                removed_count += 1

        # التحقق من الحد الأقصى للحجم
        current_size = await self._get_storage_usage()
        if current_size > max_size_bytes:
            # إزالة المحتوى الأقل أولوية
            sorted_content = sorted(
                self.offline_content.values(), key=lambda x: (x.priority, x.created_at)
            )

            for content in sorted_content:
                if current_size <= max_size_bytes:
                    break

                current_size -= content.file_size
                freed_space += content.file_size
                await self._remove_offline_content(content.content_id)
                removed_count += 1

        return {
            "success": True,
            "removed_items": removed_count,
            "freed_space_mb": freed_space // (1024 * 1024),
            "current_usage_mb": (await self._get_storage_usage()) // (1024 * 1024),
        }

    async def get_offline_stats(self) -> Dict[str, Any]:
        """إحصائيات التخزين المحلي"""
        total_content = len(self.offline_content)
        pending_sync = len(
            [t for t in self.sync_queue if t.status == SyncStatus.PENDING]
        )
        storage_usage = await self._get_storage_usage()

        content_by_type = {}
        for content in self.offline_content.values():
            content_type = content.content_type.value
            if content_type not in content_by_type:
                content_by_type[content_type] = 0
            content_by_type[content_type] += 1

        return {
            "is_online": self.is_online,
            "total_content": total_content,
            "pending_sync_tasks": pending_sync,
            "storage_usage_mb": storage_usage // (1024 * 1024),
            "max_storage_mb": self.max_storage_size // (1024 * 1024),
            "last_sync": (
                self.last_sync_time.isoformat() if self.last_sync_time else None
            ),
            "content_by_type": content_by_type,
            "offline_capabilities": {
                action.value: enabled
                for action, enabled in self.offline_capabilities.items()
            },
        }

    # الطرق المساعدة الداخلية

    async def _fetch_content_from_server(
        self, content_id: str
    ) -> Optional[Dict[str, Any]]:
        """محاكاة جلب المحتوى من الخادم"""
        # هنا سيتم الاتصال بالخادم الفعلي
        await asyncio.sleep(0.1)  # محاكاة زمن الشبكة
        return {
            "id": content_id,
            "type": "story",
            "title": f"قصة {content_id[:8]}",
            "description": "قصة تعليمية للأطفال",
            "content": "محتوى القصة...",
        }

    async def _download_media_file(self, file_url: str, content_id: str) -> Path:
        """تحميل ملف وسائط"""
        file_path = self.files_path / f"{content_id}.media"

        # محاكاة تحميل الملف
        await asyncio.sleep(0.2)

        # إنشاء ملف وهمي للاختبار
        with open(file_path, "wb") as f:
            f.write(b"dummy media content")

        return file_path

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """حساب checksum للملف"""
        if not file_path.exists():
            return ""

        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    async def _save_offline_content(self, content: OfflineContent):
        """حفظ المحتوى في قاعدة البيانات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO offline_content 
            (content_id, content_type, title, description, data, file_path, 
             created_at, last_modified, sync_status, file_size, checksum, priority, expiry_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                content.content_id,
                content.content_type.value,
                content.title,
                content.description,
                json.dumps(content.data),
                content.file_path,
                content.created_at.isoformat(),
                content.last_modified.isoformat(),
                content.sync_status.value,
                content.file_size,
                content.checksum,
                content.priority,
                content.expiry_date.isoformat() if content.expiry_date else None,
            ),
        )

        conn.commit()
        conn.close()

    async def _add_sync_task(self, task: SyncTask):
        """إضافة مهمة مزامنة"""
        self.sync_queue.append(task)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO sync_tasks 
            (task_id, content_id, action, data, created_at, attempts, max_attempts, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task.task_id,
                task.content_id,
                task.action,
                json.dumps(task.data),
                task.created_at.isoformat(),
                task.attempts,
                task.max_attempts,
                task.status.value,
                task.error_message,
            ),
        )

        conn.commit()
        conn.close()

    async def _update_sync_task(self, task: SyncTask):
        """تحديث مهمة مزامنة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE sync_tasks 
            SET attempts = ?, status = ?, error_message = ?
            WHERE task_id = ?
        """,
            (task.attempts, task.status.value, task.error_message, task.task_id),
        )

        conn.commit()
        conn.close()

    async def _delete_sync_task(self, task_id: str):
        """حذف مهمة مزامنة"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sync_tasks WHERE task_id = ?", (task_id,))

        conn.commit()
        conn.close()

    async def _upload_content_to_server(self, content_id: str) -> bool:
        """رفع المحتوى للخادم"""
        # محاكاة رفع البيانات
        await asyncio.sleep(0.3)
        return True  # نفترض النجاح للاختبار

    async def _download_content_update(self, content_id: str) -> bool:
        """تحميل تحديث للمحتوى"""
        # محاكاة تحميل التحديث
        await asyncio.sleep(0.2)
        return True

    async def _remove_offline_content(self, content_id: str):
        """إزالة المحتوى المحلي"""
        if content_id in self.offline_content:
            content = self.offline_content[content_id]

            # حذف الملف إذا كان موجوداً
            if content.file_path and os.path.exists(content.file_path):
                os.remove(content.file_path)

            # حذف من قاعدة البيانات
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM offline_content WHERE content_id = ?", (content_id,)
            )
            conn.commit()
            conn.close()

            # حذف من الذاكرة
            del self.offline_content[content_id]

    async def _get_storage_usage(self) -> int:
        """حساب استخدام التخزين بالبايت"""
        total_size = 0

        # حجم قاعدة البيانات
        if self.db_path.exists():
            total_size += self.db_path.stat().st_size

        # حجم الملفات
        for file_path in self.files_path.glob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

    async def _cleanup_storage_if_needed(self):
        """تنظيف التخزين إذا تجاوز الحد الأقصى"""
        current_usage = await self._get_storage_usage()

        if current_usage > self.max_storage_size:
            # تنظيف 20% من التخزين
            target_cleanup = int(self.max_storage_size * 0.2)
            await self.cleanup_offline_storage(
                max_size_mb=target_cleanup // (1024 * 1024)
            )

    async def _save_setting(self, key: str, value: str):
        """حفظ إعداد في قاعدة البيانات"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO offline_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """,
            (key, value, datetime.now().isoformat()),
        )

        conn.commit()
        conn.close()
