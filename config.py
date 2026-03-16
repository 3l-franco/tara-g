# config.py
from datetime import datetime, timezone, timedelta

_PH_TZ = timezone(timedelta(hours=8))  # Asia/Manila — UTC+8

def ph_now() -> datetime:
    """Current datetime in Philippine Time (UTC+8)."""
    return datetime.now(_PH_TZ)


SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

SHEETS = {
    'users':        'Users',
    'creds':        '_Creds',   # password hashes — keep this tab protected in Sheets
    'products':     'Products',
    'suppliers':    'Suppliers',
    'transactions': 'Transactions',
    'stations':     'Stations',
}

DEFAULT_STATIONS = ['Drinks', 'Kitchen', 'Packaging', 'Supplies', 'Others']

CATEGORIES = [
    'Milktea',
    'Coffee',
    'Iced Drinks',
    'Food — Noodles',
    'Food — Burger',
    'Food — Snacks',
    'Supplies / Packaging',
    'Others',
]

UNITS = ['pcs', 'cups', 'kg', 'g', 'L', 'mL', 'packs', 'bottles', 'bags', 'sachets']

OUT_REASONS = [
    'Sold',
    'Used for Production',
    'Spoiled / Expired',
    'Damaged',
    'Other — specify',
]

IN_REASONS = [
    'Delivery / Restock',
    'Return from Customer',
    'Inventory Adjustment',
    'Other',
]

MAX_LOGIN_ATTEMPTS     = 5
LOCKOUT_WINDOW_SECONDS = 300

CACHE_TTL = 300

PAGE_SIZE = 50

SESSION_TIMEOUT_SECONDS = 14400  # 4 h inactivity auto-logout (staff step away during service)
MIN_PASSWORD_LENGTH     = 8

TOKEN_EXPIRY_DAYS   = 30                    # login token valid for 30 days (monthly re-login)
# NOTE: The HMAC signing key (auth_secret) must be set in Streamlit secrets only.
# Do not add it here. See .streamlit/secrets.toml or Streamlit Cloud → App secrets.