"""Add scan-bound indexes for exact lookup and graph traversal."""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

revision: str = "0004_retrieval_indexes"
down_revision: str | None = "0003_python_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYMBOL_INDEXES = {
    "ix_symbols_scan_qualified_name": ["scan_id", "qualified_name"],
    "ix_symbols_scan_name": ["scan_id", "name"],
    "ix_symbols_scan_type": ["scan_id", "symbol_type"],
}
RELATIONSHIP_INDEXES = {
    "ix_relationships_scan_source_type": ["scan_id", "source_id", "relationship_type"],
    "ix_relationships_scan_target_type": ["scan_id", "target_id", "relationship_type"],
}


def _index_names(table: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table):
        return set()
    return {item["name"] for item in inspector.get_indexes(table)}


def upgrade() -> None:
    for table, indexes in (("symbols", SYMBOL_INDEXES), ("relationships", RELATIONSHIP_INDEXES)):
        existing = _index_names(table)
        for name, columns in indexes.items():
            if name not in existing:
                op.create_index(name, table, columns)


def downgrade() -> None:
    for table, indexes in (
        ("relationships", RELATIONSHIP_INDEXES),
        ("symbols", SYMBOL_INDEXES),
    ):
        existing = _index_names(table)
        for name in indexes:
            if name in existing:
                op.drop_index(name, table_name=table)
