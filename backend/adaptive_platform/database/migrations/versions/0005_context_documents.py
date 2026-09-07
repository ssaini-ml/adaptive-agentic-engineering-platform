"""Add immutable scan-bound documents for PostgreSQL full-text retrieval."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "0005_context_documents"
down_revision: str | None = "0004_retrieval_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _index_names(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if not _has_table("context_documents"):
        search_vector_type: sa.types.TypeEngine[object]
        search_vector_type = postgresql.TSVECTOR() if dialect == "postgresql" else sa.Text()
        op.create_table(
            "context_documents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("scan_id", sa.Uuid(), nullable=False),
            sa.Column("file_id", sa.Uuid(), nullable=False),
            sa.Column("symbol_id", sa.Uuid(), nullable=True),
            sa.Column("document_type", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("search_vector", search_vector_type, nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("start_line", sa.Integer(), nullable=False),
            sa.Column("end_line", sa.Integer(), nullable=False),
            sa.CheckConstraint(
                "document_type IN ('MODULE', 'CLASS', 'FUNCTION', 'METHOD', 'TEST', "
                "'DOCUMENTATION_SECTION', 'CONFIGURATION_SECTION')",
                name="ck_context_documents_type",
            ),
            sa.CheckConstraint(
                "start_line >= 1 AND end_line >= start_line",
                name="ck_context_documents_span",
            ),
            sa.ForeignKeyConstraint(["file_id"], ["repository_files.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["scan_id"], ["repository_scans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {
        "ix_context_documents_scan_id": ["scan_id"],
        "ix_context_documents_file_id": ["file_id"],
        "ix_context_documents_symbol_id": ["symbol_id"],
        "ix_context_documents_scan_type": ["scan_id", "document_type"],
        "ix_context_documents_scan_file": ["scan_id", "file_id"],
    }
    existing = _index_names("context_documents")
    for name, columns in indexes.items():
        if name not in existing:
            op.create_index(name, "context_documents", columns)
    if "ix_context_documents_search_vector" not in existing:
        op.create_index(
            "ix_context_documents_search_vector",
            "context_documents",
            ["search_vector"],
            postgresql_using="gin" if dialect == "postgresql" else None,
        )

    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS aaep_context_documents_immutable ON context_documents")
        op.execute(
            """
            CREATE TRIGGER aaep_context_documents_immutable
            BEFORE INSERT OR UPDATE OR DELETE ON context_documents
            FOR EACH ROW EXECUTE FUNCTION aaep_prevent_completed_evidence_mutation()
            """
        )


def downgrade() -> None:
    if not _has_table("context_documents"):
        return
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS aaep_context_documents_immutable ON context_documents")
    op.drop_table("context_documents")
