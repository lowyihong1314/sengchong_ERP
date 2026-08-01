# Data Mapping

This document maps the planned Web ERP modules to AutoCount SQL tables and SDK write paths.

## Rule Of Thumb

- Read-heavy APIs should use direct SQL for speed.
- Write operations should use AutoCount SDK/data access classes, not raw SQL inserts.
- Printing should use AutoCount report templates whenever possible.

Raw SQL writes are dangerous because AutoCount updates GL, stock cost, knock-off, audit, status, numbering, and report-related tables behind the scenes.

## Sales And AR

| ERP Module | AutoCount Tables | Current ERP Status | Needed Upgrade |
|---|---|---|---|
| Quotation | `QT`, `QTDTL` | list/detail/PDF exists | create/edit, convert to invoice, report template selection |
| Invoice | `IV`, `IVDTL`, `ARInvoice`, `ARInvoiceDTL` | list/detail/PDF/payment request exists | richer filters, status, payment timeline, copy/duplicate |
| AR Payment | `ARPayment`, `ARPaymentDTL`, `ARPaymentKnockOff`, `ARPaymentKnockOffDetail`, `CashBook` | list/detail/create from invoice/OR print exists | standalone create, multi-invoice allocation, unapplied handling |
| AR Credit Note | `ARCN`, `ARCNDtl` | not implemented | list/detail/create/print, apply to invoice |
| AR Debit Note | `ARDN`, `ARDNDtl` | data exists in `AED_SENG` | list/detail/print |
| Debtor Statement | `Debtor`, AR transaction tables, AutoCount statement report | print exists | date range, bank/template selection, batch statements |
| Debtor Aging | `ARInvoice`, `ARDN`, `ARCN`, `ARPaymentKnockOff` | not implemented | aging buckets, overdue list, collection dashboard |

## Project / Job Layer

This should be ERP-owned data linked to AutoCount documents. It should not be raw-written into AutoCount accounting tables.

| ERP Concept | AutoCount Link | ERP-Owned Fields |
|---|---|---|
| Project / Job | debtor, quotation doc no, invoice doc no, AR payment doc no, AP invoice doc no | project code, service category, site address, status, install date, notes |
| Service category | item/project tag, quotation line description | TV cabinet, kitchen cabinet, wardrobe, display cabinet, design, etc. |
| Payment milestone | invoice/payment request/AR payment | Deposit, Progress Payment, Before Installation, Final Balance |
| Job costing | AP invoice, creditor, stock movement | estimated cost, supplier/material cost, labour/subcontract cost |
| Job gallery | no direct AutoCount dependency | project photos, public/private flag, website publish flag |

## Purchase And AP

| ERP Module | AutoCount Tables | Current ERP Status | Needed Upgrade |
|---|---|---|---|
| Creditor | `Creditor`, `CreditorType`, `Terms` | not implemented in current sidebar | list/detail/create/edit |
| AP Invoice | `APInvoice`, `APInvoiceDTL` | not implemented | list/detail/create, supplier invoice no, outstanding, PDF/report |
| AP Payment | `APPayment`, `APPaymentDTL`, `APPaymentKnockOff`, `APPaymentKnockOffDetail`, `CashBook` | not implemented | pay supplier invoices, multi-invoice allocation, print payment voucher |
| AP Credit Note | `APCN`, `APCNDtl` | data exists | list/detail/apply to AP invoice |
| AP Debit Note | `APDN`, `APDNDtl` | data exists | list/detail/print |
| Purchase Order | likely `PO`, `PODTL` via AutoCount SDK | list/detail/PDF exists | create/edit, convert to AP invoice/GRN when needed |

## Inventory

| ERP Module | AutoCount Tables | Current ERP Status | Needed Upgrade |
|---|---|---|---|
| Item master | `Item`, `ItemUOM`, price/cost related tables | list/detail exists | create/edit, image, UOM, purchase/sales flags |
| Stock movement | `StockDTL` | not implemented | item movement timeline, doc source link |
| Stock balance | `StockDTL`, `StockPBalance`, `UTDStockCost` | not implemented | current balance by item/location/UOM |
| Stock adjustment | `StockAdjustment`, `StockAdjustmentDTL` if used | not active now | later phase because write risk is higher |
| Stock take | `StockTake`, `StockTakeDTL` | no active rows | later phase |

For Seng Chong, inventory should initially be treated as material/service support for projects, not POS retail inventory.

## Cashbook, Bank, GL

| ERP Module | AutoCount Tables | Current ERP Status | Needed Upgrade |
|---|---|---|---|
| Payment methods | `PaymentMethod` | list used by AR payment | admin/detail view, bank account mapping |
| Cashbook | `CashBook`, `CBPaymentDTL`, payment detail tables | list/detail, source links, OR/PV/AP/AR drilldown | edit/create cashbook entries through AutoCount SDK only |
| Bank Reconciliation | `BankTrans`, AutoCount `GL.BankRecon` SDK | list/filter/preview/commit through AutoCount BankRecon API | statement history, unreconcile workflow, report/print |
| GL accounts | `GLMast`, `GLDTL` | not implemented | account inquiry, GL transaction drilldown |
| Journals | `Journal`, `GLDTL` | not implemented | read-only first, manual journal later if needed |

## Master Data

| ERP Module | Tables | Needed Features |
|---|---|---|
| Customer | `Debtor` | create/edit contacts, address, terms, credit limit, status |
| Supplier | `Creditor` | create/edit contacts, terms, bank/payment notes |
| Item | `Item`, `ItemUOM` | create/edit, UOM, stock flags, sales/purchase tax codes |
| Terms | `Terms` | dropdown source for customer/supplier/documents |
| Tax | `TaxCode` | dropdown source, MY tax support |
| Currency | `Currency` | dropdown source, exchange rate support |
| Sales/Purchase agent | `SalesAgent`, purchase-agent fields | dropdown source when data appears |

## Reports And Numbering

| Area | Tables / Source | Needed Features |
|---|---|---|
| Report templates | `Report`, `DefaultReport`, system `report.dat` | template picker per module/company |
| Document numbering | `DocNoFormat` | display next format preview; writes should still let AutoCount allocate numbers |
| PDF export | AutoCount report engine | support invoice, quotation, PO, OR, statement, AP vouchers |
