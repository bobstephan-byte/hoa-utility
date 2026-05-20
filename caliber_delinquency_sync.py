"""
Sync Caliber delinquency records for the Treasurer dashboard.

The generated JSON contains owner/account financial information and is ignored
by Git via data/caliber_*.json.
"""

import json
import os
import sys
from datetime import datetime, timezone

from caliber_client import CaliberClient, CaliberConfigError
from parse_property_data import normalize_addr


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "caliber_delinquencies.json")
CLIENT_SEARCH = "wynbrooke"


def money_value(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_snapshot(client, delinquencies):
    records = []
    for row in delinquencies:
        address = str(row.get("Address", "")).strip()
        records.append({
            "display_name": row.get("DisplayName", ""),
            "unit_account_id": row.get("UnitAccountID"),
            "account_number": row.get("AccountNumber", ""),
            "address": address,
            "address_norm": normalize_addr(address) if address else "",
            "city": row.get("City", ""),
            "state": row.get("State", ""),
            "zip_code": row.get("ZipCode", ""),
            "stage_name": row.get("StageName", ""),
            "stage_code": row.get("StageCode", ""),
            "transaction_account": row.get("TAcctName", ""),
            "transaction_account_id": row.get("TAcctID"),
            "balance": money_value(row.get("Balance")),
        })

    total_balance = sum(record["balance"] for record in records)
    return {
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "client_id": client.get("ClientID"),
        "client_name": client.get("ClientName") or client.get("Name") or "Wynbrooke",
        "source": "Caliber FrontSteps API /client/{client_id}/delinquencies",
        "summary": {
            "accounts": len(records),
            "total_balance": total_balance,
            "stages": sorted({record["stage_name"] for record in records if record["stage_name"]}),
        },
        "records": records,
    }


def run_sync():
    client = CaliberClient.from_env()
    client.login()

    caliber_client = client.find_client(CLIENT_SEARCH)
    if not caliber_client:
        raise RuntimeError(f"No Caliber client found matching {CLIENT_SEARCH!r}")

    client_id = caliber_client["ClientID"]
    print(f"Found {caliber_client.get('ClientName', 'Wynbrooke')} clientId={client_id}")

    delinquencies = client.delinquencies(client_id)
    snapshot = build_snapshot(caliber_client, delinquencies)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

    summary = snapshot["summary"]
    print(f"Delinquent accounts: {summary['accounts']}")
    print(f"Total delinquent balance: ${summary['total_balance']:,.2f}")
    print(f"Results written to {OUTPUT_PATH}")
    return snapshot


if __name__ == "__main__":
    try:
        run_sync()
    except CaliberConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Caliber delinquency sync failed: {e}", file=sys.stderr)
        sys.exit(1)
