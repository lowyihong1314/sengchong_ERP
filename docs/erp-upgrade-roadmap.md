# ERP Upgrade Roadmap

The final target is not to replace AutoCount's accounting engine. The target is to make the web ERP fast and convenient enough that daily operations can be done from it, while AutoCount remains the source of truth.

Business context: this ERP supports interior design / custom carpentry work for Seng Chong style projects. The system should think in terms of customer jobs, quotations, deposit/progress/final collections, supplier/material cost, installation status, and completed-project photos.

## Priority Model

Priority is based on:

1. Real data volume in AutoCount DB.
2. Current user workflow pain.
3. Risk of corrupting accounting data.
4. Whether direct SQL read can solve most of the need before write support.

## Phase 0 - Stabilize Platform

Status: mostly done, continue hardening.

- URL should preserve module/detail position on refresh.
- Back should return to the previous real navigation source.
- Sidebar tab click should open module list, not stale detail.
- Auth should stay in ERP user data, not AutoCount password.
- Company switch must clear caches safely.
- RDP allow-list should remain admin-only.
- Direct SQL read cache should avoid stale data after SDK writes.

## Phase 1 - Finish Sales And AR Daily Workflow

Reason: Already used, and recent work focused on invoices, payment request, AR payments, OR, and statements.

Features:

- Invoice list/detail filters: date range, debtor, status, outstanding-only.
- Invoice detail timeline: invoice, AR payments, credit notes, debit notes.
- AR payment list/detail with direct links back to invoice.
- Standalone AR payment create:
  - select debtor
  - select one or multiple invoices
  - support unapplied amount
  - support bank/payment method
- Debtor aging:
  - current, 30, 60, 90, 120+ days
  - outstanding total
  - click debtor to see invoices
- Debtor statement:
  - date range
  - template/bank selector
  - batch PDF later
- Payment request PDF:
  - keep current AutoCount invoice format
  - maintain custom footer only in invoice total section
  - later allow milestone label such as Deposit, Progress Payment, Before Installation, Final Balance

## Phase 1B - Project / Job Layer

Reason: Seng Chong work is project-based. AutoCount documents alone do not show the operational status of a kitchen cabinet, wardrobe, display cabinet, or mall cabinet job.

Features:

- Project list:
  - project code
  - customer
  - service category
  - status
  - quotation
  - invoice
  - collected
  - outstanding
  - estimated install date
- Project detail:
  - customer/contact/site address
  - service category from Sengchong categories
  - linked quotation/invoice/AR payment/AP invoice
  - payment milestone plan
  - notes and photos
- Project statuses:
  - Lead
  - Site Measure
  - Quotation
  - Waiting Deposit
  - Confirmed
  - Drawing / Design
  - Material Ordered
  - Fabrication
  - Installation
  - Touch Up
  - Completed
  - Warranty / After Sales
- Start with ERP-owned project data linked by AutoCount doc numbers. Do not raw-write this into accounting tables.

## Phase 2 - Build AP / Supplier Workflow

Reason: `AED_MANSON` has 327 AP invoices and RM109,197.17 outstanding. This is the biggest missing area.

Features:

- Creditor module:
  - list/detail
  - contact/address/terms
  - active status
- AP invoice module:
  - list/detail
  - supplier invoice no
  - outstanding/payment status
  - line account/description/tax
  - link supplier/material cost back to Project / Job
  - create via SDK
- AP payment module:
  - select creditor
  - select AP invoices to pay
  - payment method / bank account
  - knock-off allocation
  - unapplied amount display
  - print payment voucher / remittance advice if report template exists
- AP credit/debit note:
  - list/detail first
  - apply to AP invoice later

## Phase 3 - Bank And Cashbook

Reason: `AED_MANSON` has 12 payment methods and bank-specific report templates.

Features:

- Bank/payment method admin view.
- Cashbook transaction list:
  - source doc
  - debtor/creditor
  - payment method
  - amount
  - bank account
- Bank account dashboard:
  - today/this month in/out
  - unapplied AR/AP payments
- Payment method selection should drive:
  - bank account
  - receipt/payment format
  - cheque/reference requirement

## Phase 4 - Inventory Inquiry

Reason: `AED_MANSON` has 31 items and 144 stock movements. Start read-only.

Features:

- Item stock balance by location/UOM.
- Item movement timeline from `StockDTL`.
- Source document links from stock movement to invoice/purchase docs.
- Item sales/purchase history.
- Material/service category tagging for cabinet projects.
- Item create/edit.
- Stock adjustment only after SDK path is verified.

## Phase 4B - Project Gallery / Website Content

Reason: `sengchong.com` should be a public renderer only. Its old login/backend/content editing flow should be removed. ERP should become the only place that manages website content, service categories, contact details, and which project photos are allowed to appear publicly.

Features:

- attach multiple photos to each project
- tag photos by service category
- mark photos public/private
- mark selected project photos as website visible
- choose cover image and sort order
- manage public website service/category/gallery content from ERP
- provide a read-only public gallery API for `sengchong.com`
- keep cost/customer/accounting data private

Rules:

- new project photos default to private
- new project photos default to not website visible
- `sengchong.com` must not expose quotation, invoice, AR payment, supplier cost, customer private details, margin, or site address
- old `sengchong` login/register/backend pages should be retired after ERP website management exists

## Phase 5 - Reporting And Printing System

Reason: Different company/bank/report templates already exist.

Features:

- Report template selector:
  - per company
  - per module
  - remember default in ERP config
- Print actions:
  - invoice
  - payment request
  - official receipt
  - debtor statement
  - quotation
  - PO
  - AP payment voucher
  - creditor statement if needed
- Batch PDF generation:
  - selected invoices
  - selected statements
  - monthly statement pack
- Export list to CSV/XLSX.

## Phase 6 - Compliance / E-Invoice / Audit

Reason: E-Invoice tables exist but currently have 0 active rows in the inspected DBs.

Features:

- Read E-Invoice status fields on AR/AP documents.
- Show validation UUID/link/error when data appears.
- Add submission/retry only after AutoCount SDK workflow is confirmed.
- Audit log inside ERP for:
  - who printed
  - who created payment
  - who changed RDP allow-list
  - who switched company

## Suggested Immediate Next Sprint

1. Add Project / Job basic module with Sengchong service categories.
2. Link invoice detail and quotation detail to Project / Job.
3. Add Creditor list/detail.
4. Add AP invoice list/detail with outstanding filters and project cost link.
5. Add AP payment list/detail.
6. Add report template selector for Invoice / OR / Statement.
