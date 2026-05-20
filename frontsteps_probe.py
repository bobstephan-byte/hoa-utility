# frontsteps_probe.py
# Probe the FrontSteps Caliber CAPI2 API to verify credentials,
# find the Wynbrooke clientId, and explore available unit/owner data.
#
# Run: python3 frontsteps_probe.py
# Requires in .env:
#   FRONTSTEPS_API_ENDPOINT=https://frontsteps.cloud/CAPI2_OMSI
#   FRONTSTEPS_API_CODE=your_api_code
#   FRONTSTEPS_API_USERNAME=your_api_username
#   FRONTSTEPS_API_PASSWORD=your_api_password

import base64
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("FRONTSTEPS_API_ENDPOINT", "").rstrip("/")
API_CODE = os.getenv("FRONTSTEPS_API_CODE", "")
API_USERNAME = os.getenv("FRONTSTEPS_API_USERNAME") or os.getenv("FRONTSTEPS_USERNAME", "")
API_PASSWORD = os.getenv("FRONTSTEPS_API_PASSWORD") or os.getenv("FRONTSTEPS_PASSWORD", "")

if not all([BASE_URL, API_CODE, API_USERNAME, API_PASSWORD]):
    print("ERROR: Missing one or more required env vars:")
    print("  FRONTSTEPS_API_ENDPOINT, FRONTSTEPS_API_CODE,")
    print("  FRONTSTEPS_API_USERNAME, FRONTSTEPS_API_PASSWORD")
    sys.exit(1)


def auth_header():
    """Build the Caliber v2 Authorization header.

    Caliber documents this as:
        basic base64(APICode:APIUsername:APIPassword)
    """
    security_string = f"{API_CODE}:{API_USERNAME}:{API_PASSWORD}"
    encoded = base64.b64encode(security_string.encode("utf-8")).decode("ascii")
    return f"basic {encoded}"


HEADERS = {
    "Accept": "application/json",
    "Authorization": auth_header(),
}


def request(path, *, include_auth=True):
    """GET a CAPI2 endpoint. Returns (success, status, body_text, json_data)."""
    url = f"{BASE_URL}/api/v2/{path}"
    headers = HEADERS if include_auth else {"Accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        json_data = None
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type.lower():
            try:
                json_data = resp.json()
            except ValueError:
                json_data = None
        return resp.ok, resp.status_code, resp.text[:500], json_data
    except requests.exceptions.RequestException as e:
        return False, 0, str(e), None


def get(path):
    """GET a CAPI2 endpoint with known-good auth."""
    success, status, body, data = request(path)
    if not success:
        print(f"  HTTP/REQUEST ERROR {status}: {body[:300]}")
        return None
    if data is not None:
        return data
    print(f"  Response was not JSON: {body[:300]}")
    return None


def save(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved to {filename}")


def one_line_address(value):
    if isinstance(value, dict):
        return value.get("OneLine") or ", ".join(
            part for part in [
                value.get("Address1"),
                value.get("Address2"),
                value.get("City"),
                value.get("State"),
                value.get("ZipCode"),
            ]
            if part
        )
    return value or "?"


def display_name(record):
    if record.get("DisplayName"):
        return record["DisplayName"]
    if record.get("CompanyName"):
        return record["CompanyName"]
    parts = [
        record.get("FirstName1"),
        record.get("MiddleInitial1"),
        record.get("LastName1"),
        record.get("Suffix1"),
    ]
    name = " ".join(part for part in parts if part)
    return name or "?"


def true_count(rows, field):
    return sum(1 for row in rows if row.get(field) is True)


def main():
    print(f"\n{'='*60}")
    print("FrontSteps CAPI2 Probe")
    print(f"Endpoint: {BASE_URL}")
    print(f"{'='*60}\n")

    # ── Step 1: Verify basic connectivity ────────────────────────
    print("Step 1: Checking basic connectivity...")
    for path in ("ping", "time"):
        success, status, body, _ = request(path, include_auth=False)
        result = "SUCCESS" if success else "FAILED"
        print(f"  GET api/v2/{path}: {result} ({status}) — {body[:120]}")
    print()

    # ── Step 2: Verify documented Caliber authorization ──────────
    print("Step 2: Trying documented Caliber auth against GET api/v2/login...")
    success, status, body, _ = request("login")
    result = "SUCCESS" if success else "FAILED"
    print(f"  {result} ({status}) — {body[:200]}\n")

    if not success:
        print("Login failed. Things to check:")
        print("  - Are the credentials in .env correct?")
        print("  - Is the endpoint URL exactly right?")
        print("  - Does your account have API access enabled by FrontSteps?")
        sys.exit(1)

    # ── Step 3: Fetch client list ─────────────────────────────────
    print("Step 3: Fetching client list (GET api/v2/clientlist)...")
    clients = get("clientlist")
    if not clients:
        print("  No clients returned or error.")
        sys.exit(1)

    client_list = clients if isinstance(clients, list) else [clients]
    print(f"  Total clients returned: {len(client_list)}")
    save("probe_clientlist_raw.json", client_list)

    print("\n  All communities found:")
    for c in client_list:
        cid   = c.get("ClientID") or c.get("clientId") or c.get("id") or "?"
        name  = c.get("Name") or c.get("name") or c.get("ClientName") or "?"
        city  = c.get("City") or c.get("city") or ""
        state = c.get("State") or c.get("state") or ""
        print(f"    [{cid}] {name}  —  {city}, {state}")

    # Find Wynbrooke
    wynbrooke = next(
        (c for c in client_list
         if "wynbrooke" in str(c.get("Name", "")).lower()
         or "wynbrooke" in str(c.get("name", "")).lower()
         or "wynbrooke" in str(c.get("ClientName", "")).lower()),
        None,
    )

    if not wynbrooke:
        print("\n  Wynbrooke not found in client list.")
        print("  Check the community names above and update the search term if needed.")
        sys.exit(0)

    client_id = (
        wynbrooke.get("ClientID")
        or wynbrooke.get("clientId")
        or wynbrooke.get("id")
    )
    print(f"\n  ✓ Found Wynbrooke! clientId = {client_id}")

    # ── Step 4: Units ─────────────────────────────────────────────
    print(f"\nStep 4: Fetching units for clientId={client_id}...")
    units = get(f"client/{client_id}/units")
    if units:
        unit_list = units if isinstance(units, list) else [units]
        print(f"  Total units: {len(unit_list)}")
        print(f"  HOA rental units: {true_count(unit_list, 'IsHOARental')}")
        save("probe_wynbrooke_units_raw.json", unit_list)
        print("  Sample units:")
        for u in unit_list[:5]:
            addr = one_line_address({
                "Address1": u.get("Address1"),
                "Address2": u.get("Address2"),
                "City": u.get("City"),
                "State": u.get("State"),
                "ZipCode": u.get("ZipCode"),
            })
            uid  = u.get("UnitID") or u.get("unitId") or u.get("id") or "?"
            rental = "rental" if u.get("IsHOARental") else "not rental"
            print(f"    [{uid}] {addr} — {rental}")

    # ── Step 5: Current owners ────────────────────────────────────
    print(f"\nStep 5: Fetching current owners for clientId={client_id}...")
    owners = get(f"client/{client_id}/owners/current")
    if owners:
        owner_list = owners if isinstance(owners, list) else [owners]
        print(f"  Total owner records: {len(owner_list)}")
        print(f"  Current renter contact records in owner feed: {true_count(owner_list, 'IsRenter')}")
        save("probe_wynbrooke_owners_raw.json", owner_list)
        print("  Sample owners:")
        for o in owner_list[:5]:
            name = display_name(o)
            addr = one_line_address(o.get("UnitAddress"))
            print(f"    {name}  —  {addr}")

    # ── Step 6: Current contacts/residents ───────────────────────
    print(f"\nStep 6: Fetching current contacts for clientId={client_id}...")
    contacts = get(f"client/{client_id}/contacts/current")
    if contacts:
        contact_list = contacts if isinstance(contacts, list) else [contacts]
        print(f"  Total contact records: {len(contact_list)}")
        print(f"  Renter contact records: {true_count(contact_list, 'IsRenter')}")
        print(f"  Primary occupant records: {true_count(contact_list, 'IsPrimaryOccupant')}")
        save("probe_wynbrooke_contacts_raw.json", contact_list)
        print("  Sample contacts:")
        for c in contact_list[:5]:
            name = display_name(c)
            addr = one_line_address(c.get("UnitAddress"))
            roles = []
            if c.get("IsOwner"):
                roles.append("owner")
            if c.get("IsOccupant"):
                roles.append("occupant")
            if c.get("IsRenter"):
                roles.append("renter")
            print(f"    [{', '.join(roles) or 'contact'}] {name}  —  {addr}")

    print(f"\n{'='*60}")
    print("Probe complete. Check the probe_*.json files for full data.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
