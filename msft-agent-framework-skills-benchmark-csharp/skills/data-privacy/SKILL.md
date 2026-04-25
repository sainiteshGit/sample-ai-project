---
name: data-privacy
description: Classifies data handling requests under GDPR / CCPA and Contoso privacy rules. Use for questions about PII, data retention, deletion requests, consent, or sharing customer data.
metadata:
  author: contoso-privacy
  version: "1.4"
---

# Contoso Data Privacy Handling

## 1. Data classes
- **P0 — Sensitive PII**: government ID, payment card, biometric, health, precise geolocation, minors' data.
- **P1 — PII**: name, email, phone, address, IP, device ID.
- **P2 — Pseudonymous**: hashed user ID, cohort tags.
- **P3 — Public**: marketing pages, public docs.

## 2. Retention defaults
| Class | Default retention | Encryption at rest |
|-------|-------------------|--------------------|
| P0    | 30 days           | AES-256 + HSM key  |
| P1    | 24 months         | AES-256            |
| P2    | 36 months         | AES-256            |
| P3    | unlimited         | optional           |

## 3. Subject rights (GDPR Art. 15–22 / CCPA §1798.100)
- Access request: respond within **30 days**, deliver as JSON or CSV.
- Deletion request: complete within **30 days**, includes backups within **90 days**.
- Rectification: within 30 days.
- Portability: machine-readable export of P0+P1 data the user provided.

## 4. Sharing / transfer rules
- Cross-border transfer of P0 requires Standard Contractual Clauses (SCCs) and a DPIA.
- No sharing of P0/P1 with third parties without explicit opt-in consent.
- Aggregated stats from ≥ 50 distinct users may be shared without consent.

## 5. Output format
1. `CLASSIFICATION`: P0 | P1 | P2 | P3
2. `REQUIRED_ACTION`: list (encryption, deletion deadline, consent check, etc.)
3. `LEGAL_BASIS`: cite article / section.
4. Risk callouts if any.
