# AML / Financial Intelligence Report Generator

Generates a **single-page, landscape PDF infographic** that looks like a
professional intelligence product from a bank's AML department or a government
**Financial Intelligence Unit (FIU)** — executive KPIs, money-flow Sankey,
network graph, monthly timeline, transaction-method mix, an automated
financial-crime typology engine, a risk dashboard, and top-transaction tables,
all on one clean sheet.

The pipeline is data-source agnostic. It ships with a realistic **synthetic
dataset generator** for the demo, and the *same code* regenerates the report
from a **real Excel statement** the moment you provide one.

![preview](output/preview.png)

---

## Quick start

```bash
pip install -r requirements.txt
python -m playwright install chromium      # or reuse a preinstalled Chromium

# 1) Demo — build from generated synthetic data (250–500 txns)
python generate_report.py

# 2) Real data — analyse your own statement
python generate_report.py --excel /path/to/statement.xlsx
```

Outputs land in `./output/`:

| File | Description |
|------|-------------|
| `AML_Intelligence_Report.pdf`  | The single-page landscape deliverable |
| `AML_Intelligence_Report.html` | Same report as standalone HTML (self-contained) |
| `preview.png`                  | Raster snapshot of the sheet |

> **Chromium path** – the renderer auto-detects a Chromium under
> `/opt/pw-browsers/…`. Override with `CHROME_PATH=/path/to/chrome` if needed.

---

## Input schema

The analytics operate purely on this canonical schema:

| Column | Values / meaning |
|--------|------------------|
| `Date` | transaction date |
| `Direction` | `IN` (credit) / `OUT` (debit) |
| `Account_No` | the subject's account identifier |
| `Sender` | originator (`Me` = the account holder) |
| `Sender_Type` | `Person` / `Company` |
| `Beneficiary` | recipient (`Me` = the account holder) |
| `Beneficiary_Type` | `Person` / `Company` |
| `Amount` | numeric value |
| `Transaction_Method` | `Transfer` / `Withdrawal` / `Cheque` |

**Withdrawal rule:** for `Transaction_Method = Withdrawal`, both `Sender` and
`Beneficiary` are `Me` (cash pulled from the subject's own account).

If your real file uses different headers, add a mapping to
`COLUMN_ALIASES` in [`config.py`](config.py) — the loader normalises them
automatically (a few common aliases are already wired up).

---

## Plugging in your real Excel file

1. Save your statement matching the schema above (or add header aliases in
   `config.py`).
2. Run `python generate_report.py --excel yourfile.xlsx`.
3. Fill in the header card by editing `PROFILE` in `config.py`
   (`full_name`, `nationality`, `customer_id`, optional `photo_path`).
   Fields left as `«AUTO»` are derived from the data (primary account =
   busiest account, analysis period = data date-range, risk rating = engine).

Everything else — KPIs, charts, network, typology detection, risk scores —
is recomputed from the actual data with no further changes.

---

## Financial-crime typologies detected

The engine ([`src/analysis.py`](src/analysis.py)) flags the following, each
with a **risk level**, **confidence**, and a plain-language **explanation**.
Findings are decision-support indicators only — the wording is deliberately
non-accusatory ("potential indicator", "requires review", "possible anomaly").

Structuring · Smurfing / fan-in · Layering · Funnel accounts · Pass-through /
rapid in-out · Round-dollar payments · Circular payments · One-to-many fan-out ·
Many-to-one fan-in · Dormant-then-active · Repeated identical transfers ·
Frequent withdrawals · High-value transactions · Unusual cheque activity ·
Abnormal transaction frequency · Behavioural (statistical) outliers.

Thresholds are centralised in `THRESHOLDS` / `RISK_WEIGHTS` in `config.py` and
can be tuned per jurisdiction.

---

## Project layout

```
config.py                 Profile, data-source mode, schema, thresholds, weights
generate_report.py        Root CLI entry point
src/
  data_generator.py       Synthetic dataset with embedded AML patterns
  analysis.py             KPIs, breakdowns + AML typology detection & scoring
  charts.py               All visuals (matplotlib/networkx) -> base64 PNG
  report.py               Load -> analyse -> chart -> render HTML -> print PDF
templates/
  report.html.j2          The dashboard layout (dark FIU theme, CSS grid)
data/                     Generated / input transactions
output/                   Rendered PDF / HTML / PNG
```

## How it renders on one page

The template is laid out at a fixed landscape width; `report.py` measures the
rendered `.sheet` element and prints the PDF at exactly that pixel size with
`page_ranges="1"`, guaranteeing a single landscape page with no pagination.

## Notes

- The report is fully self-contained — every chart is inlined as a base64 image,
  so the HTML/PDF needs no external assets or network access.
- The synthetic generator is seeded, so the demo output is reproducible.
- Nothing in this repository represents real individuals; all names, accounts,
  and companies are fabricated for demonstration.
