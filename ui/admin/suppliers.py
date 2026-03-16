# ui/admin/suppliers.py

import uuid
from datetime import datetime
import streamlit as st
from services.sheets_client import (
    read_df, clear_data_cache, get_ws, api_call,
    update_supplier_in_sheet, delete_supplier_from_sheet)
from ui.components import empty, safe_write, toast, esc


def page_suppliers():
    st.title('Suppliers')

    # ── Add Supplier (collapsible) ────────────────────────
    with st.expander('➕ Add Supplier', expanded=False):
        _form_add_supplier()

    st.markdown('---')

    # ── Supplier list ─────────────────────────────────────
    _tab_list_suppliers()


def _form_add_supplier():
    prods  = read_df('products')
    pnames = prods['product_name'].tolist() if not prods.empty else []

    with st.form('add_supplier'):
        c1, c2 = st.columns(2)
        with c1:
            sname  = st.text_input('Supplier / Business Name *')
            person = st.text_input('Contact Person')
            phone  = st.text_input('Phone / Mobile')
            email  = st.text_input('Email Address')
        with c2:
            loc    = st.text_area('Address / Location')
            linked = st.multiselect('Products They Supply', pnames)
            notes  = st.text_area('Notes')

        if st.form_submit_button('Add Supplier', type='primary'):
            if not sname.strip():
                st.error('Supplier name is required.')
            else:
                row_data = [
                    f'S{uuid.uuid4().hex[:12]}',
                    sname.strip(), person, phone, email,
                    loc, ', '.join(linked), notes,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ]

                def _add():
                    ws = get_ws('suppliers')
                    api_call(ws.append_row, row_data,
                             value_input_option='USER_ENTERED')

                with st.spinner('Saving…'):
                    ok = safe_write(_add)
                if ok:
                    clear_data_cache()
                    toast(f'Supplier "{sname}" saved.')
                    st.rerun()


def _tab_list_suppliers():
    df = read_df('suppliers')
    if df.empty:
        empty('No suppliers yet.',
              'Use the form above to add your first supplier.')
        return

    st.caption(f'{len(df)} supplier(s)')

    # Determine ID column
    headers = list(df.columns)
    id_col = 'supplier_id' if 'supplier_id' in headers else headers[0]

    for idx, row in df.iterrows():
        sid    = str(row.get(id_col, ''))
        sname  = str(row.get('supplier_name', ''))
        person = str(row.get('contact_person', ''))
        phone  = str(row.get('phone', ''))
        email  = str(row.get('email', ''))
        loc    = str(row.get('address', row.get('location', '')))
        prods  = str(row.get('products', ''))
        notes  = str(row.get('notes', ''))

        edit_key    = f'sup_edit_{idx}'
        del_key     = f'sup_del_{idx}'
        confirm_key = f'sup_cdel_{idx}'

        # ── Row: info + buttons ───────────────────────────
        col_info, col_edit, col_del = st.columns([8, 1, 1])
        with col_info:
            contact_parts = []
            if person and person != 'nan':
                contact_parts.append(person)
            if phone and phone != 'nan':
                contact_parts.append(phone)
            if email and email != 'nan':
                contact_parts.append(email)
            contact_str = ' · '.join(contact_parts)
            prods_badge = ''
            if prods and prods.strip() and prods != 'nan':
                prods_badge = (
                    f'<span style="font-size:.78rem;background:#FFF3CC;'
                    f'padding:1px 8px;border-radius:4px;color:#4A4A4A;'
                    f'margin-left:8px;">{esc(prods[:60])}</span>')

            st.markdown(
                f'<div style="padding:.4rem .1rem;">'
                f'<span style="font-weight:700;font-size:.95rem;">'
                f'{esc(sname)}</span>{prods_badge}<br>'
                f'<span style="font-size:.82rem;color:#7A7A7A;">'
                f'{esc(contact_str)}</span></div>',
                unsafe_allow_html=True)

        with col_edit:
            if st.button('✏️', key=f'sup_btn_edit_{idx}',
                         use_container_width=True,
                         help=f'Edit {sname}'):
                st.session_state[edit_key] = not st.session_state.get(
                    edit_key, False)
                st.rerun()

        with col_del:
            if st.button('🗑', key=f'sup_btn_del_{idx}',
                         use_container_width=True,
                         help=f'Delete {sname}'):
                st.session_state[confirm_key] = True
                st.rerun()

        # ── Inline edit form ──────────────────────────────
        if st.session_state.get(edit_key):
            all_prods = read_df('products')
            pnames = (all_prods['product_name'].tolist()
                      if not all_prods.empty else [])
            cur_linked = [p.strip() for p in prods.split(',')
                          if p.strip() and p.strip() != 'nan']

            with st.form(key=f'sup_edit_form_{idx}'):
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_name   = st.text_input('Name', value=sname)
                    e_person = st.text_input(
                        'Contact', value=person if person != 'nan' else '')
                    e_phone  = st.text_input(
                        'Phone', value=phone if phone != 'nan' else '')
                    e_email  = st.text_input(
                        'Email', value=email if email != 'nan' else '')
                with ec2:
                    e_loc  = st.text_area(
                        'Address', value=loc if loc != 'nan' else '')
                    e_prod = st.multiselect(
                        'Products', pnames,
                        default=[p for p in cur_linked if p in pnames])
                    e_note = st.text_area(
                        'Notes', value=notes if notes != 'nan' else '')

                c_save, c_cancel = st.columns(2)
                if c_save.form_submit_button('Save', type='primary'):
                    if not e_name.strip():
                        st.error('Name is required.')
                    else:
                        with st.spinner('Saving…'):
                            ok = safe_write(
                                update_supplier_in_sheet, sid, {
                                    'supplier_name':  e_name.strip(),
                                    'contact_person': e_person,
                                    'phone':          e_phone,
                                    'email':          e_email,
                                    'address':        e_loc,
                                    'products':       ', '.join(e_prod),
                                    'notes':          e_note,
                                })
                        if ok:
                            st.session_state[edit_key] = False
                            clear_data_cache()
                            toast(f'"{e_name}" updated.')
                            st.rerun()
                if c_cancel.form_submit_button('Cancel'):
                    st.session_state[edit_key] = False
                    st.rerun()

        # ── Delete confirmation ───────────────────────────
        if st.session_state.get(confirm_key):
            st.warning(f'Delete supplier **{sname}**? This cannot be undone.')
            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button('Yes, Delete', key=f'sup_cdel_yes_{idx}',
                             type='primary', use_container_width=True):
                    with st.spinner('Deleting…'):
                        ok = safe_write(
                            delete_supplier_from_sheet, sid)
                    if ok:
                        st.session_state[confirm_key] = False
                        clear_data_cache()
                        toast(f'"{sname}" deleted.')
                        st.rerun()
            with c_no:
                if st.button('Cancel', key=f'sup_cdel_no_{idx}',
                             use_container_width=True):
                    st.session_state[confirm_key] = False
                    st.rerun()

        st.markdown(
            '<hr style="margin:4px 0;border-color:#E8E0D0;">',
            unsafe_allow_html=True)