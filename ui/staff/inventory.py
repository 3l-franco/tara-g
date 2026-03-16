# ui/staff/inventory.py

import pandas as pd
import streamlit as st
from services.sheets_client import read_df, get_stations
from ui.components import compute_status, empty, esc, status_dot
from config import CATEGORIES


def _inv_table(sdf):
    """Render inventory as a compact HTML table (mobile-first).
    Columns: dot | Product (+ status label) | Stock | Min | Crit
    """
    rows_html = []
    for _, row in sdf.iterrows():
        pname  = esc(str(row.get('product_name', '—')))
        cur    = int(pd.to_numeric(row.get('current_stock', 0), errors='coerce') or 0)
        mn     = int(pd.to_numeric(row.get('min_stock',      0), errors='coerce') or 0)
        crit   = int(pd.to_numeric(row.get('critical_stock', 0), errors='coerce') or 0)
        status = str(row.get('status', ''))
        dot    = status_dot(status)
        rows_html.append(
            f'<tr>'
            f'<td class="m-sinv-dot">{dot}</td>'
            f'<td class="m-sinv-name">{pname}</td>'
            f'<td class="m-sinv-num">{cur}</td>'
            f'<td class="m-sinv-num muted">{mn}</td>'
            f'<td class="m-sinv-num muted">{crit}</td>'
            f'</tr>'
        )
    st.markdown(
        '<div style="overflow-x:auto;">'
        '<table class="m-sinv-table">'
        '<thead><tr>'
        '<th class="m-sinv-dot"></th>'
        '<th>Product</th>'
        '<th class="m-sinv-num">Stock</th>'
        '<th class="m-sinv-num">Min</th>'
        '<th class="m-sinv-num">Crit</th>'
        '</tr></thead>'
        '<tbody>' + ''.join(rows_html) + '</tbody>'
        '</table></div>',
        unsafe_allow_html=True)


def page_inventory_staff():
    df = read_df('products')
    if df.empty:
        empty('No products yet.')
        return

    df       = compute_status(df)
    STATIONS = get_stations()
    available_stns = [s for s in STATIONS if s in df['station'].values]

    # ── Station filter ────────────────────────────────────
    st.markdown('<p class="m-form-label">STATION</p>', unsafe_allow_html=True)
    sf = st.selectbox('Station', ['All'] + available_stns,
                      key='sinv_station', label_visibility='collapsed')

    # ── Search ────────────────────────────────────────────
    st.markdown('<p class="m-form-label">SEARCH</p>', unsafe_allow_html=True)
    srch = st.text_input('Search', placeholder='\U0001f50d Product name\u2026',
                         key='sinv_search', label_visibility='collapsed')

    # ── Apply filters ─────────────────────────────────────
    fdf = df.copy()
    if sf != 'All':
        fdf = fdf[fdf['station'] == sf]
    if srch:
        fdf = fdf[fdf['product_name'].str.contains(srch, case=False, na=False)]

    # Sort: Critical \u2192 Low \u2192 OK then by name within each
    _order       = {'Critical': 0, 'Low': 1, 'OK': 2}
    fdf          = fdf.copy()
    fdf['_sort'] = fdf['status'].map(_order).fillna(3)
    fdf          = (fdf.sort_values(['_sort', 'station', 'product_name'])
                       .drop(columns=['_sort'])
                       .reset_index(drop=True))

    if fdf.empty:
        empty('No products match your filter.')
        return

    st.caption(f'{len(fdf)} item(s)')

    # ── Group by station ──────────────────────────────────
    if sf == 'All':
        for stn in fdf['station'].unique():
            stn_df = fdf[fdf['station'] == stn]
            st.markdown(
                f'<p class="m-inv-station-hdr">{esc(str(stn))}</p>',
                unsafe_allow_html=True)
            _inv_table(stn_df)
    else:
        _inv_table(fdf)

