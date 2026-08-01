# Sengchong Website

The Sengchong public website is now served by the ERP Flask app.

- Single app factory: `function.create_app()`
- WSGI entry: `/home/yukang/ERP/run.py`
- Port: `5000`
- Auth: ERP users in `/home/yukang/ERP/erp_data.db`
- Content data: ERP-owned SQLite tables in `/home/yukang/ERP/erp_data.db`
- Static assets/templates remain under `/home/yukang/ERP/sengchong/`

## Ownership Rule

`sengchong.com` is public rendering only.

- No separate website login.
- No separate website backend.
- No direct website content CRUD.
- Website content, contact details, service categories, gallery photos, project photo publish flags, and sort order are managed from ERP.
- Project photos can be saved as multiple images per project in ERP.
- Only photos explicitly marked public and website-visible may render on `sengchong.com`.
- Customer, accounting, supplier, cost, margin, and private project data must never be exposed by public website routes.

## Run

```bash
cd /home/yukang/ERP
PORT=5000 python3 run.py
```

Production is handled by the ERP service:

```bash
systemctl --user restart erp-gateway.service
systemctl --user --no-pager --full status erp-gateway.service
```

## Smoke Test

```bash
curl -H 'Host: sengchong.com' http://127.0.0.1:5000/
```
