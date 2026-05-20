# Re-identification Risk

## Why Taxi Trips Are Privacy-Relevant

NYC TLC trip records do not include names, emails, or phone numbers. They do include location, time, payment, and fare information. These fields are quasi-identifiers: individually they may seem harmless, but in combination they can describe a person's routine.

The well-known Anthony Tockar analysis "Riding with the Stars" showed how NYC taxi trip data could be linked with public sightings and other auxiliary data to infer trips by specific people. This repo treats that attack as the motivating privacy threat model.

## Threat Model

An attacker may know:

- Approximate pickup and dropoff location
- Approximate pickup time
- A public event or celebrity sighting
- Payment/tip behavior or trip fare range

The attacker tries to find a unique or very small equivalence class in the taxi dataset.

## k-Anonymity Control

This repo computes k-anonymity over:

```text
pickup zone, dropoff zone, pickup hour, pickup weekday
```

If fewer than five trips share the same combination, the row is high risk.

Implemented in:

- `privacy/reidentification_risk.py`
- `dbt/models/privacy/int_reidentification_risk.sql`

## Mitigation

The privacy layer mitigates linkage risk by:

- Removing raw GPS coordinates from privacy-safe marts.
- Replacing precise timestamps with hour/day features.
- Excluding high-risk `k < 5` rows from row-level ML training output.
- Publishing analytics output only as aggregate cells with `trip_count >= 5`.
- Requiring synthetic consent flags before rows enter privacy marts.

## Demonstrated Attack

`privacy/reidentification_risk.py::simulate_tockar_attack` includes a deterministic demo:

- Raw records make the target trip unique (`k = 1`).
- Generalized records merge the target into a larger group.
- The attack succeeds on raw data and fails after transformation.

## Limitations

k-anonymity does not protect against all inference attacks. It does not guarantee diversity of sensitive values inside a group, and it can be brittle under repeated releases. Production systems should consider l-diversity, t-closeness, or differential privacy depending on the use case.

