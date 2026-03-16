# ui/admin/stock_management.py

import pandas as pd
import streamlit as st
from services.sheets_client import read_df, clear_data_cache, get_stations
from services.inventory_service import update_stock_and_log
from ui.components import empty, safe_write, toast, esc
from config import OUT_REASONS, IN_REASONS


def page_stock_admin():
    st.title('Stock Management')
    df = read_df('products')
    if df.empty:
        empty('No products found.', 'Add products in Manage Products first.')
        return
    STATIONS = get_stations()
    tab_quick, tab_detail = st.tabs(['Quick Update', 'Detailed (with notes)'])
    with tab_quick:
        _quick_stock_widget(df, 'admin', st.session_state.username, STATIONS)
    with tab_detail:
        _detailed_stock_widget(df, 'admin', st.session_state.username, STATIONS)


def _quick_stock_widget(products_df, prefix, username, STATIONS):
    df = products_df.copy()
    df['current_stock'] = pd.to_numeric(
        df['current_stock'], errors='coerce').fillna(0)
    if 'station' not in df.columns:
        df['station'] = 'Others'
    df['station'] = df['station'].replace('', 'Others').fillna('Others')

    col_filter, col_search = st.columns([1, 2])
    with col_filter:
        sf = st.selectbox(
            'Station',
            ['All'] + [s for s in STATIONS if s in df['station'].values],
            key=f'{prefix}_sf')
    with col_search:
        srch = st.text_input(
            'Search', placeholder='Filter by name…', key=f'{prefix}_srch')

    fdf = df if sf == 'All' else df[df['station'] == sf]
    if srch:
        fdf = fdf[fdf['product_name'].str.contains(srch, case=False, na=False)]
    if fdf.empty:
        empty('No products match your filter.')
        return

    def _render_rows(rows_df):
        qs_pending = st.session_state.get('qs_pending')

        if qs_pending:
            p     = qs_pending
            act   = p['action']
            new_s = p['cur'] + p['qty'] if act == 'in' else p['cur'] - p['qty']
            arrow = '+' if act == 'in' else '−'
            st.markdown(
                f'<div style="background:var(--a-surface,#FFF9E6);'
                f'border:1px solid var(--a-border,#E8E0D0);'
                f'border-left:3px solid var(--a-accent,#F5C518);'
                f'border-radius:6px;padding:.8rem 1rem;margin-bottom:.75rem;">'
                f'<p style="font-weight:700;font-size:.88rem;margin:0 0 .3rem 0;">'
                f'Confirm {"Stock In" if act == "in" else "Stock Out"}</p>'
                f'<p style="font-size:.85rem;margin:0;">'
                f'<strong>{esc(p["product"])}</strong>: '
                f'<span style="font-weight:700;">'
                f'{p["cur"]} {arrow} {new_s} {esc(p["unit"])}</span></p>'
                f'</div>', unsafe_allow_html=True)

            reason_opts = IN_REASONS if act == 'in' else OUT_REASONS
            reason = st.selectbox(
                'Reason', reason_opts,
                key=f'{prefix}_qs_reason')

            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button('Apply', key=f'{prefix}_qs_yes',
                             type='primary', use_container_width=True):
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
                if st.button('Cancel', key=f'{prefix}_qs_no',
                             use_container_width=True):
                    st.session_state.pop('qs_pending', None)
                    st.rerun()
            return

        for idx, row in rows_df.reset_index(drop=True).iterrows():
            pname = row['product_name']
            pid   = str(row.get('product_id', ''))
            cur   = int(row['current_stock'])
            unit  = row.get('unit', '')
            stn   = str(row.get('station', ''))
            mn    = int(pd.to_numeric(
                row.get('min_stock', 0), errors='coerce') or 0)
            crit  = int(pd.to_numeric(
                row.get('critical_stock', 0), errors='coerce') or 0)

            if   cur <= crit: weight = 'font-weight:800;'
            elif cur <= mn:   weight = 'font-weight:600;color:#4A4A4A;'
            else:             weight = 'color:#7A7A7A;'

            c1, c2, c3, c4 = st.columns(
                [4, 1, 1, 1], vertical_alignment='center')

            c1.markdown(
                f'<div style="padding:.45rem .1rem;">'
                f'<span style="font-size:.85rem;{weight}">'
                f'{esc(pname)}</span><br>'
                f'<span style="font-size:.82rem;color:#7A7A7A;">'
                f'Stock: <strong style="color:#111;">'
                f'{cur} {esc(unit)}</strong>'
                f'&nbsp;·&nbsp;min {mn}</span></div>',
                unsafe_allow_html=True)

            qty = c2.number_input(
                'Qty', min_value=1, value=1,
                key=f'{prefix}_qty_{stn}_{idx}',
                label_visibility='collapsed')

            if c3.button('+ In', key=f'{prefix}_in_{stn}_{idx}',
                         use_container_width=True, type='primary'):
                st.session_state['qs_pending'] = {
                    'pid': pid, 'product': pname, 'cur': cur,
                    'qty': qty, 'unit': unit,
                    'action': 'in', 'reason': 'Delivery / Restock'}
                st.rerun()

            if c4.button('− Out', key=f'{prefix}_out_{stn}_{idx}',
                         use_container_width=True):
                if qty > cur:
                    st.error(f'Only {cur} {unit} available.')
                else:
                    st.session_state['qs_pending'] = {
                        'pid': pid, 'product': pname, 'cur': cur,
                        'qty': qty, 'unit': unit,
                        'action': 'out', 'reason': ''}
                    st.rerun()

            st.markdown(
                '<hr style="margin:.1rem 0;border-color:#E8E0D0;">',
                unsafe_allow_html=True)

    if sf == 'All':
        for stn_group in STATIONS:
            group = fdf[fdf['station'] == stn_group]
            if group.empty:
                continue
            st.markdown(
                f'<p style="font-size:.75rem;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:1.5px;'
                f'color:#595959;margin:1.2rem 0 .3rem 0;">'
                f'{esc(stn_group)}</p>',
                unsafe_allow_html=True)
            _render_rows(group)
    else:
        _render_rows(fdf)


def _detailed_stock_widget(products_df, prefix, username, STATIONS):
    df = products_df.copy()
    df['current_stock'] = pd.to_numeric(
        df['current_stock'], errors='coerce').fillna(0)
    if 'station' not in df.columns:
        df['station'] = 'Others'
    df['station'] = df['station'].replace('', 'Others').fillna('Others')

    sf = st.selectbox(
        'Filter by Station',
        ['All'] + [s for s in STATIONS if s in df['station'].values],
        key=f'{prefix}_dsf')
    fdf = df if sf == 'All' else df[df['station'] == sf]

    names = fdf['product_name'].tolist()
    if not names:
        empty(f'No products in {sf}.')
        return

    tab_in, tab_out = st.tabs(['Stock In', 'Stock Out'])

    with tab_in:
        sel = st.selectbox('Product', names, key=f'{prefix}_din')
        row = fdf[fdf['product_name'] == sel].iloc[0]
        st.markdown(
            f'<div style="background:#F7F7F8;border:1px solid #EBEBEB;'
            f'border-radius:6px;padding:.5rem 1rem;'
            f'margin:.4rem 0 .8rem 0;font-size:.85rem;">'
            f'Current: <strong>{int(row["current_stock"])} {row["unit"]}</strong>'
            f'&nbsp;·&nbsp;Min: {int(row["min_stock"])}'
            f'&nbsp;·&nbsp;Critical: {int(row["critical_stock"])}</div>',
            unsafe_allow_html=True)

        with st.form(f'{prefix}_din_form'):
            qty   = st.number_input('Quantity to Add', min_value=1, value=1)
            notes = st.text_input(
                'Notes / Source',
                placeholder='e.g. Delivery from Supplier X')
            if st.form_submit_button('Confirm Stock In ✓', type='primary'):
                r   = fdf[fdf['product_name'] == sel].iloc[0]
                pid = str(r.get('product_id', ''))
                old = int(r['current_stock'])
                new = old + qty
                with st.spinner('Saving…'):
                    ok = safe_write(
                        update_stock_and_log,
                        pid, sel, 'stock_in', old, new, notes, username)
                if ok:
                    clear_data_cache()
                    toast(f'Stock In — {sel}: {old}→{new} {r["unit"]}')
                    st.rerun()

    with tab_out:
        sel = st.selectbox('Product', names, key=f'{prefix}_dout')
        row = fdf[fdf['product_name'] == sel].iloc[0]
        st.markdown(
            f'<div style="background:#F7F7F8;border:1px solid #EBEBEB;'
            f'border-radius:6px;padding:.5rem 1rem;'
            f'margin:.4rem 0 .8rem 0;font-size:.85rem;">'
            f'Current: <strong>{int(row["current_stock"])} {row["unit"]}</strong>'
            f'&nbsp;·&nbsp;Min: {int(row["min_stock"])}'
            f'&nbsp;·&nbsp;Critical: {int(row["critical_stock"])}</div>',
            unsafe_allow_html=True)

        with st.form(f'{prefix}_dout_form'):
            qty    = st.number_input('Quantity to Remove', min_value=1, value=1)
            reason = st.selectbox('Reason', OUT_REASONS)
            custom = ''
            if reason == 'Other — specify':
                custom = st.text_input('Please specify reason *')
            notes  = st.text_input('Additional Notes', placeholder='Optional')

            if st.form_submit_button('Confirm Stock Out ✓', type='primary'):
                if reason == 'Other — specify' and not custom.strip():
                    st.error('Please specify the reason.')
                else:
                    r   = fdf[fdf['product_name'] == sel].iloc[0]
                    pid = str(r.get('product_id', ''))
                    old = int(r['current_stock'])
                    if qty > old:
                        st.error(
                            f'Not enough stock. '
                            f'Available: {old} {r["unit"]}')
                    else:
                        new        = old - qty
                        reason_log = (custom if reason == 'Other — specify'
                                      else reason)
                        log_note   = (f'{reason_log} — {notes}'
                                      if notes else reason_log)
                        with st.spinner('Saving…'):
                            ok = safe_write(
                                update_stock_and_log,
                                pid, sel, 'stock_out',
                                old, new, log_note, username)
                        if ok:
                            clear_data_cache()
                            toast(
                                f'Stock Out — {sel}: '
                                f'{old}→{new} {r["unit"]}')
                            st.rerun()