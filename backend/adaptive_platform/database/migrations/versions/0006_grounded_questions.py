"""Add immutable M4 context packages, grounded answers, and claim evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0006_grounded_questions"
down_revision: str | None = "0005_context_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _index_names(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def _create_indexes(table: str, indexes: dict[str, list[str]]) -> None:
    existing = _index_names(table)
    for name, columns in indexes.items():
        if name not in existing:
            op.create_index(name, table, columns)


def upgrade() -> None:
    if not _has_table("question_tasks"):
        op.create_table(
            "question_tasks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("repository_id", sa.Uuid(), nullable=False),
            sa.Column("scan_id", sa.Uuid(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("canonical_question", sa.Text(), nullable=False),
            sa.Column("query_class", sa.String(length=32), nullable=False),
            sa.Column("query_intent", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("context_hash", sa.String(length=64), nullable=True),
            sa.Column("cache_key", sa.String(length=64), nullable=False),
            sa.Column("cache_status", sa.String(length=16), nullable=False),
            sa.Column("cached_from_task_id", sa.Uuid(), nullable=True),
            sa.Column("classifier_version", sa.String(length=64), nullable=False),
            sa.Column("assembler_version", sa.String(length=64), nullable=False),
            sa.Column("validator_version", sa.String(length=64), nullable=False),
            sa.Column("failure_code", sa.String(length=64), nullable=True),
            sa.Column("failure_message", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.CheckConstraint(
                "query_class IN ('EXACT_SYMBOL', 'STRUCTURAL', 'LOCATION', "
                "'GENERAL_STRUCTURAL', 'UNSUPPORTED')",
                name="ck_question_tasks_query_class",
            ),
            sa.CheckConstraint(
                "status IN ('PENDING', 'RUNNING', 'ANSWERED', 'PARTIAL', 'ABSTAINED', 'FAILED')",
                name="ck_question_tasks_status",
            ),
            sa.CheckConstraint(
                "cache_status IN ('MISS', 'HIT', 'NOT_CACHEABLE')",
                name="ck_question_tasks_cache_status",
            ),
            sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["scan_id"], ["repository_scans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["cached_from_task_id"], ["question_tasks.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_indexes(
        "question_tasks",
        {
            "ix_question_tasks_repository_id": ["repository_id"],
            "ix_question_tasks_scan_id": ["scan_id"],
            "ix_question_tasks_cached_from_task_id": ["cached_from_task_id"],
            "ix_question_tasks_scan_canonical": ["scan_id", "canonical_question"],
            "ix_question_tasks_cache_key": ["cache_key"],
        },
    )

    if not _has_table("context_packages"):
        op.create_table(
            "context_packages",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("repository_id", sa.Uuid(), nullable=False),
            sa.Column("scan_id", sa.Uuid(), nullable=False),
            sa.Column("slots", sa.JSON(), nullable=False),
            sa.Column("unfillable", sa.JSON(), nullable=False),
            sa.Column("assembly_log", sa.JSON(), nullable=False),
            sa.Column("canonical_package", sa.JSON(), nullable=False),
            sa.Column("item_count", sa.Integer(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("token_budget", sa.Integer(), nullable=False),
            sa.Column("render_strategy", sa.String(length=32), nullable=False),
            sa.Column("context_hash", sa.String(length=64), nullable=False),
            sa.Column("assembler_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("item_count >= 0", name="ck_context_packages_item_count"),
            sa.CheckConstraint(
                "token_count >= 0 AND token_budget > 0",
                name="ck_context_packages_token_budget",
            ),
            sa.ForeignKeyConstraint(["task_id"], ["question_tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["scan_id"], ["repository_scans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id"),
        )
    _create_indexes(
        "context_packages",
        {
            "ix_context_packages_task_id": ["task_id"],
            "ix_context_packages_repository_id": ["repository_id"],
            "ix_context_packages_scan_id": ["scan_id"],
            "ix_context_packages_context_hash": ["context_hash"],
        },
    )

    if not _has_table("answers"):
        op.create_table(
            "answers",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("answer_text", sa.Text(), nullable=True),
            sa.Column("confidence", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("validator_version", sa.String(length=64), nullable=False),
            sa.Column("gaps", sa.JSON(), nullable=False),
            sa.Column("response_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('ANSWERED', 'PARTIAL', 'ABSTAINED', 'FAILED')",
                name="ck_answers_status",
            ),
            sa.CheckConstraint(
                "confidence IN ('DETERMINISTIC', 'HIGH', 'MEDIUM', 'LOW', 'NONE')",
                name="ck_answers_confidence",
            ),
            sa.ForeignKeyConstraint(["task_id"], ["question_tasks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id"),
        )
    _create_indexes("answers", {"ix_answers_task_id": ["task_id"]})

    if not _has_table("claims"):
        op.create_table(
            "claims",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("answer_id", sa.Uuid(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("claim_type", sa.String(length=64), nullable=False),
            sa.Column("importance", sa.String(length=16), nullable=False),
            sa.Column("verdict", sa.String(length=16), nullable=False),
            sa.Column("qualifier_metadata", sa.JSON(), nullable=False),
            sa.CheckConstraint(
                "importance IN ('ESSENTIAL', 'OPTIONAL')", name="ck_claims_importance"
            ),
            sa.CheckConstraint(
                "verdict IN ('SUPPORTED', 'INFERENCE', 'UNSUPPORTED', 'CONFLICTING')",
                name="ck_claims_verdict",
            ),
            sa.CheckConstraint("position >= 0", name="ck_claims_position"),
            sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("answer_id", "position", name="uq_claims_answer_position"),
        )
    _create_indexes("claims", {"ix_claims_answer_id": ["answer_id"]})

    if not _has_table("claim_evidence"):
        op.create_table(
            "claim_evidence",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("claim_id", sa.Uuid(), nullable=False),
            sa.Column("file_id", sa.Uuid(), nullable=True),
            sa.Column("ref_type", sa.String(length=32), nullable=False),
            sa.Column("evidence_ref", sa.String(length=255), nullable=False),
            sa.Column("evidence_type", sa.String(length=64), nullable=False),
            sa.Column("provenance", sa.String(length=32), nullable=False),
            sa.Column("start_line", sa.Integer(), nullable=True),
            sa.Column("end_line", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "ref_type IN ('SOURCE_SPAN', 'SYMBOL', 'RELATIONSHIP', "
                "'CONTEXT_DOCUMENT', 'SCAN_FACT', 'LANGUAGE_PROFILE', "
                "'RETRIEVAL_RESULT')",
                name="ck_claim_evidence_ref_type",
            ),
            sa.CheckConstraint(
                "(start_line IS NULL AND end_line IS NULL) OR "
                "(start_line >= 1 AND end_line >= start_line)",
                name="ck_claim_evidence_span",
            ),
            sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["file_id"], ["repository_files.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_indexes(
        "claim_evidence",
        {
            "ix_claim_evidence_claim_id": ["claim_id"],
            "ix_claim_evidence_file_id": ["file_id"],
        },
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION aaep_prevent_grounded_artifact_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'grounded answer artifacts are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table in ("context_packages", "answers", "claims", "claim_evidence"):
            op.execute(f"DROP TRIGGER IF EXISTS aaep_{table}_immutable ON {table}")
            op.execute(
                f"CREATE TRIGGER aaep_{table}_immutable "
                f"BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW "
                "EXECUTE FUNCTION aaep_prevent_grounded_artifact_mutation()"
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    for table in ("claim_evidence", "claims", "answers", "context_packages"):
        if not _has_table(table):
            continue
        if dialect == "postgresql":
            op.execute(f"DROP TRIGGER IF EXISTS aaep_{table}_immutable ON {table}")
        op.drop_table(table)
    if _has_table("question_tasks"):
        op.drop_table("question_tasks")
    if dialect == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS aaep_prevent_grounded_artifact_mutation()")
