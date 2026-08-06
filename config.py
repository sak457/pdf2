"""
Central configuration for the AML / Financial Intelligence report generator.

Everything the report needs to know about *who* the subject is, *where* the
data comes from, and *how* the analytics behave lives here.  When the real
Excel statement is available, only this file needs to change (set
``INPUT_MODE = "excel"`` and point ``EXCEL_PATH`` at the file) — the rest of
the pipeline regenerates the identical report from the actual data.
"""

from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
#  Paths
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

CSV_PATH = os.path.join(DATA_DIR, "transactions.csv")
XLSX_PATH = os.path.join(DATA_DIR, "transactions.xlsx")
PDF_PATH = os.path.join(OUTPUT_DIR, "AML_Intelligence_Report.pdf")
HTML_PREVIEW_PATH = os.path.join(OUTPUT_DIR, "AML_Intelligence_Report.html")

# --------------------------------------------------------------------------- #
#  Data source
# --------------------------------------------------------------------------- #
# "synthetic" -> generate a realistic demo dataset (default, for the mock-up)
# "excel"     -> read the analyst's real statement from EXCEL_PATH
INPUT_MODE = os.environ.get("AML_INPUT_MODE", "synthetic")
EXCEL_PATH = os.environ.get("AML_EXCEL_PATH", XLSX_PATH)

# Canonical schema the whole pipeline expects.
COLUMNS = [
    "Date",
    "Direction",           # IN / OUT
    "Account_No",
    "Sender",
    "Sender_Type",         # Person / Company
    "Beneficiary",
    "Beneficiary_Type",    # Person / Company
    "Amount",
    "Transaction_Method",  # Transfer / Withdrawal / Cheque
]

# Map real-world column headers -> canonical names.  Extend this when the real
# Excel file uses different labels (e.g. {"Txn Date": "Date"}).
COLUMN_ALIASES: dict[str, str] = {
    "date": "Date",
    "value date": "Date",
    "transaction date": "Date",
    "direction": "Direction",
    "dr/cr": "Direction",
    "account": "Account_No",
    "account no": "Account_No",
    "account_number": "Account_No",
    "sender": "Sender",
    "originator": "Sender",
    "from": "Sender",
    "sender type": "Sender_Type",
    "beneficiary": "Beneficiary",
    "to": "Beneficiary",
    "beneficiary type": "Beneficiary_Type",
    "amount": "Amount",
    "value": "Amount",
    "method": "Transaction_Method",
    "transaction method": "Transaction_Method",
    "channel": "Transaction_Method",
}

# The token used inside the data to represent the account holder ("self").
SELF_LABEL = "Me"

# --------------------------------------------------------------------------- #
#  Subject profile (header card).  Placeholders — fill from KYC / real file.
# --------------------------------------------------------------------------- #
PROFILE = {
    "full_name": "«FULL NAME»",
    "nationality": "«NATIONALITY»",
    "customer_id": "«CUSTOMER ID»",
    "risk_rating": "«AUTO»",          # "AUTO" -> derived from analytics
    "primary_account": "«AUTO»",       # "AUTO" -> busiest account
    "analysis_period": "«AUTO»",       # "AUTO" -> min..max date in data
    "photo_path": None,                # e.g. os.path.join(ASSETS_DIR, "photo.jpg")
}

REPORT_META = {
    "title": "FINANCIAL INTELLIGENCE REPORT",
    "subtitle": "Transaction Monitoring & Anti-Money-Laundering Analysis",
    "classification": "CONFIDENTIAL — FIU / AML INVESTIGATIONS",
    "unit": "Financial Intelligence Unit  ·  Transaction Monitoring Division",
    "reference": "FIU/AML/2026/0417",
    "currency": "USD",
    "currency_symbol": "$",
}

# --------------------------------------------------------------------------- #
#  Analytics thresholds (tune per jurisdiction)
# --------------------------------------------------------------------------- #
THRESHOLDS = {
    "reporting_threshold": 10_000,     # CTR / large-cash reporting line
    "structuring_band": 0.90,          # amounts >= 90% of threshold but under it
    "structuring_min_count": 3,        # how many near-threshold txns = pattern
    "structuring_window_days": 7,
    "high_value_percentile": 0.97,     # top 3% by amount = "high value"
    "rapid_movement_days": 3,          # in-then-out window
    "rapid_movement_tolerance": 0.15,  # amount similarity for pass-through
    "smurf_min_senders": 4,            # many-senders-to-one
    "fanout_min_beneficiaries": 5,     # one-to-many
    "repeat_min_count": 4,             # identical repeated transfers
    "dormancy_days": 45,               # gap that counts as "dormant"
    "round_amount_modulo": 1_000,      # round-dollar detection
    "frequent_withdrawal_count": 8,    # withdrawals within window = frequent
    "frequent_withdrawal_window": 30,
}

# Risk-scoring weights per indicator category (0..100 contribution ceiling).
RISK_WEIGHTS = {
    "structuring": 22,
    "smurfing": 18,
    "layering": 16,
    "funnel": 16,
    "pass_through": 15,
    "rapid_movement": 14,
    "round_dollar": 8,
    "circular": 20,
    "fan_out": 12,
    "fan_in": 14,
    "dormant_active": 12,
    "repeated_identical": 10,
    "frequent_withdrawal": 10,
    "high_value": 10,
    "unusual_cheque": 9,
    "abnormal_frequency": 9,
    "behavioural_outlier": 8,
}
