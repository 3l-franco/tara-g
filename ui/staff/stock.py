# ui/staff/stock.py

import uuid
import streamlit as st
import pandas as pd
from services.sheets_client import (
    read_df, clear_data_cache, get_stations
)
from services.inventory_service import update_stock_and_log
from ui.components import empty, safe_write, toast, esc, show_success_overlay
from config import IN_REASONS, OUT_REASONS


def page_stock_staff():
    """Staff stock update page — mobile first."""
    # ── Success overlay (shown after a write completes) ───
    _s = st.session_state.pop('_stock_success', None)
    if _s:
        act_label = 'Stock In' if _s['action'] == 'in' else 'Stock Out'
        show_success_overlay(
            f'{act_label} Saved!',
            f'{_s["product"]}: {_s["old"]} \u2192 {_s["new"]} {_s["unit"]}')
        return  # rerun triggered inside overlay; this return is safety

    df = read_df('products')
    if df.empty:
        empty('No products found.', 'Ask your admin to add products first.')
        return

    df['current_stock'] = pd.to_numeric(
        df['current_stock'], errors='coerce').fillna(0)

    _staff_remote_widget(df, st.session_state.username)


def _staff_remote_widget(products_df, username):
    """
    Mobile stock in/out widget.
    Flow: Staff Name → Station → Search → Product → Qty → IN/OUT → Confirm
    """
    STATIONS = get_stations()
    df = products_df.copy()

    if 'station' not in df.columns:
        df['station'] = 'Others'
    df['station'] = df['station'].replace('', 'Others').fillna('Others')

    # ── Staff name selector (who is logging) ─────────────
    udf = read_df('users')
    staff_names = []
    default_idx = 0
    if not udf.empty:
        staff_rows = udf[udf['role'].str.lower() == 'staff']
        for _, r in staff_rows.iterrows():
            dn = str(r.get('display_name', '')).strip()
            un = str(r.get('username', '')).strip()
            staff_names.append(dn if dn else un)
        # Pre-select logged-in user
        me = udf[udf['username'].str.lower() == username.lower()]
        if not me.empty:
            my_dn = str(me.iloc[0].get('display_name', '')).strip()
            my_name = my_dn if my_dn else username
            if my_name in staff_names:
                default_idx = staff_names.index(my_name)

    if not staff_names:
        staff_names = [username]

    st.markdown('<p class="m-form-label">LOGGED BY</p>', unsafe_allow_html=True)
    acting_user = st.selectbox('Logged by', staff_names,
                               index=default_idx,
                               key='staff_acting_user',
                               label_visibility='collapsed')

    # ── Station filter ────────────────────────────────────
    available_stns = [s for s in STATIONS if s in df['station'].values]
    st.markdown('<p class="m-form-label">STATION</p>', unsafe_allow_html=True)
    station = st.selectbox('Station', available_stns,
                           key='staff_remote_stn',
                           label_visibility='collapsed')
    fdf = df[df['station'] == station]

    # ── Product search + select ───────────────────────────
    st.markdown('<p class="m-form-label">PRODUCT</p>', unsafe_allow_html=True)
    srch = st.text_input('Search product',
                         placeholder='🔍  Type to filter…',
                         key='staff_prod_search',
                         label_visibility='collapsed')

    all_names = sorted(fdf['product_name'].tolist())
    filtered_names = (
        [n for n in all_names if srch.strip().lower() in n.lower()]
        if srch.strip() else all_names
    )

    if not filtered_names:
        st.caption(f'No products match "{esc(srch)}" in {esc(station)}')
        return

    if srch.strip() and len(filtered_names) < len(all_names):
        st.caption(
            f'{len(filtered_names)} of {len(all_names)} '
            f'products in {esc(station)}')

    product = st.selectbox('Select product', filtered_names,
                           key='staff_remote_prod',
                           label_visibility='collapsed')

    # Cancel pending if product changed
    pending = st.session_state.get('staff_pending')
    if pending and pending.get('product') != product:
        st.session_state.staff_pending = None
        pending = None

    row  = fdf[fdf['product_name'] == product].iloc[0]
    cur  = int(row['current_stock'])
    mn   = int(pd.to_numeric(row.get('min_stock',     0), errors='coerce') or 0)
    crit = int(pd.to_numeric(row.get('critical_stock', 0), errors='coerce') or 0)
    unit = str(row.get('unit', ''))
    pid  = str(row.get('product_id', ''))
    stn  = str(row.get('station', ''))
    cat  = str(row.get('category', '—'))

    if   cur <= crit: cls = 'crit'; stext = 'Critical'
    elif cur <= mn:   cls = 'low';  stext = 'Low'
    else:             cls = 'ok';   stext = 'OK'

    # ── Product card (compact, CSS-class driven) ──────────
    pill_html = (
        f'<span class="m-status-pill {cls}">{stext}</span>'
        if cls != 'ok' else '')
    st.markdown(
        f'<div class="m-card {cls}">'
        f'  <div class="m-card-row">'
        f'    <div class="m-card-info">'
        f'      <span class="m-card-name">{esc(product)}</span>'
        f'      {pill_html}'
        f'    </div>'
        f'    <div class="m-card-qty">'
        f'      <span class="m-card-qty-num">{cur}</span>'
        f'      <span class="m-card-qty-unit">{esc(unit)}</span>'
        f'    </div>'
        f'  </div>'
        f'</div>', unsafe_allow_html=True)

    # ── Confirmation box ──────────────────────────────────
    if pending is not None:
        # Generate nonce once when confirm dialog appears
        if not st.session_state.get('_confirm_nonce'):
            st.session_state._confirm_nonce = str(uuid.uuid4())

        p         = pending
        act       = p['action']
        new_stock = p['cur'] + p['qty'] if act == 'in' else p['cur'] - p['qty']
        sign      = '+' if act == 'in' else '−'
        label     = 'Stock In' if act == 'in' else 'Stock Out'

        new_color = '#27ae60' if act == 'in' else '#e74c3c'
        st.markdown(
            f'<div class="m-confirm">'
            f'  <p class="m-confirm-title">Confirm {esc(label)}</p>'
            f'  <p class="m-confirm-body">'
            f'    <strong>{esc(p["product"])}</strong><br>'
            f'    <span class="m-confirm-delta">'
            f'      {p["cur"]} \u2192 '
            f'<span style="color:{new_color};font-weight:700;">'
            f'{new_stock}</span> {esc(p["unit"])}'
            f'    </span>'
            f'    <span class="m-confirm-change"> ({sign}{p["qty"]})</span><br>'
            f'    <span class="m-confirm-actor">'
            f'      by {esc(p.get("actor", username))}'
            f'    </span>'
            f'  </p>'
            f'</div>', unsafe_allow_html=True)

        reason_opts = IN_REASONS if act == 'in' else OUT_REASONS
        reason = st.selectbox('Reason', reason_opts,
                              key='staff_confirm_reason')

        c_yes, c_no = st.columns(2)
        with c_yes:
            if st.button('Confirm', key='staff_confirm_yes',
                         use_container_width=True, type='primary'):
                nonce = st.session_state.pop('_confirm_nonce', None)
                if nonce:  # first tap — nonce exists
                    log_action = 'stock_in' if act == 'in' else 'stock_out'
                    actor      = p.get('actor', username)
                    note       = f'{reason} — by {actor}'
                    st.markdown(
                        '<div style="background:var(--m-bg,#FFF9E6);'
                        'border:1px solid var(--m-border,#DDD6C8);'
                        'border-radius:8px;padding:12px 16px;'
                        'text-align:center;font-size:.88rem;'
                        'font-weight:600;color:#4A4A4A;">'
                        '⏳ Saving…</div>',
                        unsafe_allow_html=True)
                    ok = safe_write(
                        update_stock_and_log,
                        p['pid'], p['product'], log_action,
                        p['cur'], new_stock, note, actor)
                    if ok:
                        st.session_state.staff_pending = None
                        clear_data_cache()
                        st.session_state['_stock_success'] = {
                            'action':  act,
                            'product': p['product'],
                            'old':     p['cur'],
                            'new':     new_stock,
                            'unit':    p['unit'],
                        }
                        st.rerun()
        with c_no:
            if st.button('Cancel', key='staff_confirm_no',
                         use_container_width=True):
                st.session_state.staff_pending = None
                st.rerun()
        return

    # ── Qty input + IN / OUT buttons ──────────────────────
    st.markdown('<p class="m-form-label">QUANTITY</p>', unsafe_allow_html=True)
    qty = st.number_input('Qty', min_value=1, value=1,
                          key='staff_remote_qty',
                          label_visibility='collapsed')
    # Marker: CSS in mobile.css uses :has(.m-stock-out-ctx) ~ sibling to
    # style the following secondary button (Stock Out) with danger red.
    st.markdown('<div class="m-stock-out-ctx"></div>', unsafe_allow_html=True)
    if st.button('Stock In', key='staff_btn_in',
                 use_container_width=True, type='primary'):
        st.session_state.staff_pending = {
            'pid': pid, 'product': product, 'cur': cur,
            'qty': qty, 'unit': unit,
            'action': 'in', 'actor': acting_user,
        }
        st.rerun()
    if st.button('Stock Out', key='staff_btn_out',
                 use_container_width=True):
        if qty > cur:
            st.error(f'Only {cur} {unit} available.')
        else:
            st.session_state.staff_pending = {
                'pid': pid, 'product': product, 'cur': cur,
                'qty': qty, 'unit': unit,
                'action': 'out', 'actor': acting_user,
            }
            st.rerun()