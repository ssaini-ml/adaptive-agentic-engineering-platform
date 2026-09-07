"""Add immutable language-neutral symbols and relationships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0003_python_evidence"
down_revision: str | None = "0002_language_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("symbols"):
        op.create_table(
            "symbols",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("scan_id", sa.Uuid(), nullable=False),
            sa.Column("file_id", sa.Uuid(), nullable=False),
            sa.Column("parent_symbol_id", sa.Uuid(), nullable=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("qualified_name", sa.Text(), nullable=False),
            sa.Column("symbol_type", sa.String(length=32), nullable=False),
            sa.Column("signature", sa.Text(), nullable=True),
            sa.Column("docstring", sa.Text(), nullable=True),
            sa.Column("start_line", sa.Integer(), nullable=False),
            sa.Column("start_column", sa.Integer(), nullable=False),
            sa.Column("end_line", sa.Integer(), nullable=False),
            sa.Column("end_column", sa.Integer(), nullable=False),
            sa.Column("extractor_name", sa.String(length=128), nullable=False),
            sa.Column("extractor_version", sa.String(length=64), nullable=False),
            sa.Column("extension_metadata", sa.JSON(), nullable=False),
            sa.CheckConstraint(
                "symbol_type IN ('MODULE', 'CLASS', 'FUNCTION', 'METHOD', 'CONSTANT', 'ROUTE', 'MODEL')",
                name="ck_symbols_type",
            ),
            sa.CheckConstraint(
                "start_line >= 1 AND end_line >= start_line "
                "AND start_column >= 0 AND end_column >= 0",
                name="ck_symbols_span",
            ),
            sa.ForeignKeyConstraint(["file_id"], ["repository_files.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_symbol_id"], ["symbols.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["scan_id"], ["repository_scans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "scan_id",
                "qualified_name",
                "symbol_type",
                "file_id",
                "start_line",
                name="uq_symbols_scan_identity",
            ),
        )
        op.create_index("ix_symbols_scan_id", "symbols", ["scan_id"])
        op.create_index("ix_symbols_file_id", "symbols", ["file_id"])
        op.create_index("ix_symbols_parent_symbol_id", "symbols", ["parent_symbol_id"])

    if not _has_table("relationships"):
        op.create_table(
            "relationships",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("scan_id", sa.Uuid(), nullable=False),
            sa.Column("source_kind", sa.String(length=16), nullable=False),
            sa.Column("source_id", sa.Uuid(), nullable=False),
            sa.Column("target_kind", sa.String(length=16), nullable=False),
            sa.Column("target_id", sa.Uuid(), nullable=True),
            sa.Column("unresolved_target", sa.Text(), nullable=True),
            sa.Column("relationship_type", sa.String(length=32), nullable=False),
            sa.Column("resolution_status", sa.String(length=32), nullable=False),
            sa.Column("resolution_reason", sa.String(length=128), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("evidence_type", sa.String(length=64), nullable=False),
            sa.Column("provenance", sa.String(length=32), nullable=False),
            sa.Column("evidence_file_id", sa.Uuid(), nullable=False),
            sa.Column("evidence_start_line", sa.Integer(), nullable=False),
            sa.Column("evidence_start_column", sa.Integer(), nullable=False),
            sa.Column("evidence_end_line", sa.Integer(), nullable=False),
            sa.Column("evidence_end_column", sa.Integer(), nullable=False),
            sa.Column("extractor_name", sa.String(length=128), nullable=False),
            sa.Column("extractor_version", sa.String(length=64), nullable=False),
            sa.Column("extension_metadata", sa.JSON(), nullable=False),
            sa.CheckConstraint("source_kind = 'SYMBOL'", name="ck_relationships_source_kind"),
            sa.CheckConstraint("target_kind = 'SYMBOL'", name="ck_relationships_target_kind"),
            sa.CheckConstraint(
                "relationship_type IN ('DEFINES', 'IMPORTS', 'REFERENCES', 'INHERITS', 'EXPOSES', 'TESTS')",
                name="ck_relationships_type",
            ),
            sa.CheckConstraint(
                "resolution_status IN ('RESOLVED', 'PARTIALLY_RESOLVED', 'HEURISTIC', 'UNRESOLVED', 'AMBIGUOUS')",
                name="ck_relationships_resolution_status",
            ),
            sa.CheckConstraint(
                "confidence >= 0 AND confidence <= 1", name="ck_relationships_confidence"
            ),
            sa.CheckConstraint(
                "evidence_start_line >= 1 AND evidence_end_line >= evidence_start_line "
                "AND evidence_start_column >= 0 AND evidence_end_column >= 0",
                name="ck_relationships_span",
            ),
            sa.CheckConstraint(
                "(target_id IS NOT NULL AND unresolved_target IS NULL) OR "
                "(target_id IS NULL AND unresolved_target IS NOT NULL)",
                name="ck_relationships_target_xor_unresolved",
            ),
            sa.CheckConstraint(
                "resolution_status != 'UNRESOLVED' OR resolution_reason IS NOT NULL",
                name="ck_relationships_unresolved_reason",
            ),
            sa.ForeignKeyConstraint(
                ["evidence_file_id"], ["repository_files.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["scan_id"], ["repository_scans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_id"], ["symbols.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_id"], ["symbols.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_relationships_scan_id", "relationships", ["scan_id"])
        op.create_index("ix_relationships_source_id", "relationships", ["source_id"])
        op.create_index("ix_relationships_target_id", "relationships", ["target_id"])
        op.create_index("ix_relationships_evidence_file_id", "relationships", ["evidence_file_id"])

    if op.get_bind().dialect.name == "postgresql":
        _install_postgresql_guards()


def _install_postgresql_guards() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aaep_prevent_completed_evidence_mutation()
        RETURNS trigger AS $$
        DECLARE
            target_scan_id uuid;
        BEGIN
            target_scan_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.scan_id ELSE OLD.scan_id END;
            IF EXISTS (
                SELECT 1 FROM repository_scans
                WHERE id = target_scan_id AND status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'evidence belonging to completed scans is immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("symbols", "relationships"):
        trigger = f"aaep_{table}_immutable"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION aaep_prevent_completed_evidence_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("relationships", "symbols"):
            if _has_table(table):
                op.execute(f"DROP TRIGGER IF EXISTS aaep_{table}_immutable ON {table}")
        op.execute("DROP FUNCTION IF EXISTS aaep_prevent_completed_evidence_mutation()")
    if _has_table("relationships"):
        op.drop_table("relationships")
    if _has_table("symbols"):
        op.drop_table("symbols")
