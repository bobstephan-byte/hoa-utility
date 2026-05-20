"""
Wynbrooke HOA — Rental Property Tracker Dashboard
"""

import json
import os
import re
import subprocess
import sys

import pandas as pd
import streamlit as st

from parse_property_data import normalize_addr

st.set_page_config(
    page_title="Wynbrooke Rental Tracker",
    page_icon="🏘️",
    layout="wide",
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(_BASE_DIR, "data", "wynbrooke_parcels.csv")
OVERRIDES_PATH = os.path.join(_BASE_DIR, "data", "overrides.json")
MARKET_MONITOR_PATH = os.path.join(_BASE_DIR, "data", "market_monitor_listings.json")
CALIBER_RENTALS_PATH = os.path.join(_BASE_DIR, "data", "caliber_registered_rentals.json")


# ── Overrides I/O ────────────────────────────────────────────────────────────

def load_overrides():
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, "r") as f:
            return json.load(f)
    return {}


def save_overrides(overrides):
    with open(OVERRIDES_PATH, "w") as f:
        json.dump(overrides, f, indent=2)


def load_market_data():
    if os.path.exists(MARKET_MONITOR_PATH):
        with open(MARKET_MONITOR_PATH, "r") as f:
            return json.load(f)
    return None


def load_caliber_data():
    if os.path.exists(CALIBER_RENTALS_PATH):
        with open(CALIBER_RENTALS_PATH, "r") as f:
            return json.load(f)
    return None


def caliber_registry_by_address(caliber_data):
    if not caliber_data:
        return {}
    registry = {}
    for record in caliber_data.get("records", []):
        norm = record.get("address_norm")
        if norm:
            registry[norm] = record
    return registry


def rental_ad_delta_rows(rental_ads, caliber_data):
    registry = caliber_registry_by_address(caliber_data)
    rows = []
    for listing in rental_ads:
        norm = normalize_addr(listing.get("address", ""))
        caliber_record = registry.get(norm)
        registered = bool(caliber_record and caliber_record.get("is_hoa_rental"))
        rows.append({
            "Address": listing.get("address", ""),
            "Caliber Registered": "Yes" if registered else "No",
            "Asking Rent": listing.get("list_price"),
            "Days Listed": listing.get("days_on_market"),
            "Agent": listing.get("listing_agent", ""),
            "Parcel Number": listing.get("parcel_number", ""),
            "Caliber Unit ID": caliber_record.get("unit_id") if caliber_record else "",
        })
    return rows


# ── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_base_data():
    df = pd.read_csv(DATA_PATH, dtype=str)
    df["likely_rental"] = df["likely_rental"].map({"True": True, "False": False})
    df["addr_match"] = df["addr_match"].map({"True": True, "False": False})
    df["status"] = df["likely_rental"].map({True: "Likely Rental", False: "Owner-Occupied"})

    # Extract section number from legal_desc
    def extract_section(desc):
        m = re.search(r'SEC\s*(\w+)', str(desc), re.IGNORECASE)
        return m.group(1) if m else "N/A"

    df["section"] = df["legal_desc"].apply(extract_section)

    # Build a combined mailing address column for display
    df["mailing_address"] = (
        df["owner_addr"] + ", " + df["owner_city"] + ", " +
        df["owner_state"] + " " + df["owner_zip"]
    )

    # Classify parcel type
    df["parcel_type"] = "Residential"
    df.loc[
        df["prop_addr"].str.contains("COMMON AREA", case=False, na=False),
        "parcel_type",
    ] = "Common Area"
    df.loc[
        df["legal_desc"].str.contains("APT|APARTMENT|UNITS", case=False, na=False),
        "parcel_type",
    ] = "Apartment Complex"

    # Refine status: common areas and apartments aren't "rentals"
    df.loc[df["parcel_type"] != "Residential", "status"] = df.loc[
        df["parcel_type"] != "Residential", "parcel_type"
    ]
    df.loc[df["parcel_type"] != "Residential", "likely_rental"] = False

    return df


def load_data():
    """Load base data and apply manual overrides on top."""
    df = load_base_data().copy()
    overrides = load_overrides()

    # Apply overrides to status and likely_rental
    for parcel_id, override in overrides.items():
        mask = df["parcel_number"] == parcel_id
        if not mask.any():
            continue
        manual_status = override.get("status")
        if manual_status == "Confirmed Rental":
            df.loc[mask, "status"] = "Confirmed Rental"
            df.loc[mask, "likely_rental"] = True
        elif manual_status == "False Positive":
            df.loc[mask, "status"] = "Owner-Occupied"
            df.loc[mask, "likely_rental"] = False
        note = override.get("note", "")
        df.loc[mask, "override_note"] = note

    if "override_note" not in df.columns:
        df["override_note"] = ""
    df["override_note"] = df["override_note"].fillna("")

    return df


df = load_data()
overrides = load_overrides()

# ── Header ───────────────────────────────────────────────────────────────────

st.title("Wynbrooke Rental Property Tracker")
st.caption("Hendricks County, IN — Source: Indiana Gateway Real Property File (2024 pay 2025)")

residential = df[df["parcel_type"] == "Residential"]
total_res = len(residential)
confirmed = len(residential[residential["status"] == "Confirmed Rental"])
likely = len(residential[residential["status"] == "Likely Rental"])
total_rentals = confirmed + likely
owner_occ = total_res - total_rentals
rate = total_rentals / total_res * 100 if total_res else 0
common_areas = len(df[df["parcel_type"] == "Common Area"])
apartments = len(df[df["parcel_type"] == "Apartment Complex"])
override_count = len(overrides)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Residential Parcels", total_res)
col2.metric("Owner-Occupied", int(owner_occ))
col3.metric("Rentals", int(total_rentals), help=f"{confirmed} confirmed, {likely} likely")
col4.metric("Rental Rate", f"{rate:.1f}%")

st.caption(
    f"Excludes {common_areas} HOA common areas and {apartments} apartment complex parcel(s) "
    f"from rental calculation. Total parcels in dataset: {len(df)}. "
    f"Manual overrides applied: {override_count}."
)

# ── Sidebar filters ─────────────────────────────────────────────────────────

st.sidebar.header("Filters")

status_filter = st.sidebar.radio(
    "Occupancy Status",
    ["All", "Likely Rentals", "Confirmed Rentals", "Owner-Occupied"],
)

owner_search = st.sidebar.text_input("Search Owner Name")

states = sorted(df["owner_state"].dropna().unique())
state_filter = st.sidebar.multiselect("Owner State", states, default=[])

sections = sorted(df["section"].unique(), key=lambda x: (x == "N/A", x))
section_filter = st.sidebar.multiselect("Wynbrooke Section", sections, default=[])

hide_non_residential = st.sidebar.checkbox("Hide common areas & apartments", value=True)

# Apply filters
filtered = df.copy()

if hide_non_residential:
    filtered = filtered[filtered["parcel_type"] == "Residential"]

if status_filter == "Likely Rentals":
    filtered = filtered[filtered["likely_rental"]]
elif status_filter == "Confirmed Rentals":
    filtered = filtered[filtered["status"] == "Confirmed Rental"]
elif status_filter == "Owner-Occupied":
    filtered = filtered[~filtered["likely_rental"]]

if owner_search:
    filtered = filtered[filtered["owner_name"].str.contains(owner_search, case=False, na=False)]

if state_filter:
    filtered = filtered[filtered["owner_state"].isin(state_filter)]

if section_filter:
    filtered = filtered[filtered["section"].isin(section_filter)]

# ── Main content ─────────────────────────────────────────────────────────────

tab_table, tab_analytics, tab_market, tab_delta = st.tabs([
    "Property Table",
    "Analytics",
    "Market Monitor",
    "Delta Report",
])

# ── Table tab ────────────────────────────────────────────────────────────────

with tab_table:
    st.subheader(f"Properties ({len(filtered)} of {len(df)})")

    display_cols = [
        "status", "prop_addr", "prop_city", "owner_name",
        "mailing_address", "sale_date", "section", "legal_desc",
    ]
    display_names = {
        "status": "Status",
        "prop_addr": "Property Address",
        "prop_city": "City",
        "owner_name": "Owner",
        "mailing_address": "Owner Mailing Address",
        "sale_date": "Sale Date",
        "section": "Section",
        "legal_desc": "Legal Description",
    }

    st.dataframe(
        filtered[display_cols].rename(columns=display_names).sort_values(
            ["Status", "Property Address"]
        ),
        use_container_width=True,
        height=600,
        column_config={
            "Status": st.column_config.TextColumn(width="small"),
            "Section": st.column_config.TextColumn(width="small"),
            "Sale Date": st.column_config.TextColumn(width="small"),
        },
    )

    # ── Override / correction UI ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Property Overrides")
    st.caption(
        "Select a property to manually mark as Confirmed Rental, False Positive, "
        "or add a note. Overrides persist across data refreshes."
    )

    # Build a lookup label for the selectbox: "address — owner (parcel)"
    filtered_sorted = filtered.sort_values("prop_addr")
    options = filtered_sorted["parcel_number"].tolist()
    labels = {
        row["parcel_number"]: f"{row['prop_addr'].strip()} — {row['owner_name'].strip()} ({row['parcel_number'].strip()})"
        for _, row in filtered_sorted.iterrows()
    }

    selected_parcel = st.selectbox(
        "Select Property",
        options=options,
        format_func=lambda x: labels.get(x, x),
    )

    if selected_parcel:
        prop_row = df[df["parcel_number"] == selected_parcel].iloc[0]
        current_override = overrides.get(selected_parcel.strip(), {})

        col_info, col_form = st.columns([1, 1])

        with col_info:
            st.markdown(f"**Address:** {prop_row['prop_addr'].strip()}")
            st.markdown(f"**Owner:** {prop_row['owner_name'].strip()}")
            st.markdown(f"**Mailing:** {prop_row['mailing_address'].strip()}")
            st.markdown(f"**Auto-detected status:** {'Likely Rental' if not prop_row['addr_match'] else 'Owner-Occupied'}")
            st.markdown(f"**Current status:** {prop_row['status']}")
            if current_override:
                st.info(f"This property has a manual override applied.")

        with col_form:
            status_options = ["No Override", "Confirmed Rental", "False Positive"]
            current_status_override = current_override.get("status")
            default_idx = (
                status_options.index(current_status_override)
                if current_status_override in status_options
                else 0
            )

            new_status = st.radio(
                "Override Status",
                status_options,
                index=default_idx,
                key="override_status",
            )

            new_note = st.text_area(
                "Note",
                value=current_override.get("note", ""),
                placeholder="e.g., Verified rental via lease on file, or: Owner confirmed resident",
                key="override_note",
            )

            col_save, col_clear = st.columns(2)

            with col_save:
                if st.button("Save Override", type="primary"):
                    parcel_key = selected_parcel.strip()
                    if new_status == "No Override" and not new_note.strip():
                        # Remove override entirely if nothing set
                        overrides.pop(parcel_key, None)
                    else:
                        entry = {}
                        if new_status != "No Override":
                            entry["status"] = new_status
                        if new_note.strip():
                            entry["note"] = new_note.strip()
                        overrides[parcel_key] = entry
                    save_overrides(overrides)
                    st.rerun()

            with col_clear:
                if current_override and st.button("Remove Override"):
                    overrides.pop(selected_parcel.strip(), None)
                    save_overrides(overrides)
                    st.rerun()

# ── Analytics tab ────────────────────────────────────────────────────────────

with tab_analytics:
    st.subheader("Rental Analysis")

    a1, a2 = st.columns(2)

    # Rentals by section
    with a1:
        st.markdown("**Rentals by Wynbrooke Section**")
        section_counts = (
            filtered[filtered["likely_rental"]]
            .groupby("section")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        if not section_counts.empty:
            st.bar_chart(section_counts.set_index("section")["count"])
        else:
            st.info("No rental properties in current filter.")

    # Top owner states (for rentals)
    with a2:
        st.markdown("**Rental Owner Locations (by State)**")
        rental_states = (
            filtered[filtered["likely_rental"]]
            .groupby("owner_state")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        if not rental_states.empty:
            st.bar_chart(rental_states.set_index("owner_state")["count"])
        else:
            st.info("No rental properties in current filter.")

    st.markdown("---")

    # Repeat / institutional owners
    st.markdown("**Top Repeat Owners (likely investors)**")
    repeat_owners = (
        filtered[filtered["likely_rental"]]
        .groupby("owner_name")
        .agg(properties=("prop_addr", "count"), addresses=("prop_addr", list))
        .sort_values("properties", ascending=False)
        .head(15)
    )
    if not repeat_owners.empty:
        for owner, row in repeat_owners.iterrows():
            if row["properties"] > 1:
                with st.expander(f"{owner} — {row['properties']} properties"):
                    for addr in sorted(row["addresses"]):
                        st.write(f"- {addr}")
    else:
        st.info("No repeat rental owners in current filter.")

# ── Market Monitor tab ──────────────────────────────────────────────────────

with tab_market:
    st.subheader("Market Monitor — Active Listing Intelligence")

    if st.button("Refresh Listings", type="primary"):
        with st.spinner("Scanning RentCast for active listings..."):
            result = subprocess.run(
                [sys.executable, os.path.join(_BASE_DIR, "listings_scan.py")],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                st.success("Listings refreshed successfully.")
            else:
                st.error(f"Scan failed: {result.stderr or result.stdout}")
        st.rerun()

    market_data = load_market_data()

    if market_data is None:
        st.info(
            "No listing data available yet. Click **Refresh Listings** above "
            "to scan for active for-sale and for-rent listings in the Wynbrooke area."
        )
    else:
        sale_listings = [r for r in market_data if r["listing_type"] == "for_sale"]
        rental_listings = [r for r in market_data if r["listing_type"] == "for_rent"]

        at_risk = [r for r in sale_listings if r["current_status"] == "Owner-Occupied"]
        relief = [r for r in sale_listings if r["current_status"] in ("Rental", "Likely Rental")]
        rental_ads = rental_listings

        # Last scanned timestamp
        last_scanned = ""
        if market_data:
            last_scanned = market_data[0].get("last_scanned", "N/A")

        # ── Summary metrics ─────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("At-Risk Sales", len(at_risk),
                   help="Owner-occupied homes listed for sale — could become rentals if bought by investors")
        m2.metric("Relief Watch", len(relief),
                   help="Confirmed rentals listed for sale — may return to owner-occupied status")
        m3.metric("Active Rental Ads", len(rental_ads),
                   help="Wynbrooke properties currently advertised for rent")
        m4.metric("Last Scanned", last_scanned[:10] if last_scanned else "N/A")

        # ── At-Risk Sales table ─────────────────────────────────────────
        st.markdown("---")
        st.markdown("**At-Risk Sales** — Owner-occupied homes listed for sale")
        st.caption("These could become rentals if purchased by investors.")
        if at_risk:
            at_risk_df = pd.DataFrame(at_risk)[
                ["address", "current_status", "list_price", "days_on_market", "listing_agent"]
            ].sort_values("days_on_market", ascending=True, na_position="last")
            at_risk_df.columns = ["Address", "Current Status", "List Price", "Days on Market", "Agent"]
            st.dataframe(at_risk_df, use_container_width=True, hide_index=True)
        else:
            st.info("No owner-occupied homes currently listed for sale in Wynbrooke.")

        # ── Relief Watch table ──────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Relief Watch** — Rental properties listed for sale")
        st.caption(
            "These current rentals are for sale and may return to owner-occupied status, "
            "potentially lowering the community's rental percentage."
        )
        if relief:
            relief_df = pd.DataFrame(relief)[
                ["address", "current_status", "list_price", "days_on_market", "listing_agent"]
            ].sort_values("days_on_market", ascending=True, na_position="last")
            relief_df.columns = ["Address", "Current Status", "List Price", "Days on Market", "Agent"]
            st.dataframe(relief_df, use_container_width=True, hide_index=True)
        else:
            st.info("No rental properties currently listed for sale in Wynbrooke.")

        # ── Active Rental Ads table ─────────────────────────────────────
        st.markdown("---")
        st.markdown("**Active Rental Ads** — Wynbrooke properties advertised for rent")
        if rental_ads:
            rental_df = pd.DataFrame(rental_ads)
            # Flag potential violations
            rental_df["flag"] = rental_df["current_status"].apply(
                lambda s: "Potential Violation" if s == "Owner-Occupied" else ""
            )
            display_df = rental_df[
                ["address", "current_status", "list_price", "days_on_market", "listing_agent", "flag"]
            ].sort_values("days_on_market", ascending=True, na_position="last")
            display_df.columns = ["Address", "Current Status", "Asking Rent", "Days Listed", "Agent", "Flag"]
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Flag": st.column_config.TextColumn(width="small"),
                },
            )
            # Warn about potential violations
            violations = rental_df[rental_df["flag"] == "Potential Violation"]
            if not violations.empty:
                st.warning(
                    f"{len(violations)} listing(s) flagged: property is listed for rent but "
                    f"recorded as owner-occupied — possible violation in progress."
                )
        else:
            st.info("No Wynbrooke properties currently advertised for rent.")

# ── Delta Report tab ────────────────────────────────────────────────────────

with tab_delta:
    st.subheader("Delta Report — Rental Ads vs HOA Registration")

    dcol1, dcol2 = st.columns([1, 3])
    with dcol1:
        if st.button("Sync Caliber Rentals", type="primary"):
            with st.spinner("Syncing Caliber rental registrations..."):
                result = subprocess.run(
                    [sys.executable, os.path.join(_BASE_DIR, "caliber_sync.py")],
                    capture_output=True, text=True, timeout=90,
                )
                if result.returncode == 0:
                    st.success("Caliber rentals synced successfully.")
                else:
                    st.error(f"Caliber sync failed: {result.stderr or result.stdout}")
            st.rerun()

    market_data = load_market_data()
    caliber_data = load_caliber_data()

    if market_data is None:
        st.info("No RentCast listing data available yet. Refresh listings from the Market Monitor tab.")
    elif caliber_data is None:
        st.info("No Caliber rental registration snapshot available yet. Click Sync Caliber Rentals.")
    else:
        rental_ads = [r for r in market_data if r.get("listing_type") == "for_rent"]
        delta_rows = rental_ad_delta_rows(rental_ads, caliber_data)
        unregistered_ads = [row for row in delta_rows if row["Caliber Registered"] == "No"]
        registered_ads = [row for row in delta_rows if row["Caliber Registered"] == "Yes"]
        summary = caliber_data.get("summary", {})
        last_synced = caliber_data.get("last_synced", "")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Active Rental Ads", len(rental_ads))
        m2.metric("Not Registered", len(unregistered_ads))
        m3.metric("Registered Ads", len(registered_ads))
        m4.metric("Caliber Rentals", summary.get("hoa_rental_units", 0))

        st.caption(
            f"Caliber snapshot: {last_synced[:10] if last_synced else 'N/A'}. "
            f"Matched by normalized street address."
        )

        st.markdown("---")
        st.markdown("**Listed for rent but not registered in Caliber**")
        if unregistered_ads:
            st.dataframe(
                pd.DataFrame(unregistered_ads).sort_values(
                    "Days Listed", ascending=True, na_position="last"
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Parcel Number": st.column_config.TextColumn(width="medium"),
                    "Caliber Unit ID": st.column_config.TextColumn(width="small"),
                },
            )
            st.warning(
                f"{len(unregistered_ads)} active rental ad(s) are not marked as HOA rentals in Caliber."
            )
        else:
            st.success("No active rental ads are missing from Caliber registration.")

        st.markdown("---")
        st.markdown("**All active rental ads with Caliber registration status**")
        if delta_rows:
            st.dataframe(
                pd.DataFrame(delta_rows).sort_values(
                    ["Caliber Registered", "Days Listed"],
                    ascending=[True, True],
                    na_position="last",
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Parcel Number": st.column_config.TextColumn(width="medium"),
                    "Caliber Unit ID": st.column_config.TextColumn(width="small"),
                },
            )
        else:
            st.info("No active Wynbrooke rental ads in the current Market Monitor snapshot.")
