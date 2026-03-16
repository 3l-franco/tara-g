# ui/admin/manage_products.py

import pandas as pd
import streamlit as st
import gspread
from services.sheets_client import (
    read_df, clear_data_cache, get_stations, save_stations, get_ws, api_call
)
from services.inventory_service import (
    add_product_to_sheet, update_product_in_sheet,
    delete_product_from_sheet, log_transaction
)
from ui.components import (
    compute_status, empty, safe_write, toast,
    badge, status_badge, safe_idx, esc
)
from config import CATEGORIES, UNITS


def page_manage_products():
    STATIONS = get_stations()
    st.title('Manage Products')

    suppliers_df   = read_df('suppliers')
    supplier_names = ['— None —']
    if not suppliers_df.empty and 'supplier_name' in suppliers_df.columns:
        supplier_names += sorted(
            suppliers_df['supplier_name'].dropna().tolist())

    t_add, t_list, t_stations = st.tabs(
        ['Add Product', 'Master List', 'Stations'])

    # ── Add Product ───────────────────────────────────────
    with t_add:
        _tab_add(STATIONS, supplier_names)

    # ── Master List ───────────────────────────────────────
    with t_list:
        _tab_list(STATIONS, supplier_names)

    # ── Stations ──────────────────────────────────────────
    with t_stations:
        _tab_stations(STATIONS)


def _tab_add(STATIONS, supplier_names):
    with st.form('add_product'):
        c1, c2 = st.columns(2)
        with c1:
            name     = st.text_input('Product Name *')
            station  = st.selectbox('Station',   STATIONS)
            category = st.selectbox('Category',  CATEGORIES)
            unit     = st.selectbox('Unit',       UNITS)
            sup_sel  = st.selectbox('Supplier',   supplier_names, key='add_sup')
        with c2:
            init_stock = st.number_input('Initial Stock',            min_value=0, value=0)
            min_stock  = st.number_input('Low Stock Threshold',      min_value=1, value=10)
            crit_stock = st.number_input('Critical Stock Threshold', min_value=0, value=5)
        desc = st.text_area('Description / Notes', placeholder='Optional')

        if st.form_submit_button('Add Product ✓', type='primary'):
            if not name.strip():
                st.error('Product name is required.')
            elif crit_stock >= min_stock:
                st.error('Critical threshold must be lower than Low Stock threshold.')
            else:
                read_df.clear()  # bypass stale cache — freshness required on write path
                ex = read_df('products')
                if (not ex.empty and
                        name.lower() in ex['product_name'].str.lower().values):
                    st.warning(f'"{name}" already exists.')
                else:
                    sup_val = '' if sup_sel == '— None —' else sup_sel
                    with st.spinner('Adding product…'):
                        ok = safe_write(
                            add_product_to_sheet,
                            name.strip(), station, category, unit,
                            init_stock, min_stock, crit_stock, desc, sup_val)
                    if ok:
                        if init_stock > 0:
                            safe_write(
                                log_transaction,
                                name, 'stock_in', 0, init_stock,
                                'Initial stock entry',
                                st.session_state.username, unit)
                        clear_data_cache()
                        toast(f'"{name}" ({station}) added.')
                        st.rerun()


def _tab_list(STATIONS, supplier_names):
    df = read_df('products')
    if df.empty:
        empty('No products yet.', 'Add your first product in the Add Product tab.')
        return

    df     = compute_status(df)
    search = st.text_input('Search', placeholder='Filter by product name…',
                           key='prod_search')
    if search:
        df = df[df['product_name'].str.contains(search, case=False, na=False)]
        if df.empty:
            empty(f'No products matching "{search}".')
            return

    present  = ['All'] + [s for s in STATIONS if s in df['station'].values]
    stn_tabs = st.tabs(present)

    for tab, stn in zip(stn_tabs, present):
        with tab:
            sec = (df if stn == 'All'
                   else df[df['station'] == stn]).reset_index(drop=True)
            if sec.empty:
                empty(f'No products in {stn}.')
                continue

            for idx, row in sec.iterrows():
                pname  = row['product_name']
                pid    = str(row.get('product_id', ''))
                cur    = int(pd.to_numeric(
                    row.get('current_stock', 0), errors='coerce') or 0)
                unit   = row.get('unit', '')
                r_stn  = str(row.get('station', ''))
                status = str(row.get('status', ''))
                edit_key = f'edit_open_{pid if pid else pname}'

                col_name, col_stock, col_status, col_edit = st.columns(
                    [4, 2, 2, 1])

                col_name.markdown(
                    f'<span style="font-weight:600;font-size:.88rem;">'
                    f'{esc(pname)}</span>'
                    f'{"&nbsp;" + badge(r_stn) if stn == "All" else ""}',
                    unsafe_allow_html=True)
                col_stock.markdown(
                    f'<span style="font-size:.85rem;color:#444;">'
                    f'<strong>{cur}</strong> {esc(unit)}</span>',
                    unsafe_allow_html=True)
                col_status.markdown(status_badge(status), unsafe_allow_html=True)

                if col_edit.button('✎', key=f'pencil_{stn}_{idx}',
                                   help='Edit / Delete'):
                    st.session_state[edit_key] = not st.session_state.get(
                        edit_key, False)
                    st.rerun()

                if st.session_state.get(edit_key, False):
                    _edit_panel(row, idx, stn, pid, pname, STATIONS,
                                supplier_names, edit_key)

                st.markdown(
                    '<hr style="margin:.2rem 0;border-color:#E8E0D0;">',
                    unsafe_allow_html=True)


def _edit_panel(row, idx, stn, pid, pname, STATIONS, supplier_names, edit_key):
    with st.container(border=True):

        ec1, ec2 = st.columns(2)
        with ec1:
            ns  = st.selectbox('Station', STATIONS,
                               index=safe_idx(STATIONS, row.get('station', 'Others')),
                               key=f'ns_{stn}_{idx}')
            nc  = st.selectbox('Category', CATEGORIES,
                               index=safe_idx(CATEGORIES, row.get('category', 'Others')),
                               key=f'nc_{stn}_{idx}')
            nu  = st.selectbox('Unit', UNITS,
                               index=safe_idx(UNITS, row.get('unit', 'pcs')),
                               key=f'nu_{stn}_{idx}')
            cur_sup = str(row.get('supplier', ''))
            sup_idx = safe_idx(supplier_names,
                               cur_sup if cur_sup else '— None —', 0)
            ns_sup  = st.selectbox('Supplier', supplier_names,
                                   index=sup_idx, key=f'nsup_{stn}_{idx}')
        with ec2:
            nm  = st.number_input(
                'Low Stock Threshold', min_value=1,
                value=int(pd.to_numeric(
                    row.get('min_stock', 10), errors='coerce') or 10),
                key=f'nm_{stn}_{idx}')
            ncr = st.number_input(
                'Critical Stock Threshold', min_value=0,
                value=int(pd.to_numeric(
                    row.get('critical_stock', 5), errors='coerce') or 5),
                key=f'ncr_{stn}_{idx}')
            nd  = st.text_input('Description',
                                value=str(row.get('description', '')),
                                key=f'nd_{stn}_{idx}')

        btn_save, btn_del, btn_close = st.columns([2, 2, 2])

        with btn_save:
            if st.button('Save', key=f'save_{stn}_{idx}',
                         type='primary', use_container_width=True):
                if ncr >= nm:
                    st.error('Critical must be lower than Low Stock threshold.')
                else:
                    sup_save = '' if ns_sup == '— None —' else ns_sup
                    with st.spinner('Saving…'):
                        ok = safe_write(
                            update_product_in_sheet, pid, pname,
                            {'station': ns, 'category': nc, 'unit': nu,
                             'min_stock': nm, 'critical_stock': ncr,
                             'description': nd, 'supplier': sup_save})
                    if ok:
                        st.session_state[edit_key] = False
                        clear_data_cache()
                        toast(f'"{pname}" updated.')
                        st.rerun()

        with btn_del:
            del_key = f'cdel_{stn}_{idx}'
            if st.button('Delete', key=f'del_{stn}_{idx}',
                         use_container_width=True):
                st.session_state[del_key] = True
                st.rerun()

        with btn_close:
            if st.button('Close', key=f'close_{stn}_{idx}',
                         use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()

        if st.session_state.get(f'cdel_{stn}_{idx}'):
            st.warning(f'Delete **{pname}**? This cannot be undone.')
            with st.form(key=f'del_confirm_{stn}_{idx}'):
                confirm_name = st.text_input(
                    'Type the product name to confirm:',
                    placeholder=pname)
                cy, cn = st.columns(2)
                confirmed = cy.form_submit_button('Yes, Delete', type='primary')
                cancelled = cn.form_submit_button('Cancel')

            if confirmed:
                if confirm_name.strip().lower() != pname.lower():
                    st.error('Name does not match. Check spelling.')
                else:
                    with st.spinner('Deleting…'):
                        ok = safe_write(delete_product_from_sheet, pid, pname)
                    if ok:
                        st.session_state[f'cdel_{stn}_{idx}'] = False
                        st.session_state[edit_key] = False
                        clear_data_cache()
                        toast(f'"{pname}" deleted.')
                        st.rerun()
            if cancelled:
                st.session_state[f'cdel_{stn}_{idx}'] = False
                st.rerun()




def _tab_stations(STATIONS):
    current_stations = list(STATIONS)
    hc1, hc2 = st.columns([6, 1])
    hc1.subheader('Stations')

    if hc2.button('＋', key='stn_add_toggle', help='Add new station'):
        st.session_state['stn_adding'] = not st.session_state.get(
            'stn_adding', False)
        st.rerun()

    if st.session_state.get('stn_adding', False):
        with st.form('add_station_inline'):
            na_col, sb_col = st.columns([4, 1])
            new_stn = na_col.text_input(
                'New station name',
                placeholder='e.g. Bar, Bakery…',
                label_visibility='collapsed')
            if sb_col.form_submit_button('Add', use_container_width=True,
                                         type='primary'):
                if not new_stn.strip():
                    st.error('Station name is required.')
                elif new_stn.strip() in current_stations:
                    st.warning(f'"{new_stn}" already exists.')
                else:
                    updated = current_stations + [new_stn.strip()]
                    with st.spinner('Saving…'):
                        ok = save_stations(updated)
                    if ok:
                        st.session_state['stn_adding'] = False
                        clear_data_cache()
                        toast(f'Station "{new_stn.strip()}" added.')
                        st.rerun()

    st.caption('Edit or remove stations. Changes apply across the app.')

    for i, stn in enumerate(current_stations):
        edit_k = f'stn_edit_{i}'
        c_badge, c_edit, c_del = st.columns([5, 1, 1])
        c_badge.markdown(
            f'<div style="padding:.3rem 0;">{badge(stn)}</div>',
            unsafe_allow_html=True)

        if c_edit.button('Rename', key=f'stn_pencil_{i}',
                         use_container_width=True):
            st.session_state[edit_k] = not st.session_state.get(edit_k, False)
            st.rerun()

        if c_del.button('Remove', key=f'rm_stn_{i}',
                        use_container_width=True):
            if len(current_stations) <= 1:
                st.error('You must have at least one station.')
            else:
                prods_df = read_df('products')
                if not prods_df.empty and 'station' in prods_df.columns:
                    in_use = (prods_df['station'] == stn).sum()
                    if in_use > 0:
                        st.warning(
                            f'"{stn}" has {in_use} product(s) assigned. '
                            f'Reassign them first.')
                    else:
                        new_list = [s for s in current_stations if s != stn]
                        with st.spinner(f'Removing {stn}…'):
                            ok = save_stations(new_list)
                        if ok:
                            clear_data_cache()
                            toast(f'Station "{stn}" removed.')
                            st.rerun()

        if st.session_state.get(edit_k, False):
            with st.form(f'stn_rename_form_{i}'):
                rc1, rc2, rc3 = st.columns([4, 1, 1])
                new_name = rc1.text_input('New name', value=stn,
                                          label_visibility='collapsed')
                if rc2.form_submit_button('Save', type='primary'):
                    if not new_name.strip():
                        st.error('Name required.')
                    elif (new_name.strip() in current_stations
                          and new_name.strip() != stn):
                        st.warning('That name already exists.')
                    else:
                        updated = [new_name.strip() if s == stn else s
                                   for s in current_stations]
                        with st.spinner('Saving…'):
                            ok = save_stations(updated)
                        if ok:
                            try:
                                ws_p  = get_ws('products')
                                vals  = api_call(ws_p.get_all_values)
                                hdrs  = vals[0]
                                if 'station' in hdrs:
                                    sc    = hdrs.index('station') + 1
                                    cells = []
                                    for ri, rv in enumerate(vals[1:], start=2):
                                        if rv[sc - 1] == stn:
                                            cells.append(gspread.Cell(
                                                row=ri, col=sc,
                                                value=new_name.strip()))
                                    if cells:
                                        api_call(ws_p.update_cells, cells)
                            except Exception as e:
                                st.warning(
                                    f'Station renamed but some products '
                                    f'could not be updated: {e}')
                            st.session_state[edit_k] = False
                            clear_data_cache()
                            toast(f'Station renamed to "{new_name.strip()}".')
                            st.rerun()
                if rc3.form_submit_button('Cancel'):
                    st.session_state[edit_k] = False
                    st.rerun()

        st.markdown(
            '<hr style="margin:.15rem 0;border-color:#F4F4F4;">',
            unsafe_allow_html=True)