# HOA Utility

## What This Is
A Streamlit dashboard for the Wynbrooke HOA board (Hendricks County, Indiana).
Tracks parcel ownership, identifies non-owner-occupied (rental) properties,
monitors the local real estate market for the subdivision (ZIP: 46234), and
provides a local Treasurer ledger for delinquency follow-up.

## Entry Point
- `app.py` — run with: `streamlit run app.py`
- Local: http://localhost:8501
- Deployed: https://hoa.bstephan.net (via Cloudflare Tunnel)

## File Structure
- `app.py` — Streamlit app (Parcels, Market Monitor, Delta Report, Treasurer)
- `listings_scan.py` — CLI: calls RentCast API, writes to market_monitor_listings.json
- `parse_property_data.py` — parses raw property data, contains normalize_addr()
- `download_property_data.py` — downloads raw county property data
- `data/wynbrooke_parcels.csv` — master parcel list for Wynbrooke subdivision
- `data/overrides.json` — manual corrections layer on top of parcel data
- `data/market_monitor_listings.json` — TinyDB store for RentCast listings
- `data/delinquencies.csv` — local Treasurer delinquency ledger (never commit)
- `data/delinquencies_template.csv` — import template for the Treasurer ledger
- `.env` — API keys (never commit)
- `venv/` — local virtual environment (never commit)

## Stack
- Python 3.9 (system Python on Mac Mini)
- Streamlit 1.50+
- TinyDB 4.8+
- pandas, python-dotenv, requests
- Always use `python3` not `python`

## Key Functions & Patterns
- `normalize_addr()` in parse_property_data.py — normalizes address strings for
  cross-referencing parcels against RentCast listings. Always use this for any
  address matching, never roll a new approach.
- subprocess to invoke listings_scan.py from the Streamlit UI (Refresh button)
- Overrides layer: manual edits go in overrides.json, never directly in the CSV
- Treasurer delinquency records are stored in ignored local CSV data, not Git

## RentCast API
- Key: RENTCAST_API_KEY in .env
- **Developer plan: 50 requests/month — use sparingly, never in loops**
- Covers for-sale and for-rent listings in ZIP 46234
- listings_scan.py handles all API calls

## Code Style
- `st.tabs()` for layout (Parcels, Market Monitor, Delta Report, Treasurer)
- Sidebar for filters
- `st.metric()` for summary stats at top of each tab
- `st.dataframe()` with `use_container_width=True, hide_index=True`
- Graceful error handling with visible user-facing messages

## Git
- Remote: https://github.com/bobstephan-byte/hoa-utility
- Branch: main
- Never commit: venv/, .env, data/*.json, data/delinquencies.csv

## Roadmap / Pending
- Consider syncing delinquency balances from Caliber Billing Records once the
  exact endpoint and permissions are confirmed.
