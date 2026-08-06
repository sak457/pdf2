"""
Report orchestrator — the single entry point.

    python src/report.py            # build from synthetic demo data
    AML_INPUT_MODE=excel AML_EXCEL_PATH=/path/statement.xlsx python src/report.py

Pipeline:  load/generate -> analyse -> build charts -> render HTML -> print PDF.
The same code path serves both the demo dataset and a real Excel statement;
only ``config.INPUT_MODE`` / env vars change.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
import analysis
import charts

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
]


# --------------------------------------------------------------------------- #
#  Data loading
# --------------------------------------------------------------------------- #
def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Map arbitrary headers onto the canonical schema."""
    rename = {}
    for c in df.columns:
        key = str(c).strip().lower()
        if key in config.COLUMN_ALIASES:
            rename[c] = config.COLUMN_ALIASES[key]
    df = df.rename(columns=rename)
    missing = [c for c in config.COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")
    df = df[config.COLUMNS].copy()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Direction"] = df["Direction"].astype(str).str.upper().str.strip()
    return df.dropna(subset=["Date"])


def load_data() -> pd.DataFrame:
    if config.INPUT_MODE == "excel":
        path = config.EXCEL_PATH
        print(f"[data] loading real statement: {path}")
        df = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) \
            else pd.read_csv(path)
        return _normalise(df)
    # synthetic
    from data_generator import main as gen
    if not os.path.exists(config.CSV_PATH):
        return gen()
    return _normalise(pd.read_csv(config.CSV_PATH))


# --------------------------------------------------------------------------- #
#  Template context
# --------------------------------------------------------------------------- #
def build_context(results: dict, imgs: dict) -> dict:
    prof = dict(config.PROFILE)
    dp = results["derived_profile"]
    if prof.get("primary_account") in (None, "«AUTO»", "AUTO"):
        prof["primary_account"] = dp["primary_account"]
    if prof.get("analysis_period") in (None, "«AUTO»", "AUTO"):
        prof["analysis_period"] = dp["analysis_period"]
    if prof.get("risk_rating") in (None, "«AUTO»", "AUTO"):
        prof["risk_rating"] = dp["risk_rating"]

    photo_uri = None
    if prof.get("photo_path") and os.path.exists(prof["photo_path"]):
        import base64
        ext = os.path.splitext(prof["photo_path"])[1].lstrip(".") or "png"
        with open(prof["photo_path"], "rb") as fh:
            photo_uri = f"data:image/{ext};base64," + base64.b64encode(fh.read()).decode()

    k = results["kpis"]
    kpi_cards = [
        ("📊", "Total Transactions", f"{k['total_txns']:,}", "", "blue"),
        ("⬇", "Total Incoming", analysis.money(k["total_in"]), "credits", "green"),
        ("⬆", "Total Outgoing", analysis.money(k["total_out"]), "debits", "red"),
        ("💰", "Net Cash Flow", analysis.money(k["net_flow"]),
         "surplus" if k["net_flow"] >= 0 else "deficit",
         "green" if k["net_flow"] >= 0 else "red"),
        ("🏦", "Accounts", f"{k['n_accounts']}", "monitored", "blue"),
        ("👤", "Unique Senders", f"{k['n_senders']}", "originators", "teal"),
        ("🏢", "Unique Beneficiaries", f"{k['n_beneficiaries']}", "recipients", "teal"),
        ("📈", "Average Txn", analysis.money(k["avg_txn"]), "per transaction", "blue"),
        ("💠", "Largest Txn", analysis.money(k["largest_txn"]), "single movement", "amber"),
        ("⚠", "Risk Score", f"{k['risk_score']}/100",
         results["overall_band"].upper(), "risk-" + results["overall_band"].lower()),
    ]

    return {
        "meta": config.REPORT_META,
        "profile": prof,
        "photo_uri": photo_uri,
        "results": results,
        "kpis": k,
        "kpi_cards": kpi_cards,
        "flow": results["flow"],
        "accounts": results["accounts"],
        "senders": results["senders"][:8],
        "beneficiaries": results["beneficiaries"][:8],
        "sender_persons": results["top_sender_persons"],
        "sender_companies": results["top_sender_companies"],
        "ben_persons": results["top_ben_persons"],
        "ben_companies": results["top_ben_companies"],
        "methods": results["methods"],
        "findings": results["findings"],
        "risk_entities": results["risk_entities"],
        "accounts_risk": results["accounts"],
        "top_in": results["top_in"],
        "top_out": results["top_out"],
        "overall_risk": results["overall_risk"],
        "overall_band": results["overall_band"],
        "img": imgs,
        "money": analysis.money,
        "money_full": analysis.money_full,
    }


# --------------------------------------------------------------------------- #
#  Render
# --------------------------------------------------------------------------- #
def render_html(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(config.TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.globals.update(money=analysis.money, money_full=analysis.money_full,
                       band=analysis.risk_band, enumerate=enumerate)
    tmpl = env.get_template("report.html.j2")
    return tmpl.render(**context)


def _chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    import glob
    hits = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
    if hits:
        return sorted(hits)[-1]
    raise FileNotFoundError("Chromium executable not found under /opt/pw-browsers")


def to_pdf(html: str, pdf_path: str, png_path: str | None = None) -> None:
    from playwright.sync_api import sync_playwright
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=_chrome(),
                                    args=["--no-sandbox", "--force-color-profile=srgb"])
        page = browser.new_page(device_scale_factor=2)
        page.set_content(html, wait_until="networkidle")
        # Measure the sheet so the PDF is exactly one landscape page.
        dims = page.evaluate(
            "() => { const s = document.querySelector('.sheet');"
            " const r = s.getBoundingClientRect();"
            " return {w: Math.ceil(r.width), h: Math.ceil(r.height)}; }")
        if png_path:
            page.locator(".sheet").screenshot(path=png_path)
        page.pdf(path=pdf_path, print_background=True,
                 width=f"{dims['w']}px", height=f"{dims['h']}px",
                 page_ranges="1", margin={"top": "0", "bottom": "0",
                                          "left": "0", "right": "0"})
        browser.close()
    print(f"[pdf ] {pdf_path}  ({dims['w']}x{dims['h']} px, landscape="
          f"{dims['w'] > dims['h']})")


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main() -> None:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df = load_data()
    print(f"[data] {len(df)} transactions | "
          f"{df['Date'].min():%Y-%m-%d} → {df['Date'].max():%Y-%m-%d}")
    results = analysis.analyze(df)
    imgs = charts.build_all(results)
    context = build_context(results, imgs)
    html = render_html(context)
    with open(config.HTML_PREVIEW_PATH, "w") as fh:
        fh.write(html)
    png = os.path.join(config.OUTPUT_DIR, "preview.png")
    to_pdf(html, config.PDF_PATH, png_path=png)
    print(f"[html] {config.HTML_PREVIEW_PATH}")
    print(f"[png ] {png}")


if __name__ == "__main__":
    main()
