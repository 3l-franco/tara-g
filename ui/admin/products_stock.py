# ui/admin/products_stock.py
# Merged: Manage Products + Stock Management into one page.

import pandas as pd
import streamlit as st
import gspread
from services.sheets_client import (
    read_df, clear_data_cache, get_stations, save_stations,
    get_categories, save_categories,
    get_ws, api_call
)
from services.inventory_service import (
    add_product_to_sheet, update_product_in_sheet,
    delete_product_from_sheet, update_stock_and_log, log_transaction
)
from ui.components import (
    compute_status, empty, safe_write, toast,
    badge, status_badge, status_dot, safe_idx, esc,
    parse_suppliers, join_suppliers
)
from config import UNITS, OUT_REASONS, IN_REASONS


def page_products_stock():
    STATIONS   = get_stations()
    CATEGORIES = get_categories()
    st.title('Products & Stock')

    suppliers_df   = read_df('suppliers')
    supplier_names = []
    if not suppliers_df.empty and 'supplier_name' in suppliers_df.columns:
        supplier_names = sorted(
            suppliers_df['supplier_name'].dropna().tolist())

    tabs = st.tabs(['Products', 'Stock Update', 'Stations', 'Categories'])

    with tabs[0]:
        _tab_products(STATIONS, CATEGORIES, supplier_names)
    with tabs[1]:
        _tab_stock(STATIONS)
    with tabs[2]:
        _tab_stations(STATIONS)
    with tabs[3]:
        _tab_categories(CATEGORIES)


# ══════════════════════════════════════════════════════════
#  TAB: Products
# ══════════════════════════════════════════════════════════

def _tab_products(STATIONS, CATEGORIES, supplier_names):
    with st.expander('Add New Product', expanded=False):
        _form_add_product(STATIONS, CATEGORIES, supplier_names)

    st.markdown('---')

    df = read_df('products')
    if df.empty:
        empty('No products yet.', 'Use the form above to add your first item.')
        return

    df = compute_status(df)

    c_search, c_status = st.columns([3, 1])
    search = c_search.text_input(
        'Search', placeholder='Filter by product name…',
        key='ps_search')
    status_filter = c_status.selectbox(
        'Status', ['All', 'Critical', 'Low', 'OK'], key='ps_status')

    if search:
        df = df[df['product_name'].str.contains(search, case=False, na=False)]
    if status_filter != 'All':
        df = df[df['status'] == status_filter]

    if df.empty:
        empty('No products match your filter.')
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
            _render_product_grid(sec, stn, STATIONS, CATEGORIES, supplier_names)


def _form_add_product(STATIONS, CATEGORIES, supplier_names):
    with st.form('add_product'):
        c1, c2 = st.columns(2)
        with c1:
            name     = st.text_input('Product Name *')
            station  = st.selectbox('Station',  STATIONS)
            category = st.selectbox('Category', CATEGORIES)
            unit     = st.selectbox('Unit',     UNITS)
            if supplier_names:
                sup_sel = st.multiselect(
                    'Supplier(s)', supplier_names, key='add_sup_multi')
            else:
                sup_sel = []
                st.caption('No suppliers — add them in the Suppliers page.')
        with c2:
            init_stock = st.number_input('Initial Stock',           min_value=0, value=0)
            min_stock  = st.number_input('Low Stock Threshold',     min_value=1, value=10)
            crit_stock = st.number_input('Critical Stock Threshold',min_value=0, value=5)
        desc = st.text_area('Description / Notes', placeholder='Optional')

        if st.form_submit_button('Add Product', type='primary'):
            if not name.strip():
                st.error('Product name is required.')
            elif crit_stock >= min_stock:
                st.error('Critical threshold must be lower than Low Stock threshold.')
            else:
                ex = read_df('products')
                if (not ex.empty and
                        name.lower() in ex['product_name'].str.lower().values):
                    st.warning(f'"{name}" already exists.')
                else:
                    sup_val = join_suppliers(sup_sel)
                    with st.spinner('Adding product…'):
                        ok = safe_write(
                            add_product_to_sheet,
                            name.strip(), station, category, unit,
                            init_stock, min_stock, crit_stock,
                            desc, sup_val)
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


def _render_product_grid(df, stn, STATIONS, CATEGORIES, supplier_names):
    hdr_col, _ = st.columns([12, 1])
    hdr_col.markdown(
        '<div class="pgrid-header">'
        '<span></span>'
        '<span>Product</span>'
        '<span>Stock</span>'
        '<span>Unit</span>'
        '<span>Min</span>'
        '<span>Critical</span>'
        '<span>Station</span>'
        '</div>', unsafe_allow_html=True)

    for idx, row in df.iterrows():
        pname  = str(row.get('product_name', ''))
        pid    = str(row.get('product_id', ''))
        cur    = int(pd.to_numeric(row.get('current_stock', 0), errors='coerce') or 0)
        unit   = str(row.get('unit', ''))
        mn     = int(pd.to_numeric(row.get('min_stock', 0), errors='coerce') or 0)
        crit   = int(pd.to_numeric(row.get('critical_stock', 0), errors='coerce') or 0)
        r_stn  = str(row.get('station', ''))
        status = str(row.get('status', 'OK'))
        dot    = status_dot(status)
        edit_key = f'edit_open_{pid}'

        col_row, col_btn = st.columns([12, 1])
        col_row.markdown(
            f'<div class="pgrid-row">'
            f'<span>{dot}</span>'
            f'<span style="font-weight:600;">{esc(pname)}</span>'
            f'<span class="pgrid-stock">{cur}</span>'
            f'<span class="pgrid-muted">{esc(unit)}</span>'
            f'<span class="pgrid-muted">{mn}</span>'
            f'<span class="pgrid-muted">{crit}</span>'
            f'<span class="pgrid-muted">{esc(r_stn)}</span>'
            f'</div>', unsafe_allow_html=True)

        if col_btn.button('✏️', key=f'ed_{stn}_{idx}', use_container_width=True):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun()

        if st.session_state.get(edit_key, False):
            _edit_panel(row, idx, stn, pid, pname,
                        STATIONS, CATEGORIES, supplier_names, edit_key)


def _edit_panel(row, idx, stn, pid, pname, STATIONS, CATEGORIES, supplier_names, edit_key):
    with st.container(border=True):
        ec1, ec2 = st.columns(2)
        with ec1:
            ns = st.selectbox(
                'Station', STATIONS,
                index=safe_idx(STATIONS, row.get('station', 'Others')),
                key=f'ns_{stn}_{idx}')
            nc = st.selectbox(
                'Category', CATEGORIES,
                index=safe_idx(CATEGORIES, row.get('category', CATEGORIES[0])),
                key=f'nc_{stn}_{idx}')
            nu = st.selectbox(
                'Unit', UNITS,
                index=safe_idx(UNITS, row.get('unit', 'pcs')),
                key=f'nu_{stn}_{idx}')
            cur_sups = parse_suppliers(row.get('supplier', ''))
            if supplier_names:
                ns_sup = st.multiselect(
                    'Supplier(s)', supplier_names,
                    default=[s for s in cur_sups if s in supplier_names],
                    key=f'nsup_{stn}_{idx}')
            else:
                ns_sup = []
        with ec2:
            nm = st.number_input(
                'Low Stock Threshold', min_value=1,
                value=int(pd.to_numeric(row.get('min_stock', 10), errors='coerce') or 10),
                key=f'nm_{stn}_{idx}')
            ncr = st.number_input(
                'Critical Stock Threshold', min_value=0,
                value=int(pd.to_numeric(row.get('critical_stock', 5), errors='coerce') or 5),
                key=f'ncr_{stn}_{idx}')
            nd = st.text_input(
                'Description',
                value=str(row.get('description', '')),
                key=f'nd_{stn}_{idx}')

        btn_save, btn_del, btn_close = st.columns([2, 2, 2])

        with btn_save:
            if st.button('Save', key=f'save_{stn}_{idx}',
                         type='primary', use_container_width=True):
                if ncr >= nm:
                    st.error('Critical must be lower than Low Stock threshold.')
                else:
                    sup_save = join_suppliers(ns_sup)
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
            if st.button('Delete', key=f'del_{stn}_{idx}', use_container_width=True):
                st.session_state[del_key] = True
                st.rerun()

        with btn_close:
            if st.button('Close', key=f'close_{stn}_{idx}', use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()

        if st.session_state.get(f'cdel_{stn}_{idx}'):
            st.warning(f'Delete **{pname}**? This cannot be undone.')
            with st.form(key=f'del_confirm_{stn}_{idx}'):
                confirm_name = st.text_input('Type the product name to confirm:', placeholder=pname)
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


# ══════════════════════════════════════════════════════════
#  TAB: Stock Update
# ══════════════════════════════════════════════════════════

def _tab_stock(STATIONS):
    df = read_df('products')
    if df.empty:
        empty('No products found.', 'Add products first.')
        return

    username = st.session_state.username
    tab_quick, tab_detail = st.tabs(['Quick Update', 'Detailed'])

    with tab_quick:
        _quick_stock(df, username, STATIONS)
    with tab_detail:
        _detailed_stock(df, username, STATIONS)


def _quick_stock(products_df, username, STATIONS):
    df = products_df.copy()
    df['current_stock'] = pd.to_numeric(df['current_stock'], errors='coerce').fillna(0)
    if 'station' not in df.columns:
        df['station'] = 'Others'
    df['station'] = df['station'].replace('', 'Others').fillna('Others')
    df = compute_status(df)

    col_f, col_s = st.columns([1, 2])
    sf = col_f.selectbox(
        'Station',
        ['All'] + [s for s in STATIONS if s in df['station'].values],
        key='ps_qs_sf')
    srch = col_s.text_input('Search', placeholder='Filter by name…', key='ps_qs_srch')

    fdf = df if sf == 'All' else df[df['station'] == sf]
    if srch:
        fdf = fdf[fdf['product_name'].str.contains(srch, case=False, na=False)]
    if fdf.empty:
        empty('No products match your filter.')
        return

    qs_pending = st.session_state.get('qs_pending')
    if qs_pending:
        _render_pending(qs_pending, username)
        return

    for idx, row in fdf.reset_index(drop=True).iterrows():
        pname  = row['product_name']
        pid    = str(row.get('product_id', ''))
        cur    = int(row['current_stock'])
        unit   = row.get('unit', '')
        status = str(row.get('status', 'OK'))
        mn     = int(pd.to_numeric(row.get('min_stock', 0), errors='coerce') or 0)
        dot    = status_dot(status)

        c1, c2, c3, c4 = st.columns([4, 1, 1, 1], vertical_alignment='center')

        c1.markdown(
            f'<div style="padding:.35rem 0;">'
            f'<span style="font-size:.85rem;display:flex;align-items:center;gap:6px;">'
            f'{dot} {esc(pname)}</span>'
            f'<span style="font-size:.82rem;color:#7A7A7A;">'
            f'Stock: <strong style="color:#111;">{cur} {esc(unit)}</strong>'
            f'&nbsp;·&nbsp;min {mn}</span></div>',
            unsafe_allow_html=True)

        qty = c2.number_input('Qty', min_value=1, value=1,
                              key=f'ps_qty_{idx}', label_visibility='collapsed')

        if c3.button('+ In', key=f'ps_in_{idx}', use_container_width=True, type='primary'):
            st.session_state['qs_pending'] = {
                'pid': pid, 'product': pname, 'cur': cur,
                'qty': qty, 'unit': unit, 'action': 'in'}
            st.rerun()

        if c4.button('- Out', key=f'ps_out_{idx}', use_container_width=True):
            if qty > cur:
                st.error(f'Only {cur} {unit} available.')
            else:
                st.session_state['qs_pending'] = {
                    'pid': pid, 'product': pname, 'cur': cur,
                    'qty': qty, 'unit': unit, 'action': 'out'}
                st.rerun()

        st.markdown('<hr style="margin:.1rem 0;border-color:#E8E0D0;">', unsafe_allow_html=True)


def _render_pending(p, username):
    act   = p['action']
    new_s = p['cur'] + p['qty'] if act == 'in' else p['cur'] - p['qty']
    arrow = '+' if act == 'in' else '-'
    st.markdown(
        f'<div style="background:#FFF9E6;border:2px solid #E8E0D0;'
        f'border-radius:6px;padding:.8rem 1rem;margin-bottom:.75rem;">'
        f'<p style="font-weight:700;font-size:.88rem;margin:0 0 .3rem 0;">'
        f'Confirm {"Stock In" if act == "in" else "Stock Out"}</p>'
        f'<p style="font-size:.85rem;margin:0;">'
        f'<strong>{esc(p["product"])}</strong>: '
        f'<span style="font-weight:700;">{p["cur"]} {arrow} {new_s} {esc(p["unit"])}</span></p>'
        f'</div>', unsafe_allow_html=True)

    reason_opts = IN_REASONS if act == 'in' else OUT_REASONS
    reason = st.selectbox('Reason', reason_opts, key='ps_qs_reason')

    c_yes, c_no = st.columns(2)
    with c_yes:
        if st.button('Apply', key='ps_qs_yes', type='primary', use_container_width=True):
            ok = safe_write(
                update_stock_and_log,
                p['pid'], p['product'],
                'stock_in' if act == 'in' else 'stock_out',
                p['cur'], new_s, reason, username)
            if ok:
                st.session_state.pop('qs_pending', None)
                clear_data_cache()
                toast(f'{p["product"]}: {p["cur"]}→{new_s} {p["unit"]}')
                st.rerun()
    with c_no:
        if st.button('Cancel', key='ps_qs_no', use_container_width=True):
            st.session_state.pop('qs_pending', None)
            st.rerun()


def _detailed_stock(products_df, username, STATIONS):
    df = products_df.copy()
    df['current_stock'] = pd.to_numeric(df['current_stock'], errors='coerce').fillna(0)
    if 'station' not in df.columns:
        df['station'] = 'Others'
    df['station'] = df['station'].replace('', 'Others').fillna('Others')

    sf = st.selectbox(
        'Filter by Station',
        ['All'] + [s for s in STATIONS if s in df['station'].values],
        key='ps_dsf')
    fdf   = df if sf == 'All' else df[df['station'] == sf]
    names = fdf['product_name'].tolist()
    if not names:
        empty(f'No products in {sf}.')
        return

    tab_in, tab_out = st.tabs(['Stock In', 'Stock Out'])

    with tab_in:
        sel = st.selectbox('Product', names, key='ps_din')
        row = fdf[fdf['product_name'] == sel].iloc[0]
        st.markdown(
            f'<div style="background:#F7F7F8;border:1px solid #EBEBEB;'
            f'border-radius:6px;padding:.5rem 1rem;margin:.4rem 0 .8rem 0;font-size:.85rem;">'
            f'Current: <strong>{int(row["current_stock"])} {row["unit"]}</strong>'
            f'&nbsp;·&nbsp;Min: {int(row["min_stock"])}'
            f'&nbsp;·&nbsp;Critical: {int(row["critical_stock"])}</div>',
            unsafe_allow_html=True)
        with st.form('ps_din_form'):
            qty   = st.number_input('Quantity to Add', min_value=1, value=1)
            notes = st.text_input('Notes / Source', placeholder='e.g. Delivery from Supplier X')
            if st.form_submit_button('Confirm Stock In', type='primary'):
                r   = fdf[fdf['product_name'] == sel].iloc[0]
                pid = str(r.get('product_id', ''))
                old = int(r['current_stock'])
                new = old + qty
                with st.spinner('Saving…'):
                    ok = safe_write(update_stock_and_log, pid, sel, 'stock_in', old, new, notes, username)
                if ok:
                    clear_data_cache()
                    toast(f'Stock In: {sel} {old}→{new} {r["unit"]}')
                    st.rerun()

    with tab_out:
        sel = st.selectbox('Product', names, key='ps_dout')
        row = fdf[fdf['product_name'] == sel].iloc[0]
        st.markdown(
            f'<div style="background:#F7F7F8;border:1px solid #EBEBEB;'
            f'border-radius:6px;padding:.5rem 1rem;margin:.4rem 0 .8rem 0;font-size:.85rem;">'
            f'Current: <strong>{int(row["current_stock"])} {row["unit"]}</strong>'
            f'&nbsp;·&nbsp;Min: {int(row["min_stock"])}'
            f'&nbsp;·&nbsp;Critical: {int(row["critical_stock"])}</div>',
            unsafe_allow_html=True)
        with st.form('ps_dout_form'):
            qty    = st.number_input('Quantity to Remove', min_value=1, value=1)
            reason = st.selectbox('Reason', OUT_REASONS)
            custom = ''
            if reason == 'Other — specify':
                custom = st.text_input('Please specify reason *')
            notes = st.text_input('Additional Notes', placeholder='Optional')
            if st.form_submit_button('Confirm Stock Out', type='primary'):
                if reason == 'Other — specify' and not custom.strip():
                    st.error('Please specify the reason.')
                else:
                    r   = fdf[fdf['product_name'] == sel].iloc[0]
                    pid = str(r.get('product_id', ''))
                    old = int(r['current_stock'])
                    if qty > old:
                        st.error(f'Not enough stock. Available: {old} {r["unit"]}')
                    else:
                        new        = old - qty
                        reason_log = custom if reason == 'Other — specify' else reason
                        log_note   = f'{reason_log} — {notes}' if notes else reason_log
                        with st.spinner('Saving…'):
                            ok = safe_write(update_stock_and_log, pid, sel, 'stock_out', old, new, log_note, username)
                        if ok:
                            clear_data_cache()
                            toast(f'Stock Out: {sel} {old}→{new} {r["unit"]}')
                            st.rerun()


# ══════════════════════════════════════════════════════════
#  TAB: Stations
# ══════════════════════════════════════════════════════════

def _tab_stations(STATIONS):
    current_stations = list(STATIONS)
    hc1, hc2 = st.columns([6, 1])
    hc1.subheader('Stations')

    if hc2.button('Add', key='stn_add_toggle', help='Add new station'):
        st.session_state['stn_adding'] = not st.session_state.get('stn_adding', False)
        st.rerun()

    if st.session_state.get('stn_adding', False):
        with st.form('add_station_inline'):
            na_col, sb_col = st.columns([4, 1])
            new_stn = na_col.text_input('New station name', placeholder='e.g. Bar, Bakery…',
                                        label_visibility='collapsed')
            if sb_col.form_submit_button('Add', use_container_width=True, type='primary'):
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
        c_badge.markdown(f'<div style="padding:.3rem 0;">{badge(stn)}</div>', unsafe_allow_html=True)

        if c_edit.button('Rename', key=f'stn_pencil_{i}', use_container_width=True):
            st.session_state[edit_k] = not st.session_state.get(edit_k, False)
            st.rerun()

        if c_del.button('Remove', key=f'rm_stn_{i}', use_container_width=True):
            if len(current_stations) <= 1:
                st.error('You must have at least one station.')
            else:
                prods_df = read_df('products')
                if not prods_df.empty and 'station' in prods_df.columns:
                    in_use = (prods_df['station'] == stn).sum()
                    if in_use > 0:
                        st.warning(f'"{stn}" has {in_use} product(s) assigned. Reassign them first.')
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
                new_name = rc1.text_input('New name', value=stn, label_visibility='collapsed')
                if rc2.form_submit_button('Save', type='primary'):
                    if not new_name.strip():
                        st.error('Name required.')
                    elif new_name.strip() in current_stations and new_name.strip() != stn:
                        st.warning('That name already exists.')
                    else:
                        updated = [new_name.strip() if s == stn else s for s in current_stations]
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
                                            cells.append(gspread.Cell(row=ri, col=sc, value=new_name.strip()))
                                    if cells:
                                        api_call(ws_p.update_cells, cells)
                            except Exception as e:
                                st.warning(f'Station renamed but some products could not be updated: {e}')
                            st.session_state[edit_k] = False
                            clear_data_cache()
                            toast(f'Station renamed to "{new_name.strip()}".')
                            st.rerun()
                if rc3.form_submit_button('Cancel'):
                    st.session_state[edit_k] = False
                    st.rerun()

        st.markdown('<hr style="margin:.15rem 0;border-color:#F4F4F4;">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  TAB: Categories  ← NEW
# ══════════════════════════════════════════════════════════

def _tab_categories(CATEGORIES):
    """Manage the category list — add, rename, remove."""
    current_cats = list(CATEGORIES)
    hc1, hc2 = st.columns([6, 1])
    hc1.subheader('Categories')

    if hc2.button('Add', key='cat_add_toggle', help='Add new category'):
        st.session_state['cat_adding'] = not st.session_state.get('cat_adding', False)
        st.rerun()

    if st.session_state.get('cat_adding', False):
        with st.form('add_category_inline'):
            na_col, sb_col = st.columns([4, 1])
            new_cat = na_col.text_input('New category name', placeholder='e.g. Desserts, Pasta…',
                                        label_visibility='collapsed')
            if sb_col.form_submit_button('Add', use_container_width=True, type='primary'):
                if not new_cat.strip():
                    st.error('Category name is required.')
                elif new_cat.strip() in current_cats:
                    st.warning(f'"{new_cat}" already exists.')
                else:
                    updated = current_cats + [new_cat.strip()]
                    with st.spinner('Saving…'):
                        ok = save_categories(updated)
                    if ok:
                        st.session_state['cat_adding'] = False
                        clear_data_cache()
                        toast(f'Category "{new_cat.strip()}" added.')
                        st.rerun()

    st.caption('Edit or remove categories. Changes apply to new products immediately.')

    for i, cat in enumerate(current_cats):
        edit_k = f'cat_edit_{i}'
        c_badge, c_edit, c_del = st.columns([5, 1, 1])
        c_badge.markdown(f'<div style="padding:.3rem 0;">{badge(cat)}</div>', unsafe_allow_html=True)

        if c_edit.button('Rename', key=f'cat_pencil_{i}', use_container_width=True):
            st.session_state[edit_k] = not st.session_state.get(edit_k, False)
            st.rerun()

        if c_del.button('Remove', key=f'rm_cat_{i}', use_container_width=True):
            if len(current_cats) <= 1:
                st.error('You must have at least one category.')
            else:
                # Warn if any products still use this category
                prods_df = read_df('products')
                if not prods_df.empty and 'category' in prods_df.columns:
                    in_use = (prods_df['category'] == cat).sum()
                    if in_use > 0:
                        st.warning(f'"{cat}" is used by {in_use} product(s). '
                                   f'Reassign them first.')
                    else:
                        new_list = [c for c in current_cats if c != cat]
                        with st.spinner(f'Removing {cat}…'):
                            ok = save_categories(new_list)
                        if ok:
                            clear_data_cache()
                            toast(f'Category "{cat}" removed.')
                            st.rerun()
                else:
                    new_list = [c for c in current_cats if c != cat]
                    with st.spinner(f'Removing {cat}…'):
                        ok = save_categories(new_list)
                    if ok:
                        clear_data_cache()
                        toast(f'Category "{cat}" removed.')
                        st.rerun()

        if st.session_state.get(edit_k, False):
            with st.form(f'cat_rename_form_{i}'):
                rc1, rc2, rc3 = st.columns([4, 1, 1])
                new_name = rc1.text_input('New name', value=cat, label_visibility='collapsed')
                if rc2.form_submit_button('Save', type='primary'):
                    if not new_name.strip():
                        st.error('Name required.')
                    elif new_name.strip() in current_cats and new_name.strip() != cat:
                        st.warning('That name already exists.')
                    else:
                        updated = [new_name.strip() if c == cat else c for c in current_cats]
                        with st.spinner('Saving…'):
                            ok = save_categories(updated)
                        if ok:
                            # Also update the category column in Products sheet
                            try:
                                ws_p  = get_ws('products')
                                vals  = api_call(ws_p.get_all_values)
                                hdrs  = vals[0]
                                if 'category' in hdrs:
                                    cc    = hdrs.index('category') + 1
                                    cells = []
                                    for ri, rv in enumerate(vals[1:], start=2):
                                        if rv[cc - 1] == cat:
                                            cells.append(gspread.Cell(row=ri, col=cc, value=new_name.strip()))
                                    if cells:
                                        api_call(ws_p.update_cells, cells)
                            except Exception as e:
                                st.warning(f'Category renamed but some products could not be updated: {e}')
                            st.session_state[edit_k] = False
                            clear_data_cache()
                            toast(f'Category renamed to "{new_name.strip()}".')
                            st.rerun()
                if rc3.form_submit_button('Cancel'):
                    st.session_state[edit_k] = False
                    st.rerun()

        st.markdown('<hr style="margin:.15rem 0;border-color:#F4F4F4;">', unsafe_allow_html=True)
