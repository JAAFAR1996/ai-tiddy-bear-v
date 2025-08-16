# 🔴 سبب خطأ 404: Child profile not found or inactive

## المشكلة الجذرية

الكود في `src/adapters/claim_api.py` يستعلم عن حقول غير موجودة في نموذج `Child`:

### 1. الحقول المفقودة في الاستعلام (السطر 679-684):
```python
stmt = select(Child).where(
    and_(
        Child.id == child_id,
        Child.is_deleted == False,
        Child.is_active == True  # ❌ لا يوجد حقل is_active
    )
)
```

### 2. الخصائص المفقودة عند القراءة (السطر 694-701):
```python
return {
    "id": str(child.id),
    "name": child.display_name or child.name,  # ❌ لا يوجد display_name
    "age": child.age,  # ❌ لا يوجد age (فقط birth_date و estimated_age)
    "language": child.language_preference or "en",  # ❌ لا يوجد language_preference
    "voice_settings": child.voice_settings or {},  # ❌ لا يوجد voice_settings
    "safety_settings": child.safety_settings or {},  # ❌ لا يوجد safety_settings
    "parent_id": str(child.parent_id) if child.parent_id else None
}
```

### 3. مشكلة نوع المعرف:
- الدالة تتوقع `child_id` كـ string
- النموذج يستخدم UUID
- يجب تحويل: `uuid.UUID(child_id)`

## الحقول الفعلية في نموذج Child (src/infrastructure/database/models.py:338-387):

```python
class Child(BaseModel):
    __tablename__ = "children"
    
    # من BaseModel:
    id = Column(UUID(as_uuid=True), primary_key=True)  # UUID ليس string
    is_deleted = Column(Boolean, default=False)  # ✓ موجود
    # is_active غير موجود! ❌
    
    # حقول Child:
    parent_id = Column(UUID(as_uuid=True))
    name = Column(String(100))  # ✓ موجود
    birth_date = Column(DateTime)  # ليس age
    estimated_age = Column(Integer)  # هذا بدلاً من age
    safety_level = Column(Enum(SafetyLevel))  # ليس safety_settings
    # لا يوجد: display_name, language_preference, voice_settings
```

## الحل السريع - تعديل get_child_profile:

```python
async def get_child_profile(child_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """Get child profile data for device configuration"""
    try:
        # تحويل string إلى UUID
        import uuid
        try:
            child_uuid = uuid.UUID(child_id)
        except ValueError:
            logger.warning(f"Invalid UUID format: {child_id}")
            return None
        
        # استعلام بدون is_active (غير موجود)
        stmt = select(Child).where(
            and_(
                Child.id == child_uuid,
                Child.is_deleted == False,
                # إزالة: Child.is_active == True
            )
        ).options(selectinload(Child.parent))
        
        result = await db.execute(stmt)
        child = result.scalar_one_or_none()
        
        if not child:
            return None
        
        # حساب العمر من birth_date أو استخدام estimated_age
        from datetime import datetime
        age = child.estimated_age
        if child.birth_date:
            age = (datetime.now() - child.birth_date).days // 365
        
        # إرجاع البيانات المتوفرة فعلاً
        return {
            "id": str(child.id),
            "name": child.name,  # استخدام name مباشرة
            "age": age or 7,  # افتراضي 7 سنوات
            "language": "en",  # افتراضي - لا يوجد في النموذج
            "voice_settings": {},  # افتراضي - لا يوجد في النموذج
            "safety_settings": {
                "level": child.safety_level.value if child.safety_level else "safe",
                "content_filtering": child.content_filtering_enabled,
            },
            "parent_id": str(child.parent_id) if child.parent_id else None
        }
        
    except Exception as e:
        logger.error("Error retrieving child profile", extra={"child_id": child_id, "error": str(e)})
        return None
```

## أو: إضافة الحقول المفقودة للنموذج (Migration):

```sql
-- إضافة الحقول المفقودة لجدول children
ALTER TABLE children ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE children ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE children ADD COLUMN IF NOT EXISTS age INTEGER;
ALTER TABLE children ADD COLUMN IF NOT EXISTS language_preference VARCHAR(10) DEFAULT 'en';
ALTER TABLE children ADD COLUMN IF NOT EXISTS voice_settings JSONB DEFAULT '{}';

-- تحديث age من birth_date
UPDATE children 
SET age = EXTRACT(YEAR FROM age(birth_date))
WHERE birth_date IS NOT NULL AND age IS NULL;
```

## أين يتم تضمين claim_api router؟

في `src/infrastructure/routing/route_manager.py:470-481`:
```python
from src.adapters.claim_api import router as claim_router
route_manager.register_router(
    router=claim_router,
    router_name="device_claim",
    prefix="/api/v1",  # يصبح /api/v1/pair/claim
    tags=["Device Claiming"],
    require_auth=False,  # يستخدم HMAC
)
```

## المسار الكامل:
- Router prefix: `/pair` (claim_api.py:115)
- App prefix: `/api/v1` (route_manager.py:476)
- Endpoint: `/claim` (claim_api.py:711)
- **المسار النهائي**: `/api/v1/pair/claim`

## الخطوات للإصلاح:

1. **تعديل get_child_profile** في claim_api.py (الحل أعلاه)
2. **أو** إضافة الحقول المفقودة بـ migration
3. **تأكد من وجود بيانات اختبار**:
   ```sql
   INSERT INTO children (id, parent_id, name, estimated_age, is_deleted)
   VALUES ('test-child-001'::uuid, 'test-parent-001'::uuid, 'Test Child', 7, false);
   ```
4. **مسح Redis nonces** إذا لزم
5. **اختبر مرة أخرى**

هذا هو السبب الجذري لـ 404!