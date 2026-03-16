# ui/admin/transactions.py

import streamlit as st
from services.sheets_client import read_df, get_sheet_url
from ui.components import empty, esc
from config import PAGE_SIZE
from datetime import datetime
from config import ph_now


def page_transactions():
    st.title('Transaction Logs')

    df = read_df('transactions')
    if df.empty:
        empty('No transactions yet.')
        return

    # ── Filters ───────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    type_options = {
        'All': 'All',
        'Stock In':  'stock_in',
        'Stock Out': 'stock_out',
    }
    tf_label = c1.selectbox('Type', list(type_options.keys()),
                            key='tx_admin_type')
    tf       = type_options[tf_label]

    pf = c2.selectbox(
        'Product',
        ['All'] + sorted(df['product_name'].unique().tolist())
        if 'product_name' in df.columns else ['All'],
        key='tx_admin_product')

    uf = c3.selectbox(
        'User',
        ['All'] + sorted(df['username'].unique().tolist())
        if 'username' in df.columns else ['All'],
        key='tx_admin_user')

    # Reset pagination when filters change
    _filter_sig = f'{tf}|{pf}|{uf}'
    if st.session_state.get('_tx_admin_fsig') != _filter_sig:
        st.session_state['_tx_admin_fsig'] = _filter_sig
        st.session_state['tx_page_admin'] = 1

    flt = df.copy()
    if tf  != 'All': flt = flt[flt['action']       == tf]
    if pf  != 'All': flt = flt[flt['product_name'] == pf]
    if uf  != 'All': flt = flt[flt['username']     == uf]

    if 'action' in flt.columns:
        flt = flt.copy()
        flt['action'] = flt['action'].map(
            {'stock_in': 'Stock In', 'stock_out': 'Stock Out'}
        ).fillna(flt['action'])

    st.caption(f'{len(flt)} records found.')

    # ── Pagination ────────────────────────────────────────
    page_key    = 'tx_page_admin'
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    total_pages = max(1, (len(flt) + PAGE_SIZE - 1) // PAGE_SIZE)
    page        = st.session_state[page_key]
    displayed   = (flt.iloc[::-1]
                      .reset_index(drop=True)
                      .iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE])

    st.dataframe(displayed, use_container_width=True)

    if len(flt) > PAGE_SIZE:
        pg_cols = st.columns([2, 3, 2])
        with pg_cols[0]:
            if page > 1 and st.button('← Previous', key=f'{page_key}_prev'):
                st.session_state[page_key] -= 1
                st.rerun()
        with pg_cols[1]:
            st.caption(f'Page {page} of {total_pages} · {len(flt)} total')
        with pg_cols[2]:
            if (page < total_pages
                    and st.button('Next →', key=f'{page_key}_next')):
                st.session_state[page_key] += 1
                st.rerun()

    # ── Export & Sheet link ───────────────────────────────
    btn1, btn2 = st.columns(2)
    with btn1:
        st.download_button(
            'Export CSV',
            data=flt.to_csv(index=False).encode(),
            file_name=f'transactions_{ph_now().strftime("%Y%m%d")}.csv',
            mime='text/csv')
    with btn2:
        sheet_url = get_sheet_url()
        if sheet_url:
            st.markdown(
                f'<a href="{sheet_url}" target="_blank" '
                f'rel="noopener noreferrer" '
                f'style="display:block;background:#1A1A1A;color:#FFF;'
                f'border-radius:6px;padding:.45rem 1.1rem;font-size:.85rem;'
                f'font-weight:600;text-align:center;text-decoration:none;'
                f'margin-top:.15rem;">Open Google Sheet</a>',
                unsafe_allow_html=True)