# ui/components.py
import base64, os, time
import streamlit as st
import pandas as pd

def esc(text):
    return (str(text).replace('&','&amp;').replace('<','&lt;')
            .replace('>','&gt;').replace('"','&quot;')
            .replace("'",'&#39;'))

def safe_write(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return True
    except Exception as e:
        st.error(f'Write failed: {e}')
        return False

def toast(message, icon='\u2705'):
    st.toast(message, icon=icon)

def show_success_overlay(title, subtitle=''):
    """Render a full-screen centered success overlay for ~0.65 s then rerun."""
    sub_html = (f'<p style="font-size:.88rem;color:#555;margin:6px 0 0;">'
                f'{subtitle}</p>' if subtitle else '')
    st.markdown(
        f"""
        <style>
        .tg-overlay{{
            position:fixed;inset:0;
            background:rgba(0,0,0,.52);
            display:flex;align-items:center;
            justify-content:center;z-index:9999;
            animation:tg-ov-in 120ms cubic-bezier(.4,0,.2,1) forwards;
        }}
        @keyframes tg-ov-in{{
            from{{opacity:0;transform:scale(.94);}}
            to{{opacity:1;transform:none;}}
        }}
        .tg-overlay-box{{
            background:#fff;border-radius:20px;
            padding:36px 28px;text-align:center;
            max-width:270px;width:85%;
            box-shadow:0 12px 40px rgba(0,0,0,.22);
            animation:tg-box-in 150ms cubic-bezier(.34,1.56,.64,1) 60ms both;
        }}
        @keyframes tg-box-in{{
            from{{opacity:0;transform:scale(.88) translateY(12px);}}
            to{{opacity:1;transform:none;}}
        }}
        .tg-ov-icon{{
            font-size:2.6rem;margin-bottom:10px;
            animation:tg-pop .3s cubic-bezier(.34,1.56,.64,1) 120ms both;
        }}
        @keyframes tg-pop{{
            from{{transform:scale(0);}}
            to{{transform:scale(1);}}
        }}
        </style>
        <div class="tg-overlay">
          <div class="tg-overlay-box">
            <div class="tg-ov-icon">✅</div>
            <p style="font-size:1.05rem;font-weight:700;margin:0;color:#1a1a1a;">{title}</p>
            {sub_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True)
    time.sleep(0.65)
    st.rerun()

def get_logo_b64():
    for path in ['assets/App.png', 'assets/logo.png', 'assets/logo.jpg']:
        if os.path.exists(path):
            try:
                with open(path,'rb') as f:
                    return base64.b64encode(f.read()).decode()
            except Exception:
                pass
    return ''

# ── Status helpers ────────────────────────────────────────

STATUS_COLORS = {
    'Critical': '#E53935',
    'Low':      '#F9A825',
    'OK':       '#43A047',
}

def status_dot(status):
    """Returns an inline SVG colored dot + visually-hidden text for the given status."""
    color = STATUS_COLORS.get(status, '#D4C9B8')
    # The visually-hidden span ensures status is not conveyed by color alone (WCAG 1.4.1)
    return (
        f'<svg width="8" height="8" aria-hidden="true" '
        f'style="display:inline-block;vertical-align:middle;">'
        f'<circle cx="4" cy="4" r="4" fill="{color}"/></svg>'
        f'<span style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;'
        f'overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;">'
        f'{status}</span>')

def compute_status(df):
    df = df.copy()
    for col in ['current_stock','critical_stock','min_stock']:
        df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)
    def _s(row):
        if row['current_stock'] <= row['critical_stock']: return 'Critical'
        if row['current_stock'] <= row['min_stock']:      return 'Low'
        return 'OK'
    df['status'] = df.apply(_s, axis=1)
    return df

# ── Multi-supplier helpers ────────────────────────────────

def parse_suppliers(val):
    """Parse a pipe-separated supplier string into a list."""
    if not val or str(val).strip() in ('', 'nan', '— None —'):
        return []
    return [s.strip() for s in str(val).split('|') if s.strip()]

def join_suppliers(lst):
    """Join a list of supplier names into pipe-separated string."""
    return '|'.join(s.strip() for s in lst if s.strip())

# ── UI components ─────────────────────────────────────────

def empty(title, subtitle=''):
    sub = f'<p class="m-empty-sub">{esc(subtitle)}</p>' if subtitle else ''
    st.markdown(
        f'<div class="m-empty">'
        f'<p class="m-empty-icon">—</p>'
        f'<p class="m-empty-title">{esc(title)}</p>'
        f'{sub}</div>',
        unsafe_allow_html=True)

def safe_idx(lst, value, default=0):
    try:    return lst.index(value)
    except: return default

def badge(text, bg='#FFF3CC', color='#4A4A4A'):
    return (f'<span style="background:{bg};color:{color};padding:1px 8px;'
            f'border-radius:4px;font-size:.72rem;font-weight:600;">{esc(text)}</span>')

def status_badge(status):
    """Badge with colored dot + text label."""
    dot = status_dot(status)
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'font-size:.78rem;font-weight:600;color:#4A4A4A;">'
            f'{dot} {esc(status)}</span>')

def metric_card(col, label, value, css_class=''):
    cls = f' {css_class}' if css_class else ''
    col.markdown(
        f'<div class="kpi-card{cls}">'
        f'<p class="kpi-label">{esc(label)}</p>'
        f'<p class="kpi-value">{value}</p>'
        f'</div>',
        unsafe_allow_html=True)

def product_grid_header():
    st.markdown(
        '<div class="pgrid-header">'
        '<span></span>'
        '<span>Product</span>'
        '<span>Stock</span>'
        '<span>Unit</span>'
        '<span>Min</span>'
        '<span>Critical</span>'
        '<span>Station</span>'
        '</div>', unsafe_allow_html=True)

def product_grid_row(row):
    pname  = esc(str(row.get('product_name','')))
    cur    = int(pd.to_numeric(row.get('current_stock',0), errors='coerce') or 0)
    unit   = esc(str(row.get('unit','')))
    mn     = int(pd.to_numeric(row.get('min_stock',0), errors='coerce') or 0)
    crit   = int(pd.to_numeric(row.get('critical_stock',0), errors='coerce') or 0)
    stn    = esc(str(row.get('station','')))
    status = str(row.get('status','OK'))
    dot    = status_dot(status)
    st.markdown(
        f'<div class="pgrid-row">'
        f'<span>{dot}</span>'
        f'<span style="font-weight:600;">{pname}</span>'
        f'<span class="pgrid-stock">{cur}</span>'
        f'<span class="pgrid-muted">{unit}</span>'
        f'<span class="pgrid-muted">{mn}</span>'
        f'<span class="pgrid-muted">{crit}</span>'
        f'<span class="pgrid-muted">{stn}</span>'
        f'</div>', unsafe_allow_html=True)

def stock_table(df, show_min=False):
    """Renders inventory as a proper HTML table with columns."""
    if df.empty:
        empty('No products in this station.')
        return

    _STH = ('padding:6px 8px;text-align:left;font-size:.78rem;'
            'text-transform:uppercase;letter-spacing:.06em;color:#7A7A7A;'
            'font-weight:600;')
    _STD = 'padding:6px 8px;font-size:.92rem;'

    rows_html = []
    for _, row in df.iterrows():
        pname  = esc(str(row.get('product_name', '')))
        cur    = int(pd.to_numeric(row.get('current_stock', 0), errors='coerce') or 0)
        unit   = esc(str(row.get('unit', '')))
        mn     = int(pd.to_numeric(row.get('min_stock', 0), errors='coerce') or 0)
        crit   = int(pd.to_numeric(row.get('critical_stock', 0), errors='coerce') or 0)
        status = str(row.get('status', 'OK'))
        dot    = status_dot(status)
        cat    = esc(str(row.get('category', '')))

        min_td = (f'<td style="{_STD}text-align:right;color:#7A7A7A;">{mn}</td>'
                  f'<td style="{_STD}text-align:right;color:#7A7A7A;">{crit}</td>'
                  if show_min else '')
        min_th = ''
        rows_html.append(
            f'<tr style="border-bottom:1px solid #E8E0D0;">'
            f'<td style="{_STD}width:26px;">{dot}</td>'
            f'<td style="{_STD}font-weight:600;">{pname}</td>'
            f'<td style="{_STD}color:#7A7A7A;">{cat}</td>'
            f'<td style="{_STD}text-align:right;font-weight:700;">{cur}</td>'
            f'<td class="inv-col-unit" style="{_STD}color:#7A7A7A;">{unit}</td>'
            f'{min_td}'
            f'</tr>')

    min_hdr = ''
    if show_min:
        min_hdr = (
            f'<th scope="col" style="{_STH}text-align:right;">Min</th>'
            f'<th scope="col" style="{_STH}text-align:right;">Crit</th>')

    st.markdown(
        '<div style="overflow-x:auto;">'
        '<table class="admin-tbl" style="width:100%;border-collapse:collapse;'
        'font-size:.92rem;">'
        '<thead><tr style="border-bottom:2px solid #E8E0D0;">'
        f'<th scope="col" style="{_STH}width:26px;"></th>'
        f'<th scope="col" style="{_STH}">Product</th>'
        f'<th scope="col" style="{_STH}">Category</th>'
        f'<th scope="col" style="{_STH}text-align:right;">Stock</th>'
        f'<th scope="col" class="inv-col-unit" style="{_STH}">Unit</th>'
        f'{min_hdr}'
        '</tr></thead><tbody>'
        + ''.join(rows_html) +
        '</tbody></table></div>',
        unsafe_allow_html=True)

def station_stock_tabs(df, stations, show_min=False):
    stn_col = df['station'] if 'station' in df.columns else None
    present = [s for s in stations if stn_col is not None and s in stn_col.values]
    if not present:
        stock_table(df, show_min)
        return
    all_tabs = ['All'] + present
    tabs = st.tabs(all_tabs)
    for tab, stn in zip(tabs, all_tabs):
        with tab:
            if stn == 'All':
                stock_table(df, show_min)
            else:
                stock_table(df[df['station']==stn], show_min)