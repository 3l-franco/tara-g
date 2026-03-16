# app.py
# ─────────────────────────────────────────────────────────
# Tara G Inventory Management System
# Entry point only — all logic lives in services/ and ui/
# To run: streamlit run app.py
# ─────────────────────────────────────────────────────────

import os
import time
import streamlit as st
from PIL import Image as PILImage

from routers.admin_router import admin_router
from routers.staff_router import staff_router
from ui.login             import login_page
from services.auth_service import verify_auth_token
from config               import SESSION_TIMEOUT_SECONDS


def _page_icon():
    """Loads the logo as the browser tab icon."""
    for f in ['assets/App.png', 'assets/logo.png', 'assets/logo.jpg']:
        if os.path.exists(f):
            try:
                return PILImage.open(f)
            except Exception:
                pass
    return None


st.set_page_config(
    page_title='Tara G Inventory',
    page_icon=_page_icon(),
    layout='wide',
    initial_sidebar_state='expanded',
)

# Load Material Icons font for sidebar collapse button
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, '
    'maximum-scale=1.0, user-scalable=no">'
    '<link href="https://fonts.googleapis.com/icon?'
    'family=Material+Icons" rel="stylesheet">',
    unsafe_allow_html=True)


def init_state():
    """
    Initializes all session state keys with safe defaults.
    Only sets a key if it doesn't already exist —
    so navigating around never resets live state.
    """
    defaults = {
        'logged_in':    False,
        'username':     '',
        'role':         '',
        'staff_page':   'stock',
        'staff_pending': None,
        'last_activity': time.time(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def main():
    init_state()

    # ── Auto-login from persisted URL token ────────────────
    if not st.session_state.logged_in:
        token = st.query_params.get('t')
        if token:
            result = verify_auth_token(token)
            if result:
                username, role = result
                st.session_state.logged_in    = True
                st.session_state.username     = username
                st.session_state.role         = role
                st.session_state.last_activity = time.time()
            else:
                del st.query_params['t']

    # ── Session timeout ───────────────────────────────────
    if st.session_state.logged_in:
        elapsed = time.time() - st.session_state.get('last_activity', 0)
        if elapsed > SESSION_TIMEOUT_SECONDS:
            # Always force logout on inactivity — the URL token must NOT
            # bypass this so stolen sessions have a bounded exposure window.
            st.session_state.clear()
            init_state()
            st.query_params.clear()
            st.info('Session expired due to inactivity. Please log in again.')
            st.stop()
        else:
            st.session_state.last_activity = time.time()

    if not st.session_state.logged_in:
        login_page()
    elif st.session_state.role == 'admin':
        admin_router()
    elif st.session_state.role == 'staff':
        staff_router()
    else:
        st.error('Unknown role. Please log out and try again.')
        if st.button('Logout'):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()


if __name__ == '__main__':
    main()
