"""
AML / Financial-Intelligence interactive dashboard (Streamlit).

    streamlit run app/app.py

Upload a POI transaction CSV (or load the sample), slice it with the filters,
read the auto BLUF, drill into every chart's evidence, edit the POI and network
nodes, inspect transactions between any two entities, and export a customised,
high-quality PDF for a decision-maker.
"""

from __future__ import annotations

import base64
import io
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import loader, analytics, charts, network, pdfexport
from core.theme import theme, app_css, IC, TYPE_ICON

st.set_page_config(page_title="AML Intelligence Dashboard", page_icon="🛡️",
                   layout="wide", initial_sidebar_state="expanded")

PLOTLY_CFG = {"displaylogo": False,
              "toImageButtonOptions": {"scale": 3, "format": "png"},
              "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


# --------------------------------------------------------------------------- #
#  Session defaults
# --------------------------------------------------------------------------- #
def _init():
    ss = st.session_state
    ss.setdefault("theme", "night")
    ss.setdefault("poi", dict(name="«POI FULL NAME»", nationality="«NATIONALITY»",
                              doc_id="«DOC / CUSTOMER ID»", photo=None,
                              extra="", primary_account=""))
    ss.setdefault("nodes", {})           # node_name -> annotation dict
    ss.setdefault("analyst_note", "")
    ss.setdefault("bluf_override", "")
    ss.setdefault("df", None)
    ss.setdefault("data_name", "")


_init()
ss = st.session_state
t = theme(ss.theme)
st.markdown(app_css(t), unsafe_allow_html=True)


def data_uri(raw: bytes, mime="image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def kpi(col, icon, label, value, sub, color):
    col.markdown(
        f'<div class="kpi"><div class="bar" style="background:{color}"></div>'
        f'<div class="lbl">{icon} {label}</div>'
        f'<div class="val" style="color:{color}">{value}</div>'
        f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def evidence(label, explanation, df=None, basis=None, key=None):
    with st.popover(f"{IC['evidence']} {label}", use_container_width=False):
        st.markdown(f"**Why / what this shows**\n\n{explanation}")
        if basis:
            st.markdown(f"**Basis (rule & data)**\n\n_{basis}_")
        if df is not None and len(df):
            st.markdown(f"**Underlying data — {len(df)} record(s)**")
            show = df.copy()
            if "date" in show:
                show["date"] = pd.to_datetime(show["date"]).dt.strftime("%Y-%m-%d")
            if "amount" in show:
                show["amount"] = show["amount"].map(lambda x: f"{x:,.0f}")
            st.dataframe(show, use_container_width=True, hide_index=True, height=min(360, 40 + 28 * len(show)))


# --------------------------------------------------------------------------- #
#  Sidebar — data, theme, POI, filters
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(f"### {IC['app']} AML Intelligence")
    st.caption("Transaction Monitoring & Financial-Crime Analytics")

    seg = st.segmented_control(f"{IC['theme']} Appearance", ["🌙 Night", "☀️ Day"],
                               default="🌙 Night" if ss.theme == "night" else "☀️ Day")
    ss.theme = "night" if seg == "🌙 Night" else "day"

    st.divider()
    st.markdown(f"**{IC['upload']} Data source**")
    up = st.file_uploader("Upload POI transactions CSV", type=["csv"],
                          help="Columns: date, direction, account_no, sender, "
                               "beneficiary, amount, transaction_method")
    c1, c2 = st.columns(2)
    if c1.button("Load sample", use_container_width=True):
        ss.df = loader.sample_dataframe()
        ss.data_name = "sample_transactions.csv"
    if c2.download_button("Sample CSV", loader.sample_csv_bytes(),
                          "sample_transactions.csv", "text/csv", use_container_width=True):
        pass
    if up is not None:
        try:
            ss.df = loader.read_csv(up)
            ss.data_name = up.name
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

if ss.df is None:
    st.markdown(f"<div class='bluf'><span class='tag'>GET STARTED</span>"
                f"<h2>{IC['app']} AML / Financial-Intelligence Dashboard</h2>"
                f"<p class='muted'>Upload a POI transaction CSV in the sidebar, or click "
                f"<b>Load sample</b> to explore. Expected columns: "
                f"<code>date, direction (in/out/own_account), account_no (POI accounts, "
                f"“A|B” for own transfers), sender, beneficiary, amount, "
                f"transaction_method</code>.</p></div>", unsafe_allow_html=True)
    st.stop()

df_all = ss.df

# ---- Filters ---- #
with st.sidebar:
    st.divider()
    st.markdown(f"**{IC['filters']} Filters**")
    dmin, dmax = df_all.date.min().date(), df_all.date.max().date()
    dr = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    quarters = sorted(df_all.quarter.unique())
    qsel = st.multiselect("Quarter", quarters, default=quarters)
    dirs = st.multiselect("Direction", ["in", "out", "own"],
                          default=["in", "out", "own"],
                          format_func=lambda d: {"in": "⬇ Incoming", "out": "⬆ Outgoing",
                                                 "own": "🔁 Own-account"}[d])
    methods = sorted(df_all.transaction_method.unique())
    msel = st.multiselect("Method", methods, default=methods)
    accts = sorted(set(a for row in df_all.accounts for a in row))
    asel = st.multiselect("Account", accts, default=accts)
    ctypes = sorted(df_all.counterparty_type.unique())
    csel = st.multiselect("Counterparty type", ctypes, default=ctypes)
    amin, amax = float(df_all.amount.min()), float(df_all.amount.max())
    arange = st.slider("Amount range", amin, amax, (amin, amax))

# apply filters
d = df_all.copy()
if isinstance(dr, tuple) and len(dr) == 2:
    d = d[(d.date.dt.date >= dr[0]) & (d.date.dt.date <= dr[1])]
d = d[d.quarter.isin(qsel) & d.direction.isin(dirs) &
      d.transaction_method.isin(msel) & d.counterparty_type.isin(csel) &
      (d.amount >= arange[0]) & (d.amount <= arange[1])]
d = d[d.accounts.apply(lambda l: any(a in asel for a in l))]

if d.empty:
    st.warning("No transactions match the current filters. Widen the selection.")
    st.stop()

R = analytics.analyze(d)
k = R["kpis"]
if not ss.poi["primary_account"]:
    ss.poi["primary_account"] = R["accounts"][0]["account"]

# ---- POI editor (sidebar) ---- #
with st.sidebar:
    st.divider()
    with st.expander(f"{IC['poi']} POI profile", expanded=False):
        ss.poi["name"] = st.text_input("Full name", ss.poi["name"])
        ss.poi["nationality"] = st.text_input("Nationality", ss.poi["nationality"])
        ss.poi["doc_id"] = st.text_input("Doc / Customer ID", ss.poi["doc_id"])
        ss.poi["primary_account"] = st.selectbox(
            "Primary account", accts,
            index=accts.index(ss.poi["primary_account"]) if ss.poi["primary_account"] in accts else 0)
        ss.poi["extra"] = st.text_area("Other info / notes", ss.poi["extra"], height=70)
        ph = st.file_uploader("Photo", type=["png", "jpg", "jpeg"], key="poi_photo")
        if ph is not None:
            ss.poi["photo"] = ph.read()
        if ss.poi.get("photo"):
            st.image(ss.poi["photo"], width=90)

# --------------------------------------------------------------------------- #
#  Header + BLUF
# --------------------------------------------------------------------------- #
band_c = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[R["overall_band"]]
hc1, hc2 = st.columns([0.72, 0.28])
with hc1:
    bluf_text = ss.bluf_override or R["bluf"]
    st.markdown(
        f"<div class='bluf'><span class='tag'>{IC['bluf']} BLUF — BOTTOM LINE UP FRONT</span>"
        f"<h2>{ss.poi['name']} &nbsp;·&nbsp; Risk {k['risk']}/100 "
        f"<span style='color:{band_c}'>({R['overall_band']})</span></h2>"
        f"<p style='margin:0'>{bluf_text}</p></div>", unsafe_allow_html=True)
with hc2:
    st.plotly_chart(charts.risk_gauge(R["overall_risk"], R["overall_band"], t),
                    use_container_width=True, config=PLOTLY_CFG, key="gauge")

# KPI row
cols = st.columns(5)
kpi(cols[0], IC["txns"], "Transactions", f"{k['total_txns']:,}", "in scope", t["blue"])
kpi(cols[1], IC["in"], "Total Incoming", analytics.money(k["total_in"]), f"{R['flow']['in_count']} credits", t["green"])
kpi(cols[2], IC["out"], "Total Outgoing", analytics.money(k["total_out"]), f"{R['flow']['out_count']} debits", t["red"])
kpi(cols[3], IC["net"], "Net Cash Flow", analytics.money(k["net"]), "surplus" if k["net"] >= 0 else "deficit", t["green"] if k["net"] >= 0 else t["red"])
kpi(cols[4], IC["own"], "Own-Account", analytics.money(k["own_total"]), f"{R['flow']['own_count']} internal", t["violet"])
cols = st.columns(5)
kpi(cols[0], IC["accounts"], "Accounts", f"{k['n_accounts']}", "monitored", t["blue"])
kpi(cols[1], IC["senders"], "Unique Senders", f"{k['n_senders']}", "originators", t["teal"])
kpi(cols[2], IC["beneficiaries"], "Unique Beneficiaries", f"{k['n_beneficiaries']}", "recipients", t["teal"])
kpi(cols[3], IC["largest"], "Largest Txn", analytics.money(k["largest"]), "single movement", t["amber"])
kpi(cols[4], IC["risk"], "Risk Flags", f"{k['n_flags']}", f"{k['n_high']} high · {k['n_med']} medium", band_c)

st.write("")

# --------------------------------------------------------------------------- #
#  Tabs
# --------------------------------------------------------------------------- #
tabs = st.tabs([
    f"{IC['flow']} Money Flow", f"{IC['timeline']} Timeline",
    f"{IC['counterparties']} Counterparties", f"{IC['network']} Link Analysis",
    f"{IC['typology']} Financial Crime", f"{IC['riskdash']} Risk",
    f"{IC['transactions']} Transactions", f"{IC['export']} Export"])

# ---- Money Flow ---- #
with tabs[0]:
    c1, c2 = st.columns([0.62, 0.38])
    with c1:
        st.markdown("##### 💵 Money-flow Sankey — sources → accounts → destinations")
        st.plotly_chart(charts.sankey(R, t), use_container_width=True, config=PLOTLY_CFG, key="sankey")
        evidence("Evidence", "Aggregated flow: top external senders feed the POI's "
                 "accounts (hub), which disburse to top beneficiaries. Ribbon width is "
                 "proportional to total value.",
                 pd.concat([R["inc"], R["out"]])[analytics.EVID_COLS],
                 "Sources/destinations grouped by counterparty; hub = POI accounts.", key="ev_sankey")
    with c2:
        st.markdown("##### Account throughput")
        st.plotly_chart(charts.accounts_bar(R["accounts"], t), use_container_width=True, config=PLOTLY_CFG, key="acctbar")
        st.markdown("##### Inflow by source type")
        st.plotly_chart(charts.type_split(d, t), use_container_width=True, config=PLOTLY_CFG, key="typesplit")

    st.markdown("##### 🏦 Account analysis")
    adf = pd.DataFrame([{
        "Account": a["account"], "Inflow": analytics.money(a["inflow"]),
        "Outflow": analytics.money(a["outflow"]), "Txns": a["count"],
        "Largest": analytics.money(a["largest"]), "Avg": analytics.money(a["avg"]),
        "Top counterparty": a["top_counterparty"],
        "Risk": f"{a['risk']} ({a['band']})"} for a in R["accounts"]])
    st.dataframe(adf, use_container_width=True, hide_index=True)

# ---- Timeline ---- #
with tabs[1]:
    st.markdown("##### 📈 Monthly inflow vs outflow")
    st.plotly_chart(charts.timeline(R["timeline"], R["spikes"], t), use_container_width=True, config=PLOTLY_CFG, key="tl")
    sp = (R["spikes"]["inflow"] + R["spikes"]["outflow"])
    ev_tl = d[d.month.isin(sp)][analytics.EVID_COLS] if sp else d[analytics.EVID_COLS]
    evidence("Evidence — spikes", "Points marked ▲ are months whose inflow or outflow "
             "exceeds mean + 1.2σ of the monthly series — candidate periods for review.",
             ev_tl, "Spike rule: monthly total > mean + 1.2·standard-deviation.", key="ev_tl")
    st.markdown("##### 🔥 Activity heat-map (value × month × method)")
    st.plotly_chart(charts.entity_heatmap(d, t), use_container_width=True, config=PLOTLY_CFG, key="hm")

# ---- Counterparties ---- #
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ⬇ Top senders (by inflow)")
        st.plotly_chart(charts.ranked_bar(R["senders"], "green", t), use_container_width=True, config=PLOTLY_CFG, key="send")
        evidence("Evidence — senders", "External parties ranked by total value credited to "
                 "the POI. Icons mark 🏢 company / ❓ unknown.",
                 R["inc"][~R["inc"].counterparty_type.isin(["POI", "Internal"])][analytics.EVID_COLS],
                 "Excludes POI-self and internal transfers.", key="ev_send")
    with c2:
        st.markdown("##### ⬆ Top beneficiaries (by outflow)")
        st.plotly_chart(charts.ranked_bar(R["beneficiaries"], "red", t), use_container_width=True, config=PLOTLY_CFG, key="ben")
        evidence("Evidence — beneficiaries", "External parties ranked by total value the POI "
                 "paid out.",
                 R["out"][~R["out"].counterparty_type.isin(["POI", "Internal"])][analytics.EVID_COLS],
                 "Excludes POI-self and internal transfers.", key="ev_ben")
    st.markdown("##### 💳 Transaction methods")
    mc1, mc2 = st.columns(2)
    mc1.plotly_chart(charts.method_donut(R["methods"], t), use_container_width=True, config=PLOTLY_CFG, key="md")
    mc2.plotly_chart(charts.method_bar(R["methods"], t), use_container_width=True, config=PLOTLY_CFG, key="mb")

# ---- Link Analysis ---- #
with tabs[3]:
    st.markdown("##### 🕸️ Link analysis — node size = volume · edge colour = direction")
    st.plotly_chart(network.figure(d, R["entity_risk"], ss.nodes, t),
                    use_container_width=True, config=PLOTLY_CFG, key="net")
    lc1, lc2 = st.columns(2)
    with lc1:
        st.markdown("**✏️ Annotate a node** (name, doc id, photo, notes)")
        universe = network.node_universe(d)
        pick = st.selectbox("Node", universe, key="node_pick")
        ann = ss.nodes.get(pick, {})
        with st.form("nodeform", clear_on_submit=False):
            dn = st.text_input("Display name", ann.get("display_name", ""))
            did = st.text_input("Doc ID", ann.get("doc_id", ""))
            note = st.text_area("Notes", ann.get("notes", ""), height=68)
            nph = st.file_uploader("Photo", type=["png", "jpg", "jpeg"], key="nodephoto")
            saved = st.form_submit_button("💾 Save node info", use_container_width=True)
            if saved:
                newann = dict(display_name=dn, doc_id=did, notes=note,
                              photo=ann.get("photo"))
                if nph is not None:
                    newann["photo"] = data_uri(nph.read(),
                                               "image/jpeg" if nph.name.lower().endswith(("jpg", "jpeg")) else "image/png")
                ss.nodes[pick] = newann
                st.success(f"Saved annotation for “{pick}”.")
                st.rerun()
    with lc2:
        st.markdown("**🔎 Transactions between two nodes**")
        u = network.node_universe(d)
        na = st.selectbox("Node A", u, index=0, key="na")
        nb = st.selectbox("Node B", u, index=min(1, len(u) - 1), key="nb")
        et = network.edge_transactions(d, na, nb)
        if len(et):
            tot = et.amount.sum()
            st.caption(f"{len(et)} transaction(s) · total {analytics.money(tot)}")
            show = et.copy()
            show["date"] = show["date"].dt.strftime("%Y-%m-%d")
            show["amount"] = show["amount"].map(lambda x: f"{x:,.0f}")
            st.dataframe(show, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("No direct transactions between these two nodes.")

# ---- Financial Crime ---- #
with tabs[4]:
    st.markdown(f"##### 🚨 Financial-crime typology detection "
                f"<span class='muted'>— {len(R['findings'])} indicators · decision-support only, not an allegation</span>",
                unsafe_allow_html=True)
    for i, f in enumerate(R["findings"]):
        col = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[f["level"]]
        cc = st.columns([0.8, 0.2])
        with cc[0]:
            st.markdown(
                f"<div class='find' style='border-left-color:{col}'>"
                f"<div class='ttl'>{f['icon']} {f['title']} "
                f"<span class='pill pill-{f['level']}'>{f['level']}</span> "
                f"<span class='pill pill-Low' style='background:{t['blue']}22;color:{t['blue']};border-color:{t['blue']}66'>Conf: {f['confidence']}</span></div>"
                f"<div class='why'>{f['why']}</div></div>", unsafe_allow_html=True)
        with cc[1]:
            evidence("Evidence", f["why"], f["evidence"], f["basis"], key=f"ev_{f['key']}")

# ---- Risk ---- #
with tabs[5]:
    rc1, rc2 = st.columns([0.34, 0.66])
    with rc1:
        st.markdown("##### 🎯 Overall risk")
        st.plotly_chart(charts.risk_gauge(R["overall_risk"], R["overall_band"], t),
                        use_container_width=True, config=PLOTLY_CFG, key="gauge2")
        evidence("Evidence — how the score is built",
                 "The overall score aggregates the risk weight of every triggered "
                 "typology (scaled to 0–100). Higher-severity indicators contribute more.",
                 pd.DataFrame(R["risk_components"]),
                 "score = min(100, 0.85 × Σ indicator weights).", key="ev_risk")
    with rc2:
        st.markdown("##### Risk contribution by indicator")
        st.plotly_chart(charts.risk_components(R["risk_components"], t),
                        use_container_width=True, config=PLOTLY_CFG, key="rc")
    st.markdown("##### 🏦 Account & counterparty risk")
    ar = pd.DataFrame([{"Entity": a["account"], "Type": "Account", "Score": a["risk"],
                        "Band": a["band"]} for a in R["accounts"]] +
                      [{"Entity": n, "Type": v["role"], "Score": v["score"], "Band": v["band"]}
                       for n, v in sorted(R["entity_risk"].items(), key=lambda x: -x[1]["score"])[:8]])
    st.dataframe(ar, use_container_width=True, hide_index=True,
                 column_config={"Score": st.column_config.ProgressColumn(
                     "Score", min_value=0, max_value=100, format="%d")})

# ---- Transactions ---- #
with tabs[6]:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ⬇ Top 10 incoming")
        st.dataframe(pd.DataFrame([{
            "Date": x["date"].strftime("%d %b %y"), "Counterparty": x["counterparty"],
            "Method": x["method"].title(), "Amount": analytics.money_full(x["amount"])}
            for x in R["top_in"]]), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("##### ⬆ Top 10 outgoing")
        st.dataframe(pd.DataFrame([{
            "Date": x["date"].strftime("%d %b %y"), "Counterparty": x["counterparty"],
            "Method": x["method"].title(), "Amount": analytics.money_full(x["amount"])}
            for x in R["top_out"]]), use_container_width=True, hide_index=True)
    st.markdown("##### 🧾 All transactions (filtered)")
    full = d[analytics.EVID_COLS].copy()
    full["date"] = full["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(full, use_container_width=True, hide_index=True, height=420)
    st.download_button("⬇ Download filtered data (CSV)",
                       d[loader.REQUIRED].to_csv(index=False).encode(),
                       "filtered_transactions.csv", "text/csv")

# ---- Export ---- #
with tabs[7]:
    st.markdown("##### 📤 Build a decision-maker PDF")
    st.caption("Pick the exhibits, add your commentary, and export a high-quality "
               "landscape PDF with a BLUF cover, POI profile and headline KPIs.")

    catalogue = {
        "Money-flow Sankey": ("sankey", lambda: charts.sankey(R, t),
                              "Aggregated sources → POI accounts → destinations."),
        "Monthly timeline": ("timeline", lambda: charts.timeline(R["timeline"], R["spikes"], t),
                             "Monthly inflow vs outflow; ▲ marks statistical spikes."),
        "Activity heat-map": ("heatmap", lambda: charts.entity_heatmap(d, t),
                             "Aggregate value by month and method."),
        "Top senders": ("senders", lambda: charts.ranked_bar(R["senders"], "green", t),
                        "External parties ranked by inflow."),
        "Top beneficiaries": ("beneficiaries", lambda: charts.ranked_bar(R["beneficiaries"], "red", t),
                             "External parties ranked by outflow."),
        "Transaction methods": ("methods", lambda: charts.method_donut(R["methods"], t),
                               "Mix of transfer / withdrawal / cheque / cash."),
        "Account throughput": ("accounts", lambda: charts.accounts_bar(R["accounts"], t),
                              "Per-account inflow vs outflow."),
        "Link-analysis network": ("network", lambda: network.figure(d, R["entity_risk"], ss.nodes, t, height=520),
                                  "Entity relationship graph; node size = volume."),
        "Risk contribution": ("riskcomp", lambda: charts.risk_components(R["risk_components"], t),
                             "Each typology indicator and its risk weight."),
    }
    ec1, ec2 = st.columns([0.5, 0.5])
    with ec1:
        chosen = st.multiselect("Exhibits to include (in order)", list(catalogue),
                                default=["Money-flow Sankey", "Monthly timeline",
                                         "Link-analysis network", "Risk contribution"])
        include_findings = st.checkbox("Include financial-crime findings page", True)
    with ec2:
        rep_title = st.text_input("Report title", "Financial Intelligence Report")
        prepared_for = st.text_input("Prepared for", "Senior Management / Decision Maker")
        classification = st.text_input("Classification", "CONFIDENTIAL — FIU / AML")
    ss.bluf_override = st.text_area("BLUF (editable — appears on the cover)",
                                    ss.bluf_override or R["bluf"], height=110)
    ss.analyst_note = st.text_area("Analyst commentary (optional)", ss.analyst_note, height=90)

    if st.button("🖨️ Generate PDF", type="primary"):
        with st.spinner("Rendering high-resolution exhibits…"):
            meta = dict(title=rep_title, subtitle=f"Prepared for {prepared_for}",
                        classification=classification, reference="FIU/AML/2026/0417")
            poi = dict(name=ss.poi["name"], nationality=ss.poi["nationality"],
                       doc_id=ss.poi["doc_id"], primary_account=ss.poi["primary_account"],
                       period=R["period_str"], photo=ss.poi.get("photo"))
            sel = [dict(title=name, fig=catalogue[name][1](), note=catalogue[name][2])
                   for name in chosen]
            pdf = pdfexport.build_pdf(
                t=t, meta=meta, bluf=ss.bluf_override or R["bluf"], poi=poi, kpis=k,
                overall_risk=R["overall_risk"], overall_band=R["overall_band"],
                charts=sel, findings=R["findings"] if include_findings else None,
                analyst_note=ss.analyst_note)
        st.success("PDF ready.")
        st.download_button("⬇ Download report PDF", pdf,
                           "AML_Intelligence_Report.pdf", "application/pdf",
                           type="primary")

st.caption(f"Data: {ss.data_name or '—'} · {len(d):,} of {len(df_all):,} transactions in scope "
           f"· indicators are decision-support only and require analyst review.")
