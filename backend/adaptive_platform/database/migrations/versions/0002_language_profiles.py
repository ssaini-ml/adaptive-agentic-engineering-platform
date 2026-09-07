"""Add immutable repository language profiles and per-file detection metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0002_language_profiles"
down_revision: str | None = "0001_milestone1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("repository_files", "is_vendored"):
        op.add_column(
            "repository_files",
            sa.Column("is_vendored", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if not _has_column("repository_files", "detection_signal"):
        op.add_column(
            "repository_files",
            sa.Column("detection_signal", sa.String(length=255), nullable=True),
        )

    if not _has_table("repository_language_profiles"):
        op.create_table(
            "repository_language_profiles",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("scan_id", sa.Uuid(), nullable=False),
            sa.Column("repository_type", sa.String(length=32), nullable=False),
            sa.Column("primary_language", sa.String(length=64), nullable=True),
            sa.Column("profiler_name", sa.String(length=128), nullable=False),
            sa.Column("profiler_version", sa.String(length=64), nullable=False),
            sa.Column("configuration_version", sa.String(length=64), nullable=False),
            sa.Column("first_party_source_files", sa.Integer(), nullable=False),
            sa.Column("first_party_source_bytes", sa.BigInteger(), nullable=False),
            sa.Column("unprofiled_file_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "repository_type IN ('SINGLE_LANGUAGE', 'POLYGLOT', 'UNKNOWN')",
                name="ck_language_profiles_repository_type",
            ),
            sa.CheckConstraint(
                "first_party_source_files >= 0",
                name="ck_language_profiles_source_files",
            ),
            sa.CheckConstraint(
                "first_party_source_bytes >= 0",
                name="ck_language_profiles_source_bytes",
            ),
            sa.CheckConstraint(
                "unprofiled_file_count >= 0",
                name="ck_language_profiles_unprofiled_files",
            ),
            sa.ForeignKeyConstraint(["scan_id"], ["repository_scans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("scan_id"),
        )
        op.create_index(
            "ix_repository_language_profiles_scan_id",
            "repository_language_profiles",
            ["scan_id"],
            unique=True,
        )

    if not _has_table("repository_language_statistics"):
        op.create_table(
            "repository_language_statistics",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("profile_id", sa.Uuid(), nullable=False),
            sa.Column("language", sa.String(length=64), nullable=False),
            sa.Column("source_file_count", sa.Integer(), nullable=False),
            sa.Column("source_bytes", sa.BigInteger(), nullable=False),
            sa.Column("source_byte_percentage", sa.Float(), nullable=False),
            sa.Column("generated_file_count", sa.Integer(), nullable=False),
            sa.Column("generated_bytes", sa.BigInteger(), nullable=False),
            sa.Column("vendored_file_count", sa.Integer(), nullable=False),
            sa.Column("vendored_bytes", sa.BigInteger(), nullable=False),
            sa.Column("extractor_status", sa.String(length=16), nullable=False),
            sa.Column("extractor_name", sa.String(length=128), nullable=True),
            sa.Column("extractor_version", sa.String(length=64), nullable=True),
            sa.Column("detection_signals", sa.JSON(), nullable=False),
            sa.Column("diagnostics", sa.JSON(), nullable=False),
            sa.CheckConstraint(
                "extractor_status IN ('SUPPORTED', 'PARTIAL', 'UNSUPPORTED', 'FAILED')",
                name="ck_language_statistics_extractor_status",
            ),
            sa.CheckConstraint(
                "source_file_count >= 0 AND source_bytes >= 0 "
                "AND generated_file_count >= 0 AND generated_bytes >= 0 "
                "AND vendored_file_count >= 0 AND vendored_bytes >= 0",
                name="ck_language_statistics_nonnegative_counts",
            ),
            sa.CheckConstraint(
                "source_byte_percentage >= 0 AND source_byte_percentage <= 100",
                name="ck_language_statistics_percentage",
            ),
            sa.ForeignKeyConstraint(
                ["profile_id"],
                ["repository_language_profiles.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "profile_id",
                "language",
                name="uq_language_statistics_profile_language",
            ),
        )
        op.create_index(
            "ix_repository_language_statistics_profile_id",
            "repository_language_statistics",
            ["profile_id"],
            unique=False,
        )

    if op.get_bind().dialect.name == "postgresql":
        _install_postgresql_guards()


def _install_postgresql_guards() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aaep_prevent_completed_profile_mutation() RETURNS trigger AS $$
        DECLARE
            target_scan_id uuid;
        BEGIN
            target_scan_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.scan_id ELSE OLD.scan_id END;
            IF EXISTS (
                SELECT 1 FROM repository_scans
                WHERE id = target_scan_id AND status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'language profiles belonging to completed scans are immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS aaep_language_profiles_immutable ON repository_language_profiles")
    op.execute(
        """
        CREATE TRIGGER aaep_language_profiles_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON repository_language_profiles
        FOR EACH ROW EXECUTE FUNCTION aaep_prevent_completed_profile_mutation()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aaep_prevent_completed_language_stat_mutation()
        RETURNS trigger AS $$
        DECLARE
            target_profile_id uuid;
        BEGIN
            target_profile_id := CASE
                WHEN TG_OP = 'INSERT' THEN NEW.profile_id ELSE OLD.profile_id
            END;
            IF EXISTS (
                SELECT 1
                FROM repository_language_profiles profile
                JOIN repository_scans scan ON scan.id = profile.scan_id
                WHERE profile.id = target_profile_id AND scan.status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'language statistics belonging to completed scans are immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS aaep_language_statistics_immutable "
        "ON repository_language_statistics"
    )
    op.execute(
        """
        CREATE TRIGGER aaep_language_statistics_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON repository_language_statistics
        FOR EACH ROW EXECUTE FUNCTION aaep_prevent_completed_language_stat_mutation()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS aaep_language_statistics_immutable "
            "ON repository_language_statistics"
        )
        op.execute("DROP FUNCTION IF EXISTS aaep_prevent_completed_language_stat_mutation()")
        op.execute("DROP TRIGGER IF EXISTS aaep_language_profiles_immutable ON repository_language_profiles")
        op.execute("DROP FUNCTION IF EXISTS aaep_prevent_completed_profile_mutation()")
    if _has_table("repository_language_statistics"):
        op.drop_table("repository_language_statistics")
    if _has_table("repository_language_profiles"):
        op.drop_table("repository_language_profiles")
    if _has_column("repository_files", "detection_signal"):
        op.drop_column("repository_files", "detection_signal")
    if _has_column("repository_files", "is_vendored"):
        op.drop_column("repository_files", "is_vendored")
