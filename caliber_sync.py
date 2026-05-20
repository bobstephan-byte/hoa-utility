"""
Sync non-PII Caliber rental registration data for the Streamlit dashboard.

The generated JSON stores unit addresses and rental flags only. Raw owner/contact
responses should remain in ignored probe files.
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from caliber_client import CaliberClient, CaliberConfigError
from parse_property_data import normalize_addr


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "caliber_registered_rentals.json")
CLIENT_SEARCH = "wynbrooke"


def bool_value(value):
    return value is True or str(value).lower() == "true"


def unit_address(unit):
    return ", ".join(
        part
        for part in [
            unit.get("Address1", ""),
            unit.get("Address2", ""),
            unit.get("City", ""),
            unit.get("State", ""),
            unit.get("ZipCode", ""),
        ]
        if part
    )


def build_snapshot(client, units, contacts):
    contacts_by_unit = Counter()
    active_renter_contacts_by_unit = Counter()

    for contact in contacts:
        unit_id = contact.get("UnitID")
        if unit_id is None:
            continue
        if bool_value(contact.get("ContactIsDeleted")) or bool_value(contact.get("LinkIsDeleted")):
            continue
        contacts_by_unit[unit_id] += 1
        if bool_value(contact.get("IsCurrent")) and bool_value(contact.get("IsRenter")):
            active_renter_contacts_by_unit[unit_id] += 1

    records = []
    for unit in units:
        unit_id = unit.get("UnitID")
        street = unit.get("Address1", "").strip()
        is_hoa_rental = bool_value(unit.get("IsHOARental"))
        renter_contact_count = active_renter_contacts_by_unit[unit_id]
        records.append({
            "unit_id": unit_id,
            "client_id": unit.get("ClientID"),
            "lot_number": unit.get("LotNumber", ""),
            "address": unit_address(unit),
            "street_address": street,
            "address_norm": normalize_addr(street) if street else "",
            "city": unit.get("City", ""),
            "state": unit.get("State", ""),
            "zip_code": unit.get("ZipCode", ""),
            "is_hoa_rental": is_hoa_rental,
            "renter_contact_count": renter_contact_count,
            "has_renter_contact": renter_contact_count > 0,
            "is_inactive": bool_value(unit.get("InActive")),
            "is_deleted": bool_value(unit.get("IsDeleted")),
        })

    rental_count = sum(1 for record in records if record["is_hoa_rental"])
    renter_contact_units = sum(1 for record in records if record["has_renter_contact"])

    return {
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "client_id": client.get("ClientID"),
        "client_name": client.get("ClientName") or client.get("Name") or "Wynbrooke",
        "source": "Caliber FrontSteps API",
        "summary": {
            "units": len(records),
            "hoa_rental_units": rental_count,
            "units_with_renter_contacts": renter_contact_units,
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

    units = client.units(client_id)
    contacts = client.current_contacts(client_id)
    snapshot = build_snapshot(caliber_client, units, contacts)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

    summary = snapshot["summary"]
    print(f"Units: {summary['units']}")
    print(f"HOA rental units: {summary['hoa_rental_units']}")
    print(f"Units with renter contacts: {summary['units_with_renter_contacts']}")
    print(f"Results written to {OUTPUT_PATH}")
    return snapshot


if __name__ == "__main__":
    try:
        run_sync()
    except CaliberConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Caliber sync failed: {e}", file=sys.stderr)
        sys.exit(1)
