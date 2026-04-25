---
name: refund-policy
description: Determines whether a customer order qualifies for a refund, partial refund, or store credit under Contoso retail policy. Use for refund requests, returns, exchanges, or chargeback inquiries.
metadata:
  author: contoso-cx
  version: "2.3"
---

# Contoso Retail Refund Policy

## 1. Time windows
- **30 days** from delivery: full refund to original payment method.
- **31–60 days**: store credit only (110% of paid amount).
- **61–90 days**: store credit at 80% of paid amount, manager approval.
- **> 90 days**: no refund, repair only (if covered by warranty).

## 2. Condition requirements
| Item state               | 0–30d         | 31–60d        | 61–90d        |
|--------------------------|---------------|---------------|---------------|
| Sealed / unopened        | Full refund   | 110% credit   | 80% credit    |
| Opened, unused           | Full refund   | 100% credit   | 60% credit    |
| Used, no damage          | 80% refund    | 70% credit    | None          |
| Damaged by customer      | None          | None          | None          |
| DOA / defective          | Full refund + free replacement, any window |

## 3. Non-refundable categories
- Personalized / engraved items.
- Digital downloads after activation.
- Gift cards.
- Final-sale clearance items (marked at checkout).

## 4. Required evidence
- Order ID (CON-XXXXXXXX).
- Photo for damaged / DOA items.
- Original packaging for full refunds.

## 5. Output format
Respond with:
1. `DECISION`: FULL_REFUND | PARTIAL_REFUND | STORE_CREDIT | DENIED
2. Amount and method.
3. Cite the matching rule.
4. Next steps for the customer.
