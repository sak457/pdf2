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


def figure(df, entity_risk, annotations, t, highlight=None, height=560, focus=None, lang="en"):
    import plotly.graph_objects as go
    from .analytics import money
    from .theme import apply_theme

    H, vol, node_type = _build(df, entity_risk, annotations)
    pos = nx.spring_layout(H, k=1.25, seed=11, iterations=240)
    pos[POI] = (0, 0)

    tcolor = {"POI": t["poi"], "Account": t["account"],
              "Company": t["company"], "Unknown": t["unknown"], "Person": t["pink"]}
    kind_color = {"in": t["green"], "out": t["red"], "own": t["violet"],
                  "own_link": t["dim"]}

    # which nodes are connected to the focus node (for dimming)
    connected = None
    if focus and focus in H:
        connected = {focus} | set(H.predecessors(focus)) | set(H.successors(focus))

    def curve(p0, p1, bend=0.16, steps=16):
        (x0, y0), (x1, y1) = p0, p1
        mxp, myp = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = x1 - x0, y1 - y0
        cx, cy = mxp - dy * bend, myp + dx * bend  # control point off the midpoint
        xs, ys = [], []
        for i in range(steps + 1):
            s = i / steps
            xs.append((1 - s) ** 2 * x0 + 2 * (1 - s) * s * cx + s * s * x1)
            ys.append((1 - s) ** 2 * y0 + 2 * (1 - s) * s * cy + s * s * y1)
        return xs, ys

    # edges — gently curved, one trace per kind
    edge_traces = []
    for kind, col in kind_color.items():
        xs, ys = [], []
        for u, v, d in H.edges(data=True):
            if d["kind"] != kind:
                continue
            cx, cy = curve(pos[u], pos[v], 0 if kind == "own_link" else 0.16)
            xs += cx + [None]; ys += cy + [None]
        if xs:
            width = 1 if kind == "own_link" else 2.2
            op = 0.5 if kind != "own_link" else 0.25
            if connected and kind != "own_link":
                op = 0.5  # keep; dimming handled per-node below via layer
            _names = ({"in": "وارد", "out": "صادر", "own": "بين الحسابات", "own_link": "ملكية"}
                      if lang == "ar" else
                      {"in": "Incoming", "out": "Outgoing", "own": "Own-account", "own_link": "Ownership"})
            name = _names[kind]
            edge_traces.append(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color=col, width=width, shape="spline"),
                opacity=op, hoverinfo="skip", name=name,
                showlegend=kind != "own_link"))

    mx = max(vol.values()) if vol else 1
    nx_, ny, sizes, colors, texts, labels, lines, halo_x, halo_y, halo_s, halo_c, opac = \
        [], [], [], [], [], [], [], [], [], [], [], []
    for n in H.nodes:
        ann = annotations.get(n, {})
        disp = ann.get("display_name") or (n if n != POI else "POI (Subject)")
        size = 20 + 48 * (vol.get(n, 0) / mx)
        dim = connected is not None and n not in connected
        nx_.append(pos[n][0]); ny.append(pos[n][1]); sizes.append(size)
        col = tcolor.get(node_type[n], t["blue"])
        colors.append(col)
        opac.append(0.18 if dim else 1.0)
        # glow halo
        halo_x.append(pos[n][0]); halo_y.append(pos[n][1])
        halo_s.append(size * 2.1); halo_c.append(col)
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
        labels.append("" if dim else (disp if len(disp) <= 20 else disp[:18] + "…"))
        ring = t["red"] if er.get("band") == "High" else t["card2"]
        if (highlight and n in highlight) or (focus and n == focus):
            ring = t["amber"]
        lines.append(ring)

    halo_trace = go.Scatter(
        x=halo_x, y=halo_y, mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(size=halo_s, color=halo_c, opacity=0.14,
                    line=dict(width=0)), name="")
    node_trace = go.Scatter(
        x=nx_, y=ny, mode="markers+text", text=labels, textposition="bottom center",
        textfont=dict(color=t["ink"], size=10, family="Inter, sans-serif"),
        hovertext=texts, hoverinfo="text", customdata=list(H.nodes),
        marker=dict(size=sizes, color=colors, opacity=opac,
                    line=dict(color=lines, width=2.4)),
        showlegend=False, name="")

    fig = go.Figure(edge_traces + [halo_trace, node_trace])
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


def pyvis_html(df, entity_risk, annotations, t, height=640, lang="en") -> str:
    """Interactive vis.js graph (drag / zoom / hover / click-to-focus).

    Self-contained HTML (inline JS) suitable for st.components.v1.html. Clicking
    a node isolates it and its direct links; clicking empty space resets.
    """
    import json
    from pyvis.network import Network
    from .analytics import money

    H, vol, node_type = _build(df, entity_risk, annotations)
    ar = lang == "ar"
    net = Network(height=f"{height}px", width="100%", bgcolor=t["page"],
                  font_color=t["ink"], directed=True, cdn_resources="in_line")

    tcolor = {"POI": t["poi"], "Account": t["account"], "Company": t["company"],
              "Unknown": t["unknown"], "Person": t["pink"]}
    tlabel = ({"POI": "الشخص", "Account": "حساب", "Company": "شركة",
               "Unknown": "غير معروف", "Person": "فرد", "Internal": "داخلي"} if ar else
              {k: k for k in ["POI", "Account", "Company", "Unknown", "Person", "Internal"]})
    mx = max(vol.values()) if vol else 1

    for n in H.nodes:
        ann = annotations.get(n, {})
        disp = ann.get("display_name") or (n if n != POI else ("الشخص محل الاهتمام" if ar else "POI (Subject)"))
        nt = node_type[n]
        size = 16 + 40 * (vol.get(n, 0) / mx)
        er = entity_risk.get(n, {})
        tip = [disp, f"{tlabel.get(nt, nt)}"]
        if vol.get(n):
            tip.append((("الحجم: " if ar else "Volume: ") + money(vol[n])))
        if er:
            tip.append((("المخاطر: " if ar else "Risk: ") + f"{er['score']}/100 ({er['band']})"))
        if ann.get("doc_id"):
            tip.append(("رقم: " if ar else "Doc ID: ") + str(ann["doc_id"]))
        if ann.get("notes"):
            tip.append(("ملاحظة: " if ar else "Note: ") + str(ann["notes"])[:80])
        col = tcolor.get(nt, t["blue"])
        border = t["red"] if er.get("band") == "High" else t["hair"]
        kw = dict(label=disp, title="\n".join(tip), size=size,
                  color={"background": col, "border": border,
                         "highlight": {"background": col, "border": t["amber"]}},
                  borderWidth=2, borderWidthSelected=4,
                  shadow={"enabled": True, "color": col, "size": 22, "x": 0, "y": 0},
                  font={"color": t["ink"], "size": 15, "face": "Inter",
                        "strokeWidth": 3, "strokeColor": t["page"]})
        if n == POI:
            kw.update(shape="star", size=max(size, 34), color={"background": t["poi"],
                      "border": t["amber"], "highlight": {"background": t["poi"], "border": "#fff"}})
        elif ann.get("photo"):
            kw.update(shape="circularImage", image=ann["photo"], brokenImage="")
        else:
            kw.update(shape="dot")
        net.add_node(n, **kw)

    kind_color = {"in": t["green"], "out": t["red"], "own": t["violet"], "own_link": t["dim"]}
    kind_label = ({"in": "وارد", "out": "صادر", "own": "بين الحسابات", "own_link": "ملكية"} if ar
                  else {"in": "Incoming", "out": "Outgoing", "own": "Own-account", "own_link": "Ownership"})
    for u, v, d in H.edges(data=True):
        kind = d["kind"]
        if kind == "own_link":
            net.add_edge(u, v, color={"color": t["dim"], "opacity": 0.35}, width=1,
                         dashes=True, arrows="", title=kind_label[kind],
                         smooth={"type": "cubicBezier"})
        else:
            w = 1.5 + 5 * (d["w"] / mx)
            net.add_edge(u, v, color={"color": kind_color[kind], "highlight": t["amber"]},
                         width=w, title=f"{kind_label[kind]}: {money(d['w'])} · {d['n']}",
                         arrows={"to": {"enabled": True, "scaleFactor": 0.6}},
                         smooth={"type": "curvedCW", "roundness": 0.15})

    net.set_options(json.dumps({
        "interaction": {"hover": True, "dragNodes": True, "dragView": True,
                        "zoomView": True, "navigationButtons": True, "keyboard": False,
                        "tooltipDelay": 90, "hideEdgesOnDrag": True},
        "physics": {"solver": "barnesHut",
                    "barnesHut": {"gravitationalConstant": -20000, "centralGravity": 0.28,
                                  "springLength": 130, "springConstant": 0.045,
                                  "damping": 0.55, "avoidOverlap": 0.7},
                    "stabilization": {"enabled": True, "iterations": 220},
                    "minVelocity": 0.6},
        "nodes": {"scaling": {"min": 12, "max": 60}},
        "edges": {"shadow": False, "hoverWidth": 1.4, "selectionWidth": 2},
    }))

    html = net.generate_html()

    # inject click-to-focus (dim non-neighbours) + fit-on-stabilized
    focus_js = """
    <script type="text/javascript">
    (function(){
      function attach(){
        if (typeof network === 'undefined' || !network || typeof nodes === 'undefined') {
          return setTimeout(attach, 120);
        }
        var ORIG = {}; var snap = nodes.get({returnType:'Object'});
        for (var id in snap){ ORIG[id] = JSON.parse(JSON.stringify(snap[id].color || null)); }
        network.on('stabilizationIterationsDone', function(){ network.fit({animation:true}); });
        network.on('click', function(p){
          var cur = nodes.get({returnType:'Object'}); var upd = [];
          if (p.nodes.length){
            var sel = p.nodes[0]; var con = network.getConnectedNodes(sel); con.push(sel);
            for (var id in cur){
              var dim = con.indexOf(id) === -1;
              cur[id].color = dim ? {background:'rgba(130,142,165,0.10)', border:'rgba(130,142,165,0.15)'} : ORIG[id];
              cur[id].opacity = dim ? 0.35 : 1.0;
              upd.push(cur[id]);
            }
          } else {
            for (var id in cur){ cur[id].color = ORIG[id]; cur[id].opacity = 1.0; upd.push(cur[id]); }
          }
          nodes.update(upd);
        });
      }
      attach();
    })();
    </script>
    """
    return html.replace("</body>", focus_js + "</body>")


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
