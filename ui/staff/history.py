# ui/staff/history.py

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from config import ph_now
from services.sheets_client import read_df, clear_data_cache, get_or_create_ws, api_call
from ui.components import empty, esc
from config import PAGE_SIZE

_TXN_HEADERS = ['date', 'time', 'product_name', 'action',
                'quantity_changed', 'old_stock', 'new_stock', 'notes', 'username', 'unit']


def _fetch_transactions():
    """
    Read the Transactions sheet fresh every time — bypasses read_df cache.
    Auto-creates the tab + header row if missing (get_or_create_ws).
    Returns (DataFrame, error_str_or_None).
    """
    try:
        ws      = get_or_create_ws('transactions', _TXN_HEADERS)
        records = api_call(ws.get_all_records)
        return (pd.DataFrame(records) if records else pd.DataFrame()), None
    except Exception as e:
        return pd.DataFrame(), str(e)


def page_logs_staff():
    """Staff transaction history — all transactions, mobile card log."""
    # ── Refresh button ────────────────────────────────────
    if st.button('↺ Refresh', key='log_refresh', use_container_width=False):
        clear_data_cache()
        st.rerun()

    df, err = _fetch_transactions()

    if err:
        st.error(f'Could not load transactions: {err}')
        return

    if df.empty:
        empty('No transactions yet.',
              'Complete a Stock In or Stock Out to see history here.')
        return

    # ── Filters ───────────────────────────────────────────
    col_type, col_period = st.columns(2)
    with col_type:
        type_opts = {
            'All': 'All',
            'Stock In':  'stock_in',
            'Stock Out': 'stock_out',
        }
        tf_lbl = st.selectbox('Type', list(type_opts.keys()),
                              key='log_type',
                              label_visibility='collapsed')
        tf = type_opts[tf_lbl]
    with col_period:
        period = st.selectbox('Period',
                              ['All time', 'Today', 'Last 7 days'],
                              key='log_period',
                              label_visibility='collapsed')

    fdf       = df.copy()
    today_str = ph_now().strftime('%Y-%m-%d')

    if 'date' in fdf.columns:
        fdf['date'] = fdf['date'].astype(str)
        if period == 'Today':
            fdf = fdf[fdf['date'] == today_str]
        elif period == 'Last 7 days':
            cutoff = (ph_now() - timedelta(days=7)).strftime('%Y-%m-%d')
            fdf    = fdf[fdf['date'] >= cutoff]

    if tf != 'All' and 'action' in fdf.columns:
        fdf = fdf[fdf['action'] == tf]

    # Reset pagination when filters change
    _filter_sig = f'{tf}|{period}'
    if st.session_state.get('_log_staff_fsig') != _filter_sig:
        st.session_state['_log_staff_fsig'] = _filter_sig
        st.session_state['tx_page_staff_mob'] = 1

    # ── Summary stats ─────────────────────────────────────
    n_in  = int((fdf.get('action', pd.Series(dtype=str)) == 'stock_in').sum())
    n_out = int((fdf.get('action', pd.Series(dtype=str)) == 'stock_out').sum())
    st.markdown(
        f'<div class="m-stat-row">'
        f'<div class="m-stat in">'
        f'  <p class="m-stat-n">{n_in}</p>'
        f'  <p class="m-stat-lbl">Stock In</p>'
        f'</div>'
        f'<div class="m-stat out">'
        f'  <p class="m-stat-n">{n_out}</p>'
        f'  <p class="m-stat-lbl">Stock Out</p>'
        f'</div>'
        f'</div>', unsafe_allow_html=True)

    if fdf.empty:
        empty('No transactions for this filter.')
        return

    # ── Pagination ────────────────────────────────────────
    page_key = 'tx_page_staff_mob'
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    total_pages = max(1, (len(fdf) + PAGE_SIZE - 1) // PAGE_SIZE)
    pg          = st.session_state[page_key]
    fdf_sorted  = fdf.iloc[::-1].reset_index(drop=True)
    page_df     = fdf_sorted.iloc[(pg - 1) * PAGE_SIZE: pg * PAGE_SIZE]

    st.caption(f'{len(fdf)} records')

    # ── Log cards ─────────────────────────────────────────
    for _, row in page_df.iterrows():
        act   = str(row.get('action', ''))
        is_in = act == 'stock_in'
        icon  = 'IN' if is_in else 'OUT'
        sign  = '+' if is_in else '−'
        old_s = pd.to_numeric(row.get('old_stock', 0), errors='coerce')
        new_s = pd.to_numeric(row.get('new_stock',  0), errors='coerce')
        old_v = 0 if pd.isna(old_s) else int(old_s)
        new_v = 0 if pd.isna(new_s) else int(new_s)
        delta = abs(new_v - old_v)
        if delta == 0:  # fallback to stored column if available
            delta = int(pd.to_numeric(
                row.get('quantity_changed', 0), errors='coerce') or 0)
        pname = esc(str(row.get('product_name', '—')))
        unit  = esc(str(row.get('unit', '')))
        date  = esc(str(row.get('date', '')))
        time_ = esc(str(row.get('time', ''))[:5])
        notes = str(row.get('notes', ''))
        by    = esc(str(row.get('username', '')).strip())
        cls   = 'in' if is_in else 'out'

        meta_parts = [p for p in [date, time_] if p.strip()]
        if by:
            meta_parts.append(f'by {by}')
        if notes.strip():
            meta_parts.append(esc(notes[:30]))
        meta_html = ' · '.join(meta_parts)

        st.markdown(
            f'<div class="m-log-card">'
            f'  <div class="m-log-icon {cls}">{icon}</div>'
            f'  <div class="m-log-body">'
            f'    <p class="m-log-product">{pname}</p>'
            f'    <p class="m-log-meta">{meta_html}</p>'
            f'  </div>'
            f'  <span class="m-log-delta {cls}">'
            f'    {sign}{delta} {unit}'
            f'  </span>'
            f'</div>', unsafe_allow_html=True)

    # ── Pagination controls ───────────────────────────────
    if len(fdf) > PAGE_SIZE:
        pc1, pc2, pc3 = st.columns([2, 3, 2])
        with pc1:
            if pg > 1 and st.button('← Prev', key='log_mob_prev'):
                st.session_state[page_key] -= 1
                st.rerun()
        with pc2:
            st.caption(f'Page {pg} of {total_pages}')
        with pc3:
            if (pg < total_pages
                    and st.button('Next →', key='log_mob_next')):
                st.session_state[page_key] += 1
                st.rerun()

    # ── Export ────────────────────────────────────────────
    username = st.session_state.get('username', 'staff')
    st.markdown('<div class="m-spacer-8"></div>', unsafe_allow_html=True)
    st.download_button(
        'Export CSV',
        data=fdf.to_csv(index=False).encode(),
        file_name=f'transactions_{ph_now().strftime("%Y%m%d")}.csv',
        mime='text/csv',
        use_container_width=True)