"""
Update children table schema to match current model (idempotent, production-safe)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "20250920_update_children_schema"
down_revision = "20250808_add_critical_indexes"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_index(inspector, table: str, index_name: str) -> bool:
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) Add/align columns (only if missing)
    if not _has_column(insp, "children", "birth_date"):
        op.add_column("children", sa.Column("birth_date", sa.DateTime(timezone=True), nullable=True))

    if not _has_column(insp, "children", "hashed_identifier"):
        op.add_column("children", sa.Column("hashed_identifier", sa.String(length=64), nullable=True))

    for col, coltype in (
        ("consent_date", sa.DateTime(timezone=True)),
        ("consent_withdrawn_date", sa.DateTime(timezone=True)),
        ("age_verified", sa.Boolean()),
        ("age_verification_date", sa.DateTime(timezone=True)),
        ("estimated_age", sa.Integer()),
        ("content_filtering_enabled", sa.Boolean()),
        ("interaction_logging_enabled", sa.Boolean()),
        ("data_retention_days", sa.Integer()),
        ("allow_data_sharing", sa.Boolean()),
    ):
        if not _has_column(insp, "children", col):
            op.add_column("children", sa.Column(col, coltype, nullable=True))

    # JSONB fields
    if not _has_column(insp, "children", "favorite_topics"):
        op.add_column(
            "children",
            sa.Column("favorite_topics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    # Handle legacy preferences -> content_preferences
    has_content_prefs = _has_column(insp, "children", "content_preferences")
    if not has_content_prefs:
        op.add_column(
            "children",
            sa.Column("content_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        # Try backfill from legacy 'preferences' if it exists
        if _has_column(insp, "children", "preferences"):
            op.execute(
                "UPDATE children SET content_preferences = preferences::jsonb WHERE preferences IS NOT NULL"
            )

    # 2) Create safety_level enum + column
    if not _has_column(insp, "children", "safety_level"):
        safety_level_enum = postgresql.ENUM("safe", "review", "blocked", name="safetylevel")
        safety_level_enum.create(bind, checkfirst=True)
        op.add_column(
            "children",
            sa.Column(
                "safety_level",
                safety_level_enum,
                server_default=sa.text("'safe'"),
                nullable=False,
            ),
        )
        op.alter_column("children", "safety_level", server_default=None)

    # 3) Backfill sensible defaults for new columns
    op.execute(
        "UPDATE children SET age_verified = false WHERE age_verified IS NULL"
    )
    op.execute(
        "UPDATE children SET content_filtering_enabled = true WHERE content_filtering_enabled IS NULL"
    )
    op.execute(
        "UPDATE children SET interaction_logging_enabled = true WHERE interaction_logging_enabled IS NULL"
    )
    op.execute(
        "UPDATE children SET data_retention_days = 90 WHERE data_retention_days IS NULL"
    )
    op.execute(
        "UPDATE children SET allow_data_sharing = false WHERE allow_data_sharing IS NULL"
    )
    # If legacy 'age' exists, copy to estimated_age
    if _has_column(insp, "children", "age"):
        op.execute(
            "UPDATE children SET estimated_age = age WHERE estimated_age IS NULL AND age IS NOT NULL"
        )
    # Initialize JSON defaults if still null
    op.execute(
        "UPDATE children SET favorite_topics = '[]'::jsonb WHERE favorite_topics IS NULL"
    )
    op.execute(
        "UPDATE children SET content_preferences = '{}'::jsonb WHERE content_preferences IS NULL"
    )

    # 4) hashed_identifier: backfill and enforce uniqueness
    op.execute(
        "UPDATE children SET hashed_identifier = lower(replace(id::text,'-','')) WHERE hashed_identifier IS NULL"
    )
    # Enforce NOT NULL
    op.alter_column("children", "hashed_identifier", nullable=False)
    # Unique index (idempotent via IF NOT EXISTS)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_children_hashed_identifier ON children (hashed_identifier)"
    )

    # 5) Indexes (idempotent, align with model)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_children_parent_id ON children (parent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_children_hashed_identifier ON children (hashed_identifier)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_children_safety_level ON children (safety_level)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_children_consent ON children (parental_consent)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_children_retention_status ON children (retention_status)"
    )
    # Optional: hash index for fast equality lookups on hashed_identifier
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_children_hash_lookup ON children USING hash (hashed_identifier)"
    )


def downgrade():
    # Minimal, non-destructive downgrade (keeps data)
    bind = op.get_bind()
    # Drop created indexes (if present)
    for ix in (
        "idx_children_hash_lookup",
        "idx_children_retention_status",
        "idx_children_consent",
        "idx_children_safety_level",
        "idx_children_hashed_identifier",
        "uq_children_hashed_identifier",
        "idx_children_parent_id",
    ):
        op.execute(f"DROP INDEX IF EXISTS {ix}")
    # Do not drop columns in downgrade to avoid data loss
    # Optionally drop enum type if unused
    # Enum type retained to preserve data; downgrade keeps column and type.
