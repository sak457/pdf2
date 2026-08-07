"""
Link-analysis network.

Nodes  : the POI (subject), each POI account, and every counterparty
         (company / unknown).  Node size ∝ transaction volume.
Edges  : inbound (green, counterparty→account), outbound (red, account→
         counterparty), own-account (blue, account↔account), plus thin
         ownership links (account→POI).
Extras : per-node annotations (display name, doc id, photo, notes) supplied
         from the UI are merged into labels / hover / photo overlays, and any
         two nodes can be inspected for the transactions that connect them.
"""

from __future__ import annotations

import networkx as nx
import pandas as pd

from .theme import TYPE_ICON


POI = "POI"


def node_universe(df: pd.DataFrame) -> list[str]:
    accts = sorted(set(a for row in df.accounts for a in row))
    cps = sorted(df.loc[~df.counterparty_type.isin(["POI", "Internal"]),
                        "counterparty"].unique().tolist())
    return [POI] + accts + cps


def _build(df, entity_risk, annotations, max_nodes=30):
    accts = set(a for row in df.accounts for a in row)
    G = nx.DiGraph()
    vol = {}

    def bump(n, amt):
        vol[n] = vol.get(n, 0) + amt

    for _, r in df.iterrows():
        amt = r["amount"]
        if r["direction"] == "own":
            a = r["account_from"]; b = r["account_to"]
            if a and b and a != b:
                _edge(G, a, b, amt, "own")
                bump(a, amt); bump(b, amt)
        elif r["direction"] == "in":
            cp = r["counterparty"]; acc = r["account_from"]
            _edge(G, cp, acc, amt, "in"); bump(cp, amt); bump(acc, amt)
        else:  # out
            cp = r["counterparty"]; acc = r["account_from"]
            _edge(G, acc, cp, amt, "out"); bump(acc, amt); bump(cp, amt)

    # ownership links account -> POI
    for a in accts:
        _edge(G, a, POI, 0, "own_link")
        bump(POI, vol.get(a, 0))

    # prune to top nodes (keep POI, accounts, annotated)
    keep = {POI} | accts | set(annotations.keys())
    ranked = sorted(vol.items(), key=lambda kv: kv[1], reverse=True)
    for n, _ in ranked:
        if len(keep) >= max_nodes:
            break
        keep.add(n)
    H = G.subgraph([n for n in G.nodes if n in keep]).copy()

    node_type = {}
    for n in H.nodes:
        if n == POI:
            node_type[n] = "POI"
        elif n in accts:
            node_type[n] = "Account"
        else:
            row = df[df.counterparty == n]
            node_type[n] = row.counterparty_type.iat[0] if len(row) else "Company"
    return H, vol, node_type


def _edge(G, u, v, amt, kind):
    if G.has_edge(u, v):
        G[u][v]["w"] += amt
        G[u][v]["n"] += 1
    else:
        G.add_edge(u, v, w=amt, n=1, kind=kind)


def figure(df, entity_risk, annotations, t, highlight=None, height=560):
    import plotly.graph_objects as go
    from .analytics import money
    from .theme import apply_theme

    H, vol, node_type = _build(df, entity_risk, annotations)
    pos = nx.spring_layout(H, k=1.1, seed=11, iterations=200)
    pos[POI] = (0, 0)

    tcolor = {"POI": t["poi"], "Account": t["account"],
              "Company": t["company"], "Unknown": t["unknown"], "Person": t["pink"]}
    kind_color = {"in": t["green"], "out": t["red"], "own": t["violet"],
                  "own_link": t["dim"]}

    # edges (one trace per kind for legend clarity)
    edge_traces = []
    for kind, col in kind_color.items():
        xs, ys = [], []
        for u, v, d in H.edges(data=True):
            if d["kind"] != kind:
                continue
            xs += [pos[u][0], pos[v][0], None]
            ys += [pos[u][1], pos[v][1], None]
        if xs:
            width = 1 if kind == "own_link" else 2
            name = {"in": "Incoming", "out": "Outgoing", "own": "Own-account",
                    "own_link": "Ownership"}[kind]
            edge_traces.append(go.Scatter(
                x=xs, y=ys, mode="lines", line=dict(color=col, width=width),
                opacity=0.45 if kind != "own_link" else 0.3, hoverinfo="skip",
                name=name, showlegend=kind != "own_link"))

    mx = max(vol.values()) if vol else 1
    nx_, ny, sizes, colors, texts, labels, lines = [], [], [], [], [], [], []
    for n in H.nodes:
        ann = annotations.get(n, {})
        disp = ann.get("display_name") or (n if n != POI else "POI (Subject)")
        nx_.append(pos[n][0]); ny.append(pos[n][1])
        sizes.append(18 + 46 * (vol.get(n, 0) / mx))
        colors.append(tcolor.get(node_type[n], t["blue"]))
        er = entity_risk.get(n, {})
        hover = [f"<b>{disp}</b>", f"{TYPE_ICON.get(node_type[n],'')} {node_type[n]}"]
        if vol.get(n):
            hover.append(f"Volume: {money(vol[n])}")
        if er:
            hover.append(f"Risk: {er['score']}/100 ({er['band']})")
        if ann.get("doc_id"):
            hover.append(f"Doc ID: {ann['doc_id']}")
        if ann.get("notes"):
            hover.append(f"Note: {ann['notes'][:80]}")
        texts.append("<br>".join(hover))
        labels.append(disp if len(disp) <= 20 else disp[:18] + "…")
        # ring: red if high risk or highlighted
        ring = t["red"] if er.get("band") == "High" else t["card2"]
        if highlight and n in highlight:
            ring = t["amber"]
        lines.append(ring)

    node_trace = go.Scatter(
        x=nx_, y=ny, mode="markers+text", text=labels, textposition="bottom center",
        textfont=dict(color=t["ink"], size=10), hovertext=texts, hoverinfo="text",
        marker=dict(size=sizes, color=colors, line=dict(color=lines, width=2.4)),
        showlegend=False, name="")

    fig = go.Figure(edge_traces + [node_trace])
    # photo overlays for annotated nodes
    images = []
    for n in H.nodes:
        ann = annotations.get(n, {})
        if ann.get("photo"):
            images.append(dict(source=ann["photo"], xref="x", yref="y",
                               x=pos[n][0], y=pos[n][1], sizex=0.16, sizey=0.16,
                               xanchor="center", yanchor="middle", layer="above"))
    fig.update_layout(images=images,
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      legend=dict(orientation="h", y=1.02))
    fig = apply_theme(fig, t, height=height)
    fig.update_xaxes(visible=False, showgrid=False)
    fig.update_yaxes(visible=False, showgrid=False)
    return fig


def edge_transactions(df: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    """Transactions connecting two selected nodes (accounts / POI / counterparty)."""
    accts = set(x for row in df.accounts for x in row)
    cols = ["date", "direction", "account_no", "counterparty", "counterparty_type",
            "amount", "transaction_method"]
    A, B = {a, b}, None
    is_acc = lambda x: x in accts

    if is_acc(a) and is_acc(b):
        m = df.direction.eq("own") & df.accounts.apply(lambda l: {a, b} <= set(l))
    elif POI in (a, b) and (is_acc(a) or is_acc(b)):
        acc = a if is_acc(a) else b
        m = df.accounts.apply(lambda l: acc in l)
    elif POI in (a, b):  # POI <-> counterparty
        cp = a if a != POI else b
        m = df.counterparty.eq(cp)
    else:  # account <-> counterparty
        acc = a if is_acc(a) else b
        cp = b if is_acc(a) else a
        m = df.accounts.apply(lambda l: acc in l) & df.counterparty.eq(cp)
    return df[m][cols].sort_values("date")
