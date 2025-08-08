"""
Add critical indexes for performance on messages and conversations tables
"""

# Alembic identifiers
revision = "20250808_add_critical_indexes"
down_revision = None  # ضع رقم الهجرة السابقة هنا إذا كان هناك هجرات سابقة
branch_labels = None
depends_on = None


from alembic import op


def upgrade():
    # فقط إنشاء الامتداد pg_trgm (آمن داخل المعاملة)
    op.execute(
        """
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """
    )


def downgrade():
    # لا تحذف الفهارس هنا (تم إنشاؤها يدويًا)
    # Note: Do not drop pg_trgm extension automatically (may be used elsewhere)
    pass
