code = '''\
# services/sheets_client.py
import time, random
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from config import SCOPES, SHEETS, DEFAULT_STATIONS, CACHE_TTL

def _api_call(fn, *args, max_retries=4, **kwargs):
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
        creds = Credentials.from_service_account_info(
            st.secrets['gcp_service_account'], scopes=SCOPES)
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

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def read_df(key):
    try:
        ws = get_ws(key)
        records = _api_call(ws.get_all_records)
        return pd.DataFrame(records) if records else pd.DataFrame()
    except Exception as e:
        msg = str(e)
        if '429' in msg or 'quota' in msg.lower():
            st.warning('Google Sheets is busy - showing cached data.')
        else:
            st.warning(f'Could not load {key} data: {e}')
        return pd.DataFrame()

def clear_data_cache():
    read_df.clear()
    get_staff_display_names.clear()
    get_stations.clear()
    get_ws.clear()

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
        vals = _api_call(ws.col_values, 1)
        stns = [v.strip() for v in vals if v.strip()]
        return stns if stns else DEFAULT_STATIONS
    except Exception:
        return list(DEFAULT_STATIONS)

def save_stations(station_list):
    try:
        ws = get_ws('stations')
        _api_call(ws.clear)
        if station_list:
            _api_call(ws.update, 'A1',
                      [[s] for s in station_list],
                      value_input_option='USER_ENTERED')
        get_stations.clear()
        return True
    except Exception as e:
        st.error(f'Failed to save stations: {e}')
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
'''

with open('services/sheets_client.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('sheets_client.py written OK')