"""tighten column types for postgres

The baseline schema mirrored what SQLite accepted: timestamps and dates as
text, money and session expiry as float, booleans as 0/1 integers. Postgres
can hold the real types, so this revision converts them.

Every ALTER carries an explicit USING clause. Postgres has no implicit cast
from varchar to timestamptz, from double precision to timestamptz, or from
integer to boolean, so without USING these statements fail -- on an empty
table as well as a populated one.

This revision is Postgres-only by design. The legacy SQLite file is not
migrated in place; it is read by scripts/copy_to_postgres.py, which converts
the values as it copies them. Running this against SQLite raises rather than
silently producing a database whose text columns no longer parse.

Revision ID: 22688ded425d
Revises: 8cc3e9a9bd3f
Create Date: 2026-08-01 10:32:48.349389
"""
from typing import Sequence, Union

from alembic import op


revision: str = "22688ded425d"
down_revision: Union[str, Sequence[str], None] = "8cc3e9a9bd3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP_COLUMNS = [
    ("erp_users", "created_at"),
    ("erp_users", "updated_at"),
    ("erp_sessions", "created_at"),
    ("erp_projects", "created_at"),
    ("erp_projects", "updated_at"),
    ("erp_project_photos", "created_at"),
    ("erp_project_photos", "updated_at"),
    ("erp_website_audit_log", "created_at"),
    ("sengchong_settings", "updated_at"),
]
MONEY_COLUMNS = [
    ("erp_projects", "quoted_total"),
    ("erp_projects", "collected_total"),
    ("erp_projects", "outstanding_amount"),
    ("erp_projects", "estimated_cost"),
    ("erp_projects", "actual_cost"),
]
DATE_COLUMNS = [
    ("erp_projects", "expected_install_date"),
    ("erp_projects", "completion_date"),
]
BOOLEAN_COLUMNS = [
    ("erp_project_photos", "is_public"),
    ("erp_project_photos", "website_visible"),
    ("erp_project_photos", "is_cover"),
]


def _require_postgres():
    dialect = op.get_bind().dialect.name
    if dialect != "postgresql":
        raise RuntimeError(
            f"Revision 22688ded425d is Postgres-only (got dialect {dialect!r}). "
            "To move the legacy SQLite database, run scripts/copy_to_postgres.py "
            "against a Postgres database that is already at this revision."
        )


def upgrade() -> None:
    _require_postgres()

    for table, column in TIMESTAMP_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamptz "
            f"USING {column}::timestamptz"
        )

    # Session expiry moves from unix epoch seconds to a real instant.
    op.execute(
        "ALTER TABLE erp_sessions ALTER COLUMN expires_at TYPE timestamptz "
        "USING to_timestamp(expires_at)"
    )

    for table, column in MONEY_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE numeric(14, 2) "
            f"USING {column}::numeric(14, 2)"
        )

    # "" has always meant "no date"; it is not a valid DATE, so it becomes NULL.
    for table, column in DATE_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE date "
            f"USING NULLIF(btrim({column}), '')::date"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL")

    for table, column in BOOLEAN_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE boolean "
            f"USING ({column} <> 0)"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT false")


def downgrade() -> None:
    _require_postgres()

    for table, column in BOOLEAN_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE integer "
            f"USING ({column})::integer"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT 0")

    for table, column in DATE_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE varchar(20) "
            f"USING COALESCE(to_char({column}, 'YYYY-MM-DD'), '')"
        )
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT ''")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")

    for table, column in MONEY_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE double precision "
            f"USING ({column})::double precision"
        )

    op.execute(
        "ALTER TABLE erp_sessions ALTER COLUMN expires_at TYPE double precision "
        "USING extract(epoch from expires_at)"
    )

    for table, column in TIMESTAMP_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE varchar(40) "
            f"USING to_char({column} AT TIME ZONE 'UTC', "
            "'YYYY-MM-DD\"T\"HH24:MI:SS') || '+00:00'"
        )
