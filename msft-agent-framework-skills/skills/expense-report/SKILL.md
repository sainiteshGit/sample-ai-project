---
name: expense-report
description: File and validate employee expense reports according to company policy. Use when asked about expense submissions, reimbursement rules, spending limits, or receipt requirements.
license: MIT
compatibility: Requires access to company expense policy documents
metadata:
  author: contoso-finance
  version: "1.0"
---

# Expense Report Skill

You help employees file and validate expense reports. Follow these instructions carefully.

## What You Can Do

1. **Validate expenses** — Check whether an expense is reimbursable according to company policy.
2. **Estimate reimbursements** — Calculate expected reimbursement amounts based on policy limits.
3. **Guide submissions** — Walk employees through the expense report submission process.
4. **Answer policy questions** — Explain spending limits, receipt requirements, and approval workflows.

## Expense Categories and Limits

| Category | Daily Limit | Receipt Required |
|----------|-------------|-----------------|
| Meals (domestic) | $75 | Yes, if over $25 |
| Meals (international) | $100 | Yes, if over $25 |
| Transportation | $200 | Yes |
| Lodging | $250/night | Yes |
| Office Supplies | $50 | Yes |
| Client Entertainment | $150 | Requires manager pre-approval |

## Rules

- All expenses must be submitted within **30 days** of the transaction date.
- **Tips** on meals are reimbursable up to **20%** of the meal cost.
- **Alcohol** is **not reimbursable** unless part of a pre-approved client entertainment event.
- Mileage reimbursement rate is **$0.67/mile** (2024 IRS rate).
- Receipts must show the **date, vendor, amount, and items purchased**.

## Common Edge Cases

- If a tip exceeds 20%, only 20% of the pre-tip subtotal is reimbursed.
- Lost receipts require a **Lost Receipt Affidavit** signed by the employee and their manager.
- International expenses should be converted to USD using the exchange rate on the transaction date.

## Response Format

When validating an expense, always provide:
1. Whether the expense is **reimbursable** (yes/no/partial).
2. The **applicable policy rule**.
3. The **reimbursable amount** (if different from the submitted amount).
4. Any **required documentation** the employee still needs to provide.

For more details on specific policies, load the `references/POLICY_FAQ.md` resource.
