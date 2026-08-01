# Implementation Rules

These rules are for future ERP development against AutoCount.

## Data Ownership

AutoCount remains the source of truth.

The ERP can:

- read fast through SQL
- write through AutoCount SDK/data access
- print through AutoCount report engine
- maintain ERP-only settings such as web users, UI defaults, and RDP allow-list
- maintain ERP-only project/job records and photo/gallery metadata

The ERP must not:

- raw insert accounting documents
- raw update knock-off allocation
- raw update stock cost
- raw update GL postings
- raw update document numbering

## Read Strategy

Use direct SQL for:

- list pages
- detail pages
- dashboards
- filters
- search
- aging reports
- stock movement inquiry

Use cache carefully:

- list cache can be short TTL
- detail cache must be invalidated after related writes
- company switch must clear cache
- refresh button must bypass cache

## Write Strategy

Use AutoCount SDK for:

- invoice/quotation/PO creation
- AR payment creation
- bank reconciliation commit through `AutoCount.GL.BankRecon.BankReconCommand`
- AP payment creation
- AP invoice creation
- credit/debit notes
- stock adjustment if implemented later

Every write should:

- validate required fields in frontend and backend
- validate direct-SQL preview/read data before calling the SDK write
- let AutoCount allocate doc no where possible
- return created doc no/doc key
- clear affected caches
- reload affected detail
- log result in ERP audit log later

Project/job and gallery writes are ERP-owned and can be stored outside AutoCount, but their AutoCount links must use stable doc numbers/doc keys.

Bank reconciliation rule:

- list and filter `BankTrans` through direct SQL for speed
- preview selected reconciliation rows before write
- require one bank account per commit
- require statement date and actual bank statement balance
- reject already reconciled or future-dated transactions before calling AutoCount
- commit only through AutoCount `BankRecon.Save`, never by raw updating `BankTrans`

## Sengchong Website Ownership

`sengchong.com` is public rendering only.

Do not add new login, register, backend, upload, or content-editing flows to `sengchong.com`.

All website content must be managed through ERP:

- service categories
- homepage content
- contact details
- project photos
- gallery publish status
- sort order
- captions and alt text

Project photos must support multiple images per project. New photos must default to private and not website visible.

Public website APIs must return only safe display fields:

- photo URL
- thumbnail URL
- service category
- caption
- alt text
- sort order

Public website APIs must not return customer private data, AutoCount document numbers, quoted/paid/outstanding amounts, costs, margins, supplier data, or site addresses.

## Printing Strategy

Prefer AutoCount report formats.

Use ERP-side custom modifications only when:

- AutoCount template cannot satisfy a small display requirement
- the change can be added to the loaded report object without rebuilding the report
- the output still keeps AutoCount's base layout

Current example:

- Invoice payment request uses AutoCount `Invoice.art`.
- The extra paid/outstanding/request lines are inserted into the original invoice total panel.

## API Shape

Recommended REST pattern:

- `GET /api/autocount/<resource>`
- `GET /api/autocount/<resource>/<key>`
- `POST /api/autocount/<resource>`
- `GET /api/autocount/<resource>/pdf?key=...`
- specialized print endpoints only when extra payload is needed, e.g. payment request amount

Recommended future resources:

- `projects`
- `project-photos`
- `website-content`
- `website-gallery`
- `creditors`
- `ap-invoices`
- `ap-payments`
- `ar-credit-notes`
- `ar-debit-notes`
- `ap-credit-notes`
- `ap-debit-notes`
- `stock-movements`
- `stock-balances`
- `gl-entries`
- `reports`

Project APIs should be separate from AutoCount APIs because project status, milestone labels, and gallery publishing are business workflow data, not accounting postings.

## URL And Navigation

The frontend URL should record:

- module
- view
- key
- query

Rules:

- refresh should restore current page
- Back button should return to previous navigation source
- sidebar tab click should always open module list
- company switch should clear history and cache

## Security

Keep ERP users separate from AutoCount users.

Admin-only actions:

- RDP allow-list
- user management
- report default settings
- system config

Future roles:

- `admin`
- `sales`
- `ar`
- `ap`
- `inventory`
- `readonly`

## Validation

Amount rules:

- payment request amount must be greater than zero
- payment request amount must not exceed outstanding
- percentage quick buttons can use invoice total as base, then clamp to outstanding
- payment amounts must not silently over-allocate unless unapplied amount is intentional

Date rules:

- all document dates should use explicit date input
- printing should show date-only where business docs do not need time

Currency/tax rules:

- do not assume MYR only
- do not assume no tax
- load `Currency` and `TaxCode` as dropdown sources

Project rules:

- project status changes should not change AutoCount accounting data
- project outstanding should be calculated from linked invoice/AR payment data where possible
- project cost should be calculated from linked AP invoice/payment/stock data where possible
- public gallery photos must be explicitly marked public

## Testing Checklist

For every module upgrade:

- frontend build passes
- backend Python compile passes
- list API works
- detail API works
- refresh works
- URL refresh restores position
- company switch does not leak old company data
- PDF export returns non-empty PDF where applicable
- write action reloads affected records
- invalid amount/date/key returns clear error
