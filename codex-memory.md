# Codex Project Memory: HOA Market Monitor

Last reviewed: 2026-05-19

## Current Project Shape

This is a compact Streamlit dashboard for the Wynbrooke HOA rental tracking workflow.

- `app.py` is the main Streamlit entry point.
- `parse_property_data.py` parses the Hendricks County fixed-width parcel export and owns `normalize_addr()`.
- `listings_scan.py` calls RentCast and writes matched active listings to `data/market_monitor_listings.json`.
- `frontsteps_probe.py` is a Caliber/FrontSteps API discovery script.
- `caliber_client.py` contains the reusable Caliber API client and documented v2 auth header.
- `caliber_sync.py` writes a local non-PII Caliber rental snapshot to `data/caliber_registered_rentals.json`.
- `data/wynbrooke_parcels.csv` is the processed authoritative parcel list.
- `data/overrides.json` is the manual correction layer.
- `data/caliber_registered_rentals.json` is generated locally and intentionally ignored.

## Data Snapshot From Review

The parsed parcel CSV currently contains 630 Wynbrooke records.

- 462 records have matching property and owner mailing addresses.
- 168 records are flagged as likely rentals by address mismatch.
- 23 records appear to be common areas.
- 1 record appears to be an apartment complex parcel.

The current market monitor JSON contains 5 RentCast matches, all `for_rent`, all currently marked `Rental`, last scanned on 2026-04-09.

The Caliber sync currently returns:

- 615 units.
- 43 HOA rental units from `IsHOARental`.
- 36 units with active renter contacts.
- Wynbrooke `ClientID` is 191.

## Git State At Review

Current branch during review: `feature/market-monitor`.

Existing pre-integration work observed before this note:

- Modified: `data/market_monitor_listings.json`
- Untracked at the time: `frontsteps_probe.py`

## Implementation Notes

- Address matching should continue to use `normalize_addr()` from `parse_property_data.py`; do not create a parallel normalization approach without a good reason.
- RentCast should be treated as a listing smoke detector, not the authoritative rental source.
- Caliber/FrontSteps is now the authoritative source for HOA rental registration.
- The Delta Report compares active RentCast rental ads against Caliber `IsHOARental` registrations by normalized street address.

## Likely Next Steps

1. Improve fuzzy address matching across county data, RentCast, and Caliber/FrontSteps.
2. Decide whether `IsHOARental`, `IsRenter`, or a combined rule should drive board-facing compliance reporting.
3. Consider moving the Caliber sync button/status into a small admin section if the dashboard grows.
4. Replace deprecated Streamlit `use_container_width=True` usages with `width="stretch"` before the 2025-12-31 removal.

## Verification From Review

Python compilation succeeded for:

- `app.py`
- `listings_scan.py`
- `parse_property_data.py`
- `download_property_data.py`
- `frontsteps_probe.py`
- `caliber_client.py`
- `caliber_sync.py`

Compilation was run with `PYTHONPYCACHEPREFIX` pointed at `/private/tmp` to avoid macOS cache writes outside the workspace.

Caliber sync and Streamlit startup were also verified. Streamlit ran at `http://localhost:8501`.
