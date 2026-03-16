# ui/login.py
# Login page — shown to unauthenticated users.
# Calls auth_service.authenticate() and sets session state.
 
import os
import streamlit as st
from services.auth_service import authenticate, is_locked_out, generate_auth_token
from ui.components import get_logo_b64
from config import MAX_LOGIN_ATTEMPTS
 
 
def login_page():
    """Renders the login form and handles authentication."""
 
    # ── Layout ────────────────────────────────────────────
    st.markdown("""
    <style>
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    .block-container { max-width: 420px !important;
                       padding-top: 3rem !important; }
    </style>
    """, unsafe_allow_html=True)
 
    # ── Logo ──────────────────────────────────────────────
    b64 = get_logo_b64()
    if b64:
        mime = 'image/png' if os.path.exists('assets/logo.png') else 'image/jpeg'
        st.markdown(
            f'<div style="text-align:center;margin-bottom:1.5rem;">'
            f'<img src="data:{mime};base64,{b64}" '
            f'style="width:90px;border-radius:12px;"></div>',
            unsafe_allow_html=True)
 
    st.markdown(
        '<h2 style="text-align:center;font-weight:800;'
        'margin-bottom:.25rem;">Tara G</h2>'
        '<p style="text-align:center;color:#767676;'
        'margin-bottom:1.5rem;font-size:.9rem;">Inventory Management</p>',
        unsafe_allow_html=True)
 
    # ── Form ──────────────────────────────────────────────
    with st.form('login_form'):
        username = st.text_input('Username', placeholder='Enter username')
        password = st.text_input('Password', type='password',
                                 placeholder='Enter password')
        submitted = st.form_submit_button(
            'Sign In', use_container_width=True, type='primary')
 
    if not submitted:
        return
 
    if not username or not password:
        st.error('Please enter both username and password.')
        return
 
    # ── Lockout check ─────────────────────────────────────
    locked, secs = is_locked_out(username)
    if locked:
        mins     = secs // 60
        secs_rem = secs % 60
        st.error(
            f'Account locked. '
            f'Try again in {mins}m {secs_rem}s.')
        return
 
    # ── Authenticate ──────────────────────────────────────
    with st.spinner('Signing in…'):
        success, role, message = authenticate(username, password)
 
    if success:
        token = generate_auth_token(username.strip(), role)
        st.session_state.logged_in = True
        st.session_state.username  = username.strip()
        st.session_state.role      = role
        st.query_params['t']       = token
        st.rerun()
    else:
        st.error(message)
