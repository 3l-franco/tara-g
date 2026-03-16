# ui/staff/products.py
"""Staff product management — mobile first."""

import pandas as pd
import streamlit as st
from services.sheets_client import read_df, clear_data_cache, get_stations, get_categories
from services.inventory_service import (
    add_product_to_sheet, update_product_in_sheet,
    delete_product_from_sheet, log_transaction,
)
from ui.components import (
    compute_status, empty, safe_write, toast,
    status_dot, esc, safe_idx, show_success_overlay,
)
from config import UNITS


def page_products_staff():
    t_add, t_list = st.tabs(['Add Product', 'Product List'])
    with t_add:
        _tab_add()
    with t_list:
        _tab_list()


# ── Add product ───────────────────────────────────────────

def _tab_add():
    STATIONS   = get_stations()
    CATEGORIES = get_categories()
    username   = st.session_state.get('username', '')

    added_name = st.session_state.pop('sp_add_success', None)
    if added_name:
        show_success_overlay('Product Added!', f'"{added_name}" saved.')
        return

    form_key = f"staff_add_product_{st.session_state.get('sp_form_reset', 0)}"

    with st.form(form_key):
        name = st.text_input('Product Name *', placeholder='e.g. Brown Sugar Milk Tea')

        c1, c2 = st.columns(2)
        with c1:
            station  = st.selectbox('Station',  STATIONS,   key='sp_add_stn')
            category = st.selectbox('Category', CATEGORIES, key='sp_add_cat')
            unit     = st.selectbox('Unit',     UNITS,      key='sp_add_unit')
        with c2:
            init_stock = st.number_input('Initial Stock',       min_value=0, value=0,  key='sp_add_init')
            min_stock  = st.number_input('Low Stock Threshold', min_value=1, value=10, key='sp_add_min')
            crit_stock = st.number_input('Critical Threshold',  min_value=0, value=5,  key='sp_add_crit')

        desc = st.text_area('Description / Notes', placeholder='Optional', key='sp_add_desc')
        submitted = st.form_submit_button('Add Product', type='primary', use_container_width=True)

    if submitted:
        if not name.strip():
            st.error('Product name is required.')
        elif crit_stock >= min_stock:
            st.error('Critical threshold must be lower than Low Stock threshold.')
        else:
            read_df.clear()
            ex = read_df('products')
            if (not ex.empty and
                    name.strip().lower() in ex['product_name'].str.lower().values):
                st.warning(f'"{name}" already exists.')
            else:
                with st.spinner('Adding product…'):
                    ok = safe_write(
                        add_product_to_sheet,
                        name.strip(), station, category, unit,
                        init_stock, min_stock, crit_stock,
                        desc.strip(), '')
                if ok:
                    if init_stock > 0:
                        safe_write(
                            log_transaction,
                            name.strip(), 'stock_in', 0, init_stock,
                            'Initial stock entry', username, unit)
                    clear_data_cache()
                    st.session_state['sp_form_reset'] = (
                        st.session_state.get('sp_form_reset', 0) + 1)
                    st.session_state['sp_add_success'] = name.strip()
                    st.rerun()


# ── List / Edit / Delete ──────────────────────────────────

def _tab_list():
    STATIONS   = get_stations()
    CATEGORIES = get_categories()

    df = read_df('products')
    if df.empty:
        empty('No products yet.', 'Add your first product in the Add Product tab.')
        return

    df   = compute_status(df)
    srch = st.text_input('Search', placeholder='🔍  Product name…',
                         key='sp_list_srch', label_visibility='collapsed')
    if srch.strip():
        df = df[df['product_name'].str.contains(srch.strip(), case=False, na=False)]
        if df.empty:
            empty(f'No products matching "{srch}".')
            return

    df = df.reset_index(drop=True)
    st.caption(f'{len(df)} product(s)')

    _STATUS_COLOR = {'Critical': '#E53935', 'Low': '#F9A825', 'OK': '#43A047'}

    for idx, row in df.iterrows():
        pname  = str(row.get('product_name', ''))
        pid    = str(row.get('product_id',   ''))
        cur    = int(pd.to_numeric(row.get('current_stock', 0), errors='coerce') or 0)
        unit   = str(row.get('unit',    ''))
        stn    = str(row.get('station', ''))
        status = str(row.get('status', 'OK'))
        dot_c  = _STATUS_COLOR.get(status, '#43A047')
        ekey   = f'sp_edit_{pid or pname}_{idx}'

        # ── Fix: three top-level columns so buttons are not nested ──
        # [8] product info  [1] edit btn  [1] delete btn
        c_info, c_edit_btn, c_del_btn = st.columns([8, 1, 1], gap='small')

        c_info.markdown(
            f'<div style="padding:5px 2px;border-bottom:1px solid #EDE5D4;">'
            f'<span style="color:{dot_c};font-size:.6rem;">&#9679;</span> '
            f'<span style="font-size:.83rem;font-weight:600;">{esc(pname)}</span>'
            f'&ensp;<span style="font-size:.75rem;color:#777;">{esc(stn)}</span>'
            f'&ensp;&middot;&ensp;'
            f'<strong style="font-size:.82rem;">{cur}</strong>'
            f'<span style="font-size:.7rem;color:#888;"> {esc(unit)}</span>'
            f'</div>',
            unsafe_allow_html=True)

        if c_edit_btn.button('✏', key=f'sp_pencil_{idx}',
                             help='Edit', use_container_width=True):
            st.session_state[ekey] = not st.session_state.get(ekey, False)
            st.session_state[f'sp_cdel_{idx}'] = False
            st.rerun()

        if c_del_btn.button('🗑', key=f'sp_trash_{idx}',
                            help='Delete', use_container_width=True):
            st.session_state[f'sp_cdel_{idx}'] = not st.session_state.get(f'sp_cdel_{idx}', False)
            st.session_state[ekey] = False
            st.rerun()

        if st.session_state.get(ekey, False):
            _edit_panel(row, idx, pid, pname, STATIONS, CATEGORIES, ekey)

        if st.session_state.get(f'sp_cdel_{idx}', False):
            _delete_confirm(idx, pid, pname, ekey)


def _edit_panel(row, idx, pid, pname, STATIONS, CATEGORIES, ekey):
    with st.container(border=True):
        st.markdown(
            f'<p style="font-weight:700;font-size:.88rem;margin:0 0 8px;">'
            f'{esc(pname)}</p>',
            unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            ns  = st.selectbox(
                'Station', STATIONS,
                index=safe_idx(STATIONS, row.get('station', STATIONS[0])),
                key=f'sp_ns_{idx}')
            nc  = st.selectbox(
                'Category', CATEGORIES,
                index=safe_idx(CATEGORIES, row.get('category', CATEGORIES[0])),
                key=f'sp_nc_{idx}')
            nu  = st.selectbox(
                'Unit', UNITS,
                index=safe_idx(UNITS, row.get('unit', 'pcs')),
                key=f'sp_nu_{idx}')
        with c2:
            nm  = st.number_input(
                'Low Stock Threshold', min_value=1,
                value=int(pd.to_numeric(row.get('min_stock', 10), errors='coerce') or 10),
                key=f'sp_nm_{idx}')
            ncr = st.number_input(
                'Critical Threshold', min_value=0,
                value=int(pd.to_numeric(row.get('critical_stock', 5), errors='coerce') or 5),
                key=f'sp_ncr_{idx}')
            nd  = st.text_input(
                'Description',
                value=str(row.get('description', '')),
                key=f'sp_nd_{idx}')

        bs, bc = st.columns([3, 2])
        with bs:
            if st.button('Save', key=f'sp_save_{idx}',
                         type='primary', use_container_width=True):
                if ncr >= nm:
                    st.error('Critical must be lower than Low Stock threshold.')
                else:
                    with st.spinner('Saving…'):
                        ok = safe_write(
                            update_product_in_sheet, pid, pname,
                            {'station': ns, 'category': nc, 'unit': nu,
                             'min_stock': nm, 'critical_stock': ncr,
                             'description': nd})
                    if ok:
                        st.session_state[ekey] = False
                        clear_data_cache()
                        toast(f'"{pname}" updated.')
                        st.rerun()
        with bc:
            if st.button('Close', key=f'sp_close_{idx}', use_container_width=True):
                st.session_state[ekey] = False
                st.rerun()


def _delete_confirm(idx, pid, pname, ekey):
    with st.container(border=True):
        st.warning(f'Delete **{pname}**? This cannot be undone.')
        with st.form(key=f'sp_del_form_{idx}'):
            confirm_name = st.text_input(
                'Type the product name to confirm:',
                placeholder=pname,
                key=f'sp_del_input_{idx}')
            cy, cn = st.columns(2)
            confirmed = cy.form_submit_button('Yes, Delete', type='primary')
            cancelled = cn.form_submit_button('Cancel')

        if confirmed:
            if confirm_name.strip().lower() != pname.strip().lower():
                st.error('Name does not match. Check spelling.')
            else:
                with st.spinner('Deleting…'):
                    ok = safe_write(delete_product_from_sheet, pid, pname)
                if ok:
                    st.session_state[f'sp_cdel_{idx}'] = False
                    st.session_state[ekey] = False
                    clear_data_cache()
                    toast(f'"{pname}" deleted.')
                    st.rerun()
        if cancelled:
            st.session_state[f'sp_cdel_{idx}'] = False
            st.rerun()
