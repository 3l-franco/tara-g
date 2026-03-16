# ui/admin/dashboard.py

import pandas as pd
import streamlit as st
from services.sheets_client import (
    read_df, clear_data_cache, get_stations)
from ui.components import (
    compute_status, metric_card, empty, status_dot,
    esc, parse_suppliers)
from config import CATEGORIES
from datetime import datetime, timedelta
from config import ph_now


# ── Shared table-header style ─────────────────────────────
_TH = ('padding:6px 8px;text-align:left;font-size:.78rem;'
       'text-transform:uppercase;letter-spacing:.06em;color:#7A7A7A;'
       'font-weight:600;')
_TD = 'padding:6px 8px;font-size:.92rem;'


def page_dashboard():
    st.title('Dashboard')

    # ── Refresh row ───────────────────────────────────────
    c_ref, c_time = st.columns([1, 5])
    if c_ref.button('Refresh', key='dash_refresh'):
        clear_data_cache()
        st.rerun()
    c_time.caption(
        ph_now().strftime('As of %B %d, %Y · %I:%M %p')
        + ' · data cached up to 5 min')

    df = read_df('products')
    if df.empty:
        empty('No products yet.',
              'Go to Products & Stock to add your first item.')
        return

    df       = compute_status(df)
    n_total  = len(df)
    n_crit   = len(df[df['status'] == 'Critical'])
    n_low    = len(df[df['status'] == 'Low'])
    n_ok     = len(df[df['status'] == 'OK'])

    # ── KPI Cards ─────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    metric_card(c1, 'Total Products', n_total)
    metric_card(c2, 'Critical',       n_crit,  'crit')
    metric_card(c3, 'Low Stock',      n_low,   'low')
    metric_card(c4, 'Good',           n_ok,    'ok')

    st.markdown('---')

    # ── Dashboard tabs (native Streamlit tabs) ────────────
    alert_label = f'Restock Alerts ({n_crit + n_low})'
    reorder_label = f'Re-order ({n_crit + n_low})'
    t_alerts, t_cat, t_sup, t_reorder, t_activity = st.tabs(
        [alert_label, 'By Category', 'By Supplier',
         reorder_label, 'Recent Activity'])

    with t_alerts:
        _tab_restock_alerts(df)
    with t_cat:
        _tab_category(df)
    with t_sup:
        _tab_supplier(df)
    with t_reorder:
        _tab_reorder(df)
    with t_activity:
        _tab_recent_activity()


# ══════════════════════════════════════════════════════════
#  Tab: Restock Alerts
# ══════════════════════════════════════════════════════════

def _tab_restock_alerts(df):
    alerts = df[df['status'].isin(['Critical', 'Low'])]
    if alerts.empty:
        st.caption('All items are sufficiently stocked.')
        return

    # Sort: Critical first, then Low; alphabetical within each
    order = {'Critical': 0, 'Low': 1}
    alerts = alerts.copy()
    alerts['_sort'] = alerts['status'].map(order).fillna(2)
    alerts = (alerts.sort_values(['_sort', 'product_name'])
              .drop(columns=['_sort']).reset_index(drop=True))

    st.caption(f'{len(alerts)} item(s) need attention')
    _product_grid(alerts, show_station=True)


# ══════════════════════════════════════════════════════════
#  Tab: By Category
# ══════════════════════════════════════════════════════════

def _tab_category(df):
    cat_col = df['category'] if 'category' in df.columns else None
    cats_present = ['All'] + [
        c for c in CATEGORIES
        if cat_col is not None and c in cat_col.values]

    # Build labels with alert counts
    cat_labels = []
    for c in cats_present:
        sub = df if c == 'All' else df[df['category'] == c]
        cnt = len(sub[sub['status'].isin(['Critical', 'Low'])])
        label = f'{c} ({cnt})' if cnt else c
        cat_labels.append(label)

    chosen = st.selectbox(
        'Category', cat_labels, key='dash_cat_sel',
        label_visibility='collapsed')
    # Extract actual category name (strip the count suffix)
    chosen_name = chosen.split(' (')[0]

    subset = df if chosen_name == 'All' else df[df['category'] == chosen_name]

    if subset.empty:
        empty(f'No products in {chosen_name}.')
        return

    nc = len(subset[subset['status'] == 'Critical'])
    nl = len(subset[subset['status'] == 'Low'])
    nk = len(subset[subset['status'] == 'OK'])
    st.caption(
        f'{len(subset)} products — {nc} critical, {nl} low, {nk} good')

    _product_grid(subset, show_station=True)


# ══════════════════════════════════════════════════════════
#  Tab: By Supplier
# ══════════════════════════════════════════════════════════

def _tab_supplier(df):
    sup_df = read_df('suppliers')

    sup_info = {}
    if not sup_df.empty:
        for _, sr in sup_df.iterrows():
            sname = str(sr.get('supplier_name', '')).strip()
            if sname:
                sup_info[sname.lower()] = {
                    'name': sname,
                    'contact': str(sr.get('contact_person', '')),
                    'phone': str(sr.get('phone', '')),
                    'email': str(sr.get('email', '')),
                }

    groups = {}
    for _, row in df.iterrows():
        suppliers = parse_suppliers(row.get('supplier', ''))
        if not suppliers:
            suppliers = ['— No Supplier —']
        for s in suppliers:
            groups.setdefault(s, []).append(row)

    if not groups:
        empty('No supplier data available.')
        return

    for sup_name in sorted(groups.keys()):
        items = groups[sup_name]
        info = sup_info.get(sup_name.lower(), {})
        contact_parts = []
        if info.get('contact'):
            contact_parts.append(info['contact'])
        if info.get('phone'):
            contact_parts.append(info['phone'])
        if info.get('email'):
            contact_parts.append(info['email'])
        contact_line = ' · '.join(contact_parts)

        alerts_count = sum(
            1 for it in items
            if str(it.get('status', '')) in ('Critical', 'Low'))
        badge_html = ''
        if alerts_count:
            badge_html = (
                f'<span style="background:var(--dot-crit,#E53935);color:#FFF;'
                f'font-size:.72rem;font-weight:700;padding:1px 7px;'
                f'border-radius:10px;margin-left:8px;">'
                f'{alerts_count}</span>')

        grp_cls = 'supplier-group unlinked' if sup_name.startswith('\u2014') else 'supplier-group'
        st.markdown(
            f'<div class="{grp_cls}">'
            f'<p class="supplier-name">'
            f'{esc(sup_name)}{badge_html}</p>'
            + (f'<p class="supplier-contact">'
               f'{esc(contact_line)}</p>'
               if contact_line else '') +
            '</div>', unsafe_allow_html=True)

        sub = pd.DataFrame(items)
        if 'status' not in sub.columns:
            sub = compute_status(sub)
        _product_grid(sub, show_station=True)


# ══════════════════════════════════════════════════════════
#  Tab: Re-order (Critical + Low grouped by supplier)
# ══════════════════════════════════════════════════════════

def _tab_reorder(df):
    alerts = df[df['status'].isin(['Critical', 'Low'])].copy()
    if alerts.empty:
        st.caption('All items are sufficiently stocked — nothing to re-order.')
        return

    sup_df = read_df('suppliers')
    sup_info = {}
    if not sup_df.empty:
        for _, sr in sup_df.iterrows():
            sname = str(sr.get('supplier_name', '')).strip()
            if sname:
                sup_info[sname.lower()] = {
                    'name': sname,
                    'contact': str(sr.get('contact_person', '')),
                    'phone': str(sr.get('phone', '')),
                    'email': str(sr.get('email', '')),
                }

    # Group by supplier; products with 2+ suppliers appear under each
    groups = {}
    for _, row in alerts.iterrows():
        suppliers = parse_suppliers(row.get('supplier', ''))
        if not suppliers:
            suppliers = ['— No Supplier —']
        for s in suppliers:
            groups.setdefault(s, []).append(row)

    # Sort groups alphabetically, but "No Supplier" last
    sorted_keys = sorted(
        groups.keys(),
        key=lambda k: (k.startswith('—'), k.lower()))

    st.caption(
        f'{len(alerts)} item(s) need re-ordering across '
        f'{len(groups)} supplier(s)')

    for sup_name in sorted_keys:
        items = groups[sup_name]
        info = sup_info.get(sup_name.lower(), {})
        contact_parts = []
        if info.get('contact'):
            contact_parts.append(info['contact'])
        if info.get('phone'):
            contact_parts.append(info['phone'])
        if info.get('email'):
            contact_parts.append(info['email'])
        contact_line = ' · '.join(contact_parts)

        rg_cls = 'reorder-group unlinked' if sup_name.startswith('\u2014') else 'reorder-group'
        st.markdown(
            f'<div class="{rg_cls}">'
            f'<p class="reorder-supplier">{esc(sup_name)}'
            f' <span style="font-size:.8rem;color:#7A7A7A;">'
            f'({len(items)} item{"s" if len(items) != 1 else ""})</span></p>'
            + (f'<p class="reorder-contact">{esc(contact_line)}</p>'
               if contact_line else '') +
            '</div>', unsafe_allow_html=True)

        # Build table for this supplier
        order = {'Critical': 0, 'Low': 1}
        sub = pd.DataFrame(items)
        sub['_sort'] = sub['status'].map(order).fillna(2)
        sub = (sub.sort_values(['_sort', 'product_name'])
               .drop(columns=['_sort']).reset_index(drop=True))

        rows_html = []
        for _, r in sub.iterrows():
            pname  = esc(str(r.get('product_name', '')))
            cur    = int(pd.to_numeric(
                r.get('current_stock', 0), errors='coerce') or 0)
            unit   = esc(str(r.get('unit', '')))
            mn     = int(pd.to_numeric(
                r.get('min_stock', 0), errors='coerce') or 0)
            status = str(r.get('status', 'OK'))
            dot    = status_dot(status)
            cat    = esc(str(r.get('category', '')))
            stn    = esc(str(r.get('station', '')))

            rows_html.append(
                f'<tr style="border-bottom:1px solid #E8E0D0;">'
                f'<td style="{_TD}width:26px;">{dot}</td>'
                f'<td style="{_TD}font-weight:600;">{pname}</td>'
                f'<td style="{_TD}color:#7A7A7A;">{cat}</td>'
                f'<td style="{_TD}text-align:right;font-weight:700;">'
                f'{cur}</td>'
                f'<td style="{_TD}text-align:right;color:#7A7A7A;">'
                f'{mn}</td>'
                f'<td style="{_TD}color:#7A7A7A;">{unit}</td>'
                f'<td style="{_TD}color:#7A7A7A;">{stn}</td>'
                f'</tr>')

        st.markdown(
            '<div style="overflow-x:auto;margin-bottom:16px;">'
            '<table class="admin-tbl" style="width:100%;border-collapse:collapse;'
            'font-size:.92rem;">'
            '<thead><tr style="border-bottom:2px solid #E8E0D0;">'
            f'<th scope="col" style="{_TH}width:26px;"></th>'
            f'<th scope="col" style="{_TH}">Product</th>'
            f'<th scope="col" style="{_TH}">Category</th>'
            f'<th scope="col" style="{_TH}text-align:right;">Stock</th>'
            f'<th scope="col" style="{_TH}text-align:right;">Min</th>'
            f'<th scope="col" style="{_TH}">Unit</th>'
            f'<th scope="col" style="{_TH}">Station</th>'
            '</tr></thead><tbody>'
            + ''.join(rows_html) +
            '</tbody></table></div>',
            unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  Tab: Recent Activity
# ══════════════════════════════════════════════════════════

def _tab_recent_activity():
    tx = read_df('transactions')
    if tx.empty:
        empty('No transactions yet.')
        return

    time_filter = st.selectbox(
        'Period', ['All', 'Today', 'Last 7 Days', 'Last 30 Days'],
        key='dash_time_sel', label_visibility='collapsed')

    now = ph_now()
    filtered = tx.copy()

    if time_filter != 'All':
        try:
            filtered['_dt'] = filtered['date'].apply(
                lambda d: datetime.strptime(str(d).strip(), '%Y-%m-%d')
                if str(d).strip() else now)
        except Exception:
            filtered['_dt'] = now

        if time_filter == 'Today':
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_filter == 'Last 7 Days':
            cutoff = now - timedelta(days=7)
        else:
            cutoff = now - timedelta(days=30)

        filtered = filtered[filtered['_dt'] >= cutoff]
        if '_dt' in filtered.columns:
            filtered = filtered.drop(columns=['_dt'])

    if filtered.empty:
        st.caption('No transactions in this period.')
        return

    recent = filtered.tail(20).iloc[::-1].reset_index(drop=True)
    st.caption(f'{len(recent)} of {len(filtered)} transactions shown')

    rows_html = []
    for _, r in recent.iterrows():
        act   = str(r.get('action', ''))
        is_in = act == 'stock_in'
        label = 'IN' if is_in else 'OUT'
        weight = 'font-weight:700;' if is_in else 'font-weight:600;color:#4A4A4A;'
        prod  = esc(str(r.get('product_name', '—')))
        user  = esc(str(r.get('username', '')))
        date  = esc(str(r.get('date', '')))
        time_ = esc(str(r.get('time', ''))[:5])
        qty   = r.get('quantity_changed', '')
        rows_html.append(
            f'<tr style="border-bottom:1px solid #E8E0D0;">'
            f'<td style="{_TD}white-space:nowrap;">'
            f'<span style="{weight}">{label}</span></td>'
            f'<td style="{_TD}font-weight:600;">{prod}</td>'
            f'<td style="{_TD}text-align:center;">{qty}</td>'
            f'<td style="{_TD}">{user}</td>'
            f'<td style="{_TD}color:#7A7A7A;font-size:.88rem;">'
            f'{date} {time_}</td>'
            f'</tr>')

    st.markdown(
        '<div style="overflow-x:auto;">'
        '<table class="admin-tbl" style="width:100%;border-collapse:collapse;'
        'font-size:.92rem;">'
        '<thead><tr style="border-bottom:2px solid #E8E0D0;">'
        f'<th scope="col" style="{_TH}">Action</th>'
        f'<th scope="col" style="{_TH}">Product</th>'
        f'<th scope="col" style="{_TH}text-align:center;">Qty</th>'
        f'<th scope="col" style="{_TH}">User</th>'
        f'<th scope="col" style="{_TH}">Date</th>'
        '</tr></thead><tbody>'
        + ''.join(rows_html) +
        '</tbody></table></div>',
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  Shared: product grid table
# ══════════════════════════════════════════════════════════

def _product_grid(df, show_station=False):
    """Renders products as a proper HTML table with aligned columns."""
    rows_html = []
    for _, row in df.iterrows():
        pname  = esc(str(row.get('product_name', '')))
        cur    = int(pd.to_numeric(
            row.get('current_stock', 0), errors='coerce') or 0)
        unit   = esc(str(row.get('unit', '')))
        mn     = int(pd.to_numeric(
            row.get('min_stock', 0), errors='coerce') or 0)
        crit   = int(pd.to_numeric(
            row.get('critical_stock', 0), errors='coerce') or 0)
        stn    = esc(str(row.get('station', '')))
        status = str(row.get('status', 'OK'))
        dot    = status_dot(status)

        stn_td = (f'<td style="{_TD}color:#7A7A7A;">{stn}</td>'
                  if show_station else '')
        rows_html.append(
            f'<tr style="border-bottom:1px solid #E8E0D0;">'
            f'<td style="{_TD}width:26px;">{dot}</td>'
            f'<td style="{_TD}font-weight:600;">{pname}</td>'
            f'<td style="{_TD}text-align:right;font-weight:700;">'
            f'{cur}</td>'
            f'<td style="{_TD}color:#7A7A7A;">{unit}</td>'
            f'<td style="{_TD}text-align:right;color:#7A7A7A;">{mn}</td>'
            f'<td style="{_TD}text-align:right;color:#7A7A7A;">{crit}</td>'
            f'{stn_td}'
            f'</tr>')

    stn_th = (f'<th scope="col" style="{_TH}">Station</th>'
              if show_station else '')
    st.markdown(
        '<div style="overflow-x:auto;">'
        '<table class="admin-tbl" style="width:100%;border-collapse:collapse;'
        'font-size:.92rem;">'
        '<thead><tr style="border-bottom:2px solid #E8E0D0;">'
        f'<th scope="col" style="{_TH}width:26px;"></th>'
        f'<th scope="col" style="{_TH}">Product</th>'
        f'<th scope="col" style="{_TH}text-align:right;">Stock</th>'
        f'<th scope="col" style="{_TH}">Unit</th>'
        f'<th scope="col" style="{_TH}text-align:right;">Min</th>'
        f'<th scope="col" style="{_TH}text-align:right;">Crit</th>'
        f'{stn_th}'
        '</tr></thead><tbody>'
        + ''.join(rows_html) +
        '</tbody></table></div>',
        unsafe_allow_html=True)