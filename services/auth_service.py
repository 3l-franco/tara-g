# services/auth_service.py
# Login, password hashing, lockout logic.
# No UI code here — pure auth layer only.

import hashlib
import hmac as _hmac
import base64 as _b64
import time
import streamlit as _st
from services.sheets_client import read_df
from config import MAX_LOGIN_ATTEMPTS, LOCKOUT_WINDOW_SECONDS, TOKEN_EXPIRY_DAYS

# HMAC signing key — must be set in Streamlit secrets (or .streamlit/secrets.toml).
# The app will refuse to start if this secret is absent: do NOT add a hardcoded fallback.
try:
    _HMAC_SECRET: str = _st.secrets['auth_secret']
except KeyError:
    raise RuntimeError(
        "Required secret 'auth_secret' is not configured. "
        "Add auth_secret = 'your-strong-random-key' to "
        ".streamlit/secrets.toml or Streamlit Cloud → App secrets."
    ) from None

# In-memory lockout tracker.
# NOTE: Resets on server restart — known limitation.
# Key: username (lowercase), Value: {'attempts': int, 'first_attempt': float}
_FAILED_LOGINS: dict = {}


def hash_pw(password: str) -> str:
    """
    Hashes a password using scrypt (strong, memory-hard).
    Format: 'scrypt:<salt_hex>:<hash_hex>'
    New users always get scrypt. Legacy SHA256 hashes are
    auto-migrated on first successful login.
    """
    import os
    salt   = os.urandom(16)
    hashed = hashlib.scrypt(
        password.encode(), salt=salt, n=16384, r=8, p=1)
    return f'scrypt:{salt.hex()}:{hashed.hex()}'


def verify_pw(password: str, stored: str) -> bool:
    """
    Verifies a password against its stored hash.
    Supports both scrypt (new) and SHA256 (legacy) formats.
    """
    if stored.startswith('scrypt:'):
        try:
            _, salt_part, hash_part = stored.split(':')
            # Support both hex and base64 encoded hashes
            try:
                salt     = bytes.fromhex(salt_part)
                expected = bytes.fromhex(hash_part)
            except ValueError:
                import base64
                salt     = base64.b64decode(salt_part)
                expected = base64.b64decode(hash_part)
            candidate = hashlib.scrypt(
                password.encode(), salt=salt, n=16384, r=8, p=1)
            return candidate == expected
        except Exception:
            return False
    else:
        # Legacy SHA256 fallback — constant-time comparison to resist timing attacks
        candidate = hashlib.sha256(password.encode()).hexdigest()
        return _hmac.compare_digest(candidate, stored)


def is_locked_out(username: str) -> tuple[bool, int]:
    """
    Checks if a username is currently locked out.
    Returns (is_locked: bool, seconds_remaining: int).
    """
    key  = username.lower()
    info = _FAILED_LOGINS.get(key)
    if not info:
        return False, 0

    elapsed = time.time() - info['first_attempt']
    if elapsed > LOCKOUT_WINDOW_SECONDS:
        _FAILED_LOGINS.pop(key, None)
        return False, 0

    if info['attempts'] >= MAX_LOGIN_ATTEMPTS:
        remaining = int(LOCKOUT_WINDOW_SECONDS - elapsed)
        return True, max(0, remaining)

    return False, 0


def record_failed_login(username: str):
    """Records a failed login attempt for the given username."""
    key  = username.lower()
    now  = time.time()
    info = _FAILED_LOGINS.get(key)

    if not info or (now - info['first_attempt']) > LOCKOUT_WINDOW_SECONDS:
        _FAILED_LOGINS[key] = {'attempts': 1, 'first_attempt': now}
    else:
        _FAILED_LOGINS[key]['attempts'] += 1


def authenticate(username: str, password: str):
    """
    Authenticates a user against the Users sheet.
    Returns (success: bool, role: str, message: str).

    On success: clears failed login record.
    On failure: records failed attempt, checks lockout.
    Auto-migrates legacy SHA256 hashes to scrypt on success.
    """
    username = username.strip()
    password = password.strip()

    locked, secs = is_locked_out(username)
    if locked:
        mins = secs // 60
        secs_rem = secs % 60
        return False, '', (
            f'Account locked. Try again in '
            f'{mins}m {secs_rem}s.')

    df = read_df('users')
    if df.empty or 'username' not in df.columns:
        return False, '', 'No users found. Contact your admin.'

    match = df[df['username'].str.lower() == username.lower()]
    if match.empty:
        record_failed_login(username)
        locked2, _ = is_locked_out(username)
        remaining  = MAX_LOGIN_ATTEMPTS - _FAILED_LOGINS.get(
            username.lower(), {}).get('attempts', 0)
        if locked2:
            return False, '', 'Too many attempts. Account locked.'
        return False, '', (
            f'Incorrect credentials. '
            f'{max(0, remaining)} attempt(s) left before lockout.')

    row  = match.iloc[0]
    role = str(row.get('role', 'staff')).lower()

    # -- Retrieve password hash: _Creds sheet (current) or Users sheet (legacy) --
    stored          = ''
    found_in_legacy = False
    creds_df = read_df('creds')
    if not creds_df.empty and 'username' in creds_df.columns:
        cmatch = creds_df[creds_df['username'].str.lower() == username.lower()]
        if not cmatch.empty:
            stored = str(cmatch.iloc[0].get('password', ''))
    if not stored:
        # Legacy path: password still in Users sheet — will be migrated on success
        stored          = str(row.get('password', ''))
        found_in_legacy = bool(stored)

    if not verify_pw(password, stored):
        record_failed_login(username)
        locked2, _ = is_locked_out(username)
        remaining  = MAX_LOGIN_ATTEMPTS - _FAILED_LOGINS.get(
            username.lower(), {}).get('attempts', 0)
        if locked2:
            return False, '', 'Too many attempts. Account locked.'
        return False, '', (
            f'Incorrect credentials. '
            f'{max(0, remaining)} attempt(s) left before lockout.')

    # Success — clear lockout
    _FAILED_LOGINS.pop(username.lower(), None)

    # Migrate legacy Users-sheet password → _Creds, and/or upgrade SHA256 → scrypt
    needs_upgrade = not stored.startswith('scrypt:')
    if found_in_legacy or needs_upgrade:
        try:
            from services.sheets_client import get_ws, get_or_create_ws, api_call
            new_hash  = hash_pw(password)
            creds_ws  = get_or_create_ws('creds', ['username', 'password'])
            c_records = api_call(creds_ws.get_all_records)
            c_headers = api_call(creds_ws.row_values, 1)
            c_col_map = {h: i + 1 for i, h in enumerate(c_headers)}
            updated = False
            for ri, rec in enumerate(c_records, start=2):
                if rec.get('username', '').lower() == username.lower():
                    if 'password' in c_col_map:
                        api_call(creds_ws.update_cell,
                                 ri, c_col_map['password'], new_hash)
                    updated = True
                    break
            if not updated:
                api_call(creds_ws.append_row, [username, new_hash],
                         value_input_option='USER_ENTERED')
            # Blank the now-migrated password from the Users sheet
            if found_in_legacy:
                users_ws  = get_ws('users')
                u_records = api_call(users_ws.get_all_records)
                u_headers = api_call(users_ws.row_values, 1)
                u_col_map = {h: i + 1 for i, h in enumerate(u_headers)}
                for ri, rec in enumerate(u_records, start=2):
                    if rec.get('username', '').lower() == username.lower():
                        if 'password' in u_col_map:
                            api_call(users_ws.update_cell,
                                     ri, u_col_map['password'], '')
                        break
                read_df.clear()  # Refresh cache so Users sheet no longer exposes hash
        except Exception:
            pass  # Migration failure is non-fatal

    return True, role, 'OK'


# ── Token-based persistent login ──────────────────────────

def generate_auth_token(username: str, role: str) -> str:
    """Creates an HMAC-signed token for persistent login."""
    exp = int(time.time()) + TOKEN_EXPIRY_DAYS * 86400
    payload = f'{username}|{role}|{exp}'
    sig = _hmac.new(_HMAC_SECRET.encode(), payload.encode(),
                    hashlib.sha256).hexdigest()  # full 256-bit digest — never truncate
    return _b64.urlsafe_b64encode(f'{payload}|{sig}'.encode()).decode()


def verify_auth_token(token_b64: str):
    """Verifies token. Returns (username, role) or None."""
    try:
        decoded = _b64.urlsafe_b64decode(token_b64.encode()).decode()
        payload, sig = decoded.rsplit('|', 1)
        expected = _hmac.new(_HMAC_SECRET.encode(), payload.encode(),
                             hashlib.sha256).hexdigest()  # full 256-bit digest
        if not _hmac.compare_digest(sig, expected):
            return None
        parts = payload.split('|')
        if len(parts) != 3:
            return None
        username, role, exp_str = parts
        if time.time() > int(exp_str):
            return None
        return username, role
    except Exception:
        return None


def update_password(username: str, new_password: str) -> bool:
    """
    Updates the password for a given username in the _Creds sheet.
    Creates the entry if it does not yet exist (handles first-time migration).
    Returns True on success.
    """
    from services.sheets_client import get_or_create_ws, api_call
    ws      = get_or_create_ws('creds', ['username', 'password'])
    records = api_call(ws.get_all_records)
    headers = api_call(ws.row_values, 1)
    col_map = {h: i + 1 for i, h in enumerate(headers)}
    new_hash = hash_pw(new_password)

    for ri, rec in enumerate(records, start=2):
        if rec.get('username', '').lower() == username.lower():
            api_call(ws.update_cell, ri, col_map['password'], new_hash)
            return True
    # Not in _Creds yet — insert (covers users that haven't logged in post-migration)
    api_call(ws.append_row, [username, new_hash],
             value_input_option='USER_ENTERED')
    return True