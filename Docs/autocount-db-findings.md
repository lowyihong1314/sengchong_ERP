# AutoCount DB Findings

本文件记录从 AutoCount SQL Server 只读检查得到的业务信号。检查没有直接修改数据库，也没有展开客户/供应商清单。

## Companies

| Company DB | 观察 |
|---|---|
| `AED_SENG` | 销售侧数据少，AP invoice 数据较多；像轻量公司库或早期测试/导入库。 |
| `AED_MANSON` | 当前主要活跃库；销售、AR payment、AP invoice、AP payment、stock、GL 都有数据。 |

## AED_SENG Summary

| Area | Table | Count | Date Range | Amount Signal |
|---|---:|---:|---|---:|
| Sales invoice | `IV` | 1 | 2026-05-15 | Total RM392.00 |
| AR invoice | `ARInvoice` | 1 | 2026-05-15 | Outstanding RM392.00 |
| AR debit note | `ARDN` | 1 | 2026-05-25 | Outstanding RM216.00 |
| AP invoice | `APInvoice` | 125 | 2026-01-01 to 2026-04-30 | Outstanding RM129,948.80 |
| GL entries | `GLDTL` | 254 | n/a | active accounting ledger |
| Debtors | `Debtor` | 2 | n/a | small customer master |
| Creditors | `Creditor` | 6 | n/a | supplier master exists |
| Items | `Item` | 1 | n/a | minimal item master |
| Stock movement | `StockDTL` | 2 | 2026-05-15 to 2026-05-25 | minimal stock history |
| Payment methods | `PaymentMethod` | 2 | n/a | CASH, BANK |
| Custom reports | `Report` | 4 | n/a | Statement, Debit Note, Invoice, Quotation |

### AED_SENG Report Signals

Available custom report types:

- `Debtor Statement`
- `Debit Note Document`
- `Invoice Document`
- `Quotation Document`

Important doc formats:

- Sales quotation: `QT{ddMMyyyy}/<00>`
- Invoice: `SC{ddMMyyyy}/<00>`
- Purchase order: `PO-<000000>`
- Purchase invoice: `PI-<000000>`

## AED_MANSON Summary

| Area | Table | Count | Date Range | Amount Signal |
|---|---:|---:|---|---:|
| Quotation | `QT` | 2 | 2026-05-13 to 2026-05-15 | Total RM45,553.00 |
| Sales invoice | `IV` | 6 | 2026-04-27 to 2026-05-28 | Total RM92,544.24 |
| AR invoice | `ARInvoice` | 6 | 2026-04-27 to 2026-05-28 | Paid RM40,783.74; Outstanding RM51,760.50 |
| AR payment | `ARPayment` | 7 | 2026-03-22 to 2026-06-05 | Payment RM40,500.00 |
| AR payment allocation | `ARPaymentKnockOffDetail` | 58 | n/a | invoice/payment matching exists |
| AR credit note | `ARCN` | 1 | 2026-05-05 | Knock-off RM283.74 |
| AP invoice | `APInvoice` | 327 | 2026-01-01 to 2026-05-22 | Outstanding RM109,197.17 |
| AP payment | `APPayment` | 6 | 2026-05-02 to 2026-05-25 | Payment RM5,300.59; unapplied RM160.00 |
| AP credit note | `APCN` | 4 | 2026-01-31 to 2026-03-31 | Knock-off RM1,238.20 |
| AP debit note | `APDN` | 12 | 2026-03-10 to 2026-04-30 | Outstanding RM955.00 |
| GL entries | `GLDTL` | 1,071 | n/a | active accounting ledger |
| Debtors | `Debtor` | 7 | n/a | customer master active |
| Creditors | `Creditor` | 21 | n/a | supplier master active |
| Items | `Item` | 31 | n/a | product/service master active |
| Stock movement | `StockDTL` | 144 | 2026-04-27 to 2026-05-28 | stock tracking is relevant |
| Payment methods | `PaymentMethod` | 12 | n/a | multiple MY/SG bank/payment flows |
| Custom reports | `Report` | 7 | n/a | Invoice, Statement, OR, Quotation |

### AED_MANSON Report Signals

Available custom report types:

- `Debtor Statement`
- `Quotation Document`
- `Invoice Document`
- `Official Receipt`

Notable report variants:

- Invoice templates exist for CIMB and DBS.
- Debtor statement templates exist for CIMB and DBS.
- Official Receipt custom template exists.

This means the ERP should eventually allow choosing a report template or bank profile before printing.

### AED_MANSON Payment Signals

There are 12 payment methods. The configured methods include cash, cheque, online banking, credit card, e-wallet, PayNow, bank transfer, deposit, money changer, and multiple bank accounts.

Important implication: AR/AP payment screens must not hard-code one bank account or one receipt format.

### AED_MANSON Tax and Currency Signals

Currency:

- `MYR`
- `SGD`

Tax codes:

- Purchase tax 5%, 10%
- Purchase service tax 6%, 8%
- Sales tax 5%, 10%

Important implication: new document forms must support currency, exchange rate, and tax code instead of assuming MYR/no tax.

## Main Conclusions

1. AP is the biggest missing business area.
   `AED_MANSON` has 327 AP invoices and RM109,197.17 outstanding. Supplier invoice/payment workflow should be high priority.

2. AR needs aging and allocation visibility.
   AR invoice/payment tables already have real knock-off data. Invoice detail should continue linking to payment detail, and debtor aging should be added.

3. Bank/payment configuration matters.
   Payment methods and report variants are bank-specific. ERP needs bank-aware payment and printing flows.

4. Stock inquiry is useful even if stock write is delayed.
   `StockDTL` has 144 rows and item master has 31 rows. Read-only stock movement, item history, and stock balance should come before risky stock posting.

5. E-Invoice tables exist but are unused.
   E-Invoice can stay in a later phase unless compliance workflow becomes urgent.

