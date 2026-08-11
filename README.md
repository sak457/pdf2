# AML / Financial Intelligence Toolkit

Two ways to turn POI transaction data into a professional financial-intelligence
product:

1. **📊 Interactive dashboard** (`app/`) — a Streamlit web app: upload a CSV,
   slice it with filters, drill into every chart's evidence, edit the POI and
   the link-analysis nodes, and export a customised decision-maker PDF. **Start
   here for day-to-day analysis.**
2. **🖨️ Batch one-pager** (`src/`) — a headless pipeline that renders a
   single-page landscape PDF infographic from a dataset (great for automation /
   air-gapped generation).

---

## 📊 Interactive dashboard (Streamlit)

```bash
pip install -r requirements-app.txt
streamlit run app/app.py
```

Then open the browser tab it prints and **log in**. On first launch the app
creates an admin account from the environment (see *Deployment & configuration*
below); with nothing set the default is **`admin` / `admin`** and the login
screen warns you to change it. After logging in, click **Load sample** (sidebar)
to explore immediately, or upload your own CSV — **each upload becomes a saved
work session** that persists everything you do.

**Input CSV schema** (case-insensitive headers; common aliases tolerated):

| column | values |
|--------|--------|
| `date` | transaction date |
| `direction` | `in` · `out` · `own_account` |
| `account_no` | POI account; `A\|B` for own-account transfers |
| `sender` | `poi` · a company name · `unknown` |
| `beneficiary` | `poi` · a company name · `unknown` |
| `amount` | numeric |
| `transaction_method` | `transfer` · `withdrawal` · `cheque` · `cash` · … |

**What it does**

- **BLUF summary** auto-generated at the top (editable) so the picture is clear
  in one read — no briefing required.
- **Night / day** theme toggle; modern dark FIU styling by default.
- **Filters**: date range, quarter, direction, method, account, counterparty
  type, and amount range — every chart, KPI and the risk score recompute live.
- **Evidence on demand**: a `🔬 Evidence` button on the risk score, each chart,
  and every financial-crime indicator reveals *why* it fired and *the exact
  transactions* behind it.
- **POI profile** editor (name, nationality, doc/customer id, photo, notes).
- **Link analysis**: interactive relationship graph (node size = volume, edge
  colour = direction) — fully self-contained (the graph library is inlined, no
  CDN), so it renders instantly even airgapped. Annotate any node with a name /
  doc id / photo / notes, and inspect **the transactions between any two nodes**.
- **Counterparty lookup**: a floating 🪪 button (bottom-right, on every tab) —
  click it and search any account # or name to pull up that counterparty's card.
- **Financial-crime typologies**: 14 detectors (structuring, smurfing, funnel/
  layering, pass-through, round-tripping, round-dollar, own-account churn,
  fan-out, dormant-reactivation, repeated transfers, frequent withdrawals,
  high-value, unusual cheque, abnormal frequency, behavioural outliers), each
  with risk level, confidence, plain-language explanation and evidence.
- **Export**: choose exactly which exhibits to include, add commentary, and
  download a **high-quality landscape PDF** (BLUF cover + POI card + KPIs +
  selected charts + findings) for a decision-maker.

Wording is deliberately non-accusatory — every flag is a *potential indicator
requiring review*, not an allegation.

### Accounts, sessions & persistence

- **Login** — accounts live in a SQLite DB; passwords are PBKDF2-hashed. Admins
  are designated by the `AML_ADMIN_USERS` env var (they see everyone's sessions
  and can wipe all data); everyone else sees only their own work.
- **Sessions** — every CSV upload or *Load sample* creates a **work session**
  that stores the data plus a snapshot of everything you do (POI + photo,
  counterparty-card edits/merges/OSINT, node annotations, removed findings,
  hidden KPIs, BLUF, chat). Work **autosaves** continuously.
- **Manage** — the sidebar lists your sessions to open/rename/delete; admins get
  a user-management panel (add / reset password / delete) and a *wipe all
  sessions & data* action gated by a typed `DELETE ALL` (user accounts are kept).

### Deployment & configuration

Set these environment variables when you deploy (all optional; sensible
defaults, but **set a real admin password in production**):

| variable | purpose | default |
|----------|---------|---------|
| `AML_ADMIN_USERS` | comma-separated admin usernames | `admin` |
| `AML_ADMIN_PASSWORD` | password for the bootstrapped admin(s) on first run | `admin` (a "change me" warning shows until set) |
| `AML_DB_PATH` | SQLite database file path — put it on a persistent volume | `app/data/aml.db` (`/data/aml.db` in Docker) |
| `AML_OFFLINE` | skip the Google-Fonts web-font CDN so the UI loads instantly in airgapped networks (built-in fallback fonts apply) | unset (on = `1` in the Docker image) |

**Run in Docker** (slim — no system Chromium needed; DB on a named volume so it
survives restarts):

```bash
docker buildx build --platform linux/amd64 -f Dockerfile.app -t aml-dashboard:1.0 --load .

docker volume create aml-data
docker run --rm -p 8501:8501 \
    -v aml-data:/data \
    -e AML_ADMIN_USERS=admin \
    -e AML_ADMIN_PASSWORD='change-me-please' \
    aml-dashboard:1.0                         # http://localhost:8501
```

The database (users + all saved work sessions) lives at `/data/aml.db` inside the
container; the `-v aml-data:/data` mount keeps it across restarts and upgrades.

---

## 🖨️ Batch one-pager generator

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

## Docker / air-gapped deployment (amd64)

The image is built for **x86_64 / amd64** servers and bundles everything needed
at run time — Python deps, the Chromium browser, its shared libraries, and the
emoji/symbol fonts the dashboard renders — so it needs **no network access when
run**. Build it on a connected host, carry the tarball into the air-gapped
network, load, and run.

**On a network-connected build host:**

```bash
./docker-airgap-build.sh 1.0
# builds aml-report:1.0 for linux/amd64 and writes aml-report_1.0_amd64.tar.gz
```

(or manually)

```bash
docker buildx build --platform linux/amd64 -t aml-report:1.0 --load .
docker save aml-report:1.0 | gzip > aml-report_1.0_amd64.tar.gz
```

**Transfer** `aml-report_1.0_amd64.tar.gz` into the air-gapped network, then on
a target server:

```bash
gunzip -c aml-report_1.0_amd64.tar.gz | docker load
mkdir -p output

# demo report from synthetic data
docker run --rm -v "$PWD/output:/app/output" aml-report:1.0

# report from a real statement (mount it read-only)
docker run --rm -v "$PWD/output:/app/output" -v "$PWD/in:/data:ro" \
    aml-report:1.0 --excel /data/statement.xlsx
```

The PDF appears at `output/AML_Intelligence_Report.pdf`.

Notes:
- The `--platform linux/amd64` pin makes the image amd64 even if the build host
  is arm (Apple silicon) — it builds via QEMU emulation. The helper script
  verifies the resulting image architecture is `amd64`.
- Chromium runs with `--no-sandbox` (required as root inside a container) and
  `--disable-dev-shm-usage`; no extra `docker run` flags are needed.
- To override the subject profile without rebuilding, mount your own
  `config.py`: `-v "$PWD/config.py:/app/config.py:ro"`.

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
