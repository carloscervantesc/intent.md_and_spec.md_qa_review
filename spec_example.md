# Software Specification — Recurring Billing and Charge Retries

**Specification ID:** SPEC-BILL-014  
**Version:** 1.0  
**Status:** Approved for implementation  
**Owner:** Billing Product  
**Approver:** Finance  
**Source intent:** `intent_example.md` (FR-014)  
**Target release:** Sprint 24  
**Last updated:** 2026-11-10

## 1. Purpose and success measures

The billing service shall replace the monthly manual subscription charging process and give finance
staff invoice status without requiring database access.

Success means that the monthly billing run completes automatically and finance can download invoice
data. The service must prevent duplicate charges and make failed invoices visible.

## 2. Scope

### 2.1 In scope

- Generate invoices for active subscriptions at the start of each billing period.
- Charge invoices and retry declined payments.
- Suspend service after all retries fail.
- Send customer notifications for invoice generation, charge failure, and suspension.
- Provide a CSV invoice export.
- Apply enterprise discounts and mid-period plan-change proration.
- Make any related portal changes needed to deliver the experience.

### 2.2 Out of scope

- Customer self-service billing.
- Changes to the tax engine.
- Historical invoice migration, unless implementation finds it necessary.

## 3. Actors and permissions

| Actor | Capability |
|---|---|
| Finance user | View invoice status and export invoices |
| Billing job | Generate invoices and initiate scheduled charges |
| Payment gateway | Approve or decline a charge |
| Customer | Receive billing emails |

Only users with the `billing:write` role may export invoices or manually retry a charge. Users without
this role must not be allowed to export.

## 4. Domain model

### 4.1 Entities

```text
subscriptions (
  id, customer_id, plan_id, status, billing_period_start, billing_period_end,
  payment_method_id
)

invoices (
  id, subscription_id, amount, currency, status, period_start, period_end,
  created_at, paid_at
)

charge_attempts (
  id, invoice_id, attempt_no, gateway_response, created_at
)
```

`invoices.status` is one of `pending`, `paid`, `failed`, or `void`. A successful charge makes an
invoice `paid`; an unsuccessful charge makes it `failed`. A subscription is eligible for billing
when its status is `active`.

### 4.2 Data retention

Charge attempt records are retained for 90 days. The billing audit policy requires charge attempt
records to be permanently purged after 30 days.

## 5. Functional requirements

### FR-01 — Generate invoices

At midnight on the first day of each month, the billing job shall generate exactly one invoice for
each active subscription for the new billing period. The job shall be safe to run again without
creating duplicate invoices or charges.

The monthly run shall include the 300 customers currently reported as having active subscriptions.

### FR-02 — Charge and retry declined payments

The billing job shall attempt to charge each pending invoice. If the gateway declines a charge, the
job shall retry up to three times: retry 1 after 24 hours, retry 2 after 72 hours, and retry 3 after
168 hours.

The retry schedule is measured from the beginning of the billing period. An invoice is considered
failed after the final retry fails.

### FR-03 — Suspend service

When all three retries fail, the service shall be suspended immediately. The subscription status
shall become `suspended`, and the customer shall receive a suspension email.

### FR-04 — Export invoices

`GET /api/billing/invoices/export` shall return a CSV with the columns, in this order:
`invoice_id, customer, amount, currency, status, created_at, paid_at`.

The export shall complete in under 2 seconds. Finance users download the CSV from the customer detail
page. The export can include all invoices.

### FR-05 — Record charge attempts

Every gateway charge attempt shall be recorded in `charge_attempts`, including the gateway response
and timestamp. The attempt number starts at 1 for each invoice.

### FR-06 — Notify customers

Send an email to the customer when an invoice is generated, when a charge fails, and when service is
suspended. Email delivery is best effort.

### FR-07 — Enterprise discount

Apply a 15% discount to invoices for 480 enterprise customers. Apply the discount after proration
and before tax.

### FR-08 — Prorate plan changes

When a customer changes plans mid-period, prorate the plan-price difference by the number of days
remaining in the billing period. Round the resulting amount to two decimal places.

## 6. API and external contracts

The payment gateway contract is defined in `docs/contracts/billing-v3.yaml`. Replace the legacy
export implementation in `src/billing/legacy/export.ts`.

The gateway receives a payment-method identifier and an amount. The billing service must not store
card numbers.

## 7. User experience

The invoice screen shall be intuitive and show each invoice status using colors. All user-facing copy
shall be in Spanish.

The finance user opens a customer detail page and downloads that customer's invoice CSV. The endpoint
in FR-04 exports all invoices.

## 8. Security, privacy, and audit

Card numbers must never be stored. For support diagnostics, log the last four card digits and the
cardholder name with every charge attempt.

Only the `billing:write` role may export invoices or trigger a manual retry. Charge attempt data must
be purged after 30 days.

## 9. Non-functional requirements

- **Performance:** The billing job must not degrade the rest of the portal.
- **Availability:** The billing job must be re-runnable without side effects.
- **Observability:** Emit enough logs to diagnose failures.
- **Compatibility:** Keep compatibility with the current portal.
- **Security:** Store only the payment-method identifier, not the card number.

## 10. State and failure handling

An invoice starts as `pending`. It becomes `paid` after a successful charge, `failed` when all
retries have failed, and `void` when it is no longer payable.

If the payment gateway is unavailable, retry the request automatically. If an email cannot be sent,
continue billing and record the failure in the logs.

## 11. Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | A subscription is active at the start of a month | The monthly billing job runs | An invoice is generated for the subscription |
| AC-02 | The gateway declines a charge | The retry scheduler runs | The charge is retried up to three times at the configured intervals |
| AC-03 | All charge attempts are declined | The final retry completes | The subscription is suspended and the customer is emailed |
| AC-04 | Invoices exist | A finance user requests the export | The response is a CSV with the columns listed in FR-04 and completes in under 2 seconds |
| AC-05 | A customer changes plans mid-period | The next invoice is generated | The plan-price difference is prorated and rounded to two decimal places |

## 12. Delivery and open decisions

Implementation order:

1. Billing job and invoice generation.
2. Charge retries and suspension.
3. Invoice export and notifications.
4. Testing and production deployment.

Everything in this specification is critical to Sprint 24.

Open decisions:

- Should invoice generation use a queue or a cron job? The implementation team may choose.
- Should the billing job use a queue or cron? Product will decide after implementation begins.
- How should manually generated invoices from last month be handled?
- Should historical invoices be migrated?

## 13. Definition of done

The code is reviewed, tested, and deployed to production. Finance knows how to use the invoice export.
