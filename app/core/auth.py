"""
Lightweight login gate (basic authentication).

Credential sources, in priority order:
  1. st.secrets["auth"]  → { username: password_or_sha256, ... }
  2. env AML_USERS       → "user1:pass1,user2:pass2"
  3. built-in demo default → analyst / aml2026  (change before real use)

Passwords may be given as plaintext or as a pre-computed sha256 hex digest;
comparison is constant-time. This is a simple front-door for a single-analyst
tool, not an identity provider — put the app behind your own SSO/VPN for
production use.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import streamlit as st

from . import i18n


def _sha(p: str) -> str:
    return hashlib.sha256(str(p).encode()).hexdigest()


def _norm(p: str) -> str:
    p = str(p)
    if len(p) == 64 and all(c in "0123456789abcdef" for c in p.lower()):
        return p.lower()
    return _sha(p)


def _users() -> dict:
    try:
        if "auth" in st.secrets:
            return {str(u): _norm(pw) for u, pw in st.secrets["auth"].items()}
    except Exception:
        pass
    env = os.environ.get("AML_USERS", "").strip()
    if env:
        d = {}
        for pair in env.split(","):
            if ":" in pair:
                u, pw = pair.split(":", 1)
                d[u.strip()] = _norm(pw.strip())
        if d:
            return d
    return {"analyst": _sha("aml2026"), "admin": _sha("admin")}


def _check(user: str, pw: str, users: dict) -> bool:
    h = users.get(user)
    return bool(h) and hmac.compare_digest(h, _sha(pw))


def require_login(lang: str = "en", brand: str = "AML INTELLIGENCE TERMINAL") -> bool:
    ss = st.session_state
    if ss.get("authed"):
        return True

    def T(k):
        return i18n.T(k, lang)

    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(
            f"<div class='bluf' style='text-align:center'>"
            f"<span class='tag'>🔒 {T('login_secure')}</span>"
            f"<h2>🛰️ {brand}</h2>"
            f"<p class='muted'>{T('login_prompt')}</p></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input(T("username"))
            p = st.text_input(T("password"), type="password")
            ok = st.form_submit_button(f"🔓 {T('login_btn')}", use_container_width=True, type="primary")
        if ok:
            if _check(u.strip(), p, _users()):
                ss.authed = True
                ss.user = u.strip()
                st.rerun()
            else:
                st.error(T("login_bad"))
        st.caption(T("login_hint"))
    return False


def logout_button(lang: str = "en"):
    ss = st.session_state
    if ss.get("authed"):
        st.sidebar.caption(f"👤 {ss.get('user', '')}")
        if st.sidebar.button(f"🔓 {i18n.T('logout', lang)}", use_container_width=True):
            ss.pop("authed", None)
            ss.pop("user", None)
            st.rerun()
