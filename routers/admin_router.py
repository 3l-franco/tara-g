# routers/admin_router.py

import os
import streamlit as st
from ui.components import get_logo_b64, esc, compute_status
from services.sheets_client import read_df
from ui.admin.dashboard       import page_dashboard
from ui.admin.inventory       import page_inventory
from ui.admin.products_stock  import page_products_stock
from ui.admin.suppliers       import page_suppliers
from ui.admin.transactions    import page_transactions
from ui.admin.users           import page_users


# Page definitions: key → (label, page_fn)
PAGES = [
    ('Dashboard',        page_dashboard),
    ('Inventory',        page_inventory),
    ('Products & Stock', page_products_stock),
    ('Suppliers',        page_suppliers),
    ('Transaction Logs', page_transactions),
    ('Users & System',   page_users),
]

DEFAULT_PAGE = 'Dashboard'


def _load_admin_css():
    css_file = 'styles/admin.css'
    if os.path.exists(css_file):
        with open(css_file, encoding='utf-8') as f:
            st.markdown(
                f'<style>{f.read()}</style>', unsafe_allow_html=True)


def _sidebar_logo():
    b64 = get_logo_b64()
    if b64:
        import os as _os
        mime = ('image/png' if _os.path.exists('assets/logo.png')
                else 'image/jpeg')
        st.markdown(
            f'<div style="text-align:center;margin:0 0 .5rem 0;">'
            f'<img src="data:{mime};base64,{b64}" alt="Tara G logo" '
            f'style="width:80px;border-radius:8px;"></div>',
            unsafe_allow_html=True)


def _sidebar_user():
    role     = st.session_state.get('role', '').upper()
    username = st.session_state.get('username', '')
    st.markdown(
        f'<div style="text-align:center;margin:.2rem 0 .6rem 0;">'
        f'<p style="font-size:.75rem;font-weight:700;letter-spacing:2px;'
        f'text-transform:uppercase;color:#767676;margin:0 0 2px 0;">'
        f'{esc(role)}</p>'
        f'<p style="font-size:.85rem;font-weight:600;color:#444;margin:0;">'
        f'@{esc(username)}</p>'
        f'</div>',
        unsafe_allow_html=True)


def _get_critical_count():
    """Get count of critical+low stock items for sidebar badge."""
    try:
        df = read_df('products')
        if df.empty:
            return 0
        df = compute_status(df)
        return len(df[df['status'].isin(['Critical', 'Low'])])
    except Exception:
        return 0


def _sidebar_nav():
    """Custom HTML sidebar nav with active state + badge."""
    if 'admin_page' not in st.session_state:
        st.session_state['admin_page'] = DEFAULT_PAGE

    current = st.session_state['admin_page']
    crit_count = _get_critical_count()

    # Render each nav button using Streamlit buttons
    for label, _ in PAGES:
        is_active = (label == current)
        badge_html = ''
        # Show badge on Dashboard if there are critical items
        if label == 'Dashboard' and crit_count > 0:
            badge_html = f' ({crit_count})'

        btn_type = 'primary' if is_active else 'secondary'
        if st.button(
            f'{label}{badge_html}',
            key=f'nav_{label}',
            use_container_width=True,
            type=btn_type,
        ):
            st.session_state['admin_page'] = label
            st.rerun()


def admin_router():
    if st.session_state.get('role') != 'admin':
        st.error('Access denied.')
        st.stop()

    _load_admin_css()

    with st.sidebar:
        _sidebar_logo()
        _sidebar_user()
        st.markdown('---')
        _sidebar_nav()
        st.markdown('---')
        if st.button('Logout', key='admin_logout', use_container_width=True, type='secondary'):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    # Route to the selected page
    current = st.session_state.get('admin_page', DEFAULT_PAGE)
    page_map = {label: fn for label, fn in PAGES}
    page_fn = page_map.get(current, page_dashboard)
    page_fn()