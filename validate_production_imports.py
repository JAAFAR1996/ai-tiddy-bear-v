import os, sys, pathlib

# إضافة مسار المشروع
ROOT = pathlib.Path(".").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print(f"🔹 عدد متغيرات البيئة حالياً: {len(os.environ)}")

print("\n📜 أسماء المتغيرات الموجودة:")
for k in sorted(os.environ.keys()):
    print(f"- {k}")

try:
    from src.infrastructure.config.production_config import ProductionConfig

    required = list(ProductionConfig.model_fields.keys())
    missing = [v for v in required if not os.environ.get(v, "").strip()]
    print(f"\n✅ عدد الحقول المطلوبة في ProductionConfig: {len(required)}")
    if missing:
        print("⚠️ متغيرات ناقصة:")
        for v in missing:
            print(f"- {v}")
    else:
        print("🎉 لا يوجد متغيرات ناقصة.")
except Exception as e:
    print("\nℹ️ ملاحظة: تعذر استيراد ProductionConfig.")
    print("   شغّل هذا من جذر المشروع الذي يحتوي src أو أصلح المسار.")
    print(f"   التفاصيل: {type(e).__name__}: {e}")
