# ui/admin/inventory.py

import streamlit as st
from services.sheets_client import read_df, clear_data_cache, get_stations
from ui.components import (
    compute_status, empty, station_stock_tabs,
    status_dot, metric_card)


def page_inventory():
    st.title('Inventory')

    c_ref, _ = st.columns([1, 5])
    if c_ref.button('Refresh', key='inv_refresh'):
        clear_data_cache()
        st.rerun()

    df = read_df('products')
    if df.empty:
        empty('No products yet.')
        return

    df = compute_status(df)

    # ── Status summary with dots ──────────────────────────
    n_crit = len(df[df['status'] == 'Critical'])
    n_low  = len(df[df['status'] == 'Low'])
    n_ok   = len(df[df['status'] == 'OK'])
    c1, c2, c3 = st.columns(3)
    metric_card(c1, 'Critical', n_crit, 'crit')
    metric_card(c2, 'Low',      n_low,  'low')
    metric_card(c3, 'Good',     n_ok,   'ok')

    # ── Filters ───────────────────────────────────────────
    c_search, c_status = st.columns([3, 1])
    search = c_search.text_input(
        'Search', placeholder='Filter by product name…',
        key='inv_search')
    status_filter = c_status.selectbox(
        'Status', ['All', 'Critical', 'Low', 'OK'],
        key='inv_status_filter')
    if search:
        df = df[df['product_name'].str.contains(
            search, case=False, na=False)]
    if status_filter != 'All':
        df = df[df['status'] == status_filter]

    # Sort by status: Critical first, then Low, then OK
    _order = {'Critical': 0, 'Low': 1, 'OK': 2}
    df = df.copy()
    df['_sort'] = df['status'].map(_order).fillna(3)
    df = (df.sort_values(['_sort', 'product_name'])
            .drop(columns=['_sort']).reset_index(drop=True))

    STATIONS = get_stations()
    station_stock_tabs(df, STATIONS, show_min=True)