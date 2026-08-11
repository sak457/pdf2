"""
Login gate + user administration (DB-backed).

Credentials live in the SQLite ``users`` table (PBKDF2-hashed). The set of admin
usernames comes only from the ``AML_ADMIN_USERS`` env var (default "admin") — a
database write can never grant admin. The very first run bootstraps the admin
account from ``AML_ADMIN_PASSWORD`` (default "admin", with a change-me warning).
"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from . import db, i18n

COOKIE = "aml_auth"  # persistent-login cookie name


def _cookie_token() -> str | None:
    """Raw token from the browser cookie (server-side, read-only)."""
    try:
        return st.context.cookies.get(COOKIE)
    except Exception:
        return None


def _sync_cookie(ss) -> None:
    """Emit the one-shot cookie write/clear queued by login/logout. Runs on
    every require_login call so it fires even when we stop() after logout."""
    raw = ss.pop("_pending_cookie", None)
    if raw:
        maxage = db.TOKEN_TTL_HOURS * 3600
        val = json.dumps(f"{COOKIE}={raw}; path=/; max-age={maxage}; SameSite=Lax")
        components.html(f"<script>document.cookie={val};</script>", height=0)
    if ss.pop("_clear_cookie", None):
        val = json.dumps(f"{COOKIE}=; path=/; max-age=0; SameSite=Lax")
        components.html(f"<script>document.cookie={val};</script>", height=0)


def require_login(lang: str = "en", brand: str = "AML INTELLIGENCE TERMINAL") -> bool:
    ss = st.session_state
    _sync_cookie(ss)
    if ss.get("authed"):
        return True

    # Stay-logged-in: a valid cookie token auto-authenticates without the form.
    raw = _cookie_token()
    if raw:
        user = db.verify_token(raw)
        if user:
            ss.authed = True
            ss.user = user
            ss.is_admin = db.is_admin(user)
            ss.auth_token = raw
            ss._restore_session = True   # reopen the remembered session
            st.rerun()

    def T(k):
        return i18n.T(k, lang)

    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(
            f"<div class='bluf' style='text-align:center'>"
            f"<span class='tag'>🔒 {T('login_secure')}</span>"
            f"<h2>🛰️ {brand}</h2>"
            f"<p class='muted'>{T('login_prompt')}</p></div>", unsafe_allow_html=True)
        if ss.get("default_admin_pw"):
            st.warning(T("default_pw_warn"))
        with st.form("login_form"):
            u = st.text_input(T("username"))
            p = st.text_input(T("password"), type="password")
            ok = st.form_submit_button(f"🔓 {T('login_btn')}", use_container_width=True, type="primary")
        if ok:
            if db.verify_user(u.strip(), p):
                ss.authed = True
                ss.user = u.strip()
                ss.is_admin = db.is_admin(u.strip())
                # Issue a fresh persistent-login token + set the cookie.
                ss.auth_token = db.create_token(ss.user)
                ss._pending_cookie = ss.auth_token
                ss._fresh_login = True   # typed login clears any prior session/data
                st.rerun()
            else:
                st.error(T("login_bad"))
        st.caption(T("login_hint"))
    return False


def logout_button(lang: str = "en"):
    ss = st.session_state
    if ss.get("authed"):
        tag = " · 👑" if ss.get("is_admin") else ""
        st.sidebar.caption(f"👤 {ss.get('user', '')}{tag}")
        if st.sidebar.button(f"🔓 {i18n.T('logout', lang)}", use_container_width=True):
            db.delete_token(ss.get("auth_token"))
            ss._clear_cookie = True
            for k in ("authed", "user", "is_admin", "auth_token", "db_session_id"):
                ss.pop(k, None)
            st.rerun()


def admin_users_panel(lang: str = "en"):
    """User management UI (admins only). Rendered inside an admin expander."""
    def T(k):
        return i18n.T(k, lang)

    ss = st.session_state
    users = db.list_users()
    st.markdown(f"**{T('manage_users')}**")
    st.dataframe(
        [{T("username"): u["username"], "": "👑" if db.is_admin(u["username"]) else "",
          T("session_rename"): u["created_by"] or "—"} for u in users],
        use_container_width=True, hide_index=True)

    with st.form("add_user_form", clear_on_submit=True):
        st.caption(f"➕ {T('add_user')}")
        nu = st.text_input(T("new_username"), key="au_user")
        npw = st.text_input(T("new_password"), type="password", key="au_pw")
        if st.form_submit_button(T("add_user"), use_container_width=True):
            try:
                db.create_user(nu.strip(), npw, created_by=ss.get("user"))
                st.success("✓"); st.rerun()
            except ValueError as e:
                st.error(str(e))

    names = [u["username"] for u in users]
    with st.form("reset_pw_form", clear_on_submit=True):
        st.caption(f"🔑 {T('reset_pw')}")
        ru = st.selectbox(T("username"), names, key="rp_user")
        rpw = st.text_input(T("new_password"), type="password", key="rp_pw")
        if st.form_submit_button(T("reset_pw"), use_container_width=True) and rpw:
            db.set_password(ru, rpw); st.success("✓")

    deletable = [n for n in names if not db.is_admin(n) and n != ss.get("user")]
    if deletable:
        du = st.selectbox(T("delete_user"), deletable, key="du_user")
        st.caption("⚠ " + T("session_delete"))
        if st.checkbox(T("confirm_delete"), key="du_confirm") and \
                st.button(f"🗑️ {T('delete_user')}", use_container_width=True):
            db.delete_user(du); st.success("✓"); st.rerun()
