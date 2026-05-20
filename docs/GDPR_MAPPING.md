# GDPR and CCPA Mapping

| Regulation | Requirement | Repo Implementation |
|---|---|---|
| GDPR Article 5 | Data minimization, purpose limitation, storage limitation | `privacy/policies/pii_policy.yaml`, `privacy/policies/retention_policy.yaml`, `dbt/models/privacy/mart_ml_training_safe.sql`, `dbt/models/privacy/mart_analytics_safe.sql` |
| GDPR Article 7 | Consent withdrawal | `privacy/dsr_handler.py`, `privacy/policies/consent_categories.yaml` |
| GDPR Article 15 | Right of access | `privacy/dsr_handler.py::handle_access_request`, Streamlit DSR demo |
| GDPR Article 17 | Right to erasure | `privacy/dsr_handler.py::handle_erasure_request`, downstream exclusion pattern in privacy marts |
| GDPR Article 25 | Data protection by design and by default | Privacy-safe marts, dbt invariant tests, PII policy-as-code |
| GDPR Article 30 | Records of processing activities | `privacy/audit_log.py`, Streamlit audit log viewer |
| CCPA Section 1798.105 | Right to deletion | `privacy/dsr_handler.py::handle_erasure_request` records CCPA section in audit event |

## Policy-to-Process Translation

The policy layer is declarative YAML. The process layer is implemented in Python and dbt:

1. `privacy/policies/pii_policy.yaml` classifies the data.
2. `privacy/pii_inventory.py` turns the policy into inventory records.
3. `dbt/models/privacy/stg_pii_inventory.sql` makes the inventory queryable in BigQuery.
4. `privacy/reidentification_risk.py` and `dbt/models/privacy/int_reidentification_risk.sql` quantify linkage risk.
5. `privacy/transformations.py` and dbt marts enforce safer outputs.
6. `privacy/dsr_handler.py` handles rights requests.
7. `privacy/audit_log.py` records every privacy action.

