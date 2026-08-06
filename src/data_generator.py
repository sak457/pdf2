"""
Synthetic transaction generator.

Produces 250–500 realistic banking transactions for a single customer ("Me")
holding several accounts.  The data purposely blends ordinary retail-banking
behaviour (salary, shopping, utilities, withdrawals, cheques, internal
transfers) with a handful of deliberately *unusual* clusters so that the AML
engine downstream has genuine patterns to surface:

  * structuring (many deposits just below the reporting threshold)
  * smurfing / fan-in (many small senders funnelled to one beneficiary)
  * layering + pass-through (money in then straight out of a "clean" account)
  * round-dollar high-value transfers
  * a dormant account that suddenly wakes up
  * repeated identical transfers
  * a circular payment loop

The generator is deterministic (fixed seed) so the demo report is stable.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd

import config

SEED = 20260417
random.seed(SEED)

SELF = config.SELF_LABEL

# --------------------------------------------------------------------------- #
#  Reference data
# --------------------------------------------------------------------------- #
ACCOUNTS = {
    "AC-4021-8837": "Primary Current",
    "AC-4021-5590": "Savings",
    "AC-7745-1120": "Business Operating",
    "AC-9902-3341": "Joint Household",
}
ACCOUNT_LIST = list(ACCOUNTS.keys())
PRIMARY = "AC-4021-8837"
BUSINESS = "AC-7745-1120"
SAVINGS = "AC-4021-5590"
JOINT = "AC-9902-3341"

EMPLOYERS = [
    "Meridian Logistics FZE",
    "Orion Systems Ltd",
]
UTILITIES = [
    "Gulf Power & Water Authority",
    "Etisalat Telecom",
    "City Municipality Services",
    "Zenith Insurance Co",
]
MERCHANTS = [
    "Carrefour Hypermarket",
    "Apple Store Dubai Mall",
    "IKEA Home Furnishings",
    "Amazon.ae",
    "Shell Service Station",
    "Noon Marketplace",
    "Emirates Airlines",
    "Sharaf DG Electronics",
    "Spinneys Supermarket",
]
COMPANIES_MISC = [
    "Al Futtaim Real Estate",
    "Blue Harbor Trading LLC",
    "Sterling Consulting Group",
    "Nova Medical Center",
    "Falcon Auto Services",
    "Greenfield Property Mgmt",
]
PERSONS = [
    "Omar Haddad", "Layla Nasser", "Yusuf Karim", "Amira Saleh",
    "Daniel Okoro", "Sophia Rossi", "Rajesh Menon", "Fatima Al-Zahra",
    "Michael Chen", "Priya Sharma", "Hassan Aziz", "Elena Petrova",
]
# Payroll recipients for the business account
PAYROLL = [
    "Nabil Farouk", "Grace Adeyemi", "Tomas Novak",
    "Aisha Bello", "Victor Silva", "Mei Ling Tan",
]
# Smurf network — many small senders feeding one funnel beneficiary
SMURFS = [
    "Kareem Idris", "Bilal Shah", "Nadia Kamal", "Rami Fakhoury",
    "Sana Iqbal", "Joseph Mbeki", "Dana Levy", "Farhan Malik",
]
FUNNEL_BENEFICIARY = "Crescent Bay Holdings Ltd"  # offshore-sounding shell

rows: list[dict] = []


def add(d: date, direction: str, account: str, sender: str, s_type: str,
        beneficiary: str, b_type: str, amount: float, method: str) -> None:
    rows.append({
        "Date": d,
        "Direction": direction,
        "Account_No": account,
        "Sender": sender,
        "Sender_Type": s_type,
        "Beneficiary": beneficiary,
        "Beneficiary_Type": b_type,
        "Amount": round(float(amount), 2),
        "Transaction_Method": method,
    })


def jitter(base: float, pct: float = 0.06) -> float:
    return round(base * (1 + random.uniform(-pct, pct)), 2)


START = date(2025, 6, 1)
END = date(2026, 5, 31)


def month_range():
    y, m = START.year, START.month
    while (y, m) <= (END.year, END.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


# --------------------------------------------------------------------------- #
#  1. Salary — monthly, into Primary Current  (IN, Company -> Me)
# --------------------------------------------------------------------------- #
employer = EMPLOYERS[0]
base_salary = 18_500
for y, m in month_range():
    pay_day = date(y, m, 27)
    add(pay_day, "IN", PRIMARY, employer, "Company", SELF, "Person",
        jitter(base_salary, 0.02), "Transfer")

# Secondary consulting income (irregular) into Business account
for y, m in month_range():
    if random.random() < 0.6:
        d = date(y, m, random.randint(8, 20))
        add(d, "IN", BUSINESS, random.choice(COMPANIES_MISC), "Company",
            SELF, "Person", jitter(random.choice([6500, 9200, 12400]), 0.1),
            random.choice(["Transfer", "Cheque"]))

# Recurring business client revenue into the Business Operating account so
# payroll is funded by genuine income (keeps net cash-flow realistic).
CLIENTS = ["Al Futtaim Real Estate", "Nova Medical Center",
           "Falcon Auto Services", "Greenfield Property Mgmt"]
for y, m in month_range():
    for _ in range(random.randint(2, 3)):
        d = date(y, m, random.randint(2, 24))
        add(d, "IN", BUSINESS, random.choice(CLIENTS), "Company", SELF,
            "Person", jitter(random.choice([16500, 21000, 24500, 19000]), 0.08),
            random.choice(["Transfer", "Cheque"]))

# --------------------------------------------------------------------------- #
#  2. Utilities — monthly recurring  (OUT, Me -> Company)
# --------------------------------------------------------------------------- #
util_bases = {u: b for u, b in zip(UTILITIES, [640, 310, 220, 1450])}
for y, m in month_range():
    for u, base in util_bases.items():
        d = date(y, m, random.randint(3, 12))
        add(d, "OUT", PRIMARY, SELF, "Person", u, "Company",
            jitter(base, 0.12), "Transfer")

# --------------------------------------------------------------------------- #
#  3. Shopping / retail — frequent small OUT payments (card/transfer)
# --------------------------------------------------------------------------- #
for y, m in month_range():
    for _ in range(random.randint(6, 11)):
        d = date(y, m, random.randint(1, 28))
        merchant = random.choice(MERCHANTS)
        amt = random.choice([45, 88, 120, 210, 320, 540, 780, 1150, 60, 95, 260])
        add(d, "OUT", random.choice([PRIMARY, JOINT]), SELF, "Person",
            merchant, "Company", jitter(amt, 0.2), "Transfer")

# --------------------------------------------------------------------------- #
#  4. Cash withdrawals — Me -> Me  (Withdrawal rule)
# --------------------------------------------------------------------------- #
for y, m in month_range():
    for _ in range(random.randint(2, 4)):
        d = date(y, m, random.randint(1, 28))
        amt = random.choice([500, 1000, 1500, 2000, 3000])
        add(d, "OUT", random.choice([PRIMARY, JOINT]), SELF, "Person",
            SELF, "Person", jitter(amt, 0.05), "Withdrawal")

# --------------------------------------------------------------------------- #
#  5. Cheque deposits — occasional IN from persons/companies
# --------------------------------------------------------------------------- #
for _ in range(14):
    y, m = random.choice(list(month_range()))
    d = date(y, m, random.randint(1, 28))
    payer = random.choice(PERSONS + COMPANIES_MISC)
    p_type = "Company" if payer in COMPANIES_MISC else "Person"
    add(d, "IN", random.choice([PRIMARY, BUSINESS]), payer, p_type,
        SELF, "Person", jitter(random.choice([2500, 4800, 7200, 3300]), 0.15),
        "Cheque")

# --------------------------------------------------------------------------- #
#  6. Company payroll — Business account pays staff monthly  (OUT)
# --------------------------------------------------------------------------- #
payroll_bases = {p: b for p, b in zip(PAYROLL, [7200, 6100, 8400, 5300, 6800, 9100])}
for y, m in month_range():
    pay_day = date(y, m, 28)
    for p, base in payroll_bases.items():
        add(pay_day, "OUT", BUSINESS, SELF, "Person", p, "Person",
            jitter(base, 0.03), "Transfer")

# --------------------------------------------------------------------------- #
#  7. Transfers between my own accounts  (Me -> Me, different account)
# --------------------------------------------------------------------------- #
for y, m in month_range():
    if random.random() < 0.8:
        d = date(y, m, random.randint(1, 26))
        amt = random.choice([2000, 3500, 5000, 8000])
        # sweep from Primary to Savings
        add(d, "OUT", PRIMARY, SELF, "Person", SELF, "Person",
            jitter(amt, 0.1), "Transfer")
        add(d, "IN", SAVINGS, SELF, "Person", SELF, "Person",
            jitter(amt, 0.1), "Transfer")

# regular recurring rent payment (identical-ish) OUT
for y, m in month_range():
    d = date(y, m, 5)
    add(d, "OUT", PRIMARY, SELF, "Person", "Al Futtaim Real Estate", "Company",
        6500, "Transfer")

# ========================================================================== #
#  UNUSUAL / AML-TRIGGERING CLUSTERS
# ========================================================================== #

# --- (A) Structuring: 6 cash-ish deposits just below the 10k threshold ----- #
struct_start = date(2025, 9, 8)
for i in range(6):
    d = struct_start + timedelta(days=i)
    add(d, "IN", PRIMARY, random.choice(PERSONS), "Person", SELF, "Person",
        random.choice([9200, 9450, 9600, 9350, 9800, 9100]), "Cheque")

# --- (B) Smurfing / fan-in: many small senders -> one funnel beneficiary --- #
smurf_day = date(2025, 11, 3)
for i, s in enumerate(SMURFS):
    d = smurf_day + timedelta(days=random.randint(0, 5))
    amt = random.choice([2800, 3100, 2950, 3300, 2700])
    # money arrives into the business account from many individuals...
    add(d, "IN", BUSINESS, s, "Person", SELF, "Person", amt, "Transfer")
# ...then is funnelled out in two large lumps to a shell company (layering)
add(date(2025, 11, 10), "OUT", BUSINESS, SELF, "Person",
    FUNNEL_BENEFICIARY, "Company", 13400, "Transfer")
add(date(2025, 11, 11), "OUT", BUSINESS, SELF, "Person",
    FUNNEL_BENEFICIARY, "Company", 11900, "Transfer")

# --- (C) Pass-through / rapid in-out on the Joint account ------------------ #
pt_day = date(2026, 1, 14)
add(pt_day, "IN", JOINT, "Blue Harbor Trading LLC", "Company", SELF, "Person",
    24500, "Transfer")
add(pt_day + timedelta(days=1), "OUT", JOINT, SELF, "Person",
    "Sterling Consulting Group", "Company", 24200, "Transfer")

# --- (D) Round-dollar high-value transfers --------------------------------- #
for d, amt, ben in [
    (date(2026, 2, 3), 50_000, "Crescent Bay Holdings Ltd"),
    (date(2026, 2, 18), 35_000, "Blue Harbor Trading LLC"),
    (date(2026, 3, 9), 40_000, "Crescent Bay Holdings Ltd"),
]:
    add(d, "OUT", BUSINESS, SELF, "Person", ben, "Company", amt, "Transfer")

# --- (E) Dormant account suddenly active ----------------------------------- #
# Savings sits quiet, then a burst of activity in April 2026
for i in range(5):
    d = date(2026, 4, 6) + timedelta(days=i)
    add(d, "OUT", SAVINGS, SELF, "Person", random.choice(PERSONS), "Person",
        random.choice([7500, 8200, 6900, 9300]), "Transfer")

# --- (F) Repeated identical transfers -------------------------------------- #
for i in range(6):
    d = date(2025, 12, 2) + timedelta(days=i * 3)
    add(d, "OUT", PRIMARY, SELF, "Person", "Rami Fakhoury", "Person",
        4500, "Transfer")

# --- (G) Circular payment loop  Me -> X -> Y -> Me -------------------------- #
add(date(2026, 3, 20), "OUT", PRIMARY, SELF, "Person",
    "Sterling Consulting Group", "Company", 15000, "Transfer")
add(date(2026, 3, 24), "OUT", BUSINESS, "Sterling Consulting Group", "Company",
    "Blue Harbor Trading LLC", "Company", 14800, "Transfer")
add(date(2026, 3, 28), "IN", PRIMARY, "Blue Harbor Trading LLC", "Company",
    SELF, "Person", 14600, "Transfer")

# --- (H) Frequent large withdrawals in a short window ---------------------- #
for i in range(9):
    d = date(2026, 2, 20) + timedelta(days=i)
    add(d, "OUT", PRIMARY, SELF, "Person", SELF, "Person",
        random.choice([3000, 3500, 4000]), "Withdrawal")


# --------------------------------------------------------------------------- #
#  Assemble, sort, trim to 250–500
# --------------------------------------------------------------------------- #
def build() -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=config.COLUMNS)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    # Safety clamp to the requested record band.
    if len(df) > 500:
        df = df.sample(500, random_state=SEED).sort_values("Date").reset_index(drop=True)
    return df


def main() -> pd.DataFrame:
    import os
    os.makedirs(config.DATA_DIR, exist_ok=True)
    df = build()
    out = df.copy()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    out.to_csv(config.CSV_PATH, index=False)
    try:
        out.to_excel(config.XLSX_PATH, index=False)
    except Exception as exc:  # openpyxl missing, etc.
        print(f"[warn] could not write xlsx: {exc}")
    print(f"[data] generated {len(df)} transactions -> {config.CSV_PATH}")
    return df


if __name__ == "__main__":
    main()
