# AutoCount ERP Gateway

Minimal Flask + Vite React frontend for AutoCount integration. The UI only exposes:

- Invoices
- Quotations
- Items
- Purchase Orders

Flask verifies login through AutoCount SDK `UserSession.Login()` and reads the allowed modules through AutoCount SDK classes. The frontend stays on a standalone login page until that SDK login succeeds.

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

ERP-owned data is stored in `/home/yukang/ERP/erp_data.db`:

- ERP users
- Web/API sessions
- Projects/jobs and linked document numbers
- Sengchong website services, contacts, and footer settings

The current unit can run multiple workers because sessions are stored in SQLite:

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

```text
POST /api/autocount/login
GET /api/autocount/invoices
GET /api/autocount/quotations
GET /api/autocount/items
GET /api/autocount/purchase-orders
GET /api/autocount/:resource/:docNo-or-itemCode
POST /api/autocount/invoices          create AR invoice draft
POST /api/autocount/quotations        create quotation draft
POST /api/autocount/items             create item
POST /api/autocount/purchase-orders   create purchase order draft
```
