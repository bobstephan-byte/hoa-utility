"""
Parse Hendricks County Real Property file and identify likely
non-owner-occupied (rental) properties in Wynbrooke subdivision.

Logic: If owner mailing address != property address, flag as likely rental.
"""

import os
import re
import pandas as pd

DATA_FILE = os.path.join(os.path.dirname(__file__), "data",
                         "RealParcel_Hendricks_32_2024P2025.txt")

# Fixed-width field positions (0-indexed start, end)
FIELDS = {
    "parcel_number":  (0, 18),
    "prop_addr":      (93, 153),
    "prop_city":      (153, 183),
    "prop_zip":       (183, 193),
    "owner_name":     (223, 303),
    "owner_addr":     (303, 363),
    "owner_city":     (363, 393),
    "owner_state":    (393, 423),
    "owner_zip":      (423, 433),
    "country":        (433, 436),
    "sale_date":      (436, 446),
    "legal_desc":     (749, None),  # variable length to end of line
}


def parse_line(line):
    record = {}
    for name, (start, end) in FIELDS.items():
        val = line[start:end].strip() if end else line[start:].strip()
        record[name] = val
    return record


def normalize_addr(addr):
    """Normalize an address for comparison."""
    addr = addr.upper().strip()
    # Common abbreviations
    addr = re.sub(r'\bSTREET\b', 'ST', addr)
    addr = re.sub(r'\bDRIVE\b', 'DR', addr)
    addr = re.sub(r'\bCOURT\b', 'CT', addr)
    addr = re.sub(r'\bLANE\b', 'LN', addr)
    addr = re.sub(r'\bBOULEVARD\b', 'BLVD', addr)
    addr = re.sub(r'\bPLACE\b', 'PL', addr)
    addr = re.sub(r'\bCIRCLE\b', 'CIR', addr)
    addr = re.sub(r'\bWAY\b', 'WY', addr)
    # Remove extra spaces
    addr = re.sub(r'\s+', ' ', addr)
    return addr


def is_wynbrooke(legal_desc):
    return "WYNBROOKE" in legal_desc.upper()


def main():
    records = []
    with open(DATA_FILE, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i == 0:  # header row
                continue
            if is_wynbrooke(line):
                records.append(parse_line(line))

    df = pd.DataFrame(records)
    print(f"Total Wynbrooke parcels: {len(df)}")
    print()

    # Normalize addresses for comparison
    df["prop_addr_norm"] = df["prop_addr"].apply(normalize_addr)
    df["owner_addr_norm"] = df["owner_addr"].apply(normalize_addr)

    # Flag non-owner-occupied: mailing address differs from property address
    df["addr_match"] = df["prop_addr_norm"] == df["owner_addr_norm"]
    df["likely_rental"] = ~df["addr_match"]

    rentals = df[df["likely_rental"]].copy()
    owner_occ = df[~df["likely_rental"]]

    print(f"Owner-occupied (address match):    {len(owner_occ)}")
    print(f"Likely non-owner-occupied:         {len(rentals)}")
    print(f"Rental rate:                       {len(rentals)/len(df)*100:.1f}%")
    print()

    # Show all likely rentals
    print("=" * 100)
    print("LIKELY NON-OWNER-OCCUPIED PROPERTIES IN WYNBROOKE")
    print("=" * 100)
    for _, row in rentals.sort_values("prop_addr").iterrows():
        print(f"\n  Property:    {row['prop_addr']}, {row['prop_city']} {row['prop_zip']}")
        print(f"  Owner:       {row['owner_name']}")
        print(f"  Mailing to:  {row['owner_addr']}, {row['owner_city']}, {row['owner_state']} {row['owner_zip']}")
        print(f"  Legal:       {row['legal_desc']}")

    # Save full dataset to CSV for the Streamlit dashboard
    out_csv = os.path.join(os.path.dirname(__file__), "data", "wynbrooke_parcels.csv")
    df.to_csv(out_csv, index=False)
    print(f"\nSaved all {len(df)} Wynbrooke parcels to {out_csv}")


if __name__ == "__main__":
    main()
