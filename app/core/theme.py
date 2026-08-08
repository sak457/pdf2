"""
Theme, palette and icon system — "Financial Intelligence Terminal".

Design direction (deliberate, not templated):
  * Canvas    : deep near-black navy, the look of a signals / command console.
  * Type      : Space Grotesk (display) · Inter (body) · JetBrains Mono (every
                figure — money, scores, dates — set with tabular numerals so
                columns of numbers line up like a forensic ledger).
  * Signature : an amber "classification" accent + a thin status rail on cards
                + monospaced section kickers ("SECTION // 03") that evoke the
                numbered exhibits of a real intelligence report.

Two coordinated palettes (night / day) drive both the Streamlit chrome (CSS)
and the Plotly figures (apply_theme) so one toggle restyles everything.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
#  Icons
# --------------------------------------------------------------------------- #
IC = {
    "app": "🛰️",
    "bluf": "📌", "poi": "🪪", "photo": "🧑", "filters": "🎛️", "theme": "🌗",
    "evidence": "🔬", "export": "📤", "upload": "📥",
    "txns": "🧮", "in": "🟢", "out": "🔴", "net": "💰", "accounts": "🏦",
    "senders": "👥", "beneficiaries": "🏢", "avg": "📊", "largest": "💠",
    "risk": "⚠️", "own": "🔁",
    "overview": "📋", "flow": "💵", "timeline": "📈", "counterparties": "👤",
    "network": "🕸️", "typology": "🚨", "riskdash": "🎯", "transactions": "🧾",
    "transfer": "💳", "withdrawal": "🏧", "cheque": "🧾", "cash": "💵", "card": "💳",
    "up": "⬆️", "down": "⬇️", "search": "🔍", "company": "🏢", "person": "👤",
    "unknown": "❓",
}

METHOD_ICON = {"transfer": "💳", "withdrawal": "🏧", "cheque": "🧾",
               "cash": "💵", "card": "💳", "deposit": "🏦", "wire": "🌐"}

TYPE_ICON = {"POI": "🎯", "Company": "🏢", "Unknown": "❓",
             "Person": "👤", "Internal": "🔁", "Account": "🏦"}

# --------------------------------------------------------------------------- #
#  Palettes  (colours grounded in the ui-ux-pro-max "Financial Dashboard" set)
# --------------------------------------------------------------------------- #
NIGHT = {
    "name": "night",
    "page": "#020617",        # near-black navy canvas
    "page2": "#0a1122",
    "card": "#0e1526",
    "card2": "#0a1020",
    "border": "#22314c",
    "hair": "#33456a",        # brighter hairline for card top-edge
    "ink": "#f4f8ff",
    "mute": "#93a3c0",
    "dim": "#5f7195",
    "grid": "#1a2740",
    "green": "#2ee6a6",
    "red": "#ff5d6c",
    "blue": "#4b8bff",
    "teal": "#2dd4bf",
    "amber": "#f5a524",       # signature classification accent
    "violet": "#a78bfa",
    "pink": "#f472b6",
    "cyan": "#38bdf8",
    "plotly_template": "plotly_dark",
    "poi": "#f5a524",
    "account": "#4b8bff",
    "company": "#2dd4bf",
    "unknown": "#8394b3",
}

DAY = {
    "name": "day",
    "page": "#eef2f9",
    "page2": "#e3e9f4",
    "card": "#ffffff",
    "card2": "#f4f7fc",
    "border": "#d2dcec",
    "hair": "#c2d0e6",
    "ink": "#0b1a33",
    "mute": "#51637f",
    "dim": "#7788a3",
    "grid": "#dde5f1",
    "green": "#0ea672",
    "red": "#e23744",
    "blue": "#2563eb",
    "teal": "#0d9488",
    "amber": "#c77a10",
    "violet": "#7c3aed",
    "pink": "#db2777",
    "cyan": "#0284c7",
    "plotly_template": "plotly_white",
    "poi": "#c77a10",
    "account": "#2563eb",
    "company": "#0d9488",
    "unknown": "#64748b",
}

FONT_SANS = "Inter, 'Segoe UI', DejaVu Sans, sans-serif"
FONT_DISPLAY = "'Space Grotesk', Inter, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', monospace"

SERIES = lambda t: [t["teal"], t["blue"], t["amber"], t["violet"],
                    t["cyan"], t["pink"], t["green"], t["red"]]

LEVEL_COLOR = lambda t: {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}


def theme(name: str) -> dict:
    return DAY if name == "day" else NIGHT


# --------------------------------------------------------------------------- #
#  Plotly styling
# --------------------------------------------------------------------------- #
def apply_theme(fig, t: dict, *, height=None, legend=True, title=None):
    fig.update_layout(
        template=t["plotly_template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_SANS, color=t["ink"], size=13),
        margin=dict(l=12, r=12, t=42 if title else 14, b=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=t["mute"], size=12)),
        colorway=SERIES(t),
        hoverlabel=dict(bgcolor=t["card"], font=dict(color=t["ink"], family=FONT_MONO),
                        bordercolor=t["hair"]),
    )
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=15, color=t["ink"],
                          family=FONT_DISPLAY), x=0.01, xanchor="left"))
    if not legend:
        fig.update_layout(showlegend=False)
    if height:
        fig.update_layout(height=height)
    # numeric / date ticks in mono for a forensic-ledger feel
    axis = dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["grid"],
                tickfont=dict(color=t["mute"], family=FONT_MONO, size=11),
                title_font=dict(color=t["mute"], family=FONT_SANS))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


# --------------------------------------------------------------------------- #
#  App CSS
# --------------------------------------------------------------------------- #
def app_css(t: dict) -> str:
    scan = "rgba(255,255,255,0.015)" if t["name"] == "night" else "rgba(15,23,42,0.02)"
    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

      :root {{
        --ink:{t['ink']}; --mute:{t['mute']}; --dim:{t['dim']};
        --card:{t['card']}; --card2:{t['card2']}; --border:{t['border']};
        --hair:{t['hair']}; --amber:{t['amber']}; --page:{t['page']};
        --green:{t['green']}; --red:{t['red']}; --blue:{t['blue']};
        --mono:{FONT_MONO}; --sans:{FONT_SANS}; --disp:{FONT_DISPLAY};
      }}
      /* canvas — deep navy + faint scanline texture (the terminal risk) */
      .stApp {{
        background:
          repeating-linear-gradient(0deg, {scan} 0 1px, transparent 1px 3px),
          radial-gradient(1200px 640px at 6% -10%, {t['page2']} 0%, transparent 55%),
          radial-gradient(900px 520px at 108% 0%, {t['page2']} 0%, transparent 50%),
          linear-gradient(168deg, {t['page2']} 0%, {t['page']} 62%);
      }}
      html, body, [class*="css"] {{ font-family:var(--sans); color:var(--ink); }}
      .block-container {{ padding-top:2.2rem; max-width:1500px; }}

      h1,h2,h3,h4,h5 {{ font-family:var(--disp) !important; color:var(--ink) !important;
        letter-spacing:-.01em; }}
      p, span, label, li, td, th, div {{ color:var(--ink); }}
      .mono, .num {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}

      /* sidebar */
      section[data-testid="stSidebar"] {{ background:{t['card2']};
        border-right:1px solid var(--border); }}
      section[data-testid="stSidebar"] * {{ color:var(--ink); }}

      /* section headers: intelligence-report kicker + accent tick */
      .stMarkdown h5 {{ position:relative; padding-left:14px; margin:.2rem 0 .5rem;
        font-size:15px !important; text-transform:none; letter-spacing:.01em; }}
      .stMarkdown h5::before {{ content:""; position:absolute; left:0; top:2px; bottom:2px;
        width:4px; border-radius:3px;
        background:linear-gradient(180deg,var(--amber),{t['blue']}); }}

      /* tabs — mono uppercase, amber active rail */
      .stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid var(--border); }}
      .stTabs [data-baseweb="tab"] {{ background:transparent; border:none;
        font-family:var(--mono); font-size:11.5px; letter-spacing:.06em;
        text-transform:uppercase; color:var(--mute); padding:8px 14px; }}
      .stTabs [aria-selected="true"] {{ color:var(--ink) !important;
        border-bottom:2px solid var(--amber); background:linear-gradient(180deg,transparent,{t['amber']}10); }}

      /* top brand rail */
      .brand {{ display:flex; align-items:center; gap:14px; padding:10px 16px;
        border:1px solid var(--border); border-radius:12px; margin-bottom:14px;
        background:linear-gradient(90deg,{t['card']},{t['card2']});
        border-left:4px solid var(--amber); }}
      .brand .logo {{ font-size:24px; }}
      .brand .name {{ font-family:var(--disp); font-weight:700; font-size:18px;
        letter-spacing:.02em; }}
      .brand .sub {{ font-family:var(--mono); font-size:11px; color:var(--mute);
        letter-spacing:.08em; text-transform:uppercase; }}
      .brand .spacer {{ flex:1; }}
      .brand .chip {{ font-family:var(--mono); font-size:10.5px; font-weight:600;
        letter-spacing:.1em; text-transform:uppercase; padding:5px 12px;
        border-radius:20px; background:{t['amber']}1c; color:var(--amber);
        border:1px solid {t['amber']}55; }}
      .brand .stat {{ font-family:var(--mono); font-size:11px; color:var(--mute);
        padding-left:14px; border-left:1px solid var(--border); }}
      .brand .stat b {{ color:var(--ink); }}

      /* generic card */
      .card {{ background:linear-gradient(180deg,var(--card),var(--card2));
        border:1px solid var(--border); border-radius:14px; padding:14px 16px;
        position:relative; margin-bottom:12px; }}
      .card::before {{ content:""; position:absolute; inset:0 0 auto 0; height:1px;
        background:linear-gradient(90deg,transparent,var(--hair),transparent); }}

      /* KPI tiles — mono value, status rail */
      .kpi {{ background:linear-gradient(180deg,var(--card),var(--card2));
        border:1px solid var(--border); border-radius:13px; padding:12px 14px 11px;
        position:relative; overflow:hidden; height:108px; }}
      .kpi::before {{ content:""; position:absolute; inset:0 0 auto 0; height:1px;
        background:linear-gradient(90deg,transparent,var(--hair),transparent); }}
      .kpi .lbl {{ font-family:var(--mono); font-size:10px; color:var(--mute);
        text-transform:uppercase; letter-spacing:.09em; }}
      .kpi .val {{ font-family:var(--mono); font-size:27px; font-weight:700;
        margin-top:6px; line-height:1.02; font-variant-numeric:tabular-nums; }}
      .kpi .sub {{ font-size:11px; color:var(--dim); margin-top:3px; }}
      .kpi .bar {{ position:absolute; left:0; top:0; bottom:0; width:4px; }}

      /* BLUF hero */
      .bluf {{ background:
          radial-gradient(600px 200px at 100% 0%, {t['amber']}12 0%, transparent 60%),
          linear-gradient(135deg,var(--card),var(--card2));
        border:1px solid var(--border); border-left:5px solid var(--amber);
        border-radius:16px; padding:18px 22px; margin-bottom:14px;
        box-shadow:0 10px 30px rgba(0,0,0,.28); }}
      .bluf h2 {{ margin:2px 0 8px 0; font-size:22px; letter-spacing:-.01em; }}
      .bluf .num {{ font-family:var(--mono); }}
      .bluf .tag {{ display:inline-block; font-family:var(--mono); font-size:10.5px;
        font-weight:600; letter-spacing:.14em; padding:4px 11px; border-radius:20px;
        background:{t['amber']}1c; color:var(--amber); border:1px solid {t['amber']}55; }}

      /* pills / badges */
      .pill {{ display:inline-block; padding:2px 10px; border-radius:20px;
        font-family:var(--mono); font-size:10.5px; font-weight:600; letter-spacing:.04em; }}
      .pill-High {{ background:{t['red']}22; color:{t['red']}; border:1px solid {t['red']}66; }}
      .pill-Medium {{ background:{t['amber']}22; color:{t['amber']}; border:1px solid {t['amber']}66; }}
      .pill-Low {{ background:{t['green']}22; color:{t['green']}; border:1px solid {t['green']}66; }}

      /* finding cards */
      .find {{ border:1px solid var(--border); border-left-width:5px; border-radius:11px;
        padding:11px 15px; margin-bottom:8px;
        background:linear-gradient(180deg,var(--card),var(--card2)); }}
      .find .ttl {{ font-family:var(--disp); font-size:15px; font-weight:600; }}
      .find .why {{ font-size:12.5px; color:var(--mute); margin-top:5px; line-height:1.45; }}

      .muted {{ color:var(--mute); font-size:12.5px; }}
      hr {{ border-color:var(--border); }}

      /* buttons */
      .stButton button, .stDownloadButton button, .stFormSubmitButton button {{
        border-radius:10px; font-weight:600; font-family:var(--sans);
        border:1px solid var(--border); }}
      .stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {{
        background:var(--amber); color:#0a0f1c; border:none; }}

      /* dataframe container */
      [data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius:10px; }}

      /* entrance animations — replay whenever a section renders */
      @media (prefers-reduced-motion: no-preference) {{
        @keyframes upfade {{ from {{ opacity:0; transform:translateY(12px) scale(.985); }}
          to {{ opacity:1; transform:none; }} }}
        @keyframes glowin {{ from {{ opacity:0; filter:blur(6px); }} to {{ opacity:1; filter:none; }} }}
        [data-testid="stPlotlyChart"] {{ animation:glowin .5s cubic-bezier(.16,1,.3,1) both; }}
        .card, .kpi, .find, .bluf, [data-testid="stDataFrame"],
        [data-testid="stMetric"] {{ animation:upfade .38s cubic-bezier(.16,1,.3,1) both; }}
        .kpi:nth-child(2) {{ animation-delay:.04s; }}
        .kpi:nth-child(3) {{ animation-delay:.08s; }}
        .kpi:nth-child(4) {{ animation-delay:.12s; }}
        .kpi:nth-child(5) {{ animation-delay:.16s; }}
      }}

      /* info icon */
      .infowrap {{ display:inline-flex; align-items:center; gap:8px; }}
      .infobtn {{ display:inline-flex; align-items:center; justify-content:center;
        width:20px; height:20px; border-radius:50%; font-size:12px; font-weight:700;
        background:{t['blue']}22; color:{t['blue']}; border:1px solid {t['blue']}66;
        cursor:help; }}

      /* POI top card (inline-editable look) */
      .poicard {{ display:flex; gap:16px; align-items:center;
        background:linear-gradient(135deg,var(--card),var(--card2));
        border:1px solid var(--border); border-radius:16px; padding:14px 18px; }}
      .poicard .avatar {{ width:74px; height:74px; border-radius:14px; flex:none;
        background:linear-gradient(150deg,{t['blue']}33,{t['card2']});
        border:1px solid var(--border); display:flex; align-items:center;
        justify-content:center; font-size:30px; overflow:hidden; }}
      .poicard .avatar img {{ width:100%; height:100%; object-fit:cover; }}
      .poicard .nm {{ font-family:var(--disp); font-weight:700; font-size:19px; }}
      .poi-field {{ font-size:12.5px; }}
      .poi-field .k {{ font-family:var(--mono); font-size:10px; color:var(--mute);
        text-transform:uppercase; letter-spacing:.08em; display:block; }}
      .poi-field .v {{ color:var(--ink); font-weight:600; }}

      /* nav (segmented) */
      [data-testid="stSegmentedControl"] button {{ font-family:var(--mono);
        text-transform:uppercase; letter-spacing:.05em; font-size:11.5px; }}

      /* scrollbars */
      ::-webkit-scrollbar {{ width:10px; height:10px; }}
      ::-webkit-scrollbar-thumb {{ background:{t['border']}; border-radius:8px; }}
      ::-webkit-scrollbar-track {{ background:transparent; }}
    </style>
    """
