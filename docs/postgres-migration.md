# Postgres Migration

Target: move `erp_data.db` (ERP-owned data only) from SQLite to Postgres.

AutoCount's SQL Server databases are **not** part of this. They stay where they
are, read through `function/sql_reader.py` and written through the AutoCount SDK.
Nothing in this document touches `AED_SENG`, `AED_MANSON`, or `sqlserver-backups/`.

## What is already in place

- `models/` holds every ERP-owned table as a SQLAlchemy model.
- Alembic owns the schema. Baseline revision: `8cc3e9a9bd3f`.
- The database URL is read from `DATABASE_URL` in one place
  (`function/config.py`), used by both the app and `migrations/env.py`.
  Switching engines is a config change, not a code change.

So the move itself is:

```bash
# 1. create the database, then point both app and migrations at it
export DATABASE_URL="postgresql+psycopg://erp:***@127.0.0.1/erp"

# 2. build the schema from scratch
python3 -m alembic upgrade head

# 3. copy the rows across (see "Data copy" below)

# 4. restart
systemctl --user restart erp-gateway.service
```

## Type changes to make first

The current columns mirror what SQLite accepted. SQLite ignores declared types,
Postgres does not, so these should be tightened in a migration **before** the
data is copied. Each one is a separate, reviewable Alembic revision.

| Table.column | Now | Should become | Why it is not done yet |
|---|---|---|---|
| every `created_at` / `updated_at` | `VARCHAR(40)` holding ISO 8601 with offset | `TIMESTAMP WITH TIME ZONE` | Values already parse cleanly; needs the DAO layer to stop formatting strings by hand. |
| `erp_sessions.expires_at` | `FLOAT` unix epoch | `TIMESTAMP WITH TIME ZONE` | Expiry is compared numerically in `function/sessions.py`. |
| `erp_projects.expected_install_date`, `.completion_date` | `VARCHAR(20)`, `''` means unset | `DATE NULL` | `''` is not a valid `DATE`; every read/write site must learn to use `None`. |
| `erp_projects.quoted_total` and the other four money columns | `FLOAT` | `NUMERIC(14,2)` | Float is wrong for money. Values are small enough that nothing has drifted yet. |
| `erp_project_photos.is_public`, `.website_visible`, `.is_cover` | `INTEGER` 0/1 | `BOOLEAN` | The API serialises these as ints today. |

None of these are urgent for SQLite. All of them are worth doing before the
Postgres cutover, because fixing them afterwards means a second data migration.

## Data copy

Row counts are small (low hundreds), so a straight SQLAlchemy copy is enough --
no need for `pg_dump`/CSV plumbing.

```python
# scripts/copy_to_postgres.py (not written yet)
# read every model from the SQLite engine, bulk-insert into the Postgres engine
# in FK-safe order: erp_users, erp_sessions, sengchong_*, erp_projects,
# erp_project_documents, erp_project_photos, erp_website_audit_log
```

Verify after the copy by comparing `SELECT count(*)` per table, and by opening
each ERP module in the browser.

## Things that will bite

- **`sengchong_settings.key`** is a column named `key`. Legal in Postgres but it
  reads badly in raw SQL; quote it or rename it during the move.
- **Autoincrement.** `erp_project_documents.id` and `erp_website_audit_log.id`
  become `SERIAL`/identity columns. After copying rows with explicit ids, the
  sequence must be reset with `setval`, or the next insert collides.
- **`var/project-photos/`** stays on the filesystem. Only the metadata rows move.
- **Concurrency.** SQLite is why `gunicorn --workers 2` was safe to begin with
  (sessions live in the DB). Postgres does not change that, but it does make
  raising the worker count worthwhile.
