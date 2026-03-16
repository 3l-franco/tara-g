# services/sheets_client.py
import time, random
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from config import SCOPES, SHEETS, DEFAULT_STATIONS, DEFAULT_CATEGORIES, CACHE_TTL

def api_call(fn, *args, max_retries=4, **kwargs):
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if ('429' in msg or 'quota' in msg.lower() or
                    '503' in msg or 'UNAVAILABLE' in msg):
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) + random.uniform(0, 1))
                    continue
            raise
    return fn(*args, **kwargs)

@st.cache_resource(show_spinner=False)
def get_client():
    try:
        info = {k: v for k, v in st.secrets['gcp_service_account'].items()}
        pk = info.get('private_key', '')
        pk = pk.replace('\\n', '\n')
        pk = pk.strip() + '\n'
        info['private_key'] = pk
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f'Failed to connect to Google: {e}')
        return None

@st.cache_resource(show_spinner=False)
def _get_spreadsheet():
    client = get_client()
    if client is None:
        raise ConnectionError('Google Sheets client not available.')
    return client.open(st.secrets['spreadsheet_name'])

@st.cache_resource(show_spinner=False)
def get_ws(key):
    return _get_spreadsheet().worksheet(SHEETS[key])


def get_or_create_ws(key, default_headers=None):
    ss         = _get_spreadsheet()
    sheet_name = SHEETS[key]
    try:
        ws = api_call(ss.worksheet, sheet_name)
    except Exception as e:
        ename = type(e).__name__.lower()
        emsg  = str(e).lower()
        if 'notfound' in ename or 'not found' in emsg or 'worksheet' in ename:
            col_count = max(len(default_headers or []) + 2, 10)
            ws = api_call(ss.add_worksheet,
                          title=sheet_name, rows=2000, cols=col_count)
            if default_headers:
                api_call(ws.update, 'A1', [default_headers],
                         value_input_option='USER_ENTERED')
            get_ws.clear()
        else:
            raise
    else:
        if default_headers:
            first_row = api_call(ws.row_values, 1)
            if not any(str(v).strip() for v in first_row):
                api_call(ws.update, 'A1', [default_headers],
                         value_input_option='USER_ENTERED')
    return ws

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def read_df(key):
    try:
        ws = get_ws(key)
        records = api_call(ws.get_all_records)
        return pd.DataFrame(records) if records else pd.DataFrame()
    except Exception as e:
        msg = str(e)
        if '429' in msg or 'quota' in msg.lower():
            st.warning('Google Sheets is busy - showing cached data.')
        else:
            st.warning(f'Could not load {key} data: {e}')
        return pd.DataFrame()

def clear_data_cache():
    for fn, name in [
        (read_df,                 'read_df'),
        (get_staff_display_names, 'get_staff_display_names'),
        (get_stations,            'get_stations'),
        (get_categories,          'get_categories'),
        (get_ws,                  'get_ws'),
    ]:
        try:
            fn.clear()
        except Exception as exc:
            import sys
            print(f'[sheets_client] clear: could not clear {name}: {exc}',
                  file=sys.stderr)

def get_sheet_url():
    try:
        ss = _get_spreadsheet()
        return f'https://docs.google.com/spreadsheets/d/{ss.id}/edit'
    except Exception:
        return None

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_stations():
    try:
        ws = get_ws('stations')
        vals = api_call(ws.col_values, 1)
        stns = [v.strip() for v in vals if v.strip()]
        return stns if stns else DEFAULT_STATIONS
    except Exception:
        return list(DEFAULT_STATIONS)

def save_stations(station_list):
    try:
        ws = get_ws('stations')
        api_call(ws.clear)
        if station_list:
            api_call(ws.update, 'A1',
                     [[s] for s in station_list],
                     value_input_option='USER_ENTERED')
        get_stations.clear()
        return True
    except Exception as e:
        st.error(f'Failed to save stations: {e}')
        return False


# ── Categories ────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_categories():
    try:
        ws   = get_or_create_ws('categories')
        vals = api_call(ws.col_values, 1)
        cats = [v.strip() for v in vals if v.strip()]
        if cats:
            return cats
        api_call(ws.update, 'A1',
                 [[c] for c in DEFAULT_CATEGORIES],
                 value_input_option='USER_ENTERED')
        return list(DEFAULT_CATEGORIES)
    except Exception:
        return list(DEFAULT_CATEGORIES)


def save_categories(category_list):
    """Writes the full category list to the Categories sheet.
    Auto-creates the tab if it doesn't exist yet."""
    try:
        # Use get_or_create_ws so the tab is made on first write
        ws = get_or_create_ws('categories')
        api_call(ws.clear)
        if category_list:
            api_call(ws.update, 'A1',
                     [[c] for c in category_list],
                     value_input_option='USER_ENTERED')
        get_categories.clear()
        return True
    except Exception as e:
        st.error(f'Failed to save categories: {e}')
        return False


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_staff_display_names():
    try:
        df = read_df('users')
        if df.empty or 'username' not in df.columns:
            return {}
        result = {}
        for _, row in df.iterrows():
            uname = str(row.get('username', '')).strip()
            dname = str(row.get('display_name', '')).strip()
            if uname:
                result[uname.lower()] = dname if dname else uname
        return result
    except Exception:
        return {}


def reset_sheet_data(key):
    try:
        ws = get_ws(key)
        rows = api_call(ws.get_all_values)
        if len(rows) > 1:
            api_call(ws.delete_rows, 2, len(rows))
        clear_data_cache()
        return True
    except Exception as e:
        raise ValueError(f'Failed to reset {key}: {e}')


def update_supplier_in_sheet(supplier_id, updates: dict):
    import gspread as _gs
    ws = get_ws('suppliers')
    records = api_call(ws.get_all_records)
    headers = api_call(ws.row_values, 1)
    col_map = {h: idx + 1 for idx, h in enumerate(headers)}

    row_idx = None
    id_col = 'supplier_id' if 'supplier_id' in col_map else headers[0]
    for i, rec in enumerate(records, start=2):
        if str(rec.get(id_col, '')) == str(supplier_id):
            row_idx = i
            break

    if row_idx is None:
        raise ValueError(f'Supplier "{supplier_id}" not found.')

    cells = []
    for col_name, value in updates.items():
        if col_name in col_map:
            cells.append(_gs.Cell(
                row=row_idx, col=col_map[col_name], value=value))
    if cells:
        api_call(ws.update_cells, cells)


def delete_supplier_from_sheet(supplier_id):
    ws = get_ws('suppliers')
    records = api_call(ws.get_all_records)
    headers = api_call(ws.row_values, 1)
    id_col = 'supplier_id' if 'supplier_id' in headers else headers[0]

    row_idx = None
    for i, rec in enumerate(records, start=2):
        if str(rec.get(id_col, '')) == str(supplier_id):
            row_idx = i
            break

    if row_idx is None:
        raise ValueError('Supplier not found.')

    api_call(ws.delete_rows, row_idx)
