# **Enum Governance Rules - Production Standards**

## **🔒 Single Source of Truth Policy**

### **MANDATORY RULES**

#### **1. Audio Type Definitions**
```python
# ✅ CORRECT - Use shared definitions
from src.shared.audio_types import AudioFormat, AudioQuality, VoiceGender, VoiceEmotion

# ❌ FORBIDDEN - No duplicate enum definitions
class AudioFormat(Enum):  # NEVER DO THIS
    MP3 = "mp3"
```

#### **2. Inheritance for Specialized Cases**
```python
# ✅ CORRECT - Extend shared enums when needed
from src.shared.audio_types import AudioFormat as BaseAudioFormat

class CompressionAudioFormat(BaseAudioFormat):
    """Specialized for compression only."""
    WEBM = "webm"  # Add specialized formats only
```

#### **3. File Organization**
- **Shared Enums:** `src/shared/audio_types.py` (SINGLE SOURCE)
- **Specialized Enums:** Inherit from shared + add specific values
- **Domain Enums:** Domain-specific enums only (not shared types)

---

## **🚀 Implementation Standards**

### **Code Quality Requirements**

#### **Enum Definition Template**
```python
class YourEnum(Enum):
    """
    Clear purpose description.
    ========================
    
    Usage Context: Where and why this enum is used
    Validation Rules: What values are acceptable
    Child Safety: Any safety considerations
    """
    VALUE_NAME = "value"  # Clear naming convention
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Validate enum value."""
        return value in [item.value for item in cls]
```

#### **Documentation Standards**
- **Purpose:** Clear description of enum purpose
- **Usage Context:** When to use vs when not to use
- **Validation:** Built-in validation methods
- **Child Safety:** Safety implications if applicable
- **Examples:** Usage examples for developers

### **Import Standards**
```python
# ✅ PREFERRED - Explicit imports
from src.shared.audio_types import AudioFormat, AudioQuality

# ✅ ACCEPTABLE - Aliased imports
from src.shared.audio_types import AudioFormat as BaseAudioFormat

# ❌ FORBIDDEN - Wildcard imports
from src.shared.audio_types import *  # NEVER
```

---

## **⚠️ Violation Prevention**

### **Pre-Commit Checks**
1. **Search for Duplicate Enums:**
   ```bash
   grep -r "class AudioFormat\|class AudioQuality\|class VoiceGender\|class VoiceEmotion" src/
   ```

2. **Validate Import Usage:**
   ```bash
   grep -r "from.*audio_types.*import" src/
   ```

### **Code Review Checklist**
- [ ] No duplicate enum definitions
- [ ] All audio types imported from `src.shared.audio_types`
- [ ] Specialized enums use inheritance pattern
- [ ] Comprehensive documentation included
- [ ] Validation methods implemented
- [ ] Child safety considerations documented

### **Automated Testing**
```python
def test_no_enum_duplications():
    """Ensure no duplicate enum definitions exist."""
    # Add to test suite to prevent regressions
    pass
```

---

## **📚 Reference Examples**

### **✅ CORRECT Patterns**

#### **1. Basic Usage**
```python
# Domain entities
from src.shared.audio_types import AudioFormat, AudioQuality

class AudioMessage:
    def __init__(self, format: AudioFormat, quality: AudioQuality):
        self.format = format
        self.quality = quality
```

#### **2. Specialized Extension**
```python
# Compression manager
from src.shared.audio_types import AudioFormat as BaseAudioFormat

class CompressionAudioFormat(BaseAudioFormat):
    """ONLY for compression operations."""
    WEBM = "webm"
    
    @classmethod
    def get_compression_formats(cls) -> List[str]:
        """Get formats suitable for compression."""
        return [cls.MP3.value, cls.OGG.value, cls.WEBM.value]
```

#### **3. Service Integration**
```python
# TTS Provider
from src.shared.audio_types import AudioFormat, VoiceEmotion, VoiceGender

class TTSProvider:
    def generate_speech(
        self, 
        text: str, 
        format: AudioFormat = AudioFormat.MP3,
        emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    ) -> bytes:
        # Implementation
        pass
```

### **❌ FORBIDDEN Patterns**

#### **1. Duplicate Definitions**
```python
# NEVER DO THIS
class AudioFormat(Enum):
    MP3 = "mp3"
    OGG = "ogg"
```

#### **2. Inconsistent Imports**
```python
# NEVER MIX THESE
from some.local.module import AudioFormat  # Wrong source
from src.shared.audio_types import AudioQuality  # Correct source
```

#### **3. Hardcoded Values**
```python
# NEVER USE MAGIC STRINGS
if audio_format == "mp3":  # Use AudioFormat.MP3.value instead
    pass
```

---

## **🛠️ Migration Guide**

### **For New Features**
1. Check if enum exists in `src.shared.audio_types`
2. If not, add to shared location with full documentation
3. Import from shared location in your module
4. Add validation and safety checks

### **For Existing Code**
1. Identify duplicate enum usage
2. Verify shared enum has all needed values
3. Update imports to use shared location
4. Remove duplicate definitions
5. Test thoroughly

### **For Specialized Cases**
1. Inherit from shared enum
2. Add only specialized values
3. Document why specialization is needed
4. Provide conversion methods if needed

---

## **🔍 Monitoring & Maintenance**

### **Regular Audits**
- Monthly check for new duplicate enums
- Quarterly review of enum usage patterns
- Annual cleanup of unused enum values

### **Metrics to Track**
- Number of enum definitions per domain
- Import consistency across modules
- Usage patterns and frequency
- Child safety compliance

### **Emergency Procedures**
If duplicate enums are found:
1. **Immediate:** Document the duplication
2. **Short-term:** Plan consolidation approach
3. **Long-term:** Implement governance prevention

---

**Last Updated:** [Current Date]  
**Next Review:** [Date + 3 months]  
**Owner:** Development Team  
**Reviewers:** Architecture Team, Safety Team
