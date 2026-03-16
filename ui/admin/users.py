# ui/admin/users.py

import streamlit as st
from services.sheets_client import (
    read_df, clear_data_cache, get_ws, api_call, reset_sheet_data)
from services.auth_service import hash_pw, update_password
from services.inventory_service import delete_user_from_sheet
from ui.components import empty, safe_write, toast, esc
from config import MIN_PASSWORD_LENGTH
from datetime import datetime
from config import ph_now


def _validate_password(pw):
    """Returns error string or None if valid."""
    if len(pw) < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
    if not any(c.isupper() for c in pw):
        return 'Password must contain at least one uppercase letter.'
    if not any(c.isdigit() for c in pw):
        return 'Password must contain at least one digit.'
    return None


def page_users():
    st.title('Users & System')
    tabs = st.tabs([
        'Add User', 'All Users', 'Change My Password', 'System'])
    with tabs[0]:
        _tab_add_user()
    with tabs[1]:
        _tab_list_users()
    with tabs[2]:
        _tab_change_password()
    with tabs[3]:
        _tab_system()


# ══════════════════════════════════════════════════════════
#  TAB: Add User
# ══════════════════════════════════════════════════════════

def _tab_add_user():
    with st.form('add_user'):
        c1, c2 = st.columns(2)
        with c1:
            uname        = st.text_input('Username *')
            fname        = st.text_input('Full Name')
            display_name = st.text_input(
                'Staff Display Name',
                placeholder='Name shown on transaction logs')
        with c2:
            pw1  = st.text_input('Password *',         type='password')
            pw2  = st.text_input('Confirm Password *', type='password')
            role = st.selectbox('Role', ['staff', 'admin'])
        st.caption(f'Password: min {MIN_PASSWORD_LENGTH} chars, '
                   f'1 uppercase letter, 1 digit.')

        if st.form_submit_button('Add User', type='primary'):
            if not uname or not pw1:
                st.error('Username and password are required.')
            elif pw1 != pw2:
                st.error('Passwords do not match.')
            else:
                err = _validate_password(pw1)
                if err:
                    st.error(err)
                else:
                    ex = read_df('users')
                    if (not ex.empty
                            and uname.lower()
                            in ex['username'].str.lower().values):
                        st.warning('Username is already taken.')
                    else:
                        def _add():
                            from services.sheets_client import get_or_create_ws
                            ws_u = get_ws('users')
                            hdrs = api_call(ws_u.row_values, 1)
                            if 'display_name' not in hdrs:
                                api_call(ws_u.update_cell,
                                         1, len(hdrs) + 1,
                                         'display_name')
                                hdrs.append('display_name')
                            # User profile — no password stored here
                            data = {
                                'username':     uname.strip(),
                                'full_name':    fname,
                                'role':         role,
                                'display_name': display_name.strip(),
                                'added_at':     ph_now().strftime(
                                    '%Y-%m-%d %H:%M:%S'),
                            }
                            api_call(
                                ws_u.append_row,
                                [data.get(h, '') for h in hdrs],
                                value_input_option='USER_ENTERED')
                            # Write password hash to dedicated _Creds sheet
                            creds_ws = get_or_create_ws(
                                'creds', ['username', 'password'])
                            api_call(creds_ws.append_row,
                                     [uname.strip(), hash_pw(pw1)],
                                     value_input_option='USER_ENTERED')

                        with st.spinner('Creating user…'):
                            ok = safe_write(_add)
                        if ok:
                            clear_data_cache()
                            toast(f'User "@{uname}" ({role}) created.')
                            st.rerun()


# ══════════════════════════════════════════════════════════
#  TAB: All Users (list + password reset per user)
# ══════════════════════════════════════════════════════════

def _tab_list_users():
    df = read_df('users')
    if df.empty:
        empty('No users found.')
        return

    display_df   = df.drop(columns=['password'], errors='ignore')
    current_user = st.session_state.get('username', '').lower()
    st.caption(f'{len(display_df)} user(s) registered.')

    for idx, row in display_df.iterrows():
        uname_row = str(row.get('username', ''))
        role_row  = str(row.get('role', ''))
        fname_row = str(row.get('full_name', row.get('name', '')))
        dname_row = str(row.get('display_name', '')).strip()
        is_self   = uname_row.lower() == current_user

        col_info, col_pw, col_del = st.columns([5, 1, 1])
        dname_html = (
            f'&nbsp;· <span style="font-size:.75rem;background:#FFF3CC;'
            f'padding:1px 7px;border-radius:10px;color:#4A4A4A;">'
            f'display: {esc(dname_row)}</span>'
            if dname_row else '')

        with col_info:
            st.markdown(
                f'<div style="padding:.4rem .1rem;">'
                f'<span style="font-weight:700;font-size:.88rem;">'
                f'@{esc(uname_row)}</span>&nbsp;&nbsp;'
                f'<span style="font-size:.75rem;'
                f'background:{"#1A1A1A" if role_row == "admin" else "#FFF3CC"};'
                f'color:{"#FFF" if role_row == "admin" else "#4A4A4A"};'
                f'padding:1px 8px;border-radius:20px;font-weight:600;">'
                f'{esc(role_row)}</span>'
                f'{"&nbsp;&nbsp;<span style=\'font-size:.8rem;color:#595959;\'>" + esc(fname_row) + "</span>" if fname_row else ""}'
                f'{dname_html}'
                f'{"&nbsp;<span style=\'font-size:.75rem;color:#767676;\'>(you)</span>" if is_self else ""}'
                f'</div>',
                unsafe_allow_html=True)

        # ── Password Reset button ─────────────────────────
        pw_key = f'pw_reset_{idx}'
        if col_pw.button('Reset PW', key=f'btn_pw_{idx}',
                         use_container_width=True,
                         help=f'Reset password for @{uname_row}'):
            st.session_state[pw_key] = not st.session_state.get(
                pw_key, False)
            st.rerun()

        # ── Delete button ─────────────────────────────────
        del_key     = f'del_user_{idx}'
        confirm_key = f'confirm_del_user_{idx}'

        if is_self:
            col_del.markdown(
                '<span style="font-size:.8rem;color:#DDD;" '
                'title="Cannot delete yourself">—</span>',
                unsafe_allow_html=True)
        else:
            if col_del.button('Delete', key=del_key,
                              help=f'Delete @{uname_row}',
                              use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()

        # ── Password reset form (inline) ──────────────────
        if st.session_state.get(pw_key):
            with st.form(key=f'pw_form_{idx}'):
                st.caption(f'Set new password for @{uname_row}')
                np1 = st.text_input('New Password', type='password',
                                    key=f'np1_{idx}')
                np2 = st.text_input('Confirm Password', type='password',
                                    key=f'np2_{idx}')
                c_save, c_cancel = st.columns(2)
                if c_save.form_submit_button('Reset Password',
                                             type='primary'):
                    if not np1:
                        st.error('Password is required.')
                    elif np1 != np2:
                        st.error('Passwords do not match.')
                    else:
                        err = _validate_password(np1)
                        if err:
                            st.error(err)
                        else:
                            with st.spinner('Updating…'):
                                ok = safe_write(
                                    update_password, uname_row, np1)
                            if ok:
                                st.session_state[pw_key] = False
                                clear_data_cache()
                                toast(
                                    f'Password reset for '
                                    f'@{uname_row}.')
                                st.rerun()
                if c_cancel.form_submit_button('Cancel'):
                    st.session_state[pw_key] = False
                    st.rerun()

        # ── Delete confirmation ───────────────────────────
        if st.session_state.get(confirm_key):
            st.warning(
                f'Delete user **@{uname_row}**? Cannot be undone.')
            c_yes, c_no = st.columns(2)
            if c_yes.button('Yes, Delete', key=f'yes_{del_key}',
                            type='primary'):
                with st.spinner('Deleting…'):
                    ok = safe_write(delete_user_from_sheet, uname_row)
                if ok:
                    st.session_state[confirm_key] = False
                    clear_data_cache()
                    toast(f'User "@{uname_row}" deleted.')
                    st.rerun()
            if c_no.button('Cancel', key=f'no_{del_key}'):
                st.session_state[confirm_key] = False
                st.rerun()

        st.markdown(
            '<hr style="margin:.15rem 0;border-color:#E8E0D0;">',
            unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  TAB: Change My Password
# ══════════════════════════════════════════════════════════

def _tab_change_password():
    st.caption(
        f'Change password for @{st.session_state.get("username", "")}')

    with st.form('my_pw_form'):
        np1 = st.text_input('New Password',     type='password')
        np2 = st.text_input('Confirm Password',  type='password')
        st.caption(f'Min {MIN_PASSWORD_LENGTH} chars, 1 uppercase, 1 digit.')

        if st.form_submit_button('Update Password', type='primary'):
            if not np1:
                st.error('Password is required.')
            elif np1 != np2:
                st.error('Passwords do not match.')
            else:
                err = _validate_password(np1)
                if err:
                    st.error(err)
                else:
                    uname = st.session_state.get('username', '')
                    with st.spinner('Updating…'):
                        ok = safe_write(update_password, uname, np1)
                    if ok:
                        clear_data_cache()
                        toast('Your password has been updated.')


# ══════════════════════════════════════════════════════════
#  TAB: System (Data Reset — Danger Zone)
# ══════════════════════════════════════════════════════════

def _tab_system():
    st.subheader('System')
    st.caption('Administrative actions that affect the entire system.')

    st.markdown('---')
    st.markdown(
        '<p style="font-weight:700;color:#E53935;">Danger Zone</p>',
        unsafe_allow_html=True)
    st.caption(
        'These actions permanently delete data. '
        'They cannot be undone.')

    _reset_section('products', 'Products',
                   'Deletes all products. Stock data will be lost.')
    _reset_section('transactions', 'Transaction Logs',
                   'Deletes all transaction history.')
    _reset_section('suppliers', 'Suppliers',
                   'Deletes all supplier records.')


def _reset_section(sheet_key, label, description):
    st.markdown(
        f'<div style="border:1px solid #E53935;border-radius:6px;'
        f'padding:12px 16px;margin:8px 0;">'
        f'<p style="font-weight:600;margin:0 0 2px;">'
        f'Reset {esc(label)}</p>'
        f'<p style="font-size:.85rem;color:#7A7A7A;margin:0;">'
        f'{esc(description)}</p></div>',
        unsafe_allow_html=True)

    btn_key     = f'reset_btn_{sheet_key}'
    confirm_key = f'reset_confirm_{sheet_key}'

    if st.button(f'Reset {label}', key=btn_key):
        st.session_state[confirm_key] = True
        st.rerun()

    if st.session_state.get(confirm_key):
        st.warning(
            f'Type **RESET {label.upper()}** to confirm deletion.')
        typed = st.text_input(
            'Confirmation', key=f'reset_input_{sheet_key}',
            placeholder=f'RESET {label.upper()}')
        c_yes, c_no = st.columns(2)
        if c_yes.button('Confirm Delete', key=f'reset_yes_{sheet_key}',
                        type='primary'):
            expected = f'RESET {label.upper()}'
            if typed.strip() != expected:
                st.error(f'Type exactly: {expected}')
            else:
                with st.spinner(f'Resetting {label}…'):
                    ok = safe_write(reset_sheet_data, sheet_key)
                if ok:
                    st.session_state[confirm_key] = False
                    clear_data_cache()
                    toast(f'{label} data has been reset.')
                    st.rerun()
        if c_no.button('Cancel', key=f'reset_no_{sheet_key}'):
            st.session_state[confirm_key] = False
            st.rerun()