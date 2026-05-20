# Privacy Policy Artifact: NYC Taxi Data Trust Layer

## Purpose

This document defines the privacy controls implemented by the NYC Taxi Data Trust Layer. The project uses public NYC TLC yellow cab trip records, but treats the data as consumer-adjacent because trip time, location, payment type, and fare attributes can be combined into quasi-identifiers.

The goal is not to claim full production legal compliance. The goal is to demonstrate how privacy requirements can be translated into concrete data engineering controls: policy-as-code, inventory, transformation, consent gating, data subject request handling, and auditability.

## Scope

Covered data includes records from `stg_yellow_trips` and downstream privacy models under `dbt/models/privacy/`. In BigQuery, the privacy models are isolated in the `nyc_taxi_privacy_layer` dataset so privacy marts and compliance artifacts are separate from the core trust-score dataset.

Covered controls include:

- PII and quasi-identifier inventory
- Re-identification risk scoring using k-anonymity
- Suppression of precise GPS columns in privacy-safe marts
- Generalization of timestamps into hour/day features
- Synthetic consent gating for ML training and analytics
- Data subject access, erasure, and consent-withdrawal handlers
- Append-only privacy audit logging

## Data Categories

The dataset contains no known rider name, phone number, email, or government identifier. It does contain quasi-identifiers:

| Category | Columns | Handling |
|---|---|---|
| Precise location traces | `pickup_longitude`, `pickup_latitude`, `dropoff_longitude`, `dropoff_latitude` | Suppress from privacy marts |
| Coarse location traces | `pu_location_id`, `do_location_id` | Retain only with k-anonymity controls |
| Temporal traces | `pickup_at`, `dropoff_at` | Generalize to hour and weekday |
| Payment behavior | `payment_type`, `fare_amount`, `tip_amount`, `total_amount` | Retain only in consented/k-anonymous outputs |
| Operational identifiers | `vendor_id`, generated `trip_id` | Pseudonymize where row-level output is needed |

The canonical policy is stored in `privacy/policies/pii_policy.yaml`.

## Legal Basis and Control Mapping

This project maps engineering controls to GDPR and CCPA concepts:

- **GDPR Article 5**: data minimization and storage limitation through suppression/generalization policies.
- **GDPR Article 15**: access request handler returns all known data for a trip identifier in the demo store.
- **GDPR Article 17** and **CCPA Section 1798.105**: erasure request handler marks records for deletion and downstream exclusion.
- **GDPR Article 25**: privacy by design through dbt marts that expose transformed data by default.
- **GDPR Article 30**: audit log records privacy processing events.

See `docs/GDPR_MAPPING.md` for a file-level mapping.

## Consent Model

The TLC public dataset has no real consent records. This repo uses synthetic consent to demonstrate the pattern that would exist in a production consumer ML system.

Consent categories are defined in `privacy/policies/consent_categories.yaml`:

- `ml_training`
- `analytics`
- `operational`

The ML-safe mart requires `consent_ml_training = true`. The analytics mart requires `consent_analytics = true` and k-anonymous aggregate cells. Operational access is reserved for DSR and support-style workflows.

## Retention

Retention windows are defined in `privacy/policies/retention_policy.yaml`.

The policy distinguishes raw trip events, transformed ML features, and privacy audit logs. Raw precise location and timestamps should be suppressed or aggregated after the retention window. Audit logs are retained longer because they support accountability and records of processing activity.

## Re-identification Risk

The project uses k-anonymity over a practical quasi-identifier set:

```text
pickup zone, dropoff zone, pickup hour, pickup weekday
```

Rows with `k < 5` are treated as high re-identification risk. The ML-safe mart excludes these rows. The analytics mart exposes only aggregate cells with at least five trips.

This is a baseline control, not a complete privacy guarantee. Production systems should evaluate l-diversity, t-closeness, differential privacy, and threat-model-specific controls.

## Data Subject Rights

The Python module `privacy/dsr_handler.py` implements demo handlers for:

- Access request: returns associated data if available.
- Erasure request: marks a trip for downstream exclusion.
- Consent withdrawal: withdraws one processing category without deleting the record.

Every request writes an audit event through `privacy/audit_log.py`.

## Accountability

The audit log schema is:

```text
event_id, event_type, trip_id, gdpr_article, ccpa_section, timestamp, actor, details_json
```

The local demo uses `InMemoryPrivacyAuditLog`; the BigQuery adapter in `privacy/audit_log.py` can append the same event records to a warehouse table.

## Known Limitations

- Consent records are synthetic and deterministic for reproducible demos.
- This is an engineering proof of concept, not legal advice or a DPO-approved production policy.
- k-anonymity is a floor, not the ceiling.
- The dataset is public, but the linkage risks are real and documented.
