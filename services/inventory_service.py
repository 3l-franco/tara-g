# services/inventory_service.py
import uuid
from datetime import datetime
import gspread
from services.sheets_client import get_ws, api_call, get_or_create_ws
from config import ph_now


def update_stock_and_log(product_id, product_name,
                         action, old_stock, new_stock,
                         notes, username):
    new_stock = max(0, int(new_stock))
    ws = get_ws('products')
    records = api_call(ws.get_all_records)

    row_idx = None
    matched_record = None
    for i, rec in enumerate(records, start=2):
        if str(rec.get('product_id', '')) == str(product_id):
            row_idx = i
            matched_record = rec
            break

    if row_idx is None:
        raise ValueError(f'Product ID "{product_id}" not found.')

    headers = api_call(ws.row_values, 1)
    col_map = {h: idx + 1 for idx, h in enumerate(headers)}
    stock_col = col_map.get('current_stock')
    if stock_col is None:
        raise ValueError('Column "current_stock" not found.')

    # Read current stock from the already-fetched records dict —
    # avoids an extra ws.cell() API call and narrows the race window.
    try:
        current_val = int(float(str(matched_record.get('current_stock', 0) or '0')))
    except (ValueError, TypeError):
        current_val = 0

    if current_val != int(old_stock):
        raise ValueError(
            f'Stock changed by another user '
            f'(expected {old_stock}, found {current_val}). '
            f'Please refresh and try again.')

    # Read unit from the already-fetched record (saves another ws.cell() call)
    unit = str(matched_record.get('unit', '') or '')
    api_call(ws.update_cell, row_idx, stock_col, new_stock)
    log_transaction(product_name, action, old_stock,
                    new_stock, notes, username, unit)
    return True


def log_transaction(product_name, action,
                    old_stock, new_stock, notes, username, unit=''):
    _HEADERS = ['date', 'time', 'product_name', 'action',
                'quantity_changed', 'old_stock', 'new_stock', 'notes', 'username', 'unit']
    # get_or_create_ws guarantees: tab exists, header row exists.
    # Never uses the stale get_ws cache, so WorksheetNotFound is impossible.
    ws    = get_or_create_ws('transactions', _HEADERS)
    now   = ph_now()
    delta = abs(int(new_stock) - int(old_stock))
    api_call(
        ws.append_row,
        [
            now.strftime('%Y-%m-%d'),
            now.strftime('%H:%M:%S'),
            str(product_name),
            str(action),
            str(delta),
            str(old_stock),
            str(new_stock),
            str(notes),
            str(username),
            str(unit),
        ],
        value_input_option='USER_ENTERED',
    )


def add_product_to_sheet(name, station, category, unit,
                         init_stock, min_stock, critical_stock,
                         description, supplier):
    ws = get_ws('products')
    headers = api_call(ws.row_values, 1)
    pid = f'P{uuid.uuid4().hex[:12]}'
    now = ph_now().strftime('%Y-%m-%d %H:%M:%S')
    data = {
        'product_id':     pid,
        'product_name':   name,
        'station':        station,
        'category':       category,
        'unit':           unit,
        'current_stock':  int(init_stock),
        'min_stock':      int(min_stock),
        'critical_stock': int(critical_stock),
        'description':    description,
        'supplier':       supplier,
        'added_at':       now,
    }
    api_call(
        ws.append_row,
        [data.get(h, '') for h in headers],
        value_input_option='USER_ENTERED',
    )
    return pid


def update_product_in_sheet(product_id, product_name, updates: dict):
    ws = get_ws('products')
    records = api_call(ws.get_all_records)
    headers = api_call(ws.row_values, 1)
    col_map = {h: idx + 1 for idx, h in enumerate(headers)}

    row_idx = None
    for i, rec in enumerate(records, start=2):
        if str(rec.get('product_id', '')) == str(product_id):
            row_idx = i
            break

    if row_idx is None:
        raise ValueError(f'Product "{product_name}" not found.')

    cells = []
    for col_name, value in updates.items():
        if col_name in col_map:
            cells.append(gspread.Cell(
                row=row_idx, col=col_map[col_name], value=value))
    if cells:
        api_call(ws.update_cells, cells)


def delete_product_from_sheet(product_id, product_name):
    ws = get_ws('products')
    records = api_call(ws.get_all_records)

    row_idx = None
    for i, rec in enumerate(records, start=2):
        if str(rec.get('product_id', '')) == str(product_id):
            row_idx = i
            break

    if row_idx is None:
        raise ValueError(f'Product "{product_name}" not found.')

    api_call(ws.delete_rows, row_idx)


def delete_user_from_sheet(username):
    ws = get_ws('users')
    records = api_call(ws.get_all_records)

    row_idx = None
    for i, rec in enumerate(records, start=2):
        if str(rec.get('username', '')).lower() == username.lower():
            row_idx = i
            break

    if row_idx is None:
        raise ValueError(f'User "{username}" not found.')

    api_call(ws.delete_rows, row_idx)

    # Also remove from the _Creds sheet
    try:
        creds_ws = get_or_create_ws('creds', ['username', 'password'])
        c_records = api_call(creds_ws.get_all_records)
        for ci, rec in enumerate(c_records, start=2):
            if str(rec.get('username', '')).lower() == username.lower():
                api_call(creds_ws.delete_rows, ci)
                break
    except Exception:
        pass  # Non-fatal if creds entry does not exist yet
