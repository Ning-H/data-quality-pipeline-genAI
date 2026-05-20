# Consent Model

## Why Consent Is Synthetic

NYC TLC public trip data does not ship with rider-level consent records. A production consumer ML system would receive consent state from a consent management platform or privacy ledger. This repo synthesizes consent deterministically so the pattern is testable and reproducible.

## Consent Categories

Defined in `privacy/policies/consent_categories.yaml`:

| Category | Purpose | Demo Default |
|---|---|---|
| `ml_training` | Use transformed row-level features for ML training/evaluation | 80% opt-in |
| `analytics` | Use k-anonymized aggregate records for reporting | 90% opt-in |
| `operational` | Support, fraud, legal, and access workflows | 100% available |

## Enforcement

The dbt privacy marts enforce consent:

- `mart_ml_training_safe.sql` requires `consent_ml_training`.
- `mart_analytics_safe.sql` requires `consent_analytics`.

The DSR handler supports category-specific withdrawal through `handle_consent_withdrawal`.

## Production Pattern

In production, synthetic generation would be replaced by a join to a source-of-truth consent table with:

- Subject identifier
- Consent category
- Consent status
- Collection source
- Effective timestamp
- Expiration or withdrawal timestamp
- Audit event reference

