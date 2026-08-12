"""
Shared HTML renderer for the counterparty card.

Emits a self-contained, inline-styled block (no CSS variables or classes) so it
renders identically in three places: the Streamlit counterparty cards' look, the
link-analysis hover tooltip (inside the pyvis iframe, which has none of the app's
CSS), and the account-lookup panel. All analyst-supplied text is HTML-escaped.
"""

from __future__ import annotations

import html

from .analytics import money
from .i18n import T

ICON = {"Company": "🏢", "Person": "👤", "Unknown": "❓", "POI": "🎯"}
MONO = "'JetBrains Mono',ui-monospace,Menlo,monospace"


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def _box(label, value, color, arrow, t):
    return (f"<div style='flex:1;background:{color}1e;border:1px solid {color}66;"
            f"border-radius:8px;padding:6px 9px'>"
            f"<div style='font-size:10px;color:{t['mute']};font-family:{MONO}'>{arrow} {esc(label)}</div>"
            f"<div style='font-family:{MONO};font-weight:700;color:{color}'>{esc(value)}</div></div>")


def _field(label, value, t):
    return (f"<div style='margin-top:6px'>"
            f"<div style='font-size:10px;color:{t['mute']};font-family:{MONO};"
            f"text-transform:uppercase;letter-spacing:.04em'>{esc(label)}</div>"
            f"<div style='color:{t['ink']};font-weight:600'>{esc(value)}</div></div>")


def cp_card_html(card: dict, t: dict, lang: str = "en", max_width: int = 320) -> str:
    icon = ICON.get(card.get("tclass"), "❓")
    rtl = "direction:rtl;" if lang == "ar" else ""
    osint_on = bool(card.get("osint"))
    osint_col = t["green"] if osint_on else t["dim"]
    osint_txt = (("نعم" if osint_on else "لا") if lang == "ar" else ("yes" if osint_on else "no"))

    parts = [
        f"<div style='max-width:{max_width}px;{rtl}background:{t['card']};"
        f"border:1px solid {t['border']};border-radius:12px;padding:11px 13px;"
        f"font-family:Inter,\"Segoe UI\",sans-serif;color:{t['ink']};text-align:start'>",
        f"<div style='display:flex;align-items:center;gap:9px'>"
        f"<span style='font-size:24px'>{icon}</span>"
        f"<span style='font-weight:800;font-size:15px'>{esc(card.get('name') or '—')}</span></div>",
        _field(T("cp_account", lang), card.get("account") or "—", t),
        _field(T("cp_type_field", lang), card.get("type") or "—", t),
        f"<div style='margin-top:6px;font-family:{MONO};font-size:11px;color:{osint_col}'>"
        f"🔎 {esc(T('cp_osint', lang))}: {osint_txt}</div>",
    ]
    if card.get("functions"):
        parts.append(_field(T("cp_functions", lang), str(card["functions"])[:200], t))
    parts.append(
        f"<div style='display:flex;gap:8px;margin-top:8px'>"
        + _box(T("cp_in", lang), money(card.get("total_in", 0)), t["green"], "⬇", t)
        + _box(T("cp_out", lang), money(card.get("total_out", 0)), t["red"], "⬆", t)
        + "</div>")
    parts.append("</div>")
    return "".join(parts)


def simple_tip_html(lines: list[str], t: dict, max_width: int = 320) -> str:
    body = "<br>".join(esc(l) for l in lines if l)
    return (f"<div style='max-width:{max_width}px;background:{t['card']};"
            f"border:1px solid {t['border']};border-radius:10px;padding:9px 12px;"
            f"font-family:Inter,sans-serif;color:{t['ink']}'>{body}</div>")
