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
migrations/       Alembic; head revision 22688ded425d
```

`models/<name>.py` and `function/services/<name>.py` are deliberately named in
pairs: the model file describes the table, the service file holds the logic.

### Database

ERP-owned data lives in Postgres. AutoCount's own SQL Server databases are never
touched by this layer -- they are read through `function/services/sql_reader.py`
and written through the AutoCount SDK.

The engine is chosen by one environment variable, read in `function/config.py`
and reused by `migrations/env.py`:

```bash
DATABASE_URL=postgresql+psycopg://erp:pass@127.0.0.1:5432/erp   # production
DATABASE_URL=                                                   # unset -> local sqlite copy
```

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
