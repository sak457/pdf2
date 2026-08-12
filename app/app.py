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

from datetime import datetime

from core import loader, analytics, charts, network, pptx_export, chat, i18n, auth, db, cards
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
    s.setdefault("hidden_charts", set())
    s.setdefault("hidden_tabs", set())
    s.setdefault("hide_risk", False)
    s.setdefault("bluf_edit", False)
    s.setdefault("cp_groups", [])
    s.setdefault("cp_next_id", 1)
    s.setdefault("db_session_id", None)
    s.setdefault("last_saved_hash", None)
    s.setdefault("last_upload_id", None)


_init()
ss = st.session_state
lang = ss.lang
t = theme(ss.theme)
st.markdown(app_css(t), unsafe_allow_html=True)
st.markdown(i18n.rtl_css(lang), unsafe_allow_html=True)

# initialise the database once per process; remember if the default admin
# password was used so the login/admin screens can warn about it.
if "default_admin_pw" not in ss:
    ss.default_admin_pw = db.init_db()


def L(key):
    return _T(key, lang)


# --- authentication gate -------------------------------------------------- #
if not auth.require_login(lang, _T("brand", lang)):
    st.stop()

# Role: admins can create/edit everything; normal users are read-only viewers.
EDIT = bool(ss.get("is_admin"))


def data_uri(raw, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def kpi(col, icon, label, value, sub, color):
    col.markdown(f'<div class="kpi"><div class="bar" style="background:{color}"></div>'
                 f'<div class="lbl">{icon} {label}</div>'
                 f'<div class="val" style="color:{color}">{value}</div>'
                 f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def panel(el_id, title, info_key=None, level=5):
    """Header for a hideable chart/table. Returns True when the body should
    render (i.e. the element is not hidden). Admins get a 🙈 hide button and an
    optional ⓘ info popover; the hidden set is persisted with the session."""
    if el_id in ss.hidden_charts:
        return False
    c1, c2, c3 = st.columns([0.86, 0.07, 0.07])
    c1.markdown(f"{'#' * level} {title}")
    if info_key:
        with c2.popover("ⓘ", use_container_width=True):
            st.markdown(f"**{L('info')}**")
            st.write(info_text(info_key, lang))
    if EDIT and c3.button("🙈", key=f"hide_{el_id}", help=L("hide_el"), use_container_width=True):
        ss.hidden_charts.add(el_id); st.rerun()
    return True


def chart_header(title, info_key):  # back-compat (non-hideable header)
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


def reconcile_cp(agg):
    """Ensure every counterparty belongs to exactly one (mergeable) card group."""
    existing = {m for g in ss.cp_groups for m in g["members"]}
    for nm in agg:
        if nm not in existing:
            a = agg[nm]
            # pre-fill card fields from the data (still editable by admins later)
            ss.cp_groups.append(dict(id=ss.cp_next_id, members=[nm], name=nm,
                                     account=" | ".join(a["accounts"]),
                                     type=a.get("type", "") if a.get("type") in ("Person", "Company") else "",
                                     functions=a.get("details", ""), osint=bool(a.get("osint", False))))
            ss.cp_next_id += 1
    for g in ss.cp_groups:
        g["members"] = [m for m in g["members"] if m in agg]
    ss.cp_groups = [g for g in ss.cp_groups if g["members"]]


def cp_card(g, agg):
    members = [m for m in g["members"] if m in agg]
    ti = sum(agg[m]["total_in"] for m in members)
    to = sum(agg[m]["total_out"] for m in members)
    types = {agg[m]["type"] for m in members}
    tclass = "Company" if "Company" in types else ("Person" if "Person" in types else "Unknown")
    accts = sorted({a for m in members for a in agg[m]["accounts"]})
    return dict(id=g["id"], members=members, name=g["name"],
                account=g["account"] or " | ".join(accts), type=g["type"],
                functions=g["functions"], osint=g.get("osint", False), tclass=tclass,
                total_in=ti, total_out=to, total=ti + to)


# --------------------------------------------------------------------------- #
#  Work-session persistence (SQLite)
# --------------------------------------------------------------------------- #
WORK_KEYS = ["poi", "poi_edit", "nodes", "analyst_note", "bluf_override", "df",
             "data_name", "disabled", "chat", "tmpl", "kpi_hidden", "bluf_edit",
             "cp_groups", "cp_next_id", "hidden_charts", "hidden_tabs", "hide_risk"]
WIDGET_PREFIXES = ("cpn_", "cpa_", "cpt_", "cpo_", "cpf_", "cps_", "kp_", "rm_", "rs_", "ev_",
                   "hide_", "cpin_", "cpout_", "dt_", "dc_", "dk_")
WIDGET_KEYS = {"bluf_ta", "cp_merge_sel", "node_pick", "na", "nb", "np", "navseg",
               "cp_flow_sel", "cp_sort_sel", "cp_osint_sel", "cp_desc_sel", "focusnode",
               "cp_search", "cp_type_sel", "disp_risk_chk"}


def autosave():
    """Persist the current work state to the active DB session, but only when it
    actually changed (hash-gated → zero writes on idle reruns). Only admins can
    write — normal users are read-only browsers of admin sessions."""
    sid = ss.get("db_session_id")
    if not sid or not ss.get("is_admin"):
        return
    try:
        js, h = db.serialize_state(ss)
        if h != ss.get("last_saved_hash"):
            db.save_state(sid, js, h)
            ss.last_saved_hash = h
    except Exception:
        pass


def reset_work_state():
    for k in WORK_KEYS:
        ss.pop(k, None)
    for k in [k for k in list(ss.keys())
              if str(k).startswith(WIDGET_PREFIXES) or k in WIDGET_KEYS]:
        ss.pop(k, None)
    _init()


def open_db_session(sid):
    autosave()  # flush current work before switching
    try:
        row, ndf = db.load_session(sid, ss.user)
    except Exception as e:
        st.error(str(e)); return
    reset_work_state()
    ss.df, ss.data_name = ndf, row["name"]
    js = db.load_state(sid)
    if js:
        db.restore_state(ss, js)
    ss.db_session_id = sid
    ss.last_saved_hash = db.serialize_state(ss)[1]
    if ss.get("auth_token"):
        db.set_token_session(ss.auth_token, sid)   # remember across refresh
    st.rerun()


def start_new_session(ndf, name):
    autosave()
    reset_work_state()
    ss.df, ss.data_name = ndf, name
    ss.db_session_id = db.create_session(ss.user, name, ndf)
    ss.last_saved_hash = None
    if ss.get("auth_token"):
        db.set_token_session(ss.auth_token, ss.db_session_id)   # remember across refresh
    st.rerun()


# A fresh typed-credentials login starts from a clean slate (clears any session
# or data left in memory from a previous user), so selection resets.
if ss.pop("_fresh_login", False):
    reset_work_state()
    ss.db_session_id = None
# A cookie auto-login instead restores the session the user last had open.
elif ss.pop("_restore_session", False) and ss.get("auth_token"):
    _last = db.token_last_session(ss.auth_token)
    if _last:
        try:
            open_db_session(_last)   # reruns
        except Exception:
            pass


def cp_lookup_panel(key):
    """Type-to-search an account # or name → render its counterparty card
    (read-only). Uses the global CP_CARDS computed for the current scope."""
    st.markdown(f"**🪪 {L('lookup_title')}**")
    opts = {}
    for c in sorted(CP_CARDS, key=lambda c: c["name"].lower()):
        for a in [x.strip() for x in (c["account"] or "").split("|") if x.strip()]:
            opts.setdefault(f"{a} — {c['name']}", c)
        opts.setdefault(c["name"], c)
    sel = st.selectbox(L("lookup_pick"), list(opts), index=None,
                       placeholder=L("lookup_ph"), key=key, label_visibility="collapsed")
    if sel:
        st.markdown(cards.cp_card_html(opts[sel], t, lang, max_width=360), unsafe_allow_html=True)
    else:
        st.caption(L("lookup_none"))


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
    # ---- saved work sessions ----
    st.markdown(f"**💾 {L('all_sessions')}**")
    _sessions = db.list_sessions(ss.user)
    if _sessions:
        _labels = {}
        for r in _sessions:
            lab = f"{r['name']}  ·  {r['updated_at'][5:16]}"
            if ss.get("is_admin"):
                lab += f"  ·  👤{r['username']}"
            _labels[lab] = r["id"]
        _cur_label = next((l for l, i in _labels.items() if i == ss.get("db_session_id")), None)
        pick = st.selectbox(L("my_sessions"), list(_labels),
                            index=list(_labels).index(_cur_label) if _cur_label else None,
                            placeholder="—", label_visibility="collapsed", key="sess_pick")
        if pick and _labels[pick] != ss.get("db_session_id"):
            open_db_session(_labels[pick])
        # active-session controls (admins only — users are read-only)
        if ss.get("db_session_id") and ss.get("is_admin"):
            oc1, oc2 = st.columns(2)
            with oc1.popover(f"✏️ {L('session_rename')}", use_container_width=True):
                nn = st.text_input(L("session_rename"), value=ss.get("data_name", ""), key="sess_rename")
                if st.button(L("save"), use_container_width=True, key="sess_rename_btn"):
                    db.rename_session(ss.db_session_id, nn, ss.user)
                    ss.data_name = nn; st.rerun()
            with oc2.popover(f"🗑️ {L('session_delete')}", use_container_width=True):
                if st.checkbox(L("confirm_delete"), key="sess_del_confirm") and \
                        st.button(f"🗑️ {L('session_delete')}", type="primary", use_container_width=True, key="sess_del_btn"):
                    db.delete_session(ss.db_session_id, ss.user)
                    reset_work_state(); ss.db_session_id = None; st.rerun()
    else:
        st.caption(L("no_sessions") if ss.get("is_admin") else L("viewer_readonly"))

    # New sessions (upload / sample) are admin-only; users only browse.
    if ss.get("is_admin"):
        st.markdown(f"**{IC['upload']} {L('new_session')}**")
        up = st.file_uploader(L("upload_csv"), type=["csv"], key="uploader")
        c1, c2 = st.columns(2)
        if c1.button(L("load_sample"), use_container_width=True):
            start_new_session(loader.sample_dataframe(), f"sample · {datetime.now():%Y-%m-%d %H:%M}")
        c2.download_button(L("sample_csv"), loader.sample_csv_bytes(),
                           "sample_transactions.csv", "text/csv", use_container_width=True)
        if up is not None and getattr(up, "file_id", up.name) != ss.get("last_upload_id"):
            ss.last_upload_id = getattr(up, "file_id", up.name)
            try:
                start_new_session(loader.read_csv(up), f"{up.name} · {datetime.now():%Y-%m-%d %H:%M}")
            except Exception as e:
                st.error(str(e))
    else:
        st.caption(f"🔒 {L('viewer_readonly')}")

    # ---- admin panel ----
    if ss.get("is_admin"):
        st.divider()
        with st.expander(f"👑 {L('admin_panel')}"):
            auth.admin_users_panel(lang)
            st.divider()
            st.markdown(f"**⚠ {L('wipe_db')}**")
            phrase = st.text_input(L("wipe_phrase"), key="wipe_phrase")
            if st.button(f"🗑️ {L('wipe_btn')}", type="primary", disabled=phrase != "DELETE ALL",
                         use_container_width=True):
                db.wipe_all_sessions()
                reset_work_state(); ss.db_session_id = None
                st.success(L("wipe_done")); st.rerun()

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

# counterparty card registry (editable + mergeable; persists in session)
CP_AGG = analytics.counterparty_aggregates(d)
reconcile_cp(CP_AGG)
CP_CARDS = [cp_card(g, CP_AGG) for g in ss.cp_groups if any(m in CP_AGG for m in g["members"])]

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
    if EDIT and not ss.poi_edit and st.button(f"✏️ {L('edit')}", use_container_width=True):
        ss.poi_edit = True; st.rerun()
with pc1:
    st.markdown(f"###### {IC['poi']} {L('poi_profile')}")

if EDIT and ss.poi_edit:
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
              (L("analysis_period"), R["period_str"])]
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
        if EDIT and st.button(f"✏️ {L('edit_bluf')}", use_container_width=True):
            ss.bluf_edit = not ss.bluf_edit
    if EDIT and ss.bluf_edit:
        new = st.text_area(L("edit_bluf"), value=bluf_text, height=140, key="bluf_ta")
        bc1, bc2 = st.columns(2)
        if bc1.button(f"💾 {L('save')}", use_container_width=True, type="primary"):
            ss.bluf_override = new; ss.bluf_edit = False; st.rerun()
        if bc2.button(f"↺ {L('reset_auto')}", use_container_width=True):
            ss.bluf_override = ""; ss.bluf_edit = False; st.rerun()
    else:
        st.markdown(f"<div class='bluf'><span class='tag'>{IC['bluf']} {L('bluf')}</span>"
                    f"<h2>{ss.poi['name']}</h2>"
                    f"<p style='margin:0'>{bluf_text}</p></div>", unsafe_allow_html=True)
with hc2:
    if not ss.hide_risk:
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

# --------------------------------------------------------------------------- #
#  Sections + hideable-element registry (drives the nav and the Display panel)
# --------------------------------------------------------------------------- #
SECTIONS = [("flow", IC["flow"], L("sec_flow")), ("accounts", IC["accounts"], L("sec_accounts")),
            ("timeline", IC["timeline"], L("sec_timeline")),
            ("cp", IC["counterparties"], L("sec_cp")), ("net", IC["network"], L("sec_network")),
            ("crime", IC["typology"], L("sec_crime")), ("risk", IC["riskdash"], L("sec_risk")),
            ("txns", IC["transactions"], L("sec_txns")), ("chat", "💬", L("sec_chat")),
            ("export", IC["export"], L("sec_export"))]
SEC_LABEL = {sid: f"{ic} {nm}" for sid, ic, nm in SECTIONS}
CHART_REG = [
    ("flow", [("sankey", L("sankey_title")), ("acct_throughput", L("acct_throughput")),
              ("type_split", L("inflow_by_type")), ("account_analysis", L("account_analysis"))]),
    ("accounts", [("acc_table", L("acc_table_title")), ("spike_txns", L("spike_txns_title")),
                  ("acc_top", L("acc_top_title")), ("multi_acct", L("multi_title"))]),
    ("timeline", [("timeline", L("tl_title"))]),
    ("cp", [("top_senders", L("top_senders")), ("top_bens", L("top_bens")),
            ("methods", L("methods_title")), ("cp_cards", L("cp_cards_title"))]),
    ("net", [("network", L("net_title"))]),
    ("crime", [("crime_findings", L("crime_title"))]),
    ("risk", [("risk_contrib", L("risk_contrib")), ("risk_meaning", L("risk_meaning")),
              ("acct_cp_risk", L("acct_cp_risk"))]),
    ("txns", [("top10_in", L("top10_in")), ("top10_out", L("top10_out")), ("all_txns", L("all_txns"))]),
]

# ---- Display settings: hide/unhide tabs, charts, KPIs and the risk score ----
if EDIT:
    with st.popover(f"🎛️ {L('display_settings')}"):
        st.caption(L("disp_hint"))
        dtab, dchart, dkpi, drisk = st.tabs(
            [L("disp_tabs"), L("disp_charts"), L("disp_kpis"), L("disp_risk")])
        with dtab:
            for sid, ic, nm in SECTIONS:
                shown = st.checkbox(f"{ic} {nm}", value=sid not in ss.hidden_tabs, key=f"dt_{sid}")
                (ss.hidden_tabs.discard if shown else ss.hidden_tabs.add)(sid)
        with dchart:
            for tab_id, items in CHART_REG:
                st.markdown(f"**{SEC_LABEL.get(tab_id, tab_id)}**")
                for cid, clabel in items:
                    shown = st.checkbox(clabel, value=cid not in ss.hidden_charts, key=f"dc_{cid}")
                    (ss.hidden_charts.discard if shown else ss.hidden_charts.add)(cid)
        with dkpi:
            for sid, icon, label, *_ in STATS:
                shown = st.checkbox(f"{icon} {label}", value=sid not in ss.kpi_hidden, key=f"kp_{sid}")
                (ss.kpi_hidden.discard if shown else ss.kpi_hidden.add)(sid)
        with drisk:
            ss.hide_risk = not st.checkbox(L("disp_show_risk"), value=not ss.hide_risk, key="disp_risk_chk")

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
#  Navigation (hidden tabs are dropped from the nav)
# --------------------------------------------------------------------------- #
visible_sections = [s for s in SECTIONS if s[0] not in ss.hidden_tabs] or SECTIONS
labels = [f"{ic} {nm}" for _, ic, nm in visible_sections]
choice = st.segmented_control("nav", labels, default=labels[0],
                              label_visibility="collapsed", key="navseg") or labels[0]
sec = visible_sections[labels.index(choice)][0] if choice in labels else visible_sections[0][0]

# ---- Floating counterparty-lookup FAB (visible on every tab) ----
with st.container(key="cp_fab"):
    with st.popover("🪪", use_container_width=False):
        st.markdown("<div class='cp-fab-mark'></div>", unsafe_allow_html=True)
        cp_lookup_panel("cp_lookup_fab")

# ---- Money Flow ----
if sec == "flow":
    c1, c2 = st.columns([0.62, 0.38])
    with c1:
        if panel("sankey", L("sankey_title"), "sankey"):
            st.plotly_chart(charts.sankey(R, t, lang), use_container_width=True, config=PLOTLY_CFG, key="sk")
    with c2:
        if panel("acct_throughput", L("acct_throughput"), "accounts"):
            st.plotly_chart(charts.accounts_bar(R["accounts"], t), use_container_width=True, config=PLOTLY_CFG, key="ab")
        if panel("type_split", L("inflow_by_type"), "type_split"):
            st.plotly_chart(charts.type_split(d, t), use_container_width=True, config=PLOTLY_CFG, key="ts")
    if panel("account_analysis", f"🏦 {L('account_analysis')}"):
        st.dataframe(pd.DataFrame([{
            L("account"): a["account"], L("kpi_in"): analytics.money(a["inflow"]),
            L("kpi_out"): analytics.money(a["outflow"]), L("kpi_txns"): a["count"],
            L("kpi_largest"): analytics.money(a["largest"]), L("col_cp"): a["top_counterparty"],
            L("sec_risk"): f"{a['risk']} ({a['band']})"} for a in R["accounts"]]),
            use_container_width=True, hide_index=True)

# ---- Accounts Details ----
elif sec == "accounts":
    ad = analytics.account_details(d)
    if panel("acc_table", L("acc_table_title"), "accounts"):
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
    if spiky and panel("spike_txns", f"⚡ {L('spike_txns_title')}"):
        for a in spiky:
            stx = analytics.account_spike_txns(d, a["account"], a["spike_months"])
            with st.expander(L("spike_view").format(acc=a["account"], n=len(stx))):
                sh = stx.copy()
                sh["date"] = pd.to_datetime(sh["date"]).dt.strftime("%Y-%m-%d")
                sh["flow"] = sh["flow"].map(lambda x: ("🟢 " + L("flow_in")) if x == "IN" else ("🔴 " + L("flow_out")))
                if "amount" in sh:
                    sh["amount"] = sh["amount"].map(lambda x: f"{x:,.0f}")
                sh = sh.rename(columns={"flow": L("col_flow")})  # all dataset columns kept
                st.dataframe(sh, use_container_width=True, hide_index=True, height=min(340, 44 + 28 * len(sh)))

    if panel("acc_top", f"👥 {L('acc_top_title')}"):
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

    if panel("multi_acct", f"🔗 {L('multi_title')}"):
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
    if panel("timeline", L("tl_title"), "timeline"):
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
        if panel("top_senders", L("top_senders"), "senders"):
            st.plotly_chart(charts.ranked_bar(R["senders"], "green", t), use_container_width=True, config=PLOTLY_CFG, key="rs")
    with c2:
        if panel("top_bens", L("top_bens"), "beneficiaries"):
            st.plotly_chart(charts.ranked_bar(R["beneficiaries"], "red", t), use_container_width=True, config=PLOTLY_CFG, key="rb")
    if panel("methods", L("methods_title"), "methods"):
        mc1, mc2 = st.columns(2)
        mc1.plotly_chart(charts.method_donut(R["methods"], t), use_container_width=True, config=PLOTLY_CFG, key="md")
        mc2.plotly_chart(charts.method_bar(R["methods"], t), use_container_width=True, config=PLOTLY_CFG, key="mbar")

    # ---- editable, mergeable counterparty cards ----
    st.divider()
    if panel("cp_cards", f"🪪 {L('cp_cards_title')} · {len(CP_CARDS)} {L('cp_count')}"):
        # search + type filter
        srow = st.columns([0.55, 0.45])
        q = srow[0].text_input(L("cp_search"), key="cp_search", placeholder=L("cp_search"),
                               label_visibility="collapsed")
        cp_type_f = srow[1].segmented_control(
            L("cp_type_filter"), [L("cp_type_all"), L("cp_type_company"), L("cp_type_person"), L("cp_type_unknown")],
            default=L("cp_type_all"), key="cp_type_sel")
        fcol = st.columns([0.3, 0.26, 0.28, 0.16])
        flow = fcol[0].segmented_control(
            L("cp_flow"), [L("cp_flow_all"), L("cp_flow_in"), L("cp_flow_out"), L("cp_flow_both")],
            default=L("cp_flow_all"), key="cp_flow_sel")
        sort_by = fcol[1].selectbox(L("cp_sort"), [L("cp_sort_in"), L("cp_sort_out"), L("cp_sort_name")], key="cp_sort_sel")
        osint_f = fcol[2].segmented_control(
            L("cp_osint_filter"), [L("cp_osint_all"), L("cp_osint_yes"), L("cp_osint_no")],
            default=L("cp_osint_all"), key="cp_osint_sel")
        desc = fcol[3].toggle(L("cp_desc"), value=True, key="cp_desc_sel")

        # merge control (admins only)
        if EDIT:
            label_of = {f"{c['name']} · {c['account'] or '—'}  [#{c['id']}]": c["id"] for c in CP_CARDS}
            msel = st.multiselect(L("cp_merge_label"), list(label_of), key="cp_merge_sel")
            if st.button(f"🔗 {L('cp_merge_btn')}", disabled=len(msel) < 2):
                ids = {label_of[l] for l in msel}
                groups = [g for g in ss.cp_groups if g["id"] in ids]
                members = [m for g in groups for m in g["members"]]
                accts = " | ".join(sorted({a for g in groups for a in (g["account"].split(" | ") if g["account"] else []) if a}))
                first = groups[0]
                newg = dict(id=ss.cp_next_id, members=members, name=first["name"], account=accts,
                            type=first["type"] or next((g["type"] for g in groups if g["type"]), ""),
                            functions=first["functions"] or next((g["functions"] for g in groups if g["functions"]), ""),
                            osint=any(g.get("osint") for g in groups))
                ss.cp_next_id += 1
                ss.cp_groups = [g for g in ss.cp_groups if g["id"] not in ids] + [newg]
                st.rerun()

        # filter + sort
        cards = CP_CARDS
        if q:
            ql = q.strip().lower()
            cards = [c for c in cards if ql in (c["name"] or "").lower() or ql in (c["account"] or "").lower()]
        _tc = {L("cp_type_company"): "Company", L("cp_type_person"): "Person", L("cp_type_unknown"): "Unknown"}.get(cp_type_f)
        if _tc:
            cards = [c for c in cards if c["tclass"] == _tc]
        if flow == L("cp_flow_in"):
            cards = [c for c in cards if c["total_in"] > 0]
        elif flow == L("cp_flow_out"):
            cards = [c for c in cards if c["total_out"] > 0]
        elif flow == L("cp_flow_both"):
            cards = [c for c in cards if c["total_in"] > 0 and c["total_out"] > 0]
        if osint_f == L("cp_osint_yes"):
            cards = [c for c in cards if c["osint"]]
        elif osint_f == L("cp_osint_no"):
            cards = [c for c in cards if not c["osint"]]
        keyf = {L("cp_sort_in"): lambda c: c["total_in"], L("cp_sort_out"): lambda c: c["total_out"],
                L("cp_sort_name"): lambda c: c["name"].lower()}[sort_by]
        cards = sorted(cards, key=keyf, reverse=desc if sort_by != L("cp_sort_name") else not desc)

        def _cp_ev(edf):
            if len(edf):
                sh = edf.copy(); sh["date"] = pd.to_datetime(sh["date"]).dt.strftime("%Y-%m-%d")
                sh["amount"] = sh["amount"].map(lambda x: f"{x:,.0f}")
                st.dataframe(sh, use_container_width=True, hide_index=True, height=min(300, 44 + 28 * len(sh)))
            else:
                st.caption("—")

        icon_of = {"Company": "🏢", "Person": "👤", "Unknown": "❓"}
        grp_by_id = {g["id"]: g for g in ss.cp_groups}
        per_row = 3
        for i in range(0, len(cards), per_row):
            cols = st.columns(per_row)
            for j, c in enumerate(cards[i:i + per_row]):
                g = grp_by_id[c["id"]]
                with cols[j].container(border=True):
                    hc = st.columns([0.16, 0.84])
                    hc[0].markdown(f"<div style='font-size:30px'>{icon_of.get(c['tclass'],'❓')}</div>",
                                   unsafe_allow_html=True)
                    if EDIT:
                        g["name"] = hc[1].text_input(L("col_cp"), value=g["name"], key=f"cpn_{c['id']}",
                                                     label_visibility="collapsed")
                        g["account"] = st.text_input(L("cp_account"), value=g["account"], key=f"cpa_{c['id']}")
                        g["type"] = st.text_input(L("cp_type_field"), value=g["type"], key=f"cpt_{c['id']}",
                                                  placeholder=L("cp_fill"))
                        g["osint"] = st.toggle(f"🔎 {L('cp_osint')}", value=g.get("osint", False), key=f"cpo_{c['id']}")
                        g["functions"] = st.text_area(L("cp_functions"), value=g["functions"], key=f"cpf_{c['id']}",
                                                      placeholder=L("cp_fill"), height=80)
                    else:
                        hc[1].markdown(f"**{g['name'] or '—'}**")
                        st.markdown(
                            f"**{L('cp_account')}:** {g['account'] or '—'}  \n"
                            f"**{L('cp_type_field')}:** {g['type'] or '—'}  \n"
                            f"🔎 {L('cp_osint')}: {'✓' if g.get('osint') else '—'}")
                        if g["functions"]:
                            st.caption(f"{L('cp_functions')}: {g['functions']}")
                    st.markdown(
                        f"<div style='display:flex;gap:8px;margin-top:4px'>"
                        f"<div style='flex:1;background:{t['green']}1e;border:1px solid {t['green']}66;border-radius:8px;padding:6px 9px'>"
                        f"<div style='font-size:10px;color:{t['mute']};font-family:var(--mono)'>⬇ {L('cp_in')}</div>"
                        f"<div style='font-family:var(--mono);font-weight:700;color:{t['green']}'>{analytics.money(c['total_in'])}</div></div>"
                        f"<div style='flex:1;background:{t['red']}1e;border:1px solid {t['red']}66;border-radius:8px;padding:6px 9px'>"
                        f"<div style='font-size:10px;color:{t['mute']};font-family:var(--mono)'>⬆ {L('cp_out')}</div>"
                        f"<div style='font-family:var(--mono);font-weight:700;color:{t['red']}'>{analytics.money(c['total_out'])}</div></div></div>",
                        unsafe_allow_html=True)
                    # in/out evidence (merge-aware: covers every member's transactions)
                    _sub = d[d.counterparty.isin(c["members"])]
                    ev1, ev2 = st.columns(2)
                    with ev1.popover(f"⬇ {L('cp_ev_in')}", use_container_width=True):
                        _cp_ev(_sub[_sub.direction == "in"][analytics.EVID_COLS])
                    with ev2.popover(f"⬆ {L('cp_ev_out')}", use_container_width=True):
                        _cp_ev(_sub[_sub.direction == "out"][analytics.EVID_COLS])
                    if len(c["members"]) > 1:
                        st.caption(f"🔗 {L('cp_merged_of')}: " + ", ".join(c["members"]))
                        if EDIT and st.button(f"✂️ {L('cp_split')}", key=f"cps_{c['id']}", use_container_width=True):
                            ss.cp_groups = [x for x in ss.cp_groups if x["id"] != c["id"]]
                            st.rerun()

# ---- Link Analysis ----
elif sec == "net":
    import streamlit.components.v1 as components
    _net_open = panel("network", L("net_title"), "network")
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
    if _net_open:
        chips = " ".join(
            f"<span style='display:inline-flex;align-items:center;gap:7px;margin-inline-end:16px;"
            f"font-family:var(--mono);font-size:12px;color:{t['mute']}'>"
            f"{swatch(shape, c)}{lab}</span>" for shape, c, lab in lg)
        st.markdown(f"<div class='card' style='padding:10px 14px'>{chips}</div>", unsafe_allow_html=True)
        st.caption("🖱️ " + L("net_help"))
        cp_by_member = {m: c for c in CP_CARDS for m in c["members"]}

        # filter the graph to the transactions between two chosen nodes
        u = network.node_universe(d)
        ALL = L("cp_flow_all")
        fc = st.columns(2)
        na = fc[0].selectbox(L("node_a"), [ALL] + u, index=0, key="na")
        nb = fc[1].selectbox(L("node_b"), [ALL] + u, index=0, key="nb")
        pair = na != ALL and nb != ALL and na != nb
        gdf = network.edge_subset(d, na, nb) if pair else d

        if pair and not len(gdf):
            st.info(L("no_direct"))
        else:
            html = network.pyvis_html(gdf, R["entity_risk"], {}, t, height=620, lang=lang,
                                      cp_info=cp_by_member)
            components.html(html, height=650, scrolling=False)
            if pair:
                et = network.edge_transactions(d, na, nb)
                st.caption(f"{len(et)} · {L('total')} {analytics.money(et.amount.sum())}")
                show = et.copy(); show["date"] = show["date"].dt.strftime("%Y-%m-%d")
                show["amount"] = show["amount"].map(lambda x: f"{x:,.0f}")
                st.dataframe(show, use_container_width=True, hide_index=True, height=280)

# ---- Financial Crime ----
elif sec == "crime":
    if panel("crime_findings", f"{IC['typology']} {L('crime_title')} — {len(active)} · {L('crime_note')}"):
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
                if EDIT and st.button(f"❌ {L('remove')}", key=f"rm_{f['key']}", use_container_width=True):
                    ss.disabled.add(f["key"]); st.rerun()
        if removed:
            with st.expander(f"🗑️ {L('removed_title')}  ({len(removed)})"):
                for f in removed:
                    rc = st.columns([0.8, 0.2])
                    rc[0].markdown(f"{f['icon']} {typ_title(f['key'], lang, f['title'])}")
                    if EDIT and rc[1].button(f"↩️ {L('restore')}", key=f"rs_{f['key']}", use_container_width=True):
                        ss.disabled.discard(f["key"]); st.rerun()

# ---- Risk ----
elif sec == "risk":
    rc1, rc2 = st.columns([0.34, 0.66])
    with rc1:
        if not ss.hide_risk:
            chart_header(L("risk_overall"), "risk_gauge")
            st.plotly_chart(charts.risk_gauge(score, band, t), use_container_width=True, config=PLOTLY_CFG, key="g2")
            with st.popover(f"ⓘ {L('risk_how')}"):
                st.write(L("risk_how_txt"))
    with rc2:
        if panel("risk_contrib", L("risk_contrib"), "risk_contrib"):
            comps = [dict(title=typ_title(f["key"], lang, f["title"]), level=f["level"],
                          confidence=f["confidence"], weight=f["weight"]) for f in active]
            if comps:
                st.plotly_chart(charts.risk_components(comps, t), use_container_width=True, config=PLOTLY_CFG, key="rcc")
    if panel("risk_meaning", f"💡 {L('risk_meaning')}"):
        for f in active:
            with st.expander(f"{f['icon']} {typ_title(f['key'], lang, f['title'])} · +{f['weight']} ({f['level']})"):
                st.write(typ_plain(f["key"], lang))
                st.caption(f["basis"])
    if panel("acct_cp_risk", f"🏦 {L('acct_cp_risk')}"):
        ar = pd.DataFrame([{L("account"): a["account"], "Type": "Account", "Score": a["risk"], "Band": a["band"]} for a in R["accounts"]] +
                          [{L("account"): n, "Type": v["role"], "Score": v["score"], "Band": v["band"]}
                           for n, v in sorted(R["entity_risk"].items(), key=lambda x: -x[1]["score"])[:8]])
        st.dataframe(ar, use_container_width=True, hide_index=True,
                     column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")})

# ---- Transactions ----
elif sec == "txns":
    c1, c2 = st.columns(2)
    with c1:
        if panel("top10_in", f"⬇ {L('top10_in')}"):
            st.dataframe(pd.DataFrame([{L("col_date"): x["date"].strftime("%d %b %y"), L("col_cp"): x["counterparty"],
                                        L("col_method"): x["method"].title(), L("col_amount"): analytics.money_full(x["amount"])}
                                       for x in R["top_in"]]), use_container_width=True, hide_index=True)
    with c2:
        if panel("top10_out", f"⬆ {L('top10_out')}"):
            st.dataframe(pd.DataFrame([{L("col_date"): x["date"].strftime("%d %b %y"), L("col_cp"): x["counterparty"],
                                        L("col_method"): x["method"].title(), L("col_amount"): analytics.money_full(x["amount"])}
                                       for x in R["top_out"]]), use_container_width=True, hide_index=True)
    if panel("all_txns", f"🧾 {L('all_txns')}"):
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
    if EDIT:
        prompt = st.chat_input(L("chat_placeholder"))
        if prompt:
            ss.chat.append({"role": "user", "content": prompt})
            ss.chat.append({"role": "assistant", "content": chat.answer(prompt, R, d, lang)})
            st.rerun()
    else:
        st.caption(f"🔒 {L('viewer_readonly')}")

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
        inc_cp = st.checkbox(L("cp_export_inc"), False)
        cp_mode, cp_pick = None, []
        if inc_cp:
            cp_mode = st.radio(L("cp_export_mode"),
                               [L("cp_top5"), L("cp_top10"), L("cp_custom")], horizontal=True)
            if cp_mode == L("cp_custom"):
                cp_lbl = {f"{c['name']} · {c['account'] or '—'}": c["id"] for c in CP_CARDS}
                cp_pick = [cp_lbl[x] for x in st.multiselect(L("cp_pick"), list(cp_lbl))]
    with ec2:
        rep_title = st.text_input(L("report_title"), "Financial Intelligence Report")
        prepared = st.text_input(L("prepared_for"), "Senior Management")
        if EDIT:
            tmpl = st.file_uploader(L("tmpl_upload"), type=["pptx", "potx"])
            if tmpl is not None:
                ss.tmpl = tmpl.read(); st.success(L("tmpl_used"))
    if EDIT:
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
            if inc_cp:
                ordered = sorted(CP_CARDS, key=lambda c: c["total"], reverse=True)
                if cp_mode == L("cp_top5"):
                    picks = ordered[:5]
                elif cp_mode == L("cp_top10"):
                    picks = ordered[:10]
                else:
                    picks = [c for c in ordered if c["id"] in cp_pick]
                if picks:
                    cp_tbl = pd.DataFrame([{
                        L("col_cp"): c["name"], L("cp_account"): c["account"] or "—",
                        L("cp_type_field"): c["type"] or "—", L("cp_functions"): c["functions"] or "—",
                        L("cp_in"): analytics.money(c["total_in"]),
                        L("cp_out"): analytics.money(c["total_out"])} for c in picks])
                    tables = (tables or []) + [{"title": L("cp_export_title"), "df": cp_tbl}]
            pptx = pptx_export.build_pptx(t=t, meta=meta, bluf=ss.bluf_override or R["bluf"], poi=poi,
                                          kpis=k, overall_risk=score, overall_band=band, charts=sel,
                                          findings=active if inc_find else None,
                                          analyst_note=ss.analyst_note, template_bytes=ss.tmpl, tables=tables)
        st.success("✓")
        st.download_button(f"⬇ {L('download_pptx')}", pptx, "AML_Intelligence_Report.pptx",
                           "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                           type="primary")

st.caption(f"{ss.data_name or '—'} · {len(d):,}/{len(df_all):,} · {L('footer')}")

# persist any changes made during this run (hash-gated → no-op if unchanged)
autosave()
