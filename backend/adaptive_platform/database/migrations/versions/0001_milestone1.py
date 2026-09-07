"""Create Milestone 1 persistence schema and immutability guards."""

from collections.abc import Sequence

from adaptive_platform.database.models import Base
from alembic import op

revision: str = "0001_milestone1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE FUNCTION aaep_prevent_completed_scan_mutation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'COMPLETED' THEN
                RAISE EXCEPTION 'completed repository scans are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER aaep_repository_scans_immutable
        BEFORE UPDATE OR DELETE ON repository_scans
        FOR EACH ROW EXECUTE FUNCTION aaep_prevent_completed_scan_mutation();

        CREATE FUNCTION aaep_prevent_completed_file_mutation() RETURNS trigger AS $$
        DECLARE
            target_scan_id uuid;
        BEGIN
            target_scan_id := CASE WHEN TG_OP = 'INSERT' THEN NEW.scan_id ELSE OLD.scan_id END;
            IF EXISTS (
                SELECT 1 FROM repository_scans
                WHERE id = target_scan_id AND status = 'COMPLETED'
            ) THEN
                RAISE EXCEPTION 'files belonging to completed scans are immutable';
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER aaep_repository_files_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON repository_files
        FOR EACH ROW EXECUTE FUNCTION aaep_prevent_completed_file_mutation();

        CREATE FUNCTION aaep_prevent_trace_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'trace events are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER aaep_trace_events_append_only
        BEFORE UPDATE OR DELETE ON trace_events
        FOR EACH ROW EXECUTE FUNCTION aaep_prevent_trace_mutation();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            DROP TRIGGER IF EXISTS aaep_trace_events_append_only ON trace_events;
            DROP FUNCTION IF EXISTS aaep_prevent_trace_mutation();
            DROP TRIGGER IF EXISTS aaep_repository_files_immutable ON repository_files;
            DROP FUNCTION IF EXISTS aaep_prevent_completed_file_mutation();
            DROP TRIGGER IF EXISTS aaep_repository_scans_immutable ON repository_scans;
            DROP FUNCTION IF EXISTS aaep_prevent_completed_scan_mutation();
            """
        )
    Base.metadata.drop_all(bind=op.get_bind())
