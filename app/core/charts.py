"""
Interactive Plotly charts — all theme-aware (night/day) and export-ready.
Each returns a ``plotly.graph_objects.Figure``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .analytics import money
from .theme import apply_theme, SERIES


def _short(x):
    x = float(x)
    if abs(x) >= 1e6:
        return f"{x/1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"{x/1e3:.0f}K"
    return f"{x:.0f}"


# --------------------------------------------------------------------------- #
def method_donut(methods, t):
    labels = [m["method"].title() for m in methods]
    vals = [m["count"] for m in methods]
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=0.62,
        marker=dict(colors=SERIES(t), line=dict(color=t["card2"], width=2)),
        textinfo="label+percent", textfont=dict(color=t["ink"], size=12),
        hovertemplate="%{label}: %{value} txns (%{percent})<extra></extra>"))
    fig.update_layout(annotations=[dict(
        text=f"<b>{sum(vals)}</b><br>txns", showarrow=False,
        font=dict(size=20, color=t["ink"]))])
    return apply_theme(fig, t, height=300, legend=False)


def method_bar(methods, t):
    labels = [m["method"].title() for m in methods]
    fig = go.Figure(go.Bar(
        x=[m["amount"] for m in methods], y=labels, orientation="h",
        marker_color=SERIES(t)[:len(methods)],
        text=[money(m["amount"]) for m in methods], textposition="outside",
        hovertemplate="%{y}: %{text}<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return apply_theme(fig, t, height=300, legend=False)


def timeline(tl, spikes, t, lang="en"):
    x = [r["month"] for r in tl]
    lin = "الوارد" if lang == "ar" else "Inflow"
    lout = "الصادر" if lang == "ar" else "Outflow"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[r["inflow"] for r in tl], name=lin,
                             mode="lines+markers", line=dict(color=t["green"], width=3),
                             fill="tozeroy", fillcolor=_alpha(t["green"], .12),
                             hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=[r["outflow"] for r in tl], name=lout,
                             mode="lines+markers", line=dict(color=t["red"], width=3),
                             fill="tozeroy", fillcolor=_alpha(t["red"], .10),
                             hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>"))
    for m in spikes.get("inflow", []):
        r = next(z for z in tl if z["month"] == m)
        fig.add_annotation(x=m, y=r["inflow"], text="▲ spike", showarrow=False,
                           yshift=14, font=dict(color=t["green"], size=11))
    for m in spikes.get("outflow", []):
        r = next(z for z in tl if z["month"] == m)
        fig.add_annotation(x=m, y=r["outflow"], text="▲ spike", showarrow=False,
                           yshift=14, font=dict(color=t["red"], size=11))
    fig.update_yaxes(tickformat="~s")
    return apply_theme(fig, t, height=330)


def ranked_bar(entities, color_key, t, n=8):
    ents = entities[:n][::-1]
    color = t[color_key]
    icons = {"Company": "🏢", "Unknown": "❓", "POI": "🎯", "Person": "👤"}
    labels = [f'{icons.get(e["type"],"•")} {e["name"][:26]}' for e in ents]
    fig = go.Figure(go.Bar(
        x=[e["amount"] for e in ents], y=labels, orientation="h",
        marker_color=color, text=[money(e["amount"]) for e in ents],
        textposition="outside",
        customdata=[[e["count"], e["pct"]] for e in ents],
        hovertemplate="%{y}<br>%{text} · %{customdata[0]} txns · "
                      "%{customdata[1]:.1f}% of flow<extra></extra>"))
    return apply_theme(fig, t, height=max(280, 34 * len(ents)), legend=False)


def accounts_bar(accounts, t):
    labels = [a["account"] for a in accounts]
    fig = go.Figure()
    fig.add_bar(x=labels, y=[a["inflow"] for a in accounts], name="Inflow",
                marker_color=t["green"])
    fig.add_bar(x=labels, y=[a["outflow"] for a in accounts], name="Outflow",
                marker_color=t["red"])
    fig.update_layout(barmode="group")
    fig.update_yaxes(tickformat="~s")
    return apply_theme(fig, t, height=300)


def sankey(R, t, lang="en"):
    inc, out = R["inc"], R["out"]
    ar = lang == "ar"

    def groups(frame, col, other, n=5):
        s = frame[~frame.counterparty_type.isin(["POI", "Internal"])]\
            .groupby("cp_label").amount.sum().sort_values(ascending=False)
        top = list(s.head(n).items())
        if s.iloc[n:].sum() > 0:
            top.append((other, s.iloc[n:].sum()))
        return top

    left = groups(inc, "counterparty", "مصادر أخرى" if ar else "Other sources")
    right = groups(out, "counterparty", "وجهات أخرى" if ar else "Other destinations")
    hub = "حسابات الشخص" if ar else "MY ACCOUNTS"
    labels = [l[0] for l in left] + [hub] + [r[0] for r in right]
    idx = {name: i for i, name in enumerate(labels)}
    src, tgt, val, col = [], [], [], []
    for name, v in left:
        src.append(idx[name]); tgt.append(idx[hub]); val.append(v); col.append(_alpha(t["green"], .45))
    for name, v in right:
        src.append(idx[hub]); tgt.append(idx[name]); val.append(v); col.append(_alpha(t["red"], .40))
    node_col = [t["green"]] * len(left) + [t["blue"]] + [t["red"]] * len(right)
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, color=node_col, pad=16, thickness=16,
                  line=dict(color=t["card2"], width=1)),
        link=dict(source=src, target=tgt, value=val, color=col,
                  hovertemplate="%{source.label} → %{target.label}: "
                                "%{value:,.0f}<extra></extra>")))
    fig.update_traces(textfont=dict(color=t["ink"], size=12))
    return apply_theme(fig, t, height=360, legend=False)


def risk_gauge(score, band, t):
    from .theme import LEVEL_COLOR
    color = LEVEL_COLOR(t)[band]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number=dict(font=dict(size=40, color=color), suffix="/100"),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=t["mute"]),
            bar=dict(color=color, thickness=0.28),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            steps=[dict(range=[0, 33], color=_alpha(t["green"], .25)),
                   dict(range=[33, 66], color=_alpha(t["amber"], .25)),
                   dict(range=[66, 100], color=_alpha(t["red"], .25))],
            threshold=dict(line=dict(color=color, width=4), value=score))))
    return apply_theme(fig, t, height=250, legend=False)


def risk_components(components, t):
    from .theme import LEVEL_COLOR
    comp = sorted(components, key=lambda c: c["weight"])
    lc = LEVEL_COLOR(t)
    fig = go.Figure(go.Bar(
        x=[c["weight"] for c in comp], y=[c["title"] for c in comp],
        orientation="h", marker_color=[lc[c["level"]] for c in comp],
        text=[f'+{c["weight"]} ({c["level"]})' for c in comp], textposition="outside",
        hovertemplate="%{y}<br>+%{x} risk points<extra></extra>"))
    return apply_theme(fig, t, height=max(280, 30 * len(comp)), legend=False)


def entity_heatmap(df, t):
    piv = df.pivot_table(index="transaction_method", columns="month",
                         values="amount", aggfunc="sum", fill_value=0)
    piv = piv.reindex(sorted(piv.columns), axis=1)
    fig = go.Figure(go.Heatmap(
        z=piv.values, x=list(piv.columns), y=[m.title() for m in piv.index],
        colorscale=[[0, t["card2"]], [0.4, t["blue"]], [0.7, t["teal"]], [1, t["amber"]]],
        hovertemplate="%{y} · %{x}: %{z:,.0f}<extra></extra>", showscale=False))
    return apply_theme(fig, t, height=240, legend=False)


def type_split(df, t):
    inc = df[df.direction == "in"]
    grp = inc.groupby("counterparty_type").amount.sum()
    labels = list(grp.index); vals = list(grp.values)
    cmap = {"Company": t["teal"], "Unknown": t["unknown"], "POI": t["poi"],
            "Person": t["pink"], "Internal": t["blue"]}
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=0.6,
        marker=dict(colors=[cmap.get(l, t["blue"]) for l in labels]),
        textinfo="label+percent", textfont=dict(color=t["ink"])))
    fig.update_layout(annotations=[dict(text="Inflow<br>by source", showarrow=False,
                                        font=dict(size=13, color=t["mute"]))])
    return apply_theme(fig, t, height=300, legend=False)


def _alpha(hexc, a):
    hexc = hexc.lstrip("#")
    r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
    return f"rgba({r},{g},{b},{a})"
