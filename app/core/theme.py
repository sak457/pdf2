"""
Theme, palette and icon system for the AML Intelligence dashboard.

Two coordinated palettes (night / day) drive both the Streamlit chrome (via
injected CSS) and the Plotly figures (via ``apply_theme``), so a single toggle
restyles the whole application consistently.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
#  Icons — chosen to be self-explanatory to a non-technical reader
# --------------------------------------------------------------------------- #
IC = {
    "app": "🛡️",
    "bluf": "📌",
    "poi": "🪪",
    "photo": "🧑",
    "filters": "🎛️",
    "theme": "🌗",
    "evidence": "🔬",
    "export": "📤",
    "upload": "📥",
    # KPIs
    "txns": "🧮",
    "in": "🟢",
    "out": "🔴",
    "net": "💰",
    "accounts": "🏦",
    "senders": "👥",
    "beneficiaries": "🏢",
    "avg": "📊",
    "largest": "💠",
    "risk": "⚠️",
    "own": "🔁",
    # sections
    "overview": "📋",
    "flow": "💵",
    "timeline": "📈",
    "counterparties": "👤",
    "network": "🕸️",
    "typology": "🚨",
    "riskdash": "🎯",
    "transactions": "🧾",
    # methods
    "transfer": "💳",
    "withdrawal": "🏧",
    "cheque": "🧾",
    "cash": "💵",
    "card": "💳",
    # misc
    "up": "⬆️",
    "down": "⬇️",
    "search": "🔍",
    "company": "🏢",
    "person": "👤",
    "unknown": "❓",
}

METHOD_ICON = {
    "transfer": "💳", "withdrawal": "🏧", "cheque": "🧾",
    "cash": "💵", "card": "💳", "deposit": "🏦", "wire": "🌐",
}

TYPE_ICON = {"POI": "🎯", "Company": "🏢", "Unknown": "❓",
             "Person": "👤", "Internal": "🔁", "Account": "🏦"}

# --------------------------------------------------------------------------- #
#  Palettes
# --------------------------------------------------------------------------- #
NIGHT = {
    "name": "night",
    "page": "#081527",
    "page2": "#0b2244",
    "card": "#0f2645",
    "card2": "#0c1f3b",
    "border": "#22406e",
    "ink": "#e9f0fb",
    "mute": "#93a7c6",
    "dim": "#6981a6",
    "grid": "#1e3963",
    "green": "#34d399",
    "red": "#f87171",
    "blue": "#4b8bf5",
    "teal": "#2dd4bf",
    "amber": "#f5b23f",
    "violet": "#a78bfa",
    "pink": "#f472b6",
    "plotly_template": "plotly_dark",
    "poi": "#f5b23f",
    "account": "#4b8bf5",
    "company": "#2dd4bf",
    "unknown": "#8ea3c0",
}

DAY = {
    "name": "day",
    "page": "#eef2f8",
    "page2": "#e4ebf5",
    "card": "#ffffff",
    "card2": "#f5f8fc",
    "border": "#d3ddec",
    "ink": "#0f2140",
    "mute": "#51637f",
    "dim": "#7688a3",
    "grid": "#dbe4f0",
    "green": "#059669",
    "red": "#dc2626",
    "blue": "#2563eb",
    "teal": "#0d9488",
    "amber": "#d97706",
    "violet": "#7c3aed",
    "pink": "#db2777",
    "plotly_template": "plotly_white",
    "poi": "#d97706",
    "account": "#2563eb",
    "company": "#0d9488",
    "unknown": "#64748b",
}

SERIES = lambda t: [t["teal"], t["blue"], t["amber"], t["violet"],
                    t["pink"], t["green"], t["red"]]

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
        font=dict(family="Inter, Segoe UI, DejaVu Sans, sans-serif",
                  color=t["ink"], size=13),
        margin=dict(l=10, r=10, t=40 if title else 12, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=t["mute"])),
        colorway=SERIES(t),
        hoverlabel=dict(bgcolor=t["card"], font=dict(color=t["ink"]),
                        bordercolor=t["border"]),
    )
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=15, color=t["ink"]),
                                     x=0.01, xanchor="left"))
    if not legend:
        fig.update_layout(showlegend=False)
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(gridcolor=t["grid"], zerolinecolor=t["grid"],
                     linecolor=t["grid"], tickfont=dict(color=t["mute"]))
    fig.update_yaxes(gridcolor=t["grid"], zerolinecolor=t["grid"],
                     linecolor=t["grid"], tickfont=dict(color=t["mute"]))
    return fig


# --------------------------------------------------------------------------- #
#  App CSS
# --------------------------------------------------------------------------- #
def app_css(t: dict) -> str:
    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      .stApp {{ background:
          radial-gradient(1100px 600px at 8% -6%, {t['page2']} 0%, transparent 55%),
          linear-gradient(160deg, {t['page2']} 0%, {t['page']} 60%); }}
      html, body, [class*="css"] {{ font-family:'Inter',sans-serif; color:{t['ink']}; }}
      section[data-testid="stSidebar"] {{ background:{t['card2']}; border-right:1px solid {t['border']}; }}
      section[data-testid="stSidebar"] * {{ color:{t['ink']}; }}
      h1,h2,h3,h4,h5 {{ color:{t['ink']} !important; }}
      p, span, label, li, td, th {{ color:{t['ink']}; }}
      .stTabs [data-baseweb="tab-list"] {{ gap:4px; }}
      .stTabs [data-baseweb="tab"] {{
          background:{t['card']}; border:1px solid {t['border']};
          border-radius:9px 9px 0 0; padding:6px 14px; color:{t['mute']}; }}
      .stTabs [aria-selected="true"] {{ background:{t['card2']};
          color:{t['ink']} !important; border-bottom:2px solid {t['amber']}; }}

      .card {{ background:linear-gradient(180deg,{t['card']},{t['card2']});
          border:1px solid {t['border']}; border-radius:14px; padding:14px 16px;
          box-shadow:0 6px 22px rgba(0,0,0,.20); margin-bottom:12px; }}
      .kpi {{ background:linear-gradient(180deg,{t['card']},{t['card2']});
          border:1px solid {t['border']}; border-radius:12px; padding:12px 14px;
          position:relative; overflow:hidden; height:104px; }}
      .kpi .lbl {{ font-size:11px; color:{t['mute']}; text-transform:uppercase;
          letter-spacing:.04em; }}
      .kpi .val {{ font-size:26px; font-weight:800; margin-top:4px; line-height:1.05; }}
      .kpi .sub {{ font-size:11px; color:{t['dim']}; margin-top:2px; }}
      .kpi .bar {{ position:absolute; left:0; top:0; bottom:0; width:4px; }}

      .bluf {{ background:linear-gradient(135deg,{t['card']},{t['card2']});
          border:1px solid {t['border']}; border-left:6px solid {t['amber']};
          border-radius:14px; padding:16px 20px; margin-bottom:14px;
          box-shadow:0 8px 26px rgba(0,0,0,.22); }}
      .bluf h2 {{ margin:0 0 6px 0; font-size:18px; letter-spacing:.02em; }}
      .bluf .tag {{ display:inline-block; font-size:11px; font-weight:700;
          letter-spacing:.12em; padding:3px 10px; border-radius:20px;
          background:{t['amber']}22; color:{t['amber']}; border:1px solid {t['amber']}55; }}

      .pill {{ display:inline-block; padding:2px 10px; border-radius:20px;
          font-size:11px; font-weight:700; }}
      .pill-High {{ background:{t['red']}22; color:{t['red']}; border:1px solid {t['red']}66; }}
      .pill-Medium {{ background:{t['amber']}22; color:{t['amber']}; border:1px solid {t['amber']}66; }}
      .pill-Low {{ background:{t['green']}22; color:{t['green']}; border:1px solid {t['green']}66; }}

      .find {{ border:1px solid {t['border']}; border-left-width:5px;
          border-radius:10px; padding:10px 14px; margin-bottom:8px;
          background:{t['card2']}; }}
      .find .ttl {{ font-size:15px; font-weight:700; }}
      .find .why {{ font-size:12.5px; color:{t['mute']}; margin-top:4px; line-height:1.4; }}
      .prof {{ text-align:center; }}
      .prof .nm {{ font-size:17px; font-weight:800; margin-top:6px; }}
      .prof .meta {{ font-size:12px; color:{t['mute']}; }}
      .stDownloadButton button, .stButton button {{ border-radius:9px; font-weight:600; }}
      .muted {{ color:{t['mute']}; font-size:12.5px; }}
      hr {{ border-color:{t['border']}; }}
    </style>
    """
