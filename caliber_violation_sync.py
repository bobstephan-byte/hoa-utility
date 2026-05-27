"""
Sync Caliber violation records for the HOA dashboard.

The generated JSON may contain owner/unit violation information and is ignored
by Git via data/caliber_*.json.
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from caliber_client import CaliberClient, CaliberConfigError
from parse_property_data import normalize_addr


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "caliber_violations.json")
CLIENT_SEARCH = "wynbrooke"


def clean_text(value):
    return str(value or "").strip()


def money_value(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_date(value):
    value = clean_text(value)
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


def date_year(value):
    date_value = parse_date(value)
    return int(date_value[:4]) if date_value[:4].isdigit() else None


def violation_year(row):
    return date_year(row.get("ViolationDate")) or date_year(row.get("DateCreated"))


def build_snapshot(client, violations, year=None):
    year = year or datetime.now().year
    records = []

    for row in violations:
        if violation_year(row) != year:
            continue

        address = clean_text(row.get("Address"))
        category = clean_text(row.get("CategoryName")) or "Uncategorized"
        status = clean_text(row.get("Status")) or "Unknown"
        ccr = row.get("CCR") if isinstance(row.get("CCR"), dict) else {}

        records.append({
            "violation_id": row.get("ViolationID"),
            "violation_number": clean_text(row.get("ViolationNumber")),
            "unit_id": row.get("UnitID"),
            "unit_account_id": row.get("UnitAccountID"),
            "owner": clean_text(row.get("Owner")),
            "address": address,
            "address_norm": normalize_addr(address) if address else "",
            "category": category,
            "item": clean_text(row.get("ItemName")),
            "status": status,
            "violation_date": parse_date(row.get("ViolationDate")),
            "due_date": parse_date(row.get("DueDate")),
            "closed_date": parse_date(row.get("ClosedDate")),
            "date_created": parse_date(row.get("DateCreated")),
            "last_modified": parse_date(row.get("LastModified")),
            "required_action": clean_text(row.get("RequiredAction")),
            "next_action": clean_text(row.get("NextAction")),
            "inspector": clean_text(row.get("Inspector")),
            "source": clean_text(row.get("Source")),
            "pending_fine_amount": money_value(row.get("PendingFineAmount")),
            "has_letters": bool(row.get("HasLetters")),
            "has_pictures": bool(row.get("HasPictures")),
            "ccr_code": clean_text(ccr.get("Code")),
        })

    status_counts = Counter(record["status"] for record in records)
    category_counts = Counter(record["category"] for record in records)
    open_records = [
        record
        for record in records
        if record["status"].lower() not in {"closed", "resolved"}
    ]

    return {
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "client_id": client.get("ClientID"),
        "client_name": client.get("ClientName") or client.get("Name") or "Wynbrooke",
        "source": "Caliber FrontSteps API /client/{client_id}/violations/all",
        "year": year,
        "summary": {
            "violations": len(records),
            "open_violations": len(open_records),
            "closed_violations": len(records) - len(open_records),
            "pending_fines": sum(record["pending_fine_amount"] for record in records),
            "statuses": dict(sorted(status_counts.items())),
            "top_categories": dict(category_counts.most_common(10)),
        },
        "records": records,
    }


def run_sync(year=None):
    client = CaliberClient.from_env()
    client.login()

    caliber_client = client.find_client(CLIENT_SEARCH)
    if not caliber_client:
        raise RuntimeError(f"No Caliber client found matching {CLIENT_SEARCH!r}")

    client_id = caliber_client["ClientID"]
    print(f"Found {caliber_client.get('ClientName', 'Wynbrooke')} clientId={client_id}")

    violations = client.violations(client_id, "all")
    snapshot = build_snapshot(caliber_client, violations, year=year)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

    summary = snapshot["summary"]
    print(f"Violation year: {snapshot['year']}")
    print(f"Violations: {summary['violations']}")
    print(f"Open violations: {summary['open_violations']}")
    print(f"Results written to {OUTPUT_PATH}")
    return snapshot


if __name__ == "__main__":
    try:
        requested_year = int(sys.argv[1]) if len(sys.argv) > 1 else None
        run_sync(year=requested_year)
    except CaliberConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Caliber violation sync failed: {e}", file=sys.stderr)
        sys.exit(1)
