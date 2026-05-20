import pandas as pd
import plotly.express as px
import streamlit as st

from privacy.audit_log import InMemoryPrivacyAuditLog
from privacy.dsr_handler import DataSubjectRequestHandler, PrivacyDataStore
from privacy.pii_inventory import inventory_as_dicts
from privacy.reidentification_risk import compute_k_anonymity, simulate_tockar_attack, summarize_risk
from privacy.transformations import transform_trip


STAGING_COLUMNS = [
    "vendor_id",
    "pickup_at",
    "dropoff_at",
    "passenger_count",
    "trip_distance_miles",
    "pickup_longitude",
    "pickup_latitude",
    "dropoff_longitude",
    "dropoff_latitude",
    "pu_location_id",
    "do_location_id",
    "payment_type",
    "fare_amount",
    "tip_amount",
    "total_amount",
    "data_year",
    "data_month",
    "schema_version",
]


SAMPLE_TRIPS = [
    {"trip_id": "trip-001", "pickup_at": "2020-04-01T08:15:00", "pu_location_id": 161, "do_location_id": 230, "fare_amount": 11.5, "pickup_longitude": -73.98, "pickup_latitude": 40.75},
    {"trip_id": "trip-002", "pickup_at": "2020-04-01T08:20:00", "pu_location_id": 161, "do_location_id": 230, "fare_amount": 12.0, "pickup_longitude": -73.98, "pickup_latitude": 40.75},
    {"trip_id": "trip-003", "pickup_at": "2020-04-01T08:35:00", "pu_location_id": 161, "do_location_id": 230, "fare_amount": 10.5, "pickup_longitude": -73.98, "pickup_latitude": 40.75},
    {"trip_id": "trip-004", "pickup_at": "2020-04-01T08:40:00", "pu_location_id": 161, "do_location_id": 230, "fare_amount": 13.0, "pickup_longitude": -73.98, "pickup_latitude": 40.75},
    {"trip_id": "trip-005", "pickup_at": "2020-04-01T08:55:00", "pu_location_id": 161, "do_location_id": 230, "fare_amount": 9.5, "pickup_longitude": -73.98, "pickup_latitude": 40.75},
    {"trip_id": "trip-006", "pickup_at": "2020-04-01T23:10:00", "pu_location_id": 132, "do_location_id": 148, "fare_amount": 55.0, "pickup_longitude": -73.78, "pickup_latitude": 40.64},
]


def _risk_frame(show_transformed: bool) -> pd.DataFrame:
    records = SAMPLE_TRIPS
    if show_transformed:
        records = [
            {
                **trip,
                "pu_location_id": "airport_or_manhattan" if trip["pu_location_id"] in (132, 161) else trip["pu_location_id"],
                "do_location_id": "manhattan",
            }
            for trip in SAMPLE_TRIPS
        ]
    return pd.DataFrame(compute_k_anonymity(records, k_threshold=5))


def _demo_handler() -> tuple[DataSubjectRequestHandler, InMemoryPrivacyAuditLog]:
    audit = InMemoryPrivacyAuditLog()
    store = PrivacyDataStore(trips={trip["trip_id"]: trip for trip in SAMPLE_TRIPS})
    return DataSubjectRequestHandler(store, audit), audit


def render_privacy_compliance_card():
    st.subheader("Privacy & Compliance")
    st.caption(
        "Policy-as-code controls for quasi-identifiers, k-anonymity risk, synthetic consent, "
        "data subject requests, and auditability."
    )

    tab_inventory, tab_risk, tab_dsr, tab_audit = st.tabs([
        "PII Inventory",
        "Re-identification Risk",
        "DSR Demo",
        "Audit Log",
    ])

    with tab_inventory:
        st.markdown("**PII Inventory**")
        st.write("The policy marks precise location, time, payment, and fare fields as privacy-relevant.")
        inventory = pd.DataFrame(inventory_as_dicts("stg_yellow_trips", STAGING_COLUMNS))
        st.dataframe(
            inventory[["column_name", "pii_type", "sensitivity", "handling", "rationale"]],
            use_container_width=True,
            hide_index=True,
        )
        handling_counts = inventory.groupby(["handling", "sensitivity"]).size().reset_index(name="columns")
        fig = px.bar(
            handling_counts,
            x="handling",
            y="columns",
            color="sensitivity",
            title="Policy Handling by Sensitivity",
            color_discrete_map={"high": "#d1495b", "medium": "#e8c547", "low": "#4d9078"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_risk:
        st.markdown("**Re-identification Risk**")
        show_transformed = st.toggle("Show transformed/generalized data", value=False)
        risk_df = _risk_frame(show_transformed)
        summary = summarize_risk(risk_df.to_dict("records"))

        c1, c2, c3 = st.columns(3)
        c1.metric("Records", f"{summary['total_records']:,}")
        c2.metric("High-Risk Records", f"{summary['high_risk_records']:,}")
        c3.metric("High-Risk Rate", f"{summary['high_risk_rate'] * 100:.1f}%")

        heatmap = risk_df.pivot_table(
            index="pu_location_id",
            columns="pickup_hour",
            values="k_anonymity",
            aggfunc="min",
            fill_value=0,
        )
        fig = px.imshow(
            heatmap,
            text_auto=True,
            color_continuous_scale="RdYlGn",
            title="Minimum k-Anonymity by Pickup Location and Hour",
            aspect="auto",
        )
        st.plotly_chart(fig, use_container_width=True)

        attack = simulate_tockar_attack()
        st.info(
            "Tockar-style linkage demo: "
            f"raw target k={attack['raw_target_k']}; "
            f"after transformation k={attack['transformed_target_k']}."
        )

    with tab_dsr:
        st.markdown("**Data Subject Request Demo**")
        handler, _ = _demo_handler()
        trip_id = st.selectbox("Trip identifier", [trip["trip_id"] for trip in SAMPLE_TRIPS])

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Access Request", use_container_width=True):
                st.json(handler.handle_access_request(trip_id))
        with col2:
            if st.button("Erasure Request", use_container_width=True):
                st.json(handler.handle_erasure_request(trip_id))
        with col3:
            if st.button("Withdraw ML Consent", use_container_width=True):
                st.json(handler.handle_consent_withdrawal(trip_id, "ml_training"))

        st.markdown("**Transformation Example**")
        st.json(transform_trip(SAMPLE_TRIPS[0]))
        st.caption("Raw coordinates and precise timestamps are removed; a salted pseudonym replaces the row identifier.")

    with tab_audit:
        st.markdown("**Audit Log Viewer**")
        handler, audit = _demo_handler()
        handler.handle_access_request("trip-001", actor="demo")
        handler.handle_consent_withdrawal("trip-001", "ml_training", actor="demo")
        handler.handle_erasure_request("trip-006", actor="demo")
        st.dataframe(pd.DataFrame(audit.records()), use_container_width=True, hide_index=True)

