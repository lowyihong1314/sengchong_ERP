# Module Specs

This document defines the intended ERP modules and the practical buttons/views each module should have.

## Global UI

Every module should support:

- URL state: module, view, key, query.
- Back to previous navigation source.
- Sidebar tab always opens list view.
- Search.
- Date range filter where documents have dates.
- Refresh.
- Export/print where meaningful.
- Company-aware cache.

## Dashboard

Purpose: first page after login.

Cards:

- active projects
- projects waiting deposit
- projects in installation
- projects waiting final balance
- AR outstanding
- AP outstanding
- overdue debtor amount
- upcoming AP due amount
- this month sales
- this month purchases
- unapplied AR payment
- unapplied AP payment

Links:

- open active projects
- open outstanding invoices
- open debtor aging
- open AP invoices
- open bank/payment dashboard

## Project / Job

Purpose: operational layer for interior design / custom carpentry jobs.

Service categories:

- TV cabinet / 电视机橱
- Mall or commercial cabinet / 商场橱
- Kitchen cabinet / 厨房橱
- Wardrobe / 衣橱
- Bedside cabinet / 床头柜
- Arch / 拱门
- Sink cabinet / 水盆橱
- Display cabinet / 展示柜
- Design / 设计

List:

- project code
- customer
- service category
- status
- quotation doc no
- invoice doc no
- quoted total
- collected
- outstanding
- estimated install date

Detail:

- customer and contact
- site address
- service category
- dimensions/scope notes
- linked quotation
- linked invoice(s)
- linked AR payment(s)
- linked AP invoice(s)
- payment milestone plan
- Photos tab with multiple project photos
- photo public/private and website visible flags
- cover image and sort order
- margin summary

Actions:

- create quotation for project
- link existing quotation/invoice
- print payment request from linked invoice
- upload multiple project photos
- choose which project photos can appear on `sengchong.com`
- mark completed

Status:

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
- Cancelled

## Sales - Quotation

List:

- Doc no, date, debtor, total, status.
- Filters: date range, debtor, status.

Detail:

- Header fields.
- Lines.
- Customer info.
- linked Project / Job.
- Print quotation.
- Convert to invoice later.

Create/Edit:

- debtor
- project/job
- service category
- date
- line item/description/qty/uom/unit price/discount/tax
- footer discount/rounding if used

## Sales - Invoice

List:

- Doc no, date, debtor, total, paid, outstanding, status.
- Filters: date range, debtor, outstanding-only, status.

Detail:

- Header.
- Lines.
- linked Project / Job.
- AR payment records.
- AR payment detail jump.
- Payment request form.
- Print invoice.
- Print payment request.

Actions:

- Create AR payment.
- Print official receipt from linked payment.
- Print milestone payment request.
- Add note/reference later.

## AR Payment

List:

- OR/payment doc no.
- date
- debtor
- payment amount
- knock-off amount
- unapplied amount
- payment method

Detail:

- payment header
- payment lines
- allocated invoices
- invoice jump
- print official receipt

Create:

- from invoice detail
- standalone from debtor
- allocate one or multiple invoices
- allow unapplied balance if business requires

## Debtor

List:

- code
- company name
- phone/email
- terms
- active status
- outstanding

Detail:

- contacts and addresses
- open invoices
- payment history
- statement print
- aging

Actions:

- print statement
- batch statements later
- create/edit customer later

## AP Invoice

List:

- doc no
- supplier invoice no
- creditor
- date
- due date
- total
- paid
- outstanding
- status

Detail:

- header
- line accounts
- linked Project / Job cost
- linked AP payments
- credit/debit note links

Actions:

- create AP payment
- print AP document if template exists
- mark/filter overdue

## AP Payment

List:

- payment doc no
- date
- creditor
- payment amount
- knock-off amount
- unapplied amount
- method/bank

Detail:

- payment lines
- allocated AP invoices
- bank reference
- payment voucher print

Create:

- select creditor
- select invoices
- enter paid amount
- choose payment method
- allow unapplied amount if needed

## Creditor

List:

- code
- company name
- phone/email
- terms
- active status
- outstanding

Detail:

- contacts and addresses
- AP invoices
- AP payments
- AP aging

## Inventory

Item detail should show:

- item master fields
- current stock balance
- movement history
- sales history
- purchase history
- stock location/UOM where available
- project usage where linked

Stock movement list should show:

- date
- item
- doc type
- source doc
- qty
- cost
- location

For this business, item/material screens should support cabinet materials and service line items before complex stock take.

## Gallery / Website Content

Purpose: replace the old `sengchong` backend. `sengchong.com` should only render public content published by ERP.

List:

- photo
- project
- service category
- public/private
- website visible status
- cover image
- sort order

Actions:

- upload project photos
- tag service category
- mark selected photos as website visible
- hide private/customer-sensitive photos
- manage homepage/service/contact content
- preview public website output from ERP

This module should never expose quotation amount, cost, supplier, or customer details to the public website.

This module is ERP-owned data. It does not need AutoCount SDK because it is website/project metadata, not accounting data.

## Bank / Cashbook

List:

- date
- bank account
- source doc
- debtor/creditor
- payment method
- DR/CR amount

Dashboard:

- current month in/out
- unapplied AR payments
- unapplied AP payments
- payment method usage

Admin:

- show payment methods
- bank account mapping
- cheque/reference requirement
- report template mapping

## Reports

Each printable document should allow:

- default template
- optional template override
- PDF download
- later: batch print

Initial template-aware modules:

- Invoice
- Payment request
- Official receipt
- Debtor statement
- Quotation
- Purchase order
- AP payment voucher
