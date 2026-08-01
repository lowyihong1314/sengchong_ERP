# Website Next Steps

After bank reconciliation, the next ERP focus is making `sengchong.com` a public renderer controlled by ERP data.

## Rules

- `sengchong.com` should not have its own login, register, upload, or backend editing flow.
- ERP owns website content, project photo publishing, captions, sort order, and service categories.
- Public APIs must expose only safe display fields.
- AutoCount accounting/customer fields must not be exposed to the public website.

## Build Order

1. Add a website gallery manager inside ERP using existing project photos. Done.
2. Add per-photo controls for public visibility, website visibility, caption, alt text, category, and sort order. Done.
3. Import legacy `sengchong/static/images/products` into ERP-owned project photos. Done for `AED_MANSON` under `WEBSITE-GALLERY`.
4. Add a website preview page in ERP that renders the same public payload as the website. Done.
5. Replace old `sengchong` backend routes with read-only public rendering. Mostly done; old mutating endpoints return removed/backend responses.
6. Remove or block old website login/register/backend templates after ERP publishing is complete.
7. Add an audit trail for publish/unpublish changes. Done for project photo publish metadata and website footer/service/contact content.

## Current State

- ERP has `/api/website-gallery` for authenticated gallery management.
- ERP has `/api/website-gallery/import-legacy-products` for one-time legacy product image import.
- Public `/public-api/gallery` returns only photos explicitly marked public and website visible.
- Public `/public-api/gallery?company=<db>` can still filter by company when needed.
- Public `/public-api/website` returns safe service, contact, footer, and gallery display data for the website renderer.
- Public default gallery reads all website-visible photos, so `sengchong.com/products` is not tied to one AutoCount company.
- ERP Website Content now includes a Website Preview panel backed by `/public-api/website`.
- ERP records website gallery metadata, publish changes, and footer/service/contact content changes in `/api/website-audit-log`.
- ERP Website Content can list and upload service/contact images through `/api/website-content/assets/<service|contact>`.
- `sengchong.com` home, footer, and products now render from `/public-api/website`.
- Legacy `/get_api_url` points to ERP public endpoints instead of the old external website API.

## Public Payload

The public website should receive:

- image URL and thumbnail URL
- project/service category
- caption
- alt text
- sort order

The public website should not receive:

- debtor name unless explicitly approved for marketing
- phone, email, site address, or private notes
- quotation, invoice, payment, cost, margin, or supplier details
- AutoCount document numbers or document keys
