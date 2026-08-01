# AutoCount ERP Gateway

Flask + Vite React gateway over AutoCount for Seng Chong Interior Design.

The UI covers projects/jobs, quotations, invoices, AR payments and deposits,
purchase orders, AP invoices/payments/deposits, cash book, bank transactions
and reconciliation, items, debtors, creditors, ERP user management, the RDP
allow-list, and the content of `sengchong.com`.

Login is against **ERP users**, stored by this application in Postgres --
not against AutoCount's own user accounts. The frontend stays on a standalone
login page until that succeeds. AutoCount is read through direct SQL, written
through the AutoCount SDK (a PowerShell bridge), and printed through its
report engine.

## Backend

```bash
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Copy `.env.example` to `.env` and put the workstation AutoCount SQL connection there. The Flask code uses those values only to create AutoCount SDK `DBSetting`; business reads still go through AutoCount SDK classes.

```bash
cp .env.example .env
```

## Backend Structure

```text
run.py            entry point; gunicorn serves run:app
models/           SQLAlchemy models, one module per domain
  __init__.py       db = SQLAlchemy()
  user_data.py      ErpUser
  employee_data.py  ErpEmployee
  salary_data.py    ErpEmployeeSalary
  work_entry.py     ErpWorkEntry
  sessions.py       ErpSession
  project_data.py   ErpProject, ErpProjectDocument
  project_photos.py ErpProjectPhoto
  sengchong_content.py  SengchongService/Contact/Setting, ErpWebsiteAuditLog
function/         the app package
  __init__.py       create_app()
  config.py         Settings.from_env()
  routes/           blueprints
  services/         AutoCount SDK bridge, SQL reader, ERP data stores
  services/values.py  DB value <-> API JSON conversions
migrations/       Alembic; head revision a935a6328250
```

`models/<name>.py` and `function/services/<name>.py` are deliberately named in
pairs: the model file describes the table, the service file holds the logic.

### Employees and users are not the same thing

`ErpUser` is a login; `ErpEmployee` is a person who works here. Most of the
workshop and installation crew never sign in, and a login can exist without an
employee (an external bookkeeper, an integration account), so the two are
joined by an optional `erp_employees.username` -- unique, and `ON DELETE SET
NULL` so removing a login does not remove the person.

Two consequences worth remembering:

- `erp_users.role` (`admin`/`user`) is an **authorisation** role: what the
  login may click. `erp_employees.position` (木工, 安装, 设计 ...) is a **job
  title**. Do not make one drive the other -- a carpenter who needs to see his
  own job sheet should not have to be an ERP admin.
- Employees are retired by setting `status` to `Resigned`, never deleted.
  Project history refers to them.

Subcontractors are not employees. They are AutoCount creditors billed through
AP invoices; recording them here would make labour cost and AP disagree.

### Payroll

`ErpEmployeeSalary` is one row per employee holding what they are paid
(`Monthly`/`Daily`/`Hourly` plus a rate -- the workshop is often day-rated
while the office is monthly), their EPF/SOCSO/tax numbers, and their bank
details. Admin only, on reads as well as writes.

No statutory amount is stored per employee. EPF, SOCSO, EIS and PCB are
Malaysian rates set by KWSP, PERKESO and LHDN, they change, and they belong in
maintained rate tables that a payroll run reads -- not copied onto every
employee row, and not hardcoded in the calculation. Those tables ship with the
payroll run screens; until then the salary screen records inputs only and
computes nothing.

`epf_contributing` and `socso_contributing` exist because not everyone
contributes, and that decision belongs to the person rather than to the rate
table.

### Overtime is per person, not per company

Everyone is day-rated, but the overtime formula is not shared:

```
hourly base = basic_rate / ot_divisor        # 8, 9 and 10 are all in use
ot pay      = ot_hours x hourly base x ot_multiplier   # 1.5, 1.75, 2.0
```

The divisor is that person's standard hours, and the multiplier that goes with
it is theirs too. Both live on their salary row.

Overnight is worse -- all four arrangements are in use here, so
`overnight_mode` selects between them:

| mode | pay |
|---|---|
| `allowance` | `nights x overnight_allowance` |
| `hourly` | `overnight_hours x hourly base x overnight_multiplier` |
| `extra_day` | `nights x basic_rate x overnight_day_factor` |
| `allowance_plus_hours` | both of the first two |

Salary Setup renders the result as a sentence (`otRuleText`) so nobody has to
reassemble the rule from four numbers.

### Timesheets

`ErpWorkEntry` is one row per person **per date per company** -- not per day.
Somebody can work for AED_SENG and AED_MANSON on the same date and each counts
a full day, so that is two rows. A row also carries the overtime and overnight
from that stint, which is how a foreman writes it down. The project link is
optional: shop tidying and errands belong to no single job.

The money is derived on read from the salary setup rather than stored, so
correcting a rate fixes the figures instead of leaving stale ones behind. A
payroll run will snapshot what it used, and that snapshot -- not this table --
is the record for a pay dispute. Somebody with no salary setup gets no
invented figures; the row is flagged unpayable with the reason.

Two ways in, because both are how it actually gets recorded: the Timesheet
list one row at a time, and Daily Entry for the whole crew on one date and
company, where clearing a row to zero deletes it.

### Database

ERP-owned data lives in Postgres. AutoCount's own SQL Server databases are never
touched by this layer -- they are read through `function/services/sql_reader.py`
and written through the AutoCount SDK.

The engine is chosen by one environment variable, read in `function/config.py`
and reused by `migrations/env.py`:

```bash
DATABASE_URL=postgresql+psycopg://erp:pass@127.0.0.1:5432/erp
```

Required, with no fallback. The schema uses `timestamptz`, `date`, `numeric`
and `boolean` columns that SQLite cannot hold faithfully, so a fallback would
quietly produce a database the app appears to accept and then reads wrong.
Starting without it raises instead.

`function/services/values.py` converts between the typed columns
(`timestamptz`, `date`, `numeric`, `boolean`) and what the JSON API exposes, so
the frontend contract is unchanged by the column types.

Schema changes go through Alembic, never through `create_all()`:

```bash
python3 -m alembic revision --autogenerate -m "add project milestone label"
python3 -m alembic upgrade head
python3 -m alembic current
python3 -m alembic downgrade -1
```

See `docs/postgres-migration.md` for the schema, the cutover, and how to redo
it on another machine.

## Frontend Structure

```text
frontend/src/
  main.jsx        entry only: mounts <App /> and loads styles.css
  App.jsx         root component: state, data loading, routing, layout
  constants.js    shared constants (project statuses/categories, storage keys, ...)
  modules.js      MODULES registry: columns, fields, and endpoints per module
  lib/            pure helpers, no JSX
    api.js         requestJson fetch wrapper
    format.js      readValue / formatValue / toNumber / clone
    normalize.js   API payload normalizers
    totals.js      line and document total calculations
    routing.js     URL <-> route conversion, module paths
    documents.js   item/debtor/project option lists, document links
    projects.js    project form drafts, document patches, cost/financial summaries
    banking.js     bank transaction filtering and reconciliation summaries
    pdf.js         PDF export labels and status
  hooks/          stateful clusters lifted out of App
    useWebsiteAdmin.js         website content, gallery, audit, preview, assets
    useAdminSettings.js        ERP users and the RDP allow-list
    useBankReconciliation.js   bank filters, selection, preview/commit
  components/     reusable panels and inputs (Sidebar, Topbar, ...)
  pages/          one file per full-page view (LoginPage, DetailPage, ...)
```

Layering is one-directional: `constants` -> `modules` -> `lib` -> `components`/`hooks` -> `pages` -> `App`. Do not import upward; that would create a cycle.

`App.jsx` keeps the state that every module shares: route, active module, list rows,
detail, form draft, and session. A cluster only moves into `hooks/` when its state is
used by one module. Each hook registers its teardown in `clusterResetRef` so
`resetWorkspaceState` can clear it on logout or company switch.

## Frontend Dev

```bash
cd frontend
npm install
npm run dev
```

Vite runs on:

```text
http://127.0.0.1:5173
```

During dev, Vite proxies `/api` to Flask on port `5000`.

## Production Build

```bash
cd frontend
npm install
npm run build
cd ..
python run.py
```

After `npm run build`, Flask serves `frontend/dist` from:

```text
http://127.0.0.1:5000
```

## systemd Service

The gateway is managed by a user-level systemd unit on port `5000`.

- Service name: `erp-gateway.service`
- Unit path: `~/.config/systemd/user/erp-gateway.service`
- WSGI entry: `run:app`
- Working directory: `/home/yukang/ERP`
- Host/port: `0.0.0.0:5000`

ERP-owned data is stored in Postgres (see `DATABASE_URL` in `.env`):

- ERP users
- Web/API sessions
- Projects/jobs and linked document numbers
- Sengchong website services, contacts, and footer settings

The unit can run multiple workers because sessions live in the database rather
than in process memory:

```ini
[Unit]
Description=AutoCount ERP Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/yukang/ERP
Environment=PORT=5000
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/yukang/.local/bin/gunicorn --workers 2 --bind 0.0.0.0:5000 run:app
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Useful commands:

```bash
systemctl --user daemon-reload
systemctl --user enable --now erp-gateway.service
systemctl --user restart erp-gateway.service
systemctl --user --no-pager --full status erp-gateway.service
journalctl --user -u erp-gateway.service -f
systemctl --user stop erp-gateway.service
```

Smoke test:

```bash
curl -I http://127.0.0.1:5000/
curl http://127.0.0.1:5000/health
```

## Backups

`~/bin/backup-erp-to-b2.sh`, triggered nightly at 04:00 by the Windows task
`\Backup ERP and AutoCount to B2` (the 03:00 task dumps AutoCount's SQL Server
into `sqlserver-backups/` first).

Each run writes a dated `pg_dump` to `pg-backups/erp-<timestamp>.sql.gz`,
checks the dump actually contains the expected tables before trusting it,
prunes to the newest 14 locally, then syncs the whole ERP directory -- dumps,
project photos under `var/`, AutoCount `.bak` files, code -- to
`b2://SengchongServer/erp/`.

Dumps are dated rather than overwritten so B2 keeps history, and the sync
compares by modification time rather than size: a database dump can change
content while keeping the same byte count, and a size-only comparison would
skip it.

Credentials come from `~/.pgpass` (mode 600), so the password never reaches
the process list.

### Restore drill

Run this occasionally. A backup nobody has restored is not a backup.

```bash
sudo -u postgres createdb -O erp erp_restore_test
gzip -dc pg-backups/erp-<timestamp>.sql.gz | psql -h 127.0.0.1 -U erp -d erp_restore_test
# compare row counts and content against the live database, then
sudo -u postgres dropdb erp_restore_test
```

## Nginx Routing

Nginx reverse proxy config for public domains is in:

```text
nginx/sengchong.conf
```

Usage and HTTPS commands are documented in:

```text
nginx/README.md
```

## API Routes

One blueprint per domain, each in `function/routes/`. `python3 -c "from function
import create_app; [print(r) for r in create_app().url_map.iter_rules()]"` lists
the current set; the shape is:

```text
GET    /health

POST   /api/auth/login                     sign in, returns a bearer token
GET    /api/auth/me                        current session
PUT    /api/session/company                switch the active AutoCount company
GET    /api/companies

GET    /api/users                          ERP accounts (admin)
POST   /api/users
DELETE /api/users/:username

GET    /api/rdp-allow-list                 RDP firewall allow-list (admin)
PUT    /api/rdp-allow-list
POST   /api/rdp-allow-list/ip
DELETE /api/rdp-allow-list/ip/:ip
POST   /api/rdp-allow-list/apply

GET    /api/website-content                sengchong.com content
PATCH  /api/website-content/footer
PATCH  /api/website-content/services/:no
PATCH  /api/website-content/contacts/:no
GET    /api/website-content/assets/:kind
POST   /api/website-content/assets/:kind
GET    /api/website-gallery
POST   /api/website-gallery/import-legacy-products
GET    /api/website-audit-log

GET    /api/employees                      staff records (ERP-owned)
POST   /api/employees                      admin only
GET    /api/employees/:code
PATCH  /api/employees/:code                admin only
GET    /api/employees/meta                 positions and statuses

GET    /api/salary                         pay setup -- admin only, every verb
GET    /api/salary/:employeeCode
PATCH  /api/salary/:employeeCode            creates or updates, one row per person
GET    /api/salary/meta

GET    /api/work-entries                   timesheet -- admin only, every verb
POST   /api/work-entries
GET    /api/work-entries/:id
PATCH  /api/work-entries/:id
DELETE /api/work-entries/:id
GET    /api/work-entries/day                whole crew for one date + company
POST   /api/work-entries/day                batch save; a zeroed row is deleted
GET    /api/work-entries/meta

GET    /api/projects                       ERP-owned project/job layer
POST   /api/projects
GET    /api/projects/:key
PUT    /api/projects/:key
GET    /api/projects/meta
GET    /api/projects/by-document
GET    /api/projects/candidates/from-debtors
GET    /api/projects/candidates/from-documents
GET    /api/projects/:key/photos
POST   /api/projects/:key/photos
PATCH  /api/project-photos/:id
DELETE /api/project-photos/:id
GET    /api/project-photos/:id/file

*      /api/autocount/:resource             AutoCount passthrough (see
*      /api/autocount/:resource/:key        allowed_resources in config.py)
GET    /api/autocount/:resource/pdf
POST   /api/autocount/invoices/payment-request/pdf
POST   /api/autocount/bank-transactions/reconcile-preview
POST   /api/autocount/bank-transactions/reconcile

GET    /public-api/website                  read-only, for sengchong.com
GET    /public-api/gallery
GET    /public-api/project-photos/:id/file
```

Everything under `/api` except `/api/auth/login` requires
`Authorization: Bearer <token>`. `/public-api` is unauthenticated and must
never expose customer, accounting, cost or document data.
