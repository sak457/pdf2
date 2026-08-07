"""
High-quality PDF export.

Assembles a decision-maker-ready landscape PDF from a user-selected set of
charts plus a BLUF cover, the POI profile, headline KPIs and (optionally) the
financial-crime findings. Charts are rendered from Plotly to high-resolution
PNG via kaleido, so the deck stays crisp at print size.
"""

from __future__ import annotations

import io

from fpdf import FPDF
from PIL import Image

from .analytics import money


def _hex(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


_MAP = {"–": "-", "—": "-", "…": "...", "•": "-", "’": "'", "‘": "'",
        "“": '"', "”": '"', "×": "x", "·": "-", "≥": ">=", "≤": "<=",
        "→": "->", "▲": "^", "“": '"'}


def _txt(s) -> str:
    s = str(s)
    for k, v in _MAP.items():
        s = s.replace(k, v)
    # drop anything outside latin-1 (emoji etc.)
    return s.encode("latin-1", "ignore").decode("latin-1")


def _fig_png(fig, t, scale=3, width=1100, height=None):
    height = height or (fig.layout.height or 400)
    f = fig
    f.update_layout(paper_bgcolor=t["card"], plot_bgcolor=t["card"])
    png = f.to_image(format="png", scale=scale, width=width, height=int(height))
    return Image.open(io.BytesIO(png))


class Deck(FPDF):
    def __init__(self, t, meta):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.t = t
        self.meta = meta
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)

    def _bg(self):
        self.set_fill_color(*_hex(self.t["page"]))
        self.rect(0, 0, 297, 210, "F")
        # accent bar
        for i, c in enumerate([self.t["red"], self.t["amber"], self.t["teal"], self.t["blue"]]):
            self.set_fill_color(*_hex(c))
            self.rect(i * 297 / 4, 0, 297 / 4, 2.4, "F")

    def _panel(self, x, y, w, h):
        self.set_fill_color(*_hex(self.t["card"]))
        self.set_draw_color(*_hex(self.t["border"]))
        self.rect(x, y, w, h, "DF")

    def _footer(self, page_label):
        self.set_xy(0, 202)
        self.set_font("helvetica", "", 7)
        self.set_text_color(*_hex(self.t["dim"]))
        self.cell(297, 5, _txt(f"  {self.meta.get('classification','CONFIDENTIAL')}   ·   "
                               f"{self.meta.get('reference','')}   ·   {page_label}"), 0, 0, "L")


def build_pdf(*, t, meta, bluf, poi, kpis, overall_risk, overall_band,
              charts, findings=None, analyst_note="") -> bytes:
    """charts: list of {title, fig, note}. Returns PDF bytes."""
    d = Deck(t, meta)
    ink = _hex(t["ink"]); mute = _hex(t["mute"]); amber = _hex(t["amber"])
    band_c = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[overall_band]

    # ---------------- Cover ----------------
    d.add_page(); d._bg()
    d.set_xy(14, 12)
    d.set_font("helvetica", "B", 9); d.set_text_color(*_hex(amber if False else t["amber"]))
    d.cell(0, 5, _txt(meta.get("classification", "CONFIDENTIAL — FIU / AML")), 0, 2)
    d.set_font("helvetica", "B", 26); d.set_text_color(*ink)
    d.cell(0, 12, _txt(meta.get("title", "Financial Intelligence Report")), 0, 2)
    d.set_font("helvetica", "", 11); d.set_text_color(*mute)
    d.cell(0, 6, _txt(meta.get("subtitle", "Transaction Monitoring & AML Analysis")), 0, 2)

    # POI card (left)
    d._panel(14, 46, 92, 92)
    d.set_xy(20, 50); d.set_font("helvetica", "B", 8); d.set_text_color(*mute)
    d.cell(0, 5, _txt("SUBJECT / PERSON OF INTEREST"), 0, 2)
    if poi.get("photo"):
        try:
            d.image(Image.open(io.BytesIO(poi["photo"])), x=20, y=58, w=26, h=32)
        except Exception:
            pass
    tx = 50
    d.set_xy(tx, 58); d.set_font("helvetica", "B", 14); d.set_text_color(*ink)
    d.cell(0, 7, _txt(poi.get("name", "—")), 0, 2)
    d.set_x(tx); d.set_font("helvetica", "", 9); d.set_text_color(*mute)
    for label, key in [("Nationality", "nationality"), ("Doc / Customer ID", "doc_id"),
                       ("Primary Account", "primary_account")]:
        val = poi.get(key, "—") or "—"
        d.set_x(tx); d.set_text_color(*mute); d.cell(30, 5, _txt(label), 0, 0)
        d.set_text_color(*ink); d.cell(0, 5, _txt(str(val)), 0, 2)
    d.set_xy(20, 96); d.set_text_color(*mute); d.set_font("helvetica", "", 9)
    d.cell(30, 5, _txt("Analysis Period"), 0, 0); d.set_text_color(*ink)
    d.cell(0, 5, _txt(poi.get("period", "—")), 0, 2)
    d.set_xy(20, 104); d.set_text_color(*mute)
    d.cell(30, 5, _txt("Risk Rating"), 0, 0)
    d.set_text_color(*_hex(band_c)); d.set_font("helvetica", "B", 11)
    d.cell(0, 6, _txt(f"{overall_risk}/100  ·  {overall_band.upper()} RISK"), 0, 2)

    # BLUF (right top)
    d._panel(110, 46, 173, 52)
    d.set_xy(115, 50); d.set_font("helvetica", "B", 10); d.set_text_color(*_hex(t["amber"]))
    d.cell(0, 5, _txt("BLUF — BOTTOM LINE UP FRONT"), 0, 2)
    d.set_xy(115, 57); d.set_font("helvetica", "", 9.2); d.set_text_color(*ink)
    d.multi_cell(163, 4.6, _txt(bluf))

    # KPI strip (right bottom)
    kpi_items = [("Transactions", f"{kpis['total_txns']:,}", t["blue"]),
                 ("Inflow", money(kpis["total_in"]), t["green"]),
                 ("Outflow", money(kpis["total_out"]), t["red"]),
                 ("Net", money(kpis["net"]), t["green"] if kpis["net"] >= 0 else t["red"]),
                 ("Accounts", str(kpis["n_accounts"]), t["blue"]),
                 ("Flags", f"{kpis['n_flags']} ({kpis['n_high']}H)", t["amber"])]
    kx, kw = 110, 173 / 3
    for i, (lbl, val, col) in enumerate(kpi_items):
        x = kx + (i % 3) * kw; y = 104 + (i // 3) * 18
        d._panel(x + 1, y, kw - 2, 16)
        d.set_xy(x + 4, y + 2.5); d.set_font("helvetica", "", 7); d.set_text_color(*mute)
        d.cell(0, 4, _txt(lbl.upper()), 0, 2)
        d.set_x(x + 4); d.set_font("helvetica", "B", 13); d.set_text_color(*_hex(col))
        d.cell(0, 6, _txt(val), 0, 0)

    if analyst_note.strip():
        d._panel(14, 142, 269, 52)
        d.set_xy(19, 146); d.set_font("helvetica", "B", 9); d.set_text_color(*_hex(t["amber"]))
        d.cell(0, 5, _txt("ANALYST COMMENTARY"), 0, 2)
        d.set_xy(19, 153); d.set_font("helvetica", "", 9.4); d.set_text_color(*ink)
        d.multi_cell(259, 4.8, _txt(analyst_note))
    d._footer("Cover")

    # ---------------- Chart pages ----------------
    for i, ch in enumerate(charts, 1):
        d.add_page(); d._bg()
        d.set_xy(14, 10); d.set_font("helvetica", "B", 15); d.set_text_color(*ink)
        d.cell(0, 8, _txt(ch["title"]), 0, 2)
        note = ch.get("note", "")
        img = _fig_png(ch["fig"], t, width=1180,
                       height=ch["fig"].layout.height or 420)
        # fit image into content area
        avail_w, avail_h = 269, 150
        iw, ih = img.size
        ratio = min(avail_w / iw, avail_h / ih)
        w, h = iw * ratio, ih * ratio
        d._panel(14, 22, 269, 154)
        d.image(img, x=14 + (269 - w) / 2, y=22 + (154 - h) / 2, w=w, h=h)
        if note:
            d.set_xy(14, 180); d.set_font("helvetica", "I", 8.5); d.set_text_color(*mute)
            d.multi_cell(269, 4.3, _txt("Evidence — " + note))
        d._footer(f"Exhibit {i}")

    # ---------------- Findings page ----------------
    if findings:
        d.add_page(); d._bg()
        d.set_xy(14, 10); d.set_font("helvetica", "B", 15); d.set_text_color(*ink)
        d.cell(0, 8, _txt("Financial-Crime Typology Indicators"), 0, 2)
        d.set_font("helvetica", "", 8.5); d.set_text_color(*mute)
        d.set_xy(14, 19)
        d.cell(0, 5, _txt("Decision-support indicators only — not an allegation of "
                          "wrongdoing. Each requires analyst review."), 0, 2)
        y = 27
        for f in findings:
            if y > 186:
                break
            col = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[f["level"]]
            d._panel(14, y, 269, 21)
            d.set_fill_color(*_hex(col)); d.rect(14, y, 1.6, 21, "F")
            d.set_xy(19, y + 2); d.set_font("helvetica", "B", 10); d.set_text_color(*ink)
            d.cell(0, 5, _txt(f["title"]), 0, 0)
            d.set_font("helvetica", "B", 8); d.set_text_color(*_hex(col))
            d.set_xy(19, y + 2); d.cell(264, 5, _txt(f"{f['level'].upper()} · CONF {f['confidence'].upper()}"), 0, 0, "R")
            d.set_xy(19, y + 8); d.set_font("helvetica", "", 8.2); d.set_text_color(*mute)
            d.multi_cell(258, 3.9, _txt(f["why"])[:320])
            y += 23
        d._footer("Findings")

    out = d.output()
    return bytes(out)
