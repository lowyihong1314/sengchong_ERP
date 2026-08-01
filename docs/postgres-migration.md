# Postgres Migration

Status: **done**. `erp_data.db` now runs on Postgres 18. This document is the
record of how, and how to redo it on another machine.

AutoCount's SQL Server databases were not part of this and were not touched.
They are still read through `function/services/sql_reader.py` and written
through the AutoCount SDK.

## Layout

- Server: PostgreSQL 18, local, port 5432
- Role `erp`, database `erp` owned by it
- Connection string lives in `.env` as `DATABASE_URL` (gitignored)
- `function/config.py` reads it; `migrations/env.py` reads the same variable,
  so app and migrations can never drift apart

```bash
DATABASE_URL=postgresql+psycopg://erp:<password>@127.0.0.1:5432/erp
```

Leave `DATABASE_URL` unset and the app falls back to the local SQLite file --
useful for a throwaway copy, not for production.

## Column types

Revision `22688ded425d` converted the columns the SQLite schema had only
approximated:

| Column | Was | Now |
|---|---|---|
| every `created_at` / `updated_at` | `varchar(40)` ISO text | `timestamptz` |
| `erp_sessions.expires_at` | `double precision` unix epoch | `timestamptz` |
| `erp_projects.expected_install_date`, `.completion_date` | `varchar(20)`, `''` = unset | `date NULL` |
| the five `erp_projects` money columns | `double precision` | `numeric(14,2)` |
| `erp_project_photos.is_public`, `.website_visible`, `.is_cover` | `integer` 0/1 | `boolean` |

Every `ALTER` in that revision carries an explicit `USING` clause. Postgres has
no implicit cast from varchar to timestamptz, from double precision to
timestamptz, or from integer to boolean, so without one the statements fail --
on an empty table as well as a populated one.

The revision is Postgres-only and raises on any other dialect. The legacy
SQLite file was never migrated in place; `scripts/copy_to_postgres.py`
converted values as it copied them.

**The JSON API did not change.** Timestamps still serialise as ISO 8601 with an
offset, an unset date is still `""`, money is still a JSON number, and the
boolean flags still come out as `true`/`false`. All of that conversion lives in
`function/services/values.py`, and it is the reason the frontend needed no
change at all.

## Redoing it elsewhere

```bash
sudo apt-get install -y postgresql postgresql-contrib
sudo -u postgres psql -c "CREATE ROLE erp LOGIN PASSWORD '<generate one>';"
sudo -u postgres createdb -O erp erp

export DATABASE_URL="postgresql+psycopg://erp:<password>@127.0.0.1:5432/erp"
python3 -m alembic upgrade head          # builds the schema, already tightened
python3 scripts/copy_to_postgres.py      # moves the rows, converting as it goes

systemctl --user restart erp-gateway.service
```

`copy_to_postgres.py` refuses to write into a target that already has rows
unless you pass `--truncate`, checks the target is at revision `22688ded425d`
first, and compares row counts per table afterwards.

## Things that bit, or would have

- **Sequences.** `erp_project_documents.id` and `erp_website_audit_log.id` are
  identity columns. Rows were copied with explicit ids, so the copy script runs
  `setval` afterwards; without it the next insert collides on the primary key.
- **`sengchong_settings.key`** is a column literally named `key`. Legal in
  Postgres, but quote it in any hand-written SQL.
- **`var/project-photos/`** stays on the filesystem. Only metadata rows moved.
- **SQLite could not hold these types.** `DateTime(timezone=True)` silently
  loses the offset there, which would have broken the ISO strings the API
  returns. That is why the tightening is Postgres-only rather than a shared
  migration.

## Verification that was run

- Fresh-from-migration schema diffed against the live one: same tables,
  columns, foreign keys, unique constraints, named indexes.
- `downgrade` then `upgrade` round-tripped cleanly.
- 48 API payloads (142 records) captured from SQLite before the change and from
  Postgres after: **byte-identical**.
- 25 write-path checks on Postgres: money rounding, `""` to NULL dates and
  back, margin arithmetic, boolean publish/unpublish cascades, single-cover
  enforcement, audit entries, session expiry.
- Row counts per table match between the two databases.

## Rollback

The pre-cutover SQLite file is kept as `erp_data.db.bak-pre-pg-<timestamp>`.
To go back, comment out `DATABASE_URL` in `.env` and restart -- but note that
anything written since the cutover lives only in Postgres.
