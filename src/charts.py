"""
Chart factory.

Every function returns a ``data:image/png;base64,...`` URI so the HTML template
can embed the visual inline (no external files, fully self-contained PDF).
All charts share one dark "intelligence dashboard" theme.
"""

from __future__ import annotations

import base64
import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from matplotlib.patches import FancyArrowPatch, PathPatch, Rectangle
from matplotlib.path import Path

import networkx as nx

# --------------------------------------------------------------------------- #
#  Theme
# --------------------------------------------------------------------------- #
INK = "#e6edf7"          # primary light text
MUTE = "#8ea3c0"         # muted labels
GRID = "#2a3f63"
CARD = "#132a4f"
GREEN = "#34d399"        # incoming
RED = "#f87171"          # outgoing
BLUE = "#3b82f6"
TEAL = "#2dd4bf"
AMBER = "#f59e0b"
VIOLET = "#a78bfa"
PINK = "#f472b6"
SLATE = "#64748b"

SERIES = [TEAL, BLUE, AMBER, VIOLET, PINK, GREEN, RED, "#38bdf8", "#fb923c", "#4ade80"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": MUTE,
    "ytick.color": MUTE,
    "axes.edgecolor": GRID,
    "figure.dpi": 130,
})


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True,
                bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def _style(ax):
    ax.set_facecolor("none")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    return ax


def _short(x):
    x = float(x)
    if abs(x) >= 1e6:
        return f"{x/1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"{x/1e3:.0f}K"
    return f"{x:.0f}"


# --------------------------------------------------------------------------- #
#  1. Transaction-method donut
# --------------------------------------------------------------------------- #
def method_donut(methods) -> str:
    fig, ax = plt.subplots(figsize=(2.5, 2.5))
    vals = [m["count"] for m in methods]
    cols = [TEAL, AMBER, VIOLET, BLUE][:len(vals)]
    ax.pie(vals, colors=cols, startangle=90,
           wedgeprops=dict(width=0.40, edgecolor="#0b1c38", linewidth=2.4))
    total = sum(vals)
    ax.text(0, 0.10, f"{total}", ha="center", va="center",
            fontsize=30, fontweight="bold", color=INK)
    ax.text(0, -0.26, "TXNS", ha="center", va="center", fontsize=11,
            color=MUTE, fontweight="bold")
    ax.set_aspect("equal")
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  2. Person vs Company split (inflow value) donut
# --------------------------------------------------------------------------- #
def type_split_donut(df) -> str:
    inc = df[df.Direction == "IN"]
    p = inc[inc.Sender_Type == "Person"]["Amount"].sum()
    c = inc[inc.Sender_Type == "Company"]["Amount"].sum()
    fig, ax = plt.subplots(figsize=(3.1, 2.5))
    vals = [c, p]
    cols = [BLUE, PINK]
    wedges, _ = ax.pie(vals, colors=cols, startangle=90,
                       wedgeprops=dict(width=0.42, edgecolor="#0b1c38", linewidth=2))
    ax.text(0, 0.12, _short(c + p), ha="center", va="center",
            fontsize=17, fontweight="bold", color=INK)
    ax.text(0, -0.22, "INFLOW", ha="center", va="center", fontsize=9, color=MUTE)
    ax.legend(wedges, [f"Company  {_short(c)}", f"Person  {_short(p)}"],
              loc="center", bbox_to_anchor=(0.5, -0.13), frameon=False,
              fontsize=9, labelcolor=INK, handlelength=1, handleheight=1)
    ax.set_aspect("equal")
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  3+4. Horizontal ranked bars (senders / beneficiaries)
# --------------------------------------------------------------------------- #
def ranked_bar(entities, color, title_in=False, n=6) -> str:
    ents = entities[:n][::-1]
    fig, ax = plt.subplots(figsize=(5.2, 2.05))
    _style(ax)
    names = [e["name"] if len(e["name"]) <= 22 else e["name"][:20] + "…" for e in ents]
    vals = [e["amount"] for e in ents]
    icons = ["[Co]" if e["type"] == "Company" else "[Ind]" for e in ents]
    ypos = np.arange(len(ents))
    bars = ax.barh(ypos, vals, color=color, height=0.62, edgecolor="none")
    ax.set_yticks(ypos)
    ax.set_yticklabels([f"{nm}" for nm in names], fontsize=9.5)
    ax.set_xticks([])
    mx = max(vals) if vals else 1
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + mx * 0.02, b.get_y() + b.get_height() / 2,
                _short(v), va="center", ha="left", fontsize=9, color=INK,
                fontweight="bold")
    ax.set_xlim(0, mx * 1.22)
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  5. Monthly timeline (in vs out) with spike markers
# --------------------------------------------------------------------------- #
def timeline(tl, spikes) -> str:
    fig, ax = plt.subplots(figsize=(9.6, 2.05))
    _style(ax)
    months = [t["month"][2:] for t in tl]  # YY-MM
    xin = [t["in"] for t in tl]
    xout = [t["out"] for t in tl]
    x = np.arange(len(tl))
    ax.fill_between(x, xin, color=GREEN, alpha=0.16)
    ax.fill_between(x, xout, color=RED, alpha=0.12)
    ax.plot(x, xin, color=GREEN, lw=2.4, marker="o", ms=4, label="Incoming")
    ax.plot(x, xout, color=RED, lw=2.4, marker="o", ms=4, label="Outgoing")
    # spike annotations
    for i, t in enumerate(tl):
        if t["month"] in spikes.get("in", []):
            ax.annotate("spike", (x[i], t["in"]), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8, color=GREEN,
                        fontweight="bold")
        if t["month"] in spikes.get("out", []):
            ax.annotate("spike", (x[i], t["out"]), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8, color=RED,
                        fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(months, fontsize=8.5, rotation=0)
    ax.grid(axis="y", color=GRID, lw=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _short(v)))
    ax.tick_params(labelsize=8.5)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False,
              fontsize=9, labelcolor=INK, ncol=2, handlelength=1.6,
              columnspacing=2.2)
    fig.subplots_adjust(top=0.86)
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  6. Per-account grouped bars (in / out)
# --------------------------------------------------------------------------- #
def accounts_bar(accounts) -> str:
    fig, ax = plt.subplots(figsize=(4.5, 2.6))
    _style(ax)
    labels = [a["account"].replace("AC-", "") for a in accounts]
    ins = [a["in"] for a in accounts]
    outs = [a["out"] for a in accounts]
    x = np.arange(len(accounts))
    w = 0.38
    ax.bar(x - w / 2, ins, w, color=GREEN, label="In")
    ax.bar(x + w / 2, outs, w, color=RED, label="Out")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.grid(axis="y", color=GRID, lw=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _short(v)))
    ax.tick_params(labelsize=8.5)
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=INK, ncol=2)
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  7. Heat map — month x method (value intensity)
# --------------------------------------------------------------------------- #
def heatmap(df) -> str:
    piv = df.pivot_table(index="Transaction_Method", columns="Month",
                         values="Amount", aggfunc="sum", fill_value=0)
    piv = piv.reindex(sorted(piv.columns), axis=1)
    fig, ax = plt.subplots(figsize=(9.6, 1.9))
    data = piv.values
    norm = data / (data.max() or 1)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "aml", ["#0e2244", "#1d4e89", TEAL, AMBER])
    ax.imshow(norm, aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels([c[2:] for c in piv.columns], fontsize=8, rotation=0)
    ax.set_yticks(range(len(piv.index)))
    ax.set_yticklabels(piv.index, fontsize=9)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if norm[i, j] > 0.04:
                ax.text(j, i, _short(data[i, j]), ha="center", va="center",
                        fontsize=6.5,
                        color="#0b1c38" if norm[i, j] > 0.55 else INK)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  8. Risk matrix (likelihood x impact)
# --------------------------------------------------------------------------- #
_LEVEL_IMPACT = {"High": 2.6, "Medium": 1.7, "Low": 0.9}
_CONF_LIK = {"High": 2.6, "Medium": 1.7, "Low": 0.9}


def risk_matrix(findings) -> str:
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.set_facecolor("none")
    # quadrant background
    ax.imshow([[0, 1], [1, 2]], extent=(0, 3, 0, 3), origin="lower",
              cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
                  "rm", ["#12351f", "#5c4a12", "#5c1a1a"]),
              alpha=0.35, aspect="auto", interpolation="bilinear")
    jitter = np.linspace(-0.16, 0.16, len(findings))
    for i, f in enumerate(findings):
        x = _CONF_LIK.get(f["confidence"], 1.5) + jitter[i]
        y = _LEVEL_IMPACT.get(f["level"], 1.5) + jitter[i]
        col = RED if f["level"] == "High" else AMBER if f["level"] == "Medium" else GREEN
        ax.scatter(x, y, s=340, color=col, alpha=0.9, edgecolor="#0b1c38",
                   linewidth=1.2, zorder=3)
        ax.text(x, y, str(i + 1), ha="center", va="center", fontsize=8.5,
                fontweight="bold", color="#0b1c38", zorder=4)
    ax.set_xlim(0, 3.3)
    ax.set_ylim(0, 3.3)
    ax.set_xticks([0.9, 1.7, 2.6])
    ax.set_xticklabels(["Low", "Med", "High"], fontsize=8.5)
    ax.set_yticks([0.9, 1.7, 2.6])
    ax.set_yticklabels(["Low", "Med", "High"], fontsize=8.5)
    ax.set_xlabel("Confidence / Likelihood", fontsize=9, color=MUTE)
    ax.set_ylabel("Severity / Impact", fontsize=9, color=MUTE)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(length=0)
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  9. Sankey-style money-flow ribbons: sources -> accounts -> destinations
# --------------------------------------------------------------------------- #
def _ribbon(ax, x0, y0, x1, y1, h0, h1, color, alpha=0.5):
    verts = [
        (x0, y0), (x0 + (x1 - x0) * 0.5, y0), (x0 + (x1 - x0) * 0.5, y1), (x1, y1),
        (x1, y1 + h1), (x0 + (x1 - x0) * 0.5, y1 + h1),
        (x0 + (x1 - x0) * 0.5, y0 + h0), (x0, y0 + h0), (x0, y0),
    ]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
             Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color,
                           edgecolor="none", alpha=alpha))


def sankey(results) -> str:
    df = results["df"]
    inc = df[df.Direction == "IN"]
    out = df[df.Direction == "OUT"]
    # left nodes: top 4 sender groups + "Other"; right: top 4 beneficiary + other
    def top_groups(frame, col, other_label, n=4):
        s = frame.groupby(col)["Amount"].sum().sort_values(ascending=False)
        top = s.head(n)
        other = s.iloc[n:].sum()
        d = list(top.items())
        if other > 0:
            d.append((other_label, other))
        return d

    left = top_groups(inc[inc.Sender != "Me"], "Sender", "Other sources")
    right = top_groups(out[out.Beneficiary != "Me"], "Beneficiary", "Other dest.")
    total_in = sum(v for _, v in left) or 1
    total_out = sum(v for _, v in right) or 1

    fig, ax = plt.subplots(figsize=(9.6, 2.95))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    gap = 0.28
    top, bot = 9.7, 0.3
    span = top - bot
    # center hub sized to the larger side so both fans fit
    hub_h = span
    hub_y = bot
    ax.add_patch(Rectangle((4.6, hub_y), 0.8, hub_h, color=BLUE, zorder=3,
                           joinstyle="round"))
    ax.text(5.0, hub_y + hub_h / 2, "MY\nACCOUNTS", ha="center", va="center",
            fontsize=9, fontweight="bold", color="white", zorder=4)

    # left column: sources -> hub (fan into hub from the top down)
    scale_l = (span - gap * (len(left) - 1)) / total_in
    y = top
    hub_y_cursor = top
    for name, val in left:
        h = val * scale_l
        y -= h
        ax.add_patch(Rectangle((1.4, y), 0.55, h, color=GREEN, zorder=3))
        ax.text(1.32, y + h / 2, f"{name[:18]}", ha="right", va="center",
                fontsize=8, color=INK)
        _ribbon(ax, 1.95, y, 4.6, hub_y_cursor - h, h, h, GREEN, 0.30)
        hub_y_cursor -= h
        y -= gap
    # right column: hub -> destinations
    scale_r = (span - gap * (len(right) - 1)) / total_out
    y = top
    hub_y_cursor = top
    for name, val in right:
        h = val * scale_r
        y -= h
        ax.add_patch(Rectangle((8.05, y), 0.55, h, color=RED, zorder=3))
        ax.text(8.72, y + h / 2, f"{name[:18]}", ha="left", va="center",
                fontsize=8, color=INK)
        _ribbon(ax, 5.4, hub_y_cursor - h, 8.05, y, h, h, RED, 0.26)
        hub_y_cursor -= h
        y -= gap
    ax.text(1.9, 9.95, "SOURCES  ▼", fontsize=9, color=GREEN, fontweight="bold",
            ha="center")
    ax.text(8.3, 9.95, "▼  DESTINATIONS", fontsize=9, color=RED,
            fontweight="bold", ha="center")
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  10. Network graph
# --------------------------------------------------------------------------- #
def network(results, entity_risk) -> str:
    df = results["df"]
    G = nx.DiGraph()
    vol = {}
    for _, r in df.iterrows():
        s, b = r["Sender"], r["Beneficiary"]
        vol[s] = vol.get(s, 0) + r["Amount"]
        vol[b] = vol.get(b, 0) + r["Amount"]
        if G.has_edge(s, b):
            G[s][b]["w"] += r["Amount"]
        else:
            G.add_edge(s, b, w=r["Amount"], dir=r["Direction"])

    # keep top-connected nodes to avoid clutter
    deg = dict(G.degree(weight="w"))
    keep = {n for n, _ in sorted(deg.items(), key=lambda kv: kv[1],
                                 reverse=True)[:20]}
    keep.add("Me")
    keep |= set(df["Account_No"].unique())
    H = G.subgraph(keep).copy()

    # node classes
    accounts = set(df["Account_No"].unique())
    comp = set(df.loc[df.Sender_Type == "Company", "Sender"]) | \
        set(df.loc[df.Beneficiary_Type == "Company", "Beneficiary"])
    node_color, node_size, edgecol = [], [], []
    for n in H.nodes():
        if n == "Me":
            node_color.append(AMBER);
        elif n in accounts:
            node_color.append(BLUE)
        elif n in comp:
            node_color.append(TEAL)
        else:
            node_color.append(PINK)
        node_size.append(220 + 900 * (vol.get(n, 0) / (max(vol.values()) or 1)))
        # high-risk highlight ring
        er = entity_risk.get(n, {}).get("band")
        edgecol.append(RED if er == "High" else "#0b1c38")

    pos = nx.spring_layout(H, k=1.15, seed=7, iterations=160)
    fig, ax = plt.subplots(figsize=(7.8, 4.05))
    ax.axis("off")
    for u, v, d in H.edges(data=True):
        col = GREEN if d.get("dir") == "IN" else RED
        ax.annotate("", xy=pos[v], xytext=pos[u],
                    arrowprops=dict(arrowstyle="-|>", color=col, alpha=0.35,
                                    lw=0.5 + 2.2 * (d["w"] / (max(vol.values()) or 1)),
                                    shrinkA=8, shrinkB=8,
                                    connectionstyle="arc3,rad=0.08"))
    nx.draw_networkx_nodes(H, pos, node_color=node_color, node_size=node_size,
                           edgecolors=edgecol, linewidths=1.6, ax=ax)
    labels = {n: (n if len(n) <= 16 else n[:14] + "…") for n in H.nodes()}
    nx.draw_networkx_labels(H, pos, labels, font_size=7, font_color=INK, ax=ax)
    # legend
    from matplotlib.lines import Line2D
    leg = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=AMBER,
               markersize=10, label="Me"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE,
               markersize=10, label="Account"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TEAL,
               markersize=10, label="Company"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=PINK,
               markersize=10, label="Individual"),
        Line2D([0], [0], color=GREEN, lw=2.5, label="Incoming"),
        Line2D([0], [0], color=RED, lw=2.5, label="Outgoing"),
    ]
    ax.legend(handles=leg, loc="lower center", ncol=6, frameon=False,
              fontsize=8.5, labelcolor=INK, bbox_to_anchor=(0.5, -0.04))
    return _b64(fig)


# --------------------------------------------------------------------------- #
#  Build everything
# --------------------------------------------------------------------------- #
def build_all(results) -> dict:
    df = results["df"]
    return {
        "method_donut": method_donut(results["methods"]),
        "type_split": type_split_donut(df),
        "senders_bar": ranked_bar(results["senders"], GREEN),
        "beneficiaries_bar": ranked_bar(results["beneficiaries"], RED),
        "timeline": timeline(results["timeline"], results["timeline_spikes"]),
        "accounts_bar": accounts_bar(results["accounts"]),
        "heatmap": heatmap(df),
        "risk_matrix": risk_matrix(results["findings"]),
        "sankey": sankey(results),
        "network": network(results, results["entity_risk"]),
    }
