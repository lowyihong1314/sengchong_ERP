#!/usr/bin/env python3
"""
Copy the ERP-owned database from the legacy SQLite file into Postgres.

The SQLite schema stores timestamps and dates as text, money and session
expiry as float, and booleans as 0/1. The Postgres schema (revision
22688ded425d) uses real types, so this converts every value on the way across
rather than migrating the SQLite file in place.

AutoCount's SQL Server databases are not involved. Neither are the image files
under var/project-photos/ -- only the metadata rows move.

    python3 scripts/copy_to_postgres.py \\
        --source erp_data.db \\
        --target postgresql+psycopg://erp:***@127.0.0.1:5432/erp

The target must already be at head:  DATABASE_URL=... alembic upgrade head
By default the script refuses to touch a non-empty target; pass --truncate to
replace its contents.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from function.config import load_env_file  # noqa: E402
from function.services.values import parse_date, parse_datetime, parse_money  # noqa: E402
from models import db  # noqa: E402
from models.project_data import ErpProject, ErpProjectDocument  # noqa: E402
from models.project_photos import ErpProjectPhoto  # noqa: E402
from models.sengchong_content import (  # noqa: E402
    ErpWebsiteAuditLog,
    SengchongContact,
    SengchongService,
    SengchongSetting,
)
from models.sessions import ErpSession  # noqa: E402
from models.user_data import ErpUser  # noqa: E402


def _bool(value):
    return bool(value) and str(value) not in ("0", "False", "false")


def _epoch_to_datetime(value):
    from datetime import datetime, timezone

    if value in (None, ""):
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc)


# Insertion order is FK-safe: parents before children.
TABLES = [
    (
        ErpUser,
        "erp_users",
        lambda r: dict(
            username=r["username"],
            display_name=r["display_name"],
            role=r["role"],
            default_company=r["default_company"],
            password_hash=r["password_hash"],
            created_at=parse_datetime(r["created_at"]),
            updated_at=parse_datetime(r["updated_at"]),
        ),
    ),
    (
        ErpSession,
        "erp_sessions",
        lambda r: dict(
            token=r["token"],
            database_name=r["database_name"],
            username=r["username"],
            display_name=r["display_name"],
            role=r["role"],
            server=r["server"],
            expires_at=_epoch_to_datetime(r["expires_at"]),
            created_at=parse_datetime(r["created_at"]),
        ),
    ),
    (
        SengchongService,
        "sengchong_services",
        lambda r: dict(no=r["no"], service_name=r["service_name"], bg=r["bg"]),
    ),
    (
        SengchongContact,
        "sengchong_contacts",
        lambda r: dict(no=r["no"], name=r["name"], number=r["number"], bg=r["bg"]),
    ),
    (
        SengchongSetting,
        "sengchong_settings",
        lambda r: dict(
            key=r["key"], value=r["value"], updated_at=parse_datetime(r["updated_at"])
        ),
    ),
    (
        ErpProject,
        "erp_projects",
        lambda r: dict(
            id=r["id"],
            company=r["company"],
            project_code=r["project_code"],
            title=r["title"],
            debtor_code=r["debtor_code"],
            debtor_name=r["debtor_name"],
            contact_person=r["contact_person"],
            phone=r["phone"],
            site_address=r["site_address"],
            service_category=r["service_category"],
            status=r["status"],
            expected_install_date=parse_date(r["expected_install_date"]),
            completion_date=parse_date(r["completion_date"]),
            quoted_total=parse_money(r["quoted_total"]),
            collected_total=parse_money(r["collected_total"]),
            outstanding_amount=parse_money(r["outstanding_amount"]),
            estimated_cost=parse_money(r["estimated_cost"]),
            actual_cost=parse_money(r["actual_cost"]),
            notes=r["notes"],
            created_at=parse_datetime(r["created_at"]),
            updated_at=parse_datetime(r["updated_at"]),
            created_by=r["created_by"],
            updated_by=r["updated_by"],
        ),
    ),
    (
        ErpProjectDocument,
        "erp_project_documents",
        lambda r: dict(
            id=r["id"], project_id=r["project_id"], module=r["module"], doc_no=r["doc_no"]
        ),
    ),
    (
        ErpProjectPhoto,
        "erp_project_photos",
        lambda r: dict(
            id=r["id"],
            project_id=r["project_id"],
            company=r["company"],
            stored_path=r["stored_path"],
            thumbnail_path=r["thumbnail_path"],
            content_type=r["content_type"],
            original_filename=r["original_filename"],
            service_category=r["service_category"],
            caption=r["caption"],
            alt_text=r["alt_text"],
            is_public=_bool(r["is_public"]),
            website_visible=_bool(r["website_visible"]),
            is_cover=_bool(r["is_cover"]),
            sort_order=r["sort_order"],
            created_at=parse_datetime(r["created_at"]),
            updated_at=parse_datetime(r["updated_at"]),
            uploaded_by=r["uploaded_by"],
            updated_by=r["updated_by"],
        ),
    ),
    (
        ErpWebsiteAuditLog,
        "erp_website_audit_log",
        lambda r: dict(
            id=r["id"],
            company=r["company"],
            action=r["action"],
            entity_type=r["entity_type"],
            entity_id=r["entity_id"],
            project_code=r["project_code"],
            field_name=r["field_name"],
            old_value=r["old_value"],
            new_value=r["new_value"],
            username=r["username"],
            created_at=parse_datetime(r["created_at"]),
        ),
    ),
]

# Tables whose primary key is a sequence: the sequence must be moved past the
# ids we inserted explicitly, or the next insert collides.
SEQUENCE_TABLES = [("erp_project_documents", "id"), ("erp_website_audit_log", "id")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(BASE_DIR / "erp_data.db"))
    parser.add_argument("--target", default="")
    parser.add_argument("--truncate", action="store_true", help="clear the target first")
    args = parser.parse_args()

    load_env_file(BASE_DIR / ".env")
    target_url = args.target or __import__("os").getenv("DATABASE_URL", "")
    if not target_url:
        parser.error("no target: pass --target or set DATABASE_URL")
    if not target_url.startswith("postgresql"):
        parser.error(f"target must be a Postgres URL, got {target_url.split('://')[0]}")

    source = sqlite3.connect(args.source)
    source.row_factory = sqlite3.Row
    engine = create_engine(target_url)

    with Session(engine) as session:
        version = session.execute(text("select version_num from alembic_version")).scalar()
        if version != "22688ded425d":
            raise SystemExit(
                f"target is at revision {version!r}; run `alembic upgrade head` first"
            )

        existing = {
            table: session.scalar(select(func.count()).select_from(model))
            for model, table, _ in TABLES
        }
        if any(existing.values()):
            if not args.truncate:
                rows = ", ".join(f"{t}={n}" for t, n in existing.items() if n)
                raise SystemExit(f"target is not empty ({rows}); pass --truncate to replace")
            for model, table, _ in reversed(TABLES):
                session.execute(db.delete(model))
            session.flush()

        copied = {}
        for model, table, to_kwargs in TABLES:
            rows = source.execute(f'select * from "{table}"').fetchall()
            session.add_all(model(**to_kwargs(row)) for row in rows)
            session.flush()
            copied[table] = len(rows)
            print(f"  {table:26} {len(rows):5} rows")

        for table, column in SEQUENCE_TABLES:
            session.execute(
                text(
                    f"select setval(pg_get_serial_sequence('{table}', '{column}'), "
                    f"coalesce((select max({column}) from {table}), 0) + 1, false)"
                )
            )

        session.commit()

    # verify counts round-trip
    failures = []
    with Session(engine) as session:
        for model, table, _ in TABLES:
            target_count = session.scalar(select(func.count()).select_from(model))
            source_count = source.execute(f'select count(*) from "{table}"').fetchone()[0]
            if target_count != source_count:
                failures.append(f"{table}: sqlite={source_count} postgres={target_count}")

    print(f"\ncopied {sum(copied.values())} rows across {len(TABLES)} tables")
    if failures:
        print("ROW COUNT MISMATCH:\n  " + "\n  ".join(failures))
        return 1
    print("row counts match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
