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
    'creds':        '_Creds',
    'products':     'Products',
    'suppliers':    'Suppliers',
    'transactions': 'Transactions',
    'stations':     'Stations',
    'categories':   'Categories',   # ← new: managed via Products & Stock
}

DEFAULT_STATIONS = ['Drinks', 'Kitchen', 'Packaging', 'Supplies', 'Others']

DEFAULT_CATEGORIES = [
    'Milktea',
    'Coffee',
    'Iced Drinks',
    'Food — Noodles',
    'Food — Burger',
    'Food — Snacks',
    'Supplies / Packaging',
    'Others',
]

# Legacy constant kept so existing imports don't break.
# At runtime the app reads from Google Sheets via get_categories().
CATEGORIES = DEFAULT_CATEGORIES

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

SESSION_TIMEOUT_SECONDS = 14400
MIN_PASSWORD_LENGTH     = 8

TOKEN_EXPIRY_DAYS = 30
