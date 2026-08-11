"""
AML / Financial-Intelligence interactive dashboard (Streamlit).

    streamlit run app/app.py

Bilingual (EN/AR + RTL), animated, with an editable POI header, per-chart info,
a counterparty focus filter, spike drill-down, an interactive link-analysis
graph, removable financial-crime indicators, an analytics chat, and an editable
PowerPoint export (with optional template upload).
"""

from __future__ import annotations

import base64
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import loader, analytics, charts, network, pptx_export, chat, i18n, auth
from core.theme import theme, app_css, IC
from core.i18n import T as _T, info_text, typ_title, typ_plain

st.set_page_config(page_title="AML Intelligence Terminal", page_icon="🛰️",
                   layout="wide", initial_sidebar_state="expanded")

PLOTLY_CFG = {"displaylogo": False, "toImageButtonOptions": {"scale": 3, "format": "png"},
              "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def _init():
    s = st.session_state
    s.setdefault("theme", "night")
    s.setdefault("lang", "en")
    s.setdefault("poi", dict(name="«POI FULL NAME»", nationality="«NATIONALITY»",
                             doc_id="«DOC / CUSTOMER ID»", photo=None, extra="",
                             primary_account=""))
    s.setdefault("poi_edit", False)
    s.setdefault("nodes", {})
    s.setdefault("analyst_note", "")
    s.setdefault("bluf_override", "")
    s.setdefault("df", None)
    s.setdefault("data_name", "")
    s.setdefault("disabled", set())
    s.setdefault("chat", [])
    s.setdefault("tmpl", None)
    s.setdefault("nav", None)
    s.setdefault("kpi_hidden", set())
    s.setdefault("bluf_edit", False)


_init()
ss = st.session_state
lang = ss.lang
t = theme(ss.theme)
st.markdown(app_css(t), unsafe_allow_html=True)
st.markdown(i18n.rtl_css(lang), unsafe_allow_html=True)


def L(key):
    return _T(key, lang)


# --- authentication gate -------------------------------------------------- #
if not auth.require_login(lang, _T("brand", lang)):
    st.stop()


def data_uri(raw, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def kpi(col, icon, label, value, sub, color):
    col.markdown(f'<div class="kpi"><div class="bar" style="background:{color}"></div>'
                 f'<div class="lbl">{icon} {label}</div>'
                 f'<div class="val" style="color:{color}">{value}</div>'
                 f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def chart_header(title, info_key):
    c1, c2 = st.columns([0.93, 0.07])
    c1.markdown(f"##### {title}")
    with c2.popover("ⓘ", use_container_width=True):
        st.markdown(f"**{L('info')}**")
        st.write(info_text(info_key, lang))


def evidence(label, explanation, df=None, basis=None, key=None):
    with st.popover(f"{IC['evidence']} {label}"):
        st.markdown(f"**{explanation}**")
        if basis:
            st.markdown(f"_{basis}_")
        if df is not None and len(df):
            show = df.copy()
            if "date" in show:
                show["date"] = pd.to_datetime(show["date"]).dt.strftime("%Y-%m-%d")
            if "amount" in show:
                show["amount"] = show["amount"].map(lambda x: f"{x:,.0f}")
            st.dataframe(show, use_container_width=True, hide_index=True,
                         height=min(340, 40 + 28 * len(show)))


# --------------------------------------------------------------------------- #
#  Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(f"### {IC['app']} {L('brand')}")
    lsel = st.segmented_control(L("language"), ["English", "العربية"],
                                default="العربية" if lang == "ar" else "English", key="langsel")
    ss.lang = "ar" if lsel == "العربية" else "en"
    tsel = st.segmented_control(L("appearance"), [f"🌙 {L('night')}", f"☀️ {L('day')}"],
                                default=f"🌙 {L('night')}" if ss.theme == "night" else f"☀️ {L('day')}")
    ss.theme = "night" if L("night") in tsel else "day"
    auth.logout_button(lang)

    st.divider()
    st.markdown(f"**{IC['upload']} {L('data_source')}**")
    up = st.file_uploader(L("upload_csv"), type=["csv"])
    c1, c2 = st.columns(2)
    if c1.button(L("load_sample"), use_container_width=True):
        ss.df = loader.sample_dataframe(); ss.data_name = "sample_transactions.csv"
    c2.download_button(L("sample_csv"), loader.sample_csv_bytes(),
                       "sample_transactions.csv", "text/csv", use_container_width=True)
    if up is not None:
        try:
            ss.df = loader.read_csv(up); ss.data_name = up.name
        except Exception as e:
            st.error(str(e))

if ss.lang != lang:  # language just changed → rerun with new strings
    st.rerun()

if ss.df is None:
    st.markdown(f"<div class='bluf'><span class='tag'>{L('get_started')}</span>"
                f"<h2>{IC['app']} {L('welcome')}</h2>"
                f"<p class='muted'>{L('welcome_body')}</p></div>", unsafe_allow_html=True)
    st.stop()

df_all = ss.df

# ---- filters ---- #
with st.sidebar:
    st.divider()
    st.markdown(f"**{IC['filters']} {L('filters')}**")
    dmin, dmax = df_all.date.min().date(), df_all.date.max().date()
    dr = st.date_input(L("date_range"), (dmin, dmax), min_value=dmin, max_value=dmax)
    quarters = sorted(df_all.quarter.unique())
    qsel = st.multiselect(L("quarter"), quarters, default=quarters)
    dirs = st.multiselect(L("direction"), ["in", "out", "own"], default=["in", "out", "own"],
                          format_func=lambda x: {"in": L("dir_in"), "out": L("dir_out"),
                                                 "own": L("dir_own")}[x])
    methods = sorted(df_all.transaction_method.unique())
    msel = st.multiselect(L("method"), methods, default=methods)
    accts = sorted(set(a for row in df_all.accounts for a in row))
    asel = st.multiselect(L("account"), accts, default=accts)
    ctypes = sorted(df_all.counterparty_type.unique())
    csel = st.multiselect(L("cp_type"), ctypes, default=ctypes)
    stypes = sorted(df_all.sender_type.unique())
    ssel = st.multiselect(L("f_sender_type"), stypes, default=stypes)
    btypes = sorted(df_all.beneficiary_type.unique())
    bsel = st.multiselect(L("f_beneficiary_type"), btypes, default=btypes)
    amin, amax = float(df_all.amount.min()), float(df_all.amount.max())
    arange = st.slider(L("amount_range"), amin, amax, (amin, amax))
    ext_cps = sorted(df_all.loc[~df_all.counterparty_type.isin(["POI", "Internal"]),
                                "counterparty"].unique())
    focus_cp = st.selectbox(L("focus_cp"), [L("focus_all")] + ext_cps)

# apply filters
d = df_all.copy()
if isinstance(dr, tuple) and len(dr) == 2:
    d = d[(d.date.dt.date >= dr[0]) & (d.date.dt.date <= dr[1])]
d = d[d.quarter.isin(qsel) & d.direction.isin(dirs) & d.transaction_method.isin(msel) &
      d.counterparty_type.isin(csel) & d.sender_type.isin(ssel) & d.beneficiary_type.isin(bsel) &
      (d.amount >= arange[0]) & (d.amount <= arange[1])]
d = d[d.accounts.apply(lambda l: any(a in asel for a in l))]
if focus_cp != L("focus_all"):
    d = d[d.counterparty == focus_cp]

if d.empty:
    st.warning("No transactions match the current filters." if lang == "en"
               else "لا توجد معاملات مطابقة لعوامل التصفية.")
    st.stop()

R = analytics.analyze(d)
k = R["kpis"]
if not ss.poi["primary_account"]:
    ss.poi["primary_account"] = R["accounts"][0]["account"]

# active findings after removals + recomputed score
active = [f for f in R["findings"] if f["key"] not in ss.disabled]
removed = [f for f in R["findings"] if f["key"] in ss.disabled]
score = analytics.score_from(active)
band = analytics.risk_band(score)
band_c = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[band]

# --------------------------------------------------------------------------- #
#  Brand rail
# --------------------------------------------------------------------------- #
st.markdown(
    f"<div class='brand'><span class='logo'>{IC['app']}</span>"
    f"<div><div class='name'>{L('brand')}</div><div class='sub'>{L('brand_sub')}</div></div>"
    f"<span class='spacer'></span>"
    f"<span class='stat'>{L('subject')}&nbsp; <b>{ss.poi['name']}</b></span>"
    f"<span class='stat'>{L('scope')}&nbsp; <b>{R['period_str']}</b></span>"
    f"<span class='stat'>{L('records')}&nbsp; <b>{len(d):,}</b></span>"
    f"<span class='chip'>{L('classification')}</span></div>", unsafe_allow_html=True)

if focus_cp != L("focus_all"):
    st.info(f"{L('focus_active')} **{focus_cp}** · {L('kpi_in')} {analytics.money(k['total_in'])} · "
            f"{L('kpi_out')} {analytics.money(k['total_out'])}")

# --------------------------------------------------------------------------- #
#  POI header — inline editable
# --------------------------------------------------------------------------- #
pc1, pc2 = st.columns([0.85, 0.15])
with pc2:
    if not ss.poi_edit and st.button(f"✏️ {L('edit')}", use_container_width=True):
        ss.poi_edit = True; st.rerun()
with pc1:
    st.markdown(f"###### {IC['poi']} {L('poi_profile')}")

if ss.poi_edit:
    with st.form("poi_form"):
        f1, f2, f3 = st.columns(3)
        ss.poi["name"] = f1.text_input(L("full_name"), ss.poi["name"])
        ss.poi["nationality"] = f2.text_input(L("nationality"), ss.poi["nationality"])
        ss.poi["doc_id"] = f3.text_input(L("doc_id"), ss.poi["doc_id"])
        g1, g2 = st.columns([0.5, 0.5])
        ss.poi["primary_account"] = g1.selectbox(
            L("primary_account"), accts,
            index=accts.index(ss.poi["primary_account"]) if ss.poi["primary_account"] in accts else 0)
        ph = g2.file_uploader(L("photo"), type=["png", "jpg", "jpeg"])
        ss.poi["extra"] = st.text_area(L("other_info"), ss.poi["extra"], height=68)
        cc1, cc2 = st.columns(2)
        if cc1.form_submit_button(f"💾 {L('save')}", use_container_width=True, type="primary"):
            if ph is not None:
                ss.poi["photo"] = ph.read()
            ss.poi_edit = False; st.rerun()
        if cc2.form_submit_button(L("cancel"), use_container_width=True):
            ss.poi_edit = False; st.rerun()
else:
    avatar = (f"<img src='{data_uri(ss.poi['photo'])}'>" if ss.poi.get("photo") else "🧑")
    fields = [(L("nationality"), ss.poi["nationality"]), (L("doc_id"), ss.poi["doc_id"]),
              (L("primary_account"), ss.poi["primary_account"]),
              (L("analysis_period"), R["period_str"]),
              (L("risk_rating"), f"{score}/100 · {band}")]
    if ss.poi["extra"]:
        fields.append((L("other_info"), ss.poi["extra"]))
    cells = "".join(f"<div class='poi-field'><span class='k'>{kk}</span>"
                    f"<span class='v'>{vv}</span></div>" for kk, vv in fields)
    st.markdown(
        f"<div class='poicard'><div class='avatar'>{avatar}</div>"
        f"<div style='flex:1'><div class='nm'>{ss.poi['name']}</div>"
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:6px 18px;margin-top:8px'>"
        f"{cells}</div></div></div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
#  BLUF hero + gauge
# --------------------------------------------------------------------------- #
hc1, hc2 = st.columns([0.72, 0.28])
with hc1:
    bluf_text = ss.bluf_override or R["bluf"]
    tc1, tc2 = st.columns([0.8, 0.2])
    with tc2:
        if st.button(f"✏️ {L('edit_bluf')}", use_container_width=True):
            ss.bluf_edit = not ss.bluf_edit
    if ss.bluf_edit:
        new = st.text_area(L("edit_bluf"), value=bluf_text, height=140, key="bluf_ta")
        bc1, bc2 = st.columns(2)
        if bc1.button(f"💾 {L('save')}", use_container_width=True, type="primary"):
            ss.bluf_override = new; ss.bluf_edit = False; st.rerun()
        if bc2.button(f"↺ {L('reset_auto')}", use_container_width=True):
            ss.bluf_override = ""; ss.bluf_edit = False; st.rerun()
    else:
        st.markdown(f"<div class='bluf'><span class='tag'>{IC['bluf']} {L('bluf')}</span>"
                    f"<h2>{ss.poi['name']} &nbsp;·&nbsp; <span class='num'>{L('risk_word')} {score}/100</span> "
                    f"<span style='color:{band_c}'>({band})</span></h2>"
                    f"<p style='margin:0'>{bluf_text}</p></div>", unsafe_allow_html=True)
with hc2:
    st.plotly_chart(charts.risk_gauge(score, band, t), use_container_width=True,
                    config=PLOTLY_CFG, key="gauge")

# --------------------------------------------------------------------------- #
#  Statistics (KPIs) — customizable, each with an info + evidence popover
# --------------------------------------------------------------------------- #
inc_ext = R["inc"][~R["inc"].counterparty_type.isin(["POI", "Internal"])]
out_ext = R["out"][~R["out"].counterparty_type.isin(["POI", "Internal"])]
STATS = [
    ("txns", IC["txns"], L("kpi_txns"), f"{k['total_txns']:,}", "", t["blue"], "stat_txns", d[analytics.EVID_COLS]),
    ("in", IC["in"], L("kpi_in"), analytics.money(k["total_in"]), f"{R['flow']['in_count']} {L('credits')}", t["green"], "stat_in", R["inc"][analytics.EVID_COLS]),
    ("out", IC["out"], L("kpi_out"), analytics.money(k["total_out"]), f"{R['flow']['out_count']} {L('debits')}", t["red"], "stat_out", R["out"][analytics.EVID_COLS]),
    ("net", IC["net"], L("kpi_net"), analytics.money(k["net"]), L("surplus") if k["net"] >= 0 else L("deficit"), t["green"] if k["net"] >= 0 else t["red"], "stat_net", None),
    ("own", IC["own"], L("kpi_own"), analytics.money(k["own_total"]), f"{R['flow']['own_count']} {L('internal')}", t["violet"], "stat_own", R["own"][analytics.EVID_COLS]),
    ("accounts", IC["accounts"], L("kpi_accounts"), f"{k['n_accounts']}", L("monitored"), t["blue"], "stat_accounts", None),
    ("senders", IC["senders"], L("kpi_senders"), f"{k['n_senders']}", "", t["teal"], "stat_senders", None),
    ("bens", IC["beneficiaries"], L("kpi_bens"), f"{k['n_beneficiaries']}", "", t["teal"], "stat_bens", None),
    ("largest", IC["largest"], L("kpi_largest"), analytics.money(k["largest"]), "", t["amber"], "stat_largest", d.sort_values("amount", ascending=False).head(5)[analytics.EVID_COLS]),
    ("flags", IC["risk"], L("kpi_flags"), f"{len(active)}", L("high_med").format(
        h=sum(f['level'] == 'High' for f in active), m=sum(f['level'] == 'Medium' for f in active)), band_c, "stat_flags", None),
]
# lazy evidence for stats without a direct frame
import pandas as _pd
STAT_EV = {
    "net": _pd.DataFrame([{"": L("kpi_in"), " ": analytics.money(k["total_in"])},
                          {"": L("kpi_out"), " ": analytics.money(k["total_out"])},
                          {"": L("kpi_net"), " ": analytics.money(k["net"])}]),
    "accounts": _pd.DataFrame([{
        L("account"): a["account"], L("col_in_ext"): analytics.money(a["in_ext"]),
        L("col_in_own"): analytics.money(a["in_own"]), L("col_out_ext"): analytics.money(a["out_ext"]),
        L("col_out_own"): analytics.money(a["out_own"]), L("col_balance_eq"): analytics.money(a["balance"])}
        for a in analytics.account_details(d)]),
    "senders": _pd.DataFrame([{L("col_cp"): r["name"], L("col_amount"): analytics.money(r["amount"]), "#": r["count"]}
                              for r in R["senders"][:10]]),
    "bens": _pd.DataFrame([{L("col_cp"): r["name"], L("col_amount"): analytics.money(r["amount"]), "#": r["count"]}
                          for r in R["beneficiaries"][:10]]),
    "flags": _pd.DataFrame([{L("sec_crime"): typ_title(f["key"], lang, f["title"]),
                             "": f["level"]} for f in active]),
}

with st.popover(f"⚙️ {L('customize_stats')}"):
    st.caption(L("stat_show"))
    for sid, icon, label, *_ in STATS:
        shown = st.checkbox(f"{icon} {label}", value=sid not in ss.kpi_hidden, key=f"kp_{sid}")
        if shown:
            ss.kpi_hidden.discard(sid)
        else:
            ss.kpi_hidden.add(sid)

visible = [s for s in STATS if s[0] not in ss.kpi_hidden]
for i in range(0, len(visible), 5):
    row = visible[i:i + 5]
    cols = st.columns(5)
    for j, (sid, icon, label, val, sub, color, info_key, ev) in enumerate(row):
        with cols[j]:
            kpi(cols[j], icon, label, val, sub, color)
            with st.popover(f"ⓘ {L('evidence_for')}", use_container_width=True):
                st.markdown(f"**{label}** — {info_text(info_key, lang)}")
                edf = ev if ev is not None else STAT_EV.get(sid)
                if edf is not None and len(edf):
                    show = edf.copy()
                    if "date" in show:
                        show["date"] = _pd.to_datetime(show["date"]).dt.strftime("%Y-%m-%d")
                    if "amount" in show:
                        show["amount"] = show["amount"].map(lambda x: f"{x:,.0f}")
                    st.dataframe(show, use_container_width=True, hide_index=True,
                                 height=min(320, 44 + 28 * len(show)))
                if sid == "accounts":
                    st.caption("🧮 " + L("balance_formula"))

st.write("")

# --------------------------------------------------------------------------- #
#  Navigation (segmented → conditional render → charts animate on each open)
# --------------------------------------------------------------------------- #
SECTIONS = [("flow", IC["flow"], L("sec_flow")), ("accounts", IC["accounts"], L("sec_accounts")),
            ("timeline", IC["timeline"], L("sec_timeline")),
            ("cp", IC["counterparties"], L("sec_cp")), ("net", IC["network"], L("sec_network")),
            ("crime", IC["typology"], L("sec_crime")), ("risk", IC["riskdash"], L("sec_risk")),
            ("txns", IC["transactions"], L("sec_txns")), ("chat", "💬", L("sec_chat")),
            ("export", IC["export"], L("sec_export"))]
labels = [f"{ic} {nm}" for _, ic, nm in SECTIONS]
choice = st.segmented_control("nav", labels, default=labels[0],
                              label_visibility="collapsed", key="navseg") or labels[0]
sec = SECTIONS[labels.index(choice)][0]

# ---- Money Flow ----
if sec == "flow":
    c1, c2 = st.columns([0.62, 0.38])
    with c1:
        chart_header(L("sankey_title"), "sankey")
        st.plotly_chart(charts.sankey(R, t, lang), use_container_width=True, config=PLOTLY_CFG, key="sk")
    with c2:
        chart_header(L("acct_throughput"), "accounts")
        st.plotly_chart(charts.accounts_bar(R["accounts"], t), use_container_width=True, config=PLOTLY_CFG, key="ab")
        chart_header(L("inflow_by_type"), "type_split")
        st.plotly_chart(charts.type_split(d, t), use_container_width=True, config=PLOTLY_CFG, key="ts")
    st.markdown(f"##### 🏦 {L('account_analysis')}")
    st.dataframe(pd.DataFrame([{
        L("account"): a["account"], L("kpi_in"): analytics.money(a["inflow"]),
        L("kpi_out"): analytics.money(a["outflow"]), L("kpi_txns"): a["count"],
        L("kpi_largest"): analytics.money(a["largest"]), L("col_cp"): a["top_counterparty"],
        L("sec_risk"): f"{a['risk']} ({a['band']})"} for a in R["accounts"]]),
        use_container_width=True, hide_index=True)

# ---- Accounts Details ----
elif sec == "accounts":
    ad = analytics.account_details(d)
    chart_header(L("acc_table_title"), "accounts")
    st.dataframe(pd.DataFrame([{
        L("account"): a["account"], L("col_incoming"): analytics.money(a["inflow"]),
        L("col_outgoing"): analytics.money(a["outflow"]), L("col_balance"): analytics.money(a["balance"]),
        L("col_count"): a["count"], L("col_spike"): ("🔴 " + L("yes")) if a["spike"] else L("no")}
        for a in ad]), use_container_width=True, hide_index=True)

    with st.expander(f"🧮 {L('balance_help')}"):
        st.dataframe(pd.DataFrame([{
            L("account"): a["account"], L("col_in_ext"): analytics.money(a["in_ext"]),
            L("col_in_own"): analytics.money(a["in_own"]), L("col_out_ext"): analytics.money(a["out_ext"]),
            L("col_out_own"): analytics.money(a["out_own"]), L("col_balance_eq"): analytics.money(a["balance"])}
            for a in ad]), use_container_width=True, hide_index=True)
        st.caption(L("balance_formula"))

    spiky = [a for a in ad if a["spike"]]
    if spiky:
        st.markdown(f"##### ⚡ {L('spike_txns_title')}")
        for a in spiky:
            stx = analytics.account_spike_txns(d, a["account"], a["spike_months"])
            with st.expander(L("spike_view").format(acc=a["account"], n=len(stx))):
                sh = stx.copy(); sh["date"] = sh["date"].dt.strftime("%Y-%m-%d")
                sh["flow"] = sh["flow"].map(lambda x: ("🟢 " + L("flow_in")) if x == "IN" else ("🔴 " + L("flow_out")))
                sh["amount"] = sh["amount"].map(lambda x: f"{x:,.0f}")
                sh = sh.rename(columns={"date": L("col_date"), "month": L("quarter"), "flow": L("col_flow"),
                                        "party": L("col_party"), "counterparty_type": L("cp_type"),
                                        "amount": L("col_amount"), "transaction_method": L("col_method")})
                st.dataframe(sh, use_container_width=True, hide_index=True, height=min(320, 44 + 28 * len(sh)))

    st.markdown(f"##### 👥 {L('acc_top_title')}")
    for a in ad:
        with st.expander(L("acc_expander").format(acc=a["account"])):
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f"**⬇ {L('acc_top_senders')}**")
                snd = analytics.account_top(d, a["account"], "in", 5)
                st.dataframe(pd.DataFrame([{L("col_cp"): x["name"], L("cp_type"): x["type"],
                                            L("col_amount"): analytics.money(x["amount"]), "#": x["count"]} for x in snd])
                             if snd else pd.DataFrame({L("col_cp"): ["—"]}), use_container_width=True, hide_index=True)
            with sc2:
                st.markdown(f"**⬆ {L('acc_top_receivers')}**")
                rcv = analytics.account_top(d, a["account"], "out", 5)
                st.dataframe(pd.DataFrame([{L("col_cp"): x["name"], L("cp_type"): x["type"],
                                            L("col_amount"): analytics.money(x["amount"]), "#": x["count"]} for x in rcv])
                             if rcv else pd.DataFrame({L("col_cp"): ["—"]}), use_container_width=True, hide_index=True)

    st.markdown(f"##### 🔗 {L('multi_title')}")
    st.caption(L("multi_note"))
    minacc = st.number_input(L("min_accounts"), min_value=2, max_value=max(2, k["n_accounts"]), value=2, step=1)
    ma = analytics.multi_account_counterparties(d, int(minacc))
    if ma:
        st.dataframe(pd.DataFrame([{
            L("col_cp"): m["counterparty"], L("cp_type"): m["type"], L("col_naccounts"): m["n_accounts"],
            L("col_accounts"): " | ".join(m["accounts"]),
            L("col_incoming"): analytics.money(m["inflow"]), L("col_outgoing"): analytics.money(m["outflow"]),
            L("col_direction"): L("dir_both") if m["direction"] == "both" else (L("dir_in") if m["direction"] == "in" else L("dir_out"))}
            for m in ma]), use_container_width=True, hide_index=True)
    else:
        st.info(L("multi_none"))

# ---- Timeline ----
elif sec == "timeline":
    chart_header(L("tl_title"), "timeline")
    st.plotly_chart(charts.timeline(R["timeline"], R["spikes"], t, lang),
                    use_container_width=True, config=PLOTLY_CFG, key="tl")
    st.markdown(f"##### ⚡ {L('spike_inspect')}")
    spikes = sorted(set(R["spikes"]["inflow"] + R["spikes"]["outflow"]))
    if not spikes:
        st.info(L("spike_none"))
    else:
        sm = st.selectbox(L("spike_pick"), spikes)
        sb = analytics.spike_breakdown(d, sm)
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"**⬇ {L('spike_senders')}** · {analytics.money(sb['inflow'])}")
            st.dataframe(pd.DataFrame([{L("col_cp"): r["name"], L("col_amount"): analytics.money(r["amount"]),
                                        "%": f"{r['pct']:.0f}%", "#": r["count"]} for r in sb["senders"]]) if sb["senders"]
                         else pd.DataFrame({L("col_cp"): ["—"]}), use_container_width=True, hide_index=True)
        with m2:
            st.markdown(f"**⬆ {L('spike_bens')}** · {analytics.money(sb['outflow'])}")
            st.dataframe(pd.DataFrame([{L("col_cp"): r["name"], L("col_amount"): analytics.money(r["amount"]),
                                        "%": f"{r['pct']:.0f}%", "#": r["count"]} for r in sb["beneficiaries"]]) if sb["beneficiaries"]
                         else pd.DataFrame({L("col_cp"): ["—"]}), use_container_width=True, hide_index=True)
        ev = sb["evidence"].copy()
        ev["date"] = ev["date"].dt.strftime("%Y-%m-%d"); ev["amount"] = ev["amount"].map(lambda x: f"{x:,.0f}")
        with st.expander(f"{IC['evidence']} {sm} — {len(ev)} " + ("transactions" if lang == "en" else "معاملة")):
            st.dataframe(ev, use_container_width=True, hide_index=True, height=300)

# ---- Counterparties ----
elif sec == "cp":
    c1, c2 = st.columns(2)
    with c1:
        chart_header(L("top_senders"), "senders")
        st.plotly_chart(charts.ranked_bar(R["senders"], "green", t), use_container_width=True, config=PLOTLY_CFG, key="rs")
    with c2:
        chart_header(L("top_bens"), "beneficiaries")
        st.plotly_chart(charts.ranked_bar(R["beneficiaries"], "red", t), use_container_width=True, config=PLOTLY_CFG, key="rb")
    chart_header(L("methods_title"), "methods")
    mc1, mc2 = st.columns(2)
    mc1.plotly_chart(charts.method_donut(R["methods"], t), use_container_width=True, config=PLOTLY_CFG, key="md")
    mc2.plotly_chart(charts.method_bar(R["methods"], t), use_container_width=True, config=PLOTLY_CFG, key="mbar")

# ---- Link Analysis ----
elif sec == "net":
    import streamlit.components.v1 as components
    chart_header(L("net_title"), "network")
    # legend — node classes (distinct shapes) + edge directions
    def swatch(shape, c):
        base = f"display:inline-block;width:13px;height:13px;box-shadow:0 0 8px {c};"
        if shape == "star":
            return f"<span style='color:{c};text-shadow:0 0 8px {c};font-size:15px'>★</span>"
        if shape == "square":
            return f"<span style='{base}background:{c}'></span>"
        if shape == "triangle":
            return (f"<span style='display:inline-block;width:0;height:0;"
                    f"border-left:7px solid transparent;border-right:7px solid transparent;"
                    f"border-bottom:12px solid {c};filter:drop-shadow(0 0 5px {c})'></span>")
        if shape == "diamond":
            return f"<span style='{base}background:{c};transform:rotate(45deg)'></span>"
        if shape == "line":
            return f"<span style='display:inline-block;width:18px;height:3px;border-radius:2px;background:{c};box-shadow:0 0 6px {c}'></span>"
        return f"<span style='{base}background:{c};border-radius:50%'></span>"  # dot

    lg = [("star", t["poi"], L("lg_poi")), ("square", t["account"], L("lg_account")),
          ("dot", t["company"], L("lg_company")), ("triangle", t["pink"], L("lg_person")),
          ("diamond", t["unknown"], L("lg_unknown")),
          ("line", t["green"], L("lg_in")), ("line", t["red"], L("lg_out")),
          ("line", t["violet"], L("lg_own"))]
    chips = " ".join(
        f"<span style='display:inline-flex;align-items:center;gap:7px;margin-inline-end:16px;"
        f"font-family:var(--mono);font-size:12px;color:{t['mute']}'>"
        f"{swatch(shape, c)}{lab}</span>" for shape, c, lab in lg)
    st.markdown(f"<div class='card' style='padding:10px 14px'>{chips}</div>", unsafe_allow_html=True)
    st.caption("🖱️ " + L("net_help"))
    html = network.pyvis_html(d, R["entity_risk"], ss.nodes, t, height=620, lang=lang)
    components.html(html, height=650, scrolling=False)
    u = network.node_universe(d)
    lc1, lc2 = st.columns(2)
    with lc1:
        st.markdown(f"**✏️ {L('annotate_node')}**")
        pick = st.selectbox(L("node"), u, key="node_pick")
        ann = ss.nodes.get(pick, {})
        with st.form("nodeform"):
            dn = st.text_input(L("display_name"), ann.get("display_name", ""))
            did = st.text_input(L("doc_id"), ann.get("doc_id", ""))
            note = st.text_area(L("notes"), ann.get("notes", ""), height=68)
            nph = st.file_uploader(L("photo"), type=["png", "jpg", "jpeg"], key="np")
            if st.form_submit_button(f"💾 {L('save_node')}", use_container_width=True, type="primary"):
                na = dict(display_name=dn, doc_id=did, notes=note, photo=ann.get("photo"))
                if nph is not None:
                    na["photo"] = data_uri(nph.read(), "image/jpeg" if nph.name.lower().endswith(("jpg", "jpeg")) else "image/png")
                ss.nodes[pick] = na; st.success("✓"); st.rerun()
    with lc2:
        st.markdown(f"**🔎 {L('txn_between')}**")
        na = st.selectbox(L("node_a"), u, index=0, key="na")
        nb = st.selectbox(L("node_b"), u, index=min(1, len(u) - 1), key="nb")
        et = network.edge_transactions(d, na, nb)
        if len(et):
            st.caption(f"{len(et)} · {L('total')} {analytics.money(et.amount.sum())}")
            show = et.copy(); show["date"] = show["date"].dt.strftime("%Y-%m-%d")
            show["amount"] = show["amount"].map(lambda x: f"{x:,.0f}")
            st.dataframe(show, use_container_width=True, hide_index=True, height=280)
        else:
            st.info(L("no_direct"))

# ---- Financial Crime ----
elif sec == "crime":
    st.markdown(f"##### {IC['typology']} {L('crime_title')} "
                f"<span class='muted'>— {len(active)} · {L('crime_note')}</span>", unsafe_allow_html=True)
    for f in active:
        col = {"High": t["red"], "Medium": t["amber"], "Low": t["green"]}[f["level"]]
        cc = st.columns([0.72, 0.14, 0.14])
        with cc[0]:
            st.markdown(
                f"<div class='find' style='border-left-color:{col}'>"
                f"<div class='ttl'>{f['icon']} {typ_title(f['key'], lang, f['title'])} "
                f"<span class='pill pill-{f['level']}'>{f['level']}</span> "
                f"<span class='pill' style='background:{t['blue']}22;color:{t['blue']};border:1px solid {t['blue']}66'>{L('conf')}: {f['confidence']}</span></div>"
                f"<div class='why'>{typ_plain(f['key'], lang)}</div></div>", unsafe_allow_html=True)
        with cc[1]:
            evidence(L("info"), typ_plain(f["key"], lang), f["evidence"], f["basis"], key=f"ev_{f['key']}")
        with cc[2]:
            if st.button(f"❌ {L('remove')}", key=f"rm_{f['key']}", use_container_width=True):
                ss.disabled.add(f["key"]); st.rerun()
    if removed:
        with st.expander(f"🗑️ {L('removed_title')}  ({len(removed)})"):
            for f in removed:
                rc = st.columns([0.8, 0.2])
                rc[0].markdown(f"{f['icon']} {typ_title(f['key'], lang, f['title'])}")
                if rc[1].button(f"↩️ {L('restore')}", key=f"rs_{f['key']}", use_container_width=True):
                    ss.disabled.discard(f["key"]); st.rerun()

# ---- Risk ----
elif sec == "risk":
    rc1, rc2 = st.columns([0.34, 0.66])
    with rc1:
        chart_header(L("risk_overall"), "risk_gauge")
        st.plotly_chart(charts.risk_gauge(score, band, t), use_container_width=True, config=PLOTLY_CFG, key="g2")
        with st.popover(f"ⓘ {L('risk_how')}"):
            st.write(L("risk_how_txt"))
    with rc2:
        chart_header(L("risk_contrib"), "risk_contrib")
        comps = [dict(title=typ_title(f["key"], lang, f["title"]), level=f["level"],
                      confidence=f["confidence"], weight=f["weight"]) for f in active]
        if comps:
            st.plotly_chart(charts.risk_components(comps, t), use_container_width=True, config=PLOTLY_CFG, key="rcc")
    st.markdown(f"##### 💡 {L('risk_meaning')}")
    for f in active:
        with st.expander(f"{f['icon']} {typ_title(f['key'], lang, f['title'])} · +{f['weight']} ({f['level']})"):
            st.write(typ_plain(f["key"], lang))
            st.caption(f["basis"])
    st.markdown(f"##### 🏦 {L('acct_cp_risk')}")
    ar = pd.DataFrame([{L("account"): a["account"], "Type": "Account", "Score": a["risk"], "Band": a["band"]} for a in R["accounts"]] +
                      [{L("account"): n, "Type": v["role"], "Score": v["score"], "Band": v["band"]}
                       for n, v in sorted(R["entity_risk"].items(), key=lambda x: -x[1]["score"])[:8]])
    st.dataframe(ar, use_container_width=True, hide_index=True,
                 column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")})

# ---- Transactions ----
elif sec == "txns":
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"##### ⬇ {L('top10_in')}")
        st.dataframe(pd.DataFrame([{L("col_date"): x["date"].strftime("%d %b %y"), L("col_cp"): x["counterparty"],
                                    L("col_method"): x["method"].title(), L("col_amount"): analytics.money_full(x["amount"])}
                                   for x in R["top_in"]]), use_container_width=True, hide_index=True)
    with c2:
        st.markdown(f"##### ⬆ {L('top10_out')}")
        st.dataframe(pd.DataFrame([{L("col_date"): x["date"].strftime("%d %b %y"), L("col_cp"): x["counterparty"],
                                    L("col_method"): x["method"].title(), L("col_amount"): analytics.money_full(x["amount"])}
                                   for x in R["top_out"]]), use_container_width=True, hide_index=True)
    st.markdown(f"##### 🧾 {L('all_txns')}")
    full = d[analytics.EVID_COLS].copy(); full["date"] = full["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(full, use_container_width=True, hide_index=True, height=420)
    st.download_button(f"⬇ {L('download_csv')}", d[loader.export_columns(d)].to_csv(index=False).encode(),
                       "filtered_transactions.csv", "text/csv")

# ---- Chat ----
elif sec == "chat":
    st.markdown(f"##### 💬 {L('chat_title')}")
    st.caption(L("chat_hint"))
    for msg in ss.chat:
        with st.chat_message(msg["role"], avatar="🛰️" if msg["role"] == "assistant" else "🧑"):
            st.markdown(msg["content"])
    if not ss.chat:
        with st.chat_message("assistant", avatar="🛰️"):
            st.markdown(L("chat_intro"))
    prompt = st.chat_input(L("chat_placeholder"))
    if prompt:
        ss.chat.append({"role": "user", "content": prompt})
        ss.chat.append({"role": "assistant", "content": chat.answer(prompt, R, d, lang)})
        st.rerun()

# ---- Export ----
elif sec == "export":
    st.markdown(f"##### {IC['export']} {L('export_title')}")
    st.caption(L("export_note"))
    catalogue = {
        L("sankey_title"): (lambda: charts.sankey(R, t, lang), info_text("sankey", lang)),
        L("tl_title"): (lambda: charts.timeline(R["timeline"], R["spikes"], t, lang), info_text("timeline", lang)),
        L("top_senders"): (lambda: charts.ranked_bar(R["senders"], "green", t), info_text("senders", lang)),
        L("top_bens"): (lambda: charts.ranked_bar(R["beneficiaries"], "red", t), info_text("beneficiaries", lang)),
        L("methods_title"): (lambda: charts.method_donut(R["methods"], t), info_text("methods", lang)),
        L("acct_throughput"): (lambda: charts.accounts_bar(R["accounts"], t), info_text("accounts", lang)),
        L("net_title"): (lambda: network.figure(d, R["entity_risk"], ss.nodes, t, height=520, lang=lang), info_text("network", lang)),
        L("risk_contrib"): (lambda: charts.risk_components(
            [dict(title=typ_title(f["key"], lang, f["title"]), level=f["level"], confidence=f["confidence"], weight=f["weight"]) for f in active], t),
            info_text("risk_contrib", lang)),
    }
    ec1, ec2 = st.columns(2)
    with ec1:
        chosen = st.multiselect(L("exhibits"), list(catalogue),
                                default=[L("sankey_title"), L("tl_title"), L("net_title"), L("risk_contrib")])
        inc_find = st.checkbox(L("inc_findings"), True)
        inc_acc = st.checkbox(L("inc_accounts"), True)
    with ec2:
        rep_title = st.text_input(L("report_title"), "Financial Intelligence Report")
        prepared = st.text_input(L("prepared_for"), "Senior Management")
        tmpl = st.file_uploader(L("tmpl_upload"), type=["pptx", "potx"])
        if tmpl is not None:
            ss.tmpl = tmpl.read(); st.success(L("tmpl_used"))
    ss.bluf_override = st.text_area("BLUF", ss.bluf_override or R["bluf"], height=100)
    ss.analyst_note = st.text_area(L("commentary"), ss.analyst_note, height=80)
    if st.button(f"🖨️ {L('gen_pptx')}", type="primary"):
        with st.spinner(L("rendering")):
            meta = dict(title=rep_title, subtitle=f"Prepared for {prepared}",
                        classification=L("classification"), reference="FIU/AML/2026/0417")
            poi = dict(name=ss.poi["name"], nationality=ss.poi["nationality"], doc_id=ss.poi["doc_id"],
                       primary_account=ss.poi["primary_account"], period=R["period_str"], photo=ss.poi.get("photo"))
            sel = [dict(title=nm, fig=catalogue[nm][0](), note=catalogue[nm][1]) for nm in chosen]
            tables = None
            if inc_acc:
                ad = analytics.account_details(d)
                acc_tbl = pd.DataFrame([{
                    L("account"): a["account"], L("col_incoming"): analytics.money(a["inflow"]),
                    L("col_outgoing"): analytics.money(a["outflow"]), L("col_balance"): analytics.money(a["balance"]),
                    L("col_spike"): L("yes") if a["spike"] else L("no")} for a in ad])
                ma = analytics.multi_account_counterparties(d, 2)
                multi_tbl = pd.DataFrame([{
                    L("col_cp"): m["counterparty"], L("cp_type"): m["type"], L("col_naccounts"): m["n_accounts"],
                    L("col_accounts"): " | ".join(m["accounts"]), L("col_incoming"): analytics.money(m["inflow"]),
                    L("col_outgoing"): analytics.money(m["outflow"])} for m in ma])
                tables = [{"title": L("acc_table_title"), "df": acc_tbl}]
                if len(multi_tbl):
                    tables.append({"title": L("multi_title"), "df": multi_tbl})
            pptx = pptx_export.build_pptx(t=t, meta=meta, bluf=ss.bluf_override or R["bluf"], poi=poi,
                                          kpis=k, overall_risk=score, overall_band=band, charts=sel,
                                          findings=active if inc_find else None,
                                          analyst_note=ss.analyst_note, template_bytes=ss.tmpl, tables=tables)
        st.success("✓")
        st.download_button(f"⬇ {L('download_pptx')}", pptx, "AML_Intelligence_Report.pptx",
                           "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                           type="primary")

st.caption(f"{ss.data_name or '—'} · {len(d):,}/{len(df_all):,} · {L('footer')}")
