# Business Context

This ERP is for Seng Chong Interior Design / 成昌家私 style work, not a generic retail shop.

The legacy `sengchong/` site is a marketing and portfolio site. It shows service categories, contact info, and project/product photos. The ERP roadmap should therefore prioritize project-based sales, staged collections, supplier costs, material tracking, and photo/report reuse.

## Service Categories From Sengchong

The public site currently presents these services:

| Service | ERP Meaning |
|---|---|
| 电视机橱 | built-in TV cabinet / feature wall job |
| 商场橱 | commercial / mall cabinet job |
| 厨房橱 | kitchen cabinet job |
| 衣橱 | wardrobe job |
| 床头柜 | bedside cabinet / bedroom built-in job |
| 拱门 | arch / decorative carpentry job |
| 水盆橱 | sink cabinet / bathroom or utility cabinet job |
| 展示柜 | display cabinet job |
| 设计 | design / consultation / drawing work |

These should become ERP project/service tags, not only website text.

## Business Workflow

Likely day-to-day flow:

1. Lead / customer contacts Seng Chong from website, referral, WhatsApp, or phone.
2. Staff records customer, address, contact person, job category, and site measurement appointment.
3. Quotation is prepared by job scope:
   - cabinet type
   - dimensions
   - material/finish
   - hardware
   - installation/labour
   - optional design fee
4. Customer confirms, often with deposit or staged payment.
5. Materials and supplier invoices are purchased against the job.
6. Work progresses through design, fabrication, installation, touch-up, completion.
7. Invoice/payment request is printed for each collection stage.
8. Official receipt is printed after payment.
9. Final job margin is reviewed:
   - quoted amount
   - collected amount
   - supplier/material cost
   - labour/subcontract cost
   - outstanding balance
10. Completed job photos can be saved for future quotation reference and website/gallery use.

## Business-Specific ERP Goals

The ERP should eventually answer these questions quickly:

- Which customer still owes money?
- Which job is waiting for deposit, progress payment, or final payment?
- Which supplier invoices are unpaid?
- Which jobs are profitable after material and supplier cost?
- Which payment went into which bank account?
- Which AutoCount document belongs to which renovation/carpentry job?
- What photos and service category should be linked to a completed job?
- Which quotations are still pending follow-up?

## Project Object

AutoCount documents are accounting documents. The web ERP should add a business-facing `Project / Job` layer on top.

Suggested project fields:

- project code
- customer/debtor
- contact person
- phone/WhatsApp
- site address
- service category
- project status
- quotation doc no
- invoice doc no(s)
- AR payment doc no(s)
- supplier/AP invoice doc no(s)
- expected install date
- completion date
- quoted total
- collected total
- outstanding amount
- estimated cost
- actual cost
- margin
- photo folder / gallery links
- notes

This can be stored in ERP-owned data first, then linked to AutoCount doc numbers. It does not need to be forced into AutoCount raw tables immediately.

## Project Statuses

Recommended statuses:

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

## Payment Milestones

For renovation/carpentry jobs, payments are usually staged. The current payment request PDF is useful because it can ask for a partial amount without creating a fake new invoice.

Recommended milestone labels:

- Deposit
- Progress Payment
- Before Installation
- After Installation
- Final Balance
- Variation Order

ERP should allow a payment request to include one of these labels later, while still clamping amount to invoice outstanding.

## Website / Gallery Integration

The legacy site has a product image gallery and service images. The final target is that `sengchong.com` becomes a public renderer only:

- no separate website login
- no separate website backend
- no direct website content editing outside ERP
- all service/category/contact/gallery content is managed from ERP

ERP should replace the website backend:

- attach multiple before/after/completed photos to a project
- tag photos by service category
- mark photos public/private
- mark selected photos as website visible
- choose which project images can appear on the public site
- push only selected public photos to the website gallery
- keep internal costing/customer/accounting information private

This is a later phase, after accounting-critical AR/AP workflows are stable.
