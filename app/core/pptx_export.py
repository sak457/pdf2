"""
Editable PowerPoint (PPTX) export.

Builds a decision-maker deck from selected charts. If the analyst uploads a
.pptx template, the deck is created on top of it (its slide size, theme and
background are preserved); otherwise a clean 16:9 dark deck is generated.
Charts are inserted as high-resolution PNGs (kaleido) but all text is real,
editable PowerPoint text — the recipient can change anything.
"""

from __future__ import annotations

import io

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from PIL import Image

from .analytics import money


def _rgb(hexc: str) -> RGBColor:
    return RGBColor.from_string(hexc.lstrip("#").upper())


def _blank_layout(prs: Presentation):
    """Pick the emptiest layout available in the (template's) master."""
    best, best_ph = None, 999
    for lay in prs.slide_layouts:
        n = len(lay.placeholders)
        if n < best_ph:
            best, best_ph = lay, n
    return best or prs.slide_layouts[-1]


def _fig_png(fig, t, scale=3, width=1200, height=None):
    height = int(height or (fig.layout.height or 420))
    fig.update_layout(paper_bgcolor=t["card"], plot_bgcolor=t["card"])
    return fig.to_image(format="png", scale=scale, width=width, height=height)


def _text(slide, x, y, w, h, runs, *, size=14, bold=False, color="FFFFFF",
          align=PP_ALIGN.LEFT, font="Segoe UI", anchor=MSO_ANCHOR.TOP, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    lines = runs if isinstance(runs, list) else [runs]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = str(line)
        r.font.size = Pt(size); r.font.bold = bold
        r.font.name = font; r.font.color.rgb = _rgb(color)
    return tb


def _rect(slide, x, y, w, h, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                Inches(w), Inches(h))
    sp.fill.solid(); sp.fill.fore_color.rgb = _rgb(fill)
    if line:
        sp.line.color.rgb = _rgb(line); sp.line.width = Pt(0.75)
    else:
        sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


def build_pptx(*, t, meta, bluf, poi, kpis, overall_risk, overall_band,
               charts, findings=None, analyst_note="", template_bytes=None) -> bytes:
    if template_bytes:
        prs = Presentation(io.BytesIO(template_bytes))
    else:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    SW = prs.slide_width / 914400.0    # inches
    SH = prs.slide_height / 914400.0
    layout = _blank_layout(prs)
    ink = t["ink"].lstrip("#").upper()
    amber = t["amber"].lstrip("#").upper()
    mute = t["mute"].lstrip("#").upper()
    band_c = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[overall_band].lstrip("#").upper()
    dark = t["name"] == "night"
    paint_bg = (not template_bytes)  # only paint our own bg when no template

    def new_slide(title=None):
        s = prs.slides.add_slide(layout)
        if paint_bg:
            _rect(s, 0, 0, SW, SH, t["page"].lstrip("#").upper())
            _rect(s, 0, 0, SW, 0.09, amber)
        if title:
            _text(s, 0.5, 0.28, SW - 1, 0.7, title, size=24, bold=True,
                  color=ink if dark or not paint_bg else "0B1A33")
        return s

    # ---- Title / cover ----
    s = new_slide()
    _text(s, 0.6, 0.5, SW - 1.2, 0.4, meta.get("classification", "CONFIDENTIAL"),
          size=11, bold=True, color=amber)
    _text(s, 0.6, 1.5, SW - 1.2, 1.0, meta.get("title", "Financial Intelligence Report"),
          size=34, bold=True, color=ink if dark else "0B1A33")
    _text(s, 0.6, 2.5, SW - 1.2, 0.5, meta.get("subtitle", ""), size=15, color=mute)
    # risk chip
    _rect(s, 0.6, 3.4, 3.2, 1.0, t["card"].lstrip("#").upper(), t["border"].lstrip("#").upper())
    _text(s, 0.75, 3.5, 3.0, 0.3, "OVERALL RISK", size=10, bold=True, color=mute)
    _text(s, 0.75, 3.75, 3.0, 0.6, f"{overall_risk}/100  ·  {overall_band.upper()}",
          size=22, bold=True, color=band_c)
    _text(s, 0.6, 4.7, SW - 1.2, 0.4, f"Subject: {poi.get('name','—')}   ·   "
          f"{poi.get('period','')}", size=13, color=ink if dark else "0B1A33")

    # ---- BLUF + POI + KPIs ----
    s = new_slide("BLUF — Bottom Line Up Front")
    _rect(s, 0.5, 1.1, SW - 1.0, 2.1, t["card"].lstrip("#").upper(), t["border"].lstrip("#").upper())
    _text(s, 0.7, 1.25, SW - 1.4, 1.9, bluf, size=13, color=ink if dark else "0B1A33")
    # POI line
    poi_line = (f"{poi.get('name','—')}   |   {poi.get('nationality','')}   |   "
                f"ID {poi.get('doc_id','')}   |   Primary {poi.get('primary_account','')}")
    _text(s, 0.5, 3.35, SW - 1.0, 0.4, poi_line, size=12, bold=True, color=amber)
    # KPI tiles
    tiles = [("Transactions", f"{kpis['total_txns']:,}", t["blue"]),
             ("Inflow", money(kpis["total_in"]), t["green"]),
             ("Outflow", money(kpis["total_out"]), t["red"]),
             ("Net", money(kpis["net"]), t["green"] if kpis["net"] >= 0 else t["red"]),
             ("Accounts", str(kpis["n_accounts"]), t["blue"]),
             ("Risk flags", f"{kpis['n_flags']}", t["amber"])]
    tw = (SW - 1.0 - 0.5 * 5) / 6
    for i, (lbl, val, col) in enumerate(tiles):
        x = 0.5 + i * (tw + 0.5)
        _rect(s, x, 4.0, tw, 1.2, t["card"].lstrip("#").upper(), t["border"].lstrip("#").upper())
        _text(s, x + 0.12, 4.12, tw - 0.2, 0.3, lbl.upper(), size=8, color=mute)
        _text(s, x + 0.12, 4.45, tw - 0.2, 0.6, val, size=16, bold=True,
              color=col.lstrip("#").upper())
    if analyst_note.strip():
        _text(s, 0.5, 5.5, SW - 1.0, 1.4, "Analyst commentary: " + analyst_note,
              size=11, color=mute)

    # ---- Chart slides ----
    for ch in charts:
        s = new_slide(ch["title"])
        png = _fig_png(ch["fig"], t, width=1200, height=ch["fig"].layout.height or 460)
        img = Image.open(io.BytesIO(png)); iw, ih = img.size
        avail_w, avail_h = SW - 1.2, SH - 2.2
        ratio = min(avail_w / (iw / 96.0), avail_h / (ih / 96.0))
        w = (iw / 96.0) * ratio; h = (ih / 96.0) * ratio
        _rect(s, 0.5, 1.05, SW - 1.0, avail_h + 0.2, t["card"].lstrip("#").upper(),
              t["border"].lstrip("#").upper())
        s.shapes.add_picture(io.BytesIO(png), Inches((SW - w) / 2), Inches(1.15),
                             width=Inches(w), height=Inches(h))
        if ch.get("note"):
            _text(s, 0.6, SH - 1.05, SW - 1.2, 0.8, "What this shows — " + ch["note"],
                  size=11, color=mute)

    # ---- Findings ----
    if findings:
        s = new_slide("Financial-Crime Typology Indicators")
        _text(s, 0.5, 1.0, SW - 1.0, 0.35,
              "Decision-support indicators only — not an allegation; each requires review.",
              size=10, color=mute)
        y = 1.5
        for f in findings[:9]:
            if y > SH - 0.9:
                break
            col = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[f["level"]].lstrip("#").upper()
            _rect(s, 0.5, y, SW - 1.0, 0.52, t["card"].lstrip("#").upper(), t["border"].lstrip("#").upper())
            _rect(s, 0.5, y, 0.08, 0.52, col)
            _text(s, 0.7, y + 0.04, SW - 4.0, 0.44, f["title"], size=12, bold=True,
                  color=ink if dark else "0B1A33", anchor=MSO_ANCHOR.MIDDLE)
            _text(s, SW - 3.2, y + 0.04, 2.7, 0.44,
                  f"{f['level'].upper()} · CONF {f['confidence'].upper()}", size=10,
                  bold=True, color=col, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
            y += 0.62

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
