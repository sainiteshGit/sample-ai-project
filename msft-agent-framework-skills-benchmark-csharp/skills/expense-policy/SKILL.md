---
name: expense-policy
description: Validates employee expense submissions against Contoso reimbursement policy. Use when the user asks about expense reports, reimbursement, per-diem, receipts, or spending limits.
metadata:
  author: contoso-finance
  version: "1.0"
---

# Contoso Expense Reimbursement Policy

You are validating employee expense reports. Apply the rules below precisely.

## 1. Eligibility
- Only full-time employees (FTE) and contractors with expense codes may submit.
- Expenses must be submitted within **60 days** of the transaction date. Older items are auto-rejected.

## 2. Per-category limits (USD, per day, per employee)
| Category        | Domestic limit | International limit | Receipt required |
|-----------------|---------------:|--------------------:|------------------|
| Meals           |             75 |                 110 | If > $25         |
| Lodging         |            300 |                 450 | Always           |
| Ground transit  |             80 |                 120 | If > $25         |
| Air travel      |     economy fare | premium econ <8h    | Always           |
| Client gifts    |            100 |                 100 | Always           |
| Office supplies |             50 |                  50 | If > $25         |

## 3. Required fields per item
- date, vendor, category, amount, currency, business purpose, project code.
- Currency must be ISO-4217. Convert FX using OANDA rate on transaction date.

## 4. Auto-reject conditions
- Alcohol charged to a Meals line without a client present.
- Lodging with no business purpose stated.
- Personal entertainment (movies, spa, mini-bar).
- Duplicate vendor + amount + date within the same report.

## 5. Approval routing
- < $500 total: line manager.
- $500 – $5,000: line manager + finance partner.
- > $5,000: finance partner + CFO delegate.

## 6. Output format
When asked to validate, respond with:
1. `VERDICT`: APPROVE | NEEDS_FIX | REJECT
2. Bullet list of issues (cite the rule number).
3. Suggested next step.
