# routers/staff_router.py

import streamlit as st
from ui.staff.topbar    import load_mobile_css, staff_topbar
from ui.staff.stock     import page_stock_staff
from ui.staff.inventory import page_inventory_staff
from ui.staff.history   import page_logs_staff
from ui.staff.products  import page_products_staff
from ui.components      import esc
from services.sheets_client import clear_data_cache


def staff_router():
    if st.session_state.get('role') != 'staff':
        st.error('Access denied.')
        st.stop()

    load_mobile_css()
    staff_topbar()

    # ── Tab navigation ────────────────────────────────────
    tab_stock, tab_inv, tab_hist, tab_prod, tab_more = st.tabs(
        ['Stock', 'View', 'Log', 'Items', '⚙️'])

    with tab_stock:
        page_stock_staff()

    with tab_inv:
        page_inventory_staff()

    with tab_hist:
        page_logs_staff()

    with tab_prod:
        page_products_staff()

    with tab_more:
        from config import ph_now as _ph_now
        username = esc(st.session_state.get('username', ''))
        role     = esc(st.session_state.get('role', '').capitalize())
        now_str  = _ph_now().strftime('%b %d, %Y  %I:%M %p')

        st.markdown(
            f'<div class="m-more-section">'
            f'<div class="m-more-row">'
            f'<span class="m-more-label">Signed in as</span>'
            f'<span class="m-more-value">@{username}</span>'
            f'</div>'
            f'<div class="m-more-row">'
            f'<span class="m-more-label">Role</span>'
            f'<span class="m-more-value">{role}</span>'
            f'</div>'
            f'<div class="m-more-row">'
            f'<span class="m-more-label">Server time</span>'
            f'<span class="m-more-value">{now_str}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True)

        if st.button('↺  Refresh Data', key='topbar_refresh',
                     use_container_width=True):
            clear_data_cache()
            st.rerun()
        st.markdown('<div class="m-spacer-8"></div>', unsafe_allow_html=True)
        # Marker: CSS in mobile.css uses :has(.m-signout-ctx) ~ sibling to
        # style the following secondary button (Sign Out) with danger red.
        st.markdown('<div class="m-signout-ctx"></div>', unsafe_allow_html=True)
        if st.button('Sign Out', key='topbar_signout',
                     use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()
