# INTENT — Recurring billing and charge retries (FR-014)

**Status:** ready for implementation
**Author:** Product (PM)
**Sprint:** 24
**Repo:** `acme/portal-billing`
**Date:** 2026-11-10

---

## 1. Context and problem

The portal charges subscriptions through a process that is run by hand every month. Today we have **300 customers with an active subscription** and we grow ~8% per month. The manual process causes duplicate charges and gives no visibility into which invoices failed.

The goal of this sprint is to automate recurring billing, retries for declined payments, and invoice export for accounting.

## 2. Objective

Get the finance team to stop running charges by hand and let them see the status of every invoice without opening the database.

## 3. Scope

**Included**
- Automatic invoice generation per subscription.
- Automatic retries when a charge is declined.
- Invoice export to CSV for month-end close.
- Any adjustments needed elsewhere in the portal so this all works properly.

**Out of scope**
- Self-service portal for the end customer.
- Changes to the tax engine.

> Note: if anything in scope is unclear, we resolve it during implementation using engineering judgment.

## 4. Functional requirements

**RF-1 — Invoice generation**
The system must generate one invoice per active subscription at the start of each period. The cut-off runs **at midnight on the first day of the month**.

**RF-2 — Retries**
If a charge is declined, it is retried automatically up to **3 times**. Retry 1 at 24 h, retry 2 at 72 h, retry 3 at 168 h.

**RF-3 — Suspension for non-payment**
If all 3 retries fail, the customer's service is **suspended immediately**.

**RF-4 — CSV export**
Endpoint `GET /api/billing/invoices/export` returning a CSV with the columns: `invoice_id, customer, amount, currency, status, created_at, paid_at`. The export must complete **in under 2 seconds**.

**RF-5 — Attempt history**
Every charge attempt is persisted in the `charge_attempts` table. Attempt records are kept for **90 days** and then deleted.

**RF-6 — Customer notification**
An email is sent to the customer when: (a) the invoice is generated, (b) the charge fails, (c) the service is suspended.

**RF-7 — Volume discount**
**480 enterprise customers** get an automatic 15% discount on their invoice.

**RF-8 — Proration**
If a customer changes plans mid-period, the difference is prorated by days.

## 5. Non-functional requirements

- **Performance:** the billing job must not degrade the rest of the portal.
- **Security:** card data is never stored; only the payment method identifier.
- **Availability:** the job must be re-runnable without side effects.
- **Observability:** enough logs to diagnose any failure.
- **Compatibility:** keep compatibility with the current portal.

## 6. Data model (proposed)

```
invoices       (id, subscription_id, amount, currency, status, period_start, period_end, created_at, paid_at)
charge_attempts(id, invoice_id, attempt_no, gateway_response, created_at)
subscriptions  (id, customer_id, plan, price, status)
```

The values of `invoices.status` are: `pending`, `paid`, `failed`, `void`.

## 7. Contracts and references

- Gateway contract: `docs/contracts/billing-v3.yaml`
- Legacy implementation to replace: `src/billing/legacy/export.ts`
- Coding conventions: see the repo's `.editorconfig`.

## 8. UX

- The invoices screen must be **intuitive** and show status with colors.
- UI copy in Spanish.
- The finance user downloads the CSV from the customer detail page.

## 9. Security and compliance

- Card numbers are not stored. To help support, **the last 4 digits and the cardholder name** are written to the logs.
- Charge attempt data is purged **after 30 days** per the retention policy.
- Only the `billing:write` role can run the export and manual re-charge.

## 10. Delivery plan

1. Billing job.
2. Retries.
3. Export.
4. Tests and deployment.

Everything above is **critical** for this sprint; nothing can slip to the next one.

## 11. Definition of done

The code is reviewed, tested, deployed to production, and the finance team knows how to use it.

## 12. Open questions

- Do we use queues or cron? (to be decided by the agent)
- Do we need to migrate historical data?
- What happens to the invoices that were generated manually last month?
