"""
CSV loading & normalisation for the POI transaction schema.

Expected columns (case-insensitive, aliases tolerated):
    date, direction, account_no, sender, beneficiary, amount, transaction_method

  * direction        : in | out | own_account
  * account_no       : POI account(s); own-account rows may hold "ACCA|ACCB"
  * sender / beneficiary : "poi" (the subject), a company name, or "unknown"
  * transaction_method   : transfer | withdrawal | cheque | cash | ...

The loader classifies each counterparty, derives the POI-relative direction,
and adds period helpers (quarter / month) used by the filters.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

SELF_TOKENS = {"poi", "me", "self", "subject", "own", "self_account"}
UNKNOWN_TOKENS = {"unknown", "unknow", "unk", "n/a", "na", "", "nan", "none"}

ALIASES = {
    "date": "date", "value date": "date", "transaction date": "date", "txn date": "date",
    "direction": "direction", "dir": "direction", "flow": "direction",
    "account_no": "account_no", "account": "account_no", "account no": "account_no",
    "account number": "account_no", "accounts": "account_no", "poi_account": "account_no",
    "sender": "sender", "originator": "sender", "from": "sender", "payer": "sender",
    "beneficiary": "beneficiary", "to": "beneficiary", "payee": "beneficiary",
    "receiver": "beneficiary",
    "amount": "amount", "value": "amount", "amt": "amount",
    "transaction_method": "transaction_method", "method": "transaction_method",
    "channel": "transaction_method", "type": "transaction_method",
    "transaction method": "transaction_method",
}

REQUIRED = ["date", "direction", "account_no", "sender", "beneficiary",
            "amount", "transaction_method"]


def _norm_dir(v: str) -> str:
    v = str(v).strip().lower().replace("-", "_").replace(" ", "_")
    if v in {"own_account", "own", "internal", "self", "transfer_own", "own_acc"}:
        return "own"
    if v in {"in", "credit", "cr", "inbound", "incoming", "c"}:
        return "in"
    if v in {"out", "debit", "dr", "outbound", "outgoing", "d"}:
        return "out"
    return v


def _classify(name: str) -> tuple[str, str]:
    """Return (display_name, type) for a sender/beneficiary token."""
    raw = str(name).strip()
    low = raw.lower()
    if low in SELF_TOKENS:
        return ("POI", "POI")
    if low in UNKNOWN_TOKENS:
        return ("Unknown", "Unknown")
    return (raw, "Company")


def read_csv(file) -> pd.DataFrame:
    if hasattr(file, "read"):
        raw = file.read()
        df = pd.read_csv(io.BytesIO(raw) if isinstance(raw, bytes) else io.StringIO(raw))
    else:
        df = pd.read_csv(file)
    return normalise(df)


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: ALIASES.get(str(c).strip().lower(), str(c).strip().lower())
                            for c in df.columns})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {', '.join(missing)}.\n"
            f"Expected: {', '.join(REQUIRED)}")

    df = df[REQUIRED].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).abs()
    df["direction"] = df["direction"].map(_norm_dir)
    df["transaction_method"] = df["transaction_method"].astype(str).str.strip().str.lower()
    df["account_no"] = df["account_no"].astype(str).str.strip()

    # split multi-account cells
    df["accounts"] = df["account_no"].apply(
        lambda s: [a.strip() for a in str(s).split("|") if a.strip()])
    df["account_from"] = df["accounts"].apply(lambda a: a[0] if a else "")
    df["account_to"] = df["accounts"].apply(lambda a: a[1] if len(a) > 1 else a[0] if a else "")
    df["primary_account"] = df["account_from"]

    s_name, s_type, b_name, b_type = [], [], [], []
    for _, r in df.iterrows():
        sn, stp = _classify(r["sender"])
        bn, btp = _classify(r["beneficiary"])
        s_name.append(sn); s_type.append(stp)
        b_name.append(bn); b_type.append(btp)
    df["sender_name"], df["sender_type"] = s_name, s_type
    df["beneficiary_name"], df["beneficiary_type"] = b_name, b_type

    # POI-relative counterparty
    def counterparty(r):
        if r["direction"] == "own":
            return ("Internal transfer", "Internal")
        if r["direction"] == "in":
            return (r["sender_name"], r["sender_type"])
        return (r["beneficiary_name"], r["beneficiary_type"])

    cp = df.apply(counterparty, axis=1, result_type="expand")
    df["counterparty"] = cp[0]
    df["counterparty_type"] = cp[1]

    # period helpers
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["quarter"] = df["date"].dt.year.astype(str) + "-Q" + df["date"].dt.quarter.astype(str)
    df["day"] = df["date"].dt.date

    return df.sort_values("date").reset_index(drop=True)


# --------------------------------------------------------------------------- #
#  Synthetic sample dataset (new schema) for the "Load sample" button
# --------------------------------------------------------------------------- #
def sample_dataframe(seed: int = 7) -> pd.DataFrame:
    import random
    from datetime import date, timedelta
    random.seed(seed)

    A1, A2, A3 = "AC-4021-8837", "AC-4021-5590", "AC-7745-1120"
    rows = []

    def add(d, direction, acct, sender, beneficiary, amount, method):
        rows.append(dict(date=d, direction=direction, account_no=acct,
                         sender=sender, beneficiary=beneficiary,
                         amount=round(float(amount), 2), transaction_method=method))

    employer = "Meridian Logistics FZE"
    utilities = ["Gulf Power & Water", "Etisalat Telecom", "City Municipality"]
    merchants = ["Carrefour Hypermarket", "Apple Store", "IKEA", "Amazon.ae",
                 "Shell Station", "Noon Marketplace", "Spinneys"]
    clients = ["Nova Medical Center", "Falcon Auto Services", "Greenfield Property"]
    shells = ["Crescent Bay Holdings", "Blue Harbor Trading", "Sterling Consulting"]
    smurfs = ["unknown"] * 6 + ["Kareem Idris", "Bilal Shah"]

    months = pd.period_range("2025-06", "2026-05", freq="M")
    for p in months:
        y, m = p.year, p.month
        # salary in
        add(date(y, m, 27), "in", A1, employer, "poi", round(18500 * random.uniform(.98, 1.02)), "transfer")
        # business client revenue in
        for _ in range(random.randint(2, 3)):
            add(date(y, m, random.randint(2, 24)), "in", A3, random.choice(clients),
                "poi", random.choice([16500, 21000, 24500, 19000]) * random.uniform(.95, 1.05), "transfer")
        # utilities out
        for u, base in zip(utilities, [640, 310, 1450]):
            add(date(y, m, random.randint(3, 12)), "out", A1, "poi", u, base * random.uniform(.9, 1.1), "transfer")
        # shopping out
        for _ in range(random.randint(5, 9)):
            add(date(y, m, random.randint(1, 28)), "out", A1, "poi", random.choice(merchants),
                random.choice([45, 120, 320, 540, 780, 95, 260]) * random.uniform(.8, 1.2), "card")
        # cash withdrawals (self)
        for _ in range(random.randint(2, 3)):
            add(date(y, m, random.randint(1, 28)), "out", A1, "poi", "poi",
                random.choice([500, 1000, 1500, 2000, 3000]), "withdrawal")
        # own-account sweep A1 -> A2
        if random.random() < .8:
            add(date(y, m, random.randint(1, 26)), "own_account", f"{A1}|{A2}", "poi", "poi",
                random.choice([2000, 3500, 5000, 8000]), "transfer")
        # rent out
        add(date(y, m, 5), "out", A1, "poi", "Greenfield Property", 6500, "transfer")

    # cheque deposits
    for _ in range(10):
        p = random.choice(months)
        add(date(p.year, p.month, random.randint(1, 28)), "in", random.choice([A1, A3]),
            random.choice(clients + ["unknown"]), "poi", random.choice([2500, 4800, 7200, 3300]), "cheque")

    # --- AML clusters ---
    # structuring: sub-threshold credits
    for i in range(6):
        add(date(2025, 9, 8) + timedelta(days=i), "in", A1, random.choice(["unknown", "Kareem Idris"]),
            "poi", random.choice([9200, 9450, 9600, 9350, 9800, 9100]), "cheque")
    # smurfing fan-in then funnel out
    for i, s in enumerate(smurfs):
        add(date(2025, 11, 3) + timedelta(days=random.randint(0, 5)), "in", A3, s, "poi",
            random.choice([2800, 3100, 2950, 3300]), "transfer")
    add(date(2025, 11, 10), "out", A3, "poi", "Crescent Bay Holdings", 13400, "transfer")
    add(date(2025, 11, 11), "out", A3, "poi", "Crescent Bay Holdings", 11900, "transfer")
    # pass-through
    add(date(2026, 1, 14), "in", A2, "Blue Harbor Trading", "poi", 24500, "transfer")
    add(date(2026, 1, 15), "out", A2, "poi", "Sterling Consulting", 24200, "transfer")
    # round-dollar high value
    for d, amt, ben in [(date(2026, 2, 3), 50000, "Crescent Bay Holdings"),
                        (date(2026, 2, 18), 35000, "Blue Harbor Trading"),
                        (date(2026, 3, 9), 40000, "Crescent Bay Holdings")]:
        add(d, "out", A3, "poi", ben, amt, "transfer")
    # round-tripping: out to entity then back in
    add(date(2026, 3, 20), "out", A1, "poi", "Sterling Consulting", 15000, "transfer")
    add(date(2026, 3, 28), "in", A1, "Sterling Consulting", "poi", 14600, "transfer")
    # dormant then active (A2)
    for i in range(5):
        add(date(2026, 4, 6) + timedelta(days=i), "out", A2, "poi",
            random.choice(shells + ["unknown"]), random.choice([7500, 8200, 6900, 9300]), "transfer")
    # repeated identical
    for i in range(6):
        add(date(2025, 12, 2) + timedelta(days=i * 3), "out", A1, "poi", "Blue Harbor Trading", 4500, "transfer")
    # frequent withdrawals burst
    for i in range(9):
        add(date(2026, 2, 20) + timedelta(days=i), "out", A1, "poi", "poi",
            random.choice([3000, 3500, 4000]), "withdrawal")

    df = pd.DataFrame(rows)
    return normalise(df)


def sample_csv_bytes(seed: int = 7) -> bytes:
    df = sample_dataframe(seed)
    out = df[REQUIRED].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.to_csv(index=False).encode()
