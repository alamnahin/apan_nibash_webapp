#!/usr/bin/env python3
"""
APAN NIBASH - Web Application
Flask backend for financial management (Supabase)
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import init_database, get_client, using_supabase
from datetime import datetime, date
import os
import sqlite3 as _sqlite3  # only for local dev fallback

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-me')

def format_currency(cents):
    if cents is None:
        return "0"
    return "{:,.0f}".format(cents / 100)

app.jinja_env.filters['currency'] = format_currency

AUTH_USERNAME = os.environ.get('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD', 'changeme')

# ---------------------------------------------------------------------------
# Database helpers (Supabase-first, SQLite fallback)
# ---------------------------------------------------------------------------
def _get_db():
    """Return a connection-like object.
    With Supabase: returns the Supabase client.
    With SQLite: returns a sqlite3 connection with dict rows.
    """
    if using_supabase():
        return get_client()
    conn = _sqlite3.connect(os.environ.get('DB_PATH', 'data/apan_nibash.db'))
    conn.row_factory = _sqlite3.Row
    return conn

def _rows(result):
    """Normalize Supabase response to list of dicts."""
    if result is None:
        return []
    data = getattr(result, 'data', None)
    if data is None:
        return []
    return data if isinstance(data, list) else [data]

def _one(result):
    """Return first row or None."""
    r = _rows(result)
    return r[0] if r else None

def _val(result):
    """Return first cell value or None."""
    r = _rows(result)
    if not r:
        return None
    row = r[0]
    if isinstance(row, dict):
        # For aggregation queries that return unnamed columns
        vals = list(row.values())
        return vals[0] if vals else None
    return row[0] if hasattr(row, '__getitem__') else row

def to_cents(value):
    try:
        return int(round(float(value or 0) * 100))
    except (TypeError, ValueError):
        return 0

def _today_str():
    return date.today().strftime('%Y-%m-%d')

# ---------------------------------------------------------------------------
# Supabase helper functions
# ---------------------------------------------------------------------------
def sb_aggregate(table, selects, filters=None, group_by=None, order_by=None, limit=None):
    """Run an aggregate query on a Supabase table."""
    client = get_client()
    q = client.table(table).select(selects)
    if filters:
        for key, val in filters.items():
            q = q.eq(key, val)
    if group_by:
        q = q.order(group_by)
    return q.execute()

def sb_select(table, columns="*", filters=None, order=None, limit=None):
    client = get_client()
    q = client.table(table).select(columns)
    if filters:
        for key, val in filters.items():
            q = q.eq(key, val)
    if order:
        q = q.order(order[0], desc=order[1]) if len(order) > 1 else q.order(order)
    if limit:
        q = q.limit(limit)
    return q.execute()

def sb_insert(table, data):
    client = get_client()
    return client.table(table).insert(data).execute()

def sb_delete(table, filters):
    client = get_client()
    q = client.table(table).delete()
    for key, val in filters.items():
        q = q.eq(key, val)
    return q.execute()

def sb_update(table, data, filters):
    client = get_client()
    q = client.table(table).update(data)
    for key, val in filters.items():
        q = q.eq(key, val)
    return q.execute()

def generate_voucher_no(voucher_type):
    today = datetime.now()
    prefix = voucher_type
    year_month = today.strftime('%Y%m')
    like_pattern = f'{prefix}-{year_month}-%'

    if using_supabase():
        # Get all vouchers matching the pattern and find max sequence
        result = sb_select('vouchers', columns="voucher_no",
                          filters={'voucher_type': voucher_type})
        max_seq = 0
        for r in _rows(result):
            vn = r.get('voucher_no', '')
            if vn.startswith(f'{prefix}-{year_month}-'):
                try:
                    seq = int(vn.split('-')[-1])
                    if seq > max_seq:
                        max_seq = seq
                except (ValueError, IndexError):
                    pass
        next_seq = max_seq + 1
    else:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(CAST(SUBSTR(voucher_no, -4) AS INTEGER)) as max_seq
            FROM vouchers WHERE voucher_no LIKE ?
        ''', (like_pattern,))
        row = cursor.fetchone()
        next_seq = (row['max_seq'] or 0) + 1
        conn.close()

    return f"{prefix}-{year_month}-{next_seq:04d}"

def ensure_payor_profile(name):
    name = str(name or '').strip().title()
    if not name:
        return
    if using_supabase():
        sb_insert('payor_profiles', {"name": name})
    else:
        conn = _get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO payor_profiles (name) VALUES (?)', (name,))
        conn.commit()
        conn.close()

init_database()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    error = ''
    if request.method == 'POST':
        username = str(request.form.get('username', '')).strip()
        password = str(request.form.get('password', ''))
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session['authenticated'] = True
            session['username'] = AUTH_USERNAME
            return redirect(request.args.get('next') or url_for('dashboard'))
        error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def dashboard():
    today = _today_str()
    current_month = today[:7]

    if using_supabase():
        client = get_client()

        # Today's income/expense
        today_v = _rows(client.table('vouchers').select('credit_amount,debit_amount').eq('date', today).execute())
        today_income = sum(r.get('credit_amount', 0) for r in today_v if r.get('credit_amount', 0) > 0)
        today_expense = sum(r.get('debit_amount', 0) for r in today_v if r.get('debit_amount', 0) > 0)

        # Month income/expense
        month_v = _rows(client.table('vouchers').select('date,credit_amount,debit_amount').execute())
        month_income = sum(r.get('credit_amount', 0) for r in month_v
                          if r.get('date', '').startswith(current_month) and r.get('credit_amount', 0) > 0)
        month_expense = sum(r.get('debit_amount', 0) for r in month_v
                           if r.get('date', '').startswith(current_month) and r.get('debit_amount', 0) > 0)

        # Total income/expense
        all_v = _rows(client.table('vouchers').select('credit_amount,debit_amount').execute())
        total_income = sum(r.get('credit_amount', 0) for r in all_v if r.get('credit_amount', 0) > 0)
        total_expense = sum(r.get('debit_amount', 0) for r in all_v if r.get('debit_amount', 0) > 0)

        # Recent vouchers
        recent_vouchers = _rows(client.table('vouchers').select('*,account_codes(name)').order('created_at', desc=True).limit(10).execute())

        # Flatholders
        fhs = _rows(client.table('flatholders').select('paid_amount,total_amount').execute())
        total_buyers = len(fhs)
        total_collected = sum(r.get('paid_amount', 0) for r in fhs)
        total_due = sum(max(0, r.get('total_amount', 0) - r.get('paid_amount', 0)) for r in fhs)
    else:
        conn = _get_db()
        cur = conn.cursor()

        cur.execute('''
            SELECT COALESCE(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END), 0)
            FROM vouchers WHERE date = ?
        ''', (today,))
        row = cur.fetchone()
        today_income, today_expense = row[0], row[1]

        cur.execute('''
            SELECT COALESCE(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END), 0)
            FROM vouchers WHERE strftime('%Y-%m', date) = ?
        ''', (current_month,))
        row = cur.fetchone()
        month_income, month_expense = row[0], row[1]

        cur.execute('''
            SELECT COALESCE(SUM(credit_amount), 0), COALESCE(SUM(debit_amount), 0)
            FROM vouchers
        ''')
        row = cur.fetchone()
        total_income, total_expense = row[0], row[1]

        cur.execute('SELECT * FROM vouchers ORDER BY created_at DESC LIMIT 10')
        recent_vouchers = cur.fetchall()

        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(paid_amount), 0), COALESCE(SUM(total_amount - paid_amount), 0)
            FROM flatholders
        ''')
        row = cur.fetchone()
        total_buyers, total_collected, total_due = row[0], row[1], row[2]
        conn.close()

    return render_template('dashboard.html',
                           today={'today_income': today_income, 'today_expense': today_expense},
                           month={'month_income': month_income, 'month_expense': month_expense},
                           total={'total_income': total_income, 'total_expense': total_expense},
                           recent_vouchers=recent_vouchers,
                           flatholders={'total_buyers': total_buyers, 'total_collected': total_collected, 'total_due': total_due},
                           current_date=today)

@app.route('/vouchers')
def vouchers():
    return render_template('vouchers.html')

@app.route('/voucher/new')
def new_voucher():
    if using_supabase():
        accounts = _rows(get_client().table('account_codes').select('*').order('code').execute())
    else:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute('SELECT * FROM account_codes ORDER BY code')
        accounts = cur.fetchall()
        conn.close()
    return render_template('voucher_form.html', accounts=accounts, today=_today_str())

@app.route('/api/vouchers', methods=['GET'])
def get_vouchers():
    voucher_type = request.args.get('type', '')
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    account_code = request.args.get('account_code', '')
    payee_payor = request.args.get('payee_payor', '').strip()
    limit = int(request.args.get('limit', 100))

    if using_supabase():
        client = get_client()
        q = client.table('vouchers').select('*,account_codes(name)')
        if voucher_type:
            q = q.eq('voucher_type', voucher_type)
        if from_date:
            q = q.gte('date', from_date)
        if to_date:
            q = q.lte('date', to_date)
        if account_code:
            q = q.eq('account_code', account_code)
        if payee_payor:
            q = q.ilike('payee_payor', f'%{payee_payor}%')
        q = q.order('date', desc=True).limit(limit)
        data = _rows(q.execute())
    else:
        conn = _get_db()
        cur = conn.cursor()
        query = '''
            SELECT v.*, ac.name as account_name
            FROM vouchers v JOIN account_codes ac ON v.account_code = ac.code
            WHERE 1=1
        '''
        params = []
        if voucher_type:
            query += ' AND v.voucher_type = ?'
            params.append(voucher_type)
        if from_date:
            query += ' AND v.date >= ?'
            params.append(from_date)
        if to_date:
            query += ' AND v.date <= ?'
            params.append(to_date)
        if account_code:
            query += ' AND v.account_code = ?'
            params.append(account_code)
        if payee_payor:
            query += ' AND v.payee_payor LIKE ?'
            params.append(f'%{payee_payor}%')
        query += ' ORDER BY v.date DESC, v.created_at DESC LIMIT ?'
        params.append(limit)
        cur.execute(query, params)
        data = cur.fetchall()
        conn.close()

    return jsonify({'success': True, 'data': data})

@app.route('/api/voucher', methods=['POST'])
def create_voucher():
    data = request.json or {}
    try:
        required = ['date', 'voucher_type', 'account_code', 'description']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({'success': False, 'error': f"Missing: {', '.join(missing)}"}), 400

        debit_amount = to_cents(data.get('debit_amount'))
        credit_amount = to_cents(data.get('credit_amount'))

        if debit_amount == 0 and credit_amount == 0:
            return jsonify({'success': False, 'error': 'Debit or credit amount is required'}), 400

        vt = data['voucher_type']
        if vt == 'RV' and credit_amount <= 0:
            return jsonify({'success': False, 'error': 'RV must have credit amount'}), 400
        if vt == 'PV' and debit_amount <= 0:
            return jsonify({'success': False, 'error': 'PV must have debit amount'}), 400
        if vt == 'JV' and (debit_amount == 0 or credit_amount == 0):
            return jsonify({'success': False, 'error': 'JV must have both debit and credit amounts'}), 400

        voucher_no = generate_voucher_no(vt)

        if using_supabase():
            payload = {
                'voucher_no': voucher_no,
                'date': data['date'],
                'voucher_type': vt,
                'account_code': data['account_code'],
                'description': data['description'],
                'debit_amount': debit_amount,
                'credit_amount': credit_amount,
                'reference_no': data.get('reference_no', ''),
                'payee_payor': data.get('payee_payor', ''),
                'notes': data.get('notes', ''),
            }
            result = sb_insert('vouchers', payload)
            ensure_payor_profile(data.get('payee_payor', ''))
            voucher_id = _rows(result)[0]['id'] if _rows(result) else None
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO vouchers
                (voucher_no, date, voucher_type, account_code, description,
                 debit_amount, credit_amount, reference_no, payee_payor, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (voucher_no, data['date'], vt, data['account_code'],
                  data['description'], debit_amount, credit_amount,
                  data.get('reference_no', ''), data.get('payee_payor', ''),
                  data.get('notes', '')))
            ensure_payor_profile(data.get('payee_payor', ''))
            conn.commit()
            voucher_id = cur.lastrowid
            conn.close()

        return jsonify({
            'success': True,
            'message': 'Voucher created successfully',
            'voucher_no': voucher_no,
            'id': voucher_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/voucher/<int:id>', methods=['DELETE'])
def delete_voucher(id):
    try:
        if using_supabase():
            sb_delete('vouchers', {'id': id})
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('DELETE FROM vouchers WHERE id = ?', (id,))
            conn.commit()
            conn.close()
        return jsonify({'success': True, 'message': 'Voucher deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reports')
def reports():
    return render_template('reports.html')

@app.route('/api/reports/period', methods=['GET'])
def period_report():
    period_type = request.args.get('period_type', 'monthly')
    year = request.args.get('year', datetime.now().year)

    if using_supabase():
        client = get_client()
        all_v = _rows(client.table('vouchers').select('date,credit_amount,debit_amount,account_code,voucher_type').execute())
        ac_map = {r['code']: r['name'] for r in _rows(client.table('account_codes').select('code,name').execute())}

        if period_type == 'monthly':
            months = {}
            for r in all_v:
                d = r.get('date', '')
                if not d.startswith(str(year)):
                    continue
                p = d[:7]
                if p not in months:
                    months[p] = {'period': p, 'voucher_count': 0, 'income': 0, 'expense': 0}
                months[p]['voucher_count'] += 1
                months[p]['income'] += r.get('credit_amount', 0) if r.get('credit_amount', 0) > 0 else 0
                months[p]['expense'] += r.get('debit_amount', 0) if r.get('debit_amount', 0) > 0 else 0
            results = sorted(months.values(), key=lambda x: x['period'])

        elif period_type == 'yearly':
            years = {}
            for r in all_v:
                d = r.get('date', '')
                if not d:
                    continue
                p = d[:4]
                if p not in years:
                    years[p] = {'period': p, 'voucher_count': 0, 'income': 0, 'expense': 0}
                years[p]['voucher_count'] += 1
                years[p]['income'] += r.get('credit_amount', 0) if r.get('credit_amount', 0) > 0 else 0
                years[p]['expense'] += r.get('debit_amount', 0) if r.get('debit_amount', 0) > 0 else 0
            results = sorted(years.values(), key=lambda x: x['period'])

        elif period_type == 'category':
            cats = {}
            for r in all_v:
                code = r.get('account_code', '')
                if code not in cats:
                    cats[code] = {'category': ac_map.get(code, code), 'type': '', 'total_debit': 0, 'total_credit': 0, 'transaction_count': 0}
                cats[code]['total_debit'] += r.get('debit_amount', 0)
                cats[code]['total_credit'] += r.get('credit_amount', 0)
                cats[code]['transaction_count'] += 1
            results = list(cats.values())
        else:
            results = []
    else:
        conn = _get_db()
        cur = conn.cursor()
        if period_type == 'monthly':
            cur.execute('''
                SELECT strftime('%Y-%m', date) as period, COUNT(*) as voucher_count,
                       SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as income,
                       SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as expense
                FROM vouchers WHERE strftime('%Y', date) = ?
                GROUP BY period ORDER BY period
            ''', (str(year),))
        elif period_type == 'yearly':
            cur.execute('''
                SELECT strftime('%Y', date) as period, COUNT(*) as voucher_count,
                       SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as income,
                       SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as expense
                FROM vouchers GROUP BY period ORDER BY period
            ''')
        elif period_type == 'category':
            cur.execute('''
                SELECT ac.name as category, ac.type, SUM(v.debit_amount) as total_debit,
                       SUM(v.credit_amount) as total_credit, COUNT(*) as transaction_count
                FROM vouchers v JOIN account_codes ac ON v.account_code = ac.code
                GROUP BY v.account_code ORDER BY ac.type, ac.name
            ''')
        results = cur.fetchall()
        conn.close()

    return jsonify({'success': True, 'data': results})

@app.route('/api/reports/balance', methods=['GET'])
def balance_report():
    if using_supabase():
        client = get_client()
        all_v = _rows(client.table('vouchers').select('account_code,debit_amount,credit_amount').execute())
        ac_map = {r['code']: r for r in _rows(client.table('account_codes').select('code,name,type').execute())}

        accts = {}
        for r in all_v:
            code = r.get('account_code', '')
            if code not in accts:
                info = ac_map.get(code, {})
                accts[code] = {
                    'account_code': code, 'name': info.get('name', code),
                    'type': info.get('type', ''), 'total_debit': 0, 'total_credit': 0,
                }
            accts[code]['total_debit'] += r.get('debit_amount', 0)
            accts[code]['total_credit'] += r.get('credit_amount', 0)

        accounts = sorted(accts.values(), key=lambda x: (x['type'], x['account_code']))
        total_income = sum(v['total_credit'] for v in accounts.values() if v['total_credit'] > 0)
        total_expense = sum(v['total_debit'] for v in accounts.values() if v['total_debit'] > 0)
    else:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT account_code, ac.name, ac.type, SUM(debit_amount), SUM(credit_amount),
                   SUM(credit_amount) - SUM(debit_amount) as balance
            FROM vouchers JOIN account_codes ac ON vouchers.account_code = ac.code
            GROUP BY account_code ORDER BY ac.type, account_code
        ''')
        accounts = cur.fetchall()
        cur.execute('SELECT COALESCE(SUM(credit_amount),0), COALESCE(SUM(debit_amount),0) FROM vouchers')
        totals = cur.fetchone()
        total_income = totals[0]
        total_expense = totals[1]
        conn.close()
        accounts = []

    return jsonify({'success': True, 'accounts': accounts, 'totals': {'total_income': total_income, 'total_expense': total_expense}})

@app.route('/flatholders')
def flatholders():
    return render_template('flatholders.html')

@app.route('/api/payors', methods=['GET'])
def get_payors():
    if using_supabase():
        client = get_client()
        profiles = _rows(client.table('payor_profiles').select('*').order('name').execute())
        all_vouchers = _rows(client.table('vouchers').select('payee_payor,voucher_type,credit_amount,debit_amount,date').execute())

        result = []
        for p in profiles:
            name_lower = p['name'].lower().strip()
            rv_total = pv_total = jv_credit = jv_debit = count = 0
            last_date = ''
            for v in all_vouchers:
                if v.get('payee_payor', '').lower().strip() == name_lower:
                    count += 1
                    if v['voucher_type'] == 'RV':
                        rv_total += v.get('credit_amount', 0)
                    elif v['voucher_type'] == 'PV':
                        pv_total += v.get('debit_amount', 0)
                    elif v['voucher_type'] == 'JV':
                        jv_credit += v.get('credit_amount', 0)
                        jv_debit += v.get('debit_amount', 0)
                    d = v.get('date', '')
                    if d > last_date:
                        last_date = d

            row = dict(p)
            row['voucher_count'] = count
            row['rv_total'] = rv_total
            row['pv_total'] = pv_total
            row['jv_credit_total'] = jv_credit
            row['jv_debit_total'] = jv_debit
            row['last_transaction_date'] = last_date if last_date else None
            row['net_status'] = (rv_total + jv_credit) - (pv_total + jv_debit)
            result.append(row)
    else:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT p.id, p.name, p.phone, p.email, p.address, p.notes, p.status,
                   p.created_at, p.updated_at,
                   COUNT(v.id) as voucher_count,
                   COALESCE(SUM(CASE WHEN v.voucher_type = 'RV' THEN v.credit_amount ELSE 0 END), 0) as rv_total,
                   COALESCE(SUM(CASE WHEN v.voucher_type = 'PV' THEN v.debit_amount ELSE 0 END), 0) as pv_total,
                   COALESCE(SUM(CASE WHEN v.voucher_type = 'JV' THEN v.credit_amount ELSE 0 END), 0) as jv_credit_total,
                   COALESCE(SUM(CASE WHEN v.voucher_type = 'JV' THEN v.debit_amount ELSE 0 END), 0) as jv_debit_total,
                   MAX(v.date) as last_transaction_date
            FROM payor_profiles p
            LEFT JOIN vouchers v ON LOWER(TRIM(v.payee_payor)) = LOWER(TRIM(p.name))
            GROUP BY p.id ORDER BY p.name COLLATE NOCASE
        ''')
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d['net_status'] = (d['rv_total'] + d['jv_credit_total']) - (d['pv_total'] + d['jv_debit_total'])
            result.append(d)
        conn.close()

    return jsonify({'success': True, 'data': result})

@app.route('/api/payor/<int:id>', methods=['PUT'])
def update_payor(id):
    data = request.json or {}
    try:
        status = str(data.get('status', 'ACTIVE') or 'ACTIVE').strip().upper()
        if status not in ('ACTIVE', 'INACTIVE'):
            return jsonify({'success': False, 'error': 'status must be ACTIVE or INACTIVE'}), 400

        if using_supabase():
            existing = _one(get_client().table('payor_profiles').select('id').eq('id', id).execute())
            if not existing:
                return jsonify({'success': False, 'error': 'Payor profile not found'}), 404
            sb_update('payor_profiles', {
                'phone': str(data.get('phone', '') or '').strip(),
                'email': str(data.get('email', '') or '').strip(),
                'address': str(data.get('address', '') or '').strip(),
                'notes': str(data.get('notes', '') or '').strip(),
                'status': status,
                'updated_at': datetime.utcnow().isoformat(),
            }, {'id': id})
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('SELECT id FROM payor_profiles WHERE id = ?', (id,))
            if not cur.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Payor profile not found'}), 404
            cur.execute('''
                UPDATE payor_profiles SET phone=?, email=?, address=?, notes=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
            ''', (str(data.get('phone', '') or '').strip(), str(data.get('email', '') or '').strip(),
                  str(data.get('address', '') or '').strip(), str(data.get('notes', '') or '').strip(),
                  status, id))
            conn.commit()
            conn.close()

        return jsonify({'success': True, 'message': 'Payor profile updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flatholders', methods=['GET'])
def get_flatholders():
    if using_supabase():
        fhs = _rows(get_client().table('flatholders').select('*').order('serial_no').execute())
        for r in fhs:
            r['due_amount'] = max(0, r.get('total_amount', 0) - r.get('paid_amount', 0))
            pa = r.get('paid_amount', 0)
            ta = r.get('total_amount', 0)
            r['payment_status'] = 'NOT_PAID' if pa == 0 else ('PARTIAL' if pa < ta else 'FULL')
    else:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT *, (total_amount - paid_amount) as due_amount,
                   CASE WHEN paid_amount = 0 THEN 'NOT_PAID'
                        WHEN paid_amount < total_amount THEN 'PARTIAL'
                        ELSE 'FULL' END as payment_status
            FROM flatholders ORDER BY serial_no
        ''')
        fhs = cur.fetchall()
        conn.close()

    return jsonify({'success': True, 'data': fhs})

@app.route('/api/flatholder', methods=['POST'])
def create_flatholder():
    data = request.json or {}
    try:
        serial_no = int(data.get('serial_no') or 0)
        name = str(data.get('name') or '').strip()
        if serial_no <= 0 or not name:
            return jsonify({'success': False, 'error': 'serial_no and name are required'}), 400

        total_amount = int(round(float(data.get('total_amount', 0) or 0) * 100))
        if total_amount < 0:
            return jsonify({'success': False, 'error': 'total_amount cannot be negative'}), 400

        if using_supabase():
            payload = {
                'serial_no': serial_no, 'name': name,
                'phone': data.get('phone', ''), 'email': data.get('email', ''),
                'address': data.get('address', ''), 'flat_unit': data.get('flat_unit', ''),
                'total_amount': total_amount,
            }
            result = sb_insert('flatholders', payload)
            fh_id = _rows(result)[0]['id'] if _rows(result) else None
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO flatholders (serial_no, name, phone, email, address, flat_unit, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (serial_no, name, data.get('phone', ''), data.get('email', ''),
                  data.get('address', ''), data.get('flat_unit', ''), total_amount))
            conn.commit()
            fh_id = cur.lastrowid
            conn.close()

        return jsonify({'success': True, 'message': 'Flatholder added successfully', 'id': fh_id})
    except Exception as e:
        err = str(e).lower()
        if 'duplicate' in err or 'unique' in err or 'already' in err:
            return jsonify({'success': False, 'error': 'This serial number already exists'}), 409
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/flatholder/<int:id>', methods=['PUT'])
def update_flatholder(id):
    data = request.json or {}
    try:
        serial_no = int(data.get('serial_no') or 0)
        name = str(data.get('name') or '').strip()
        if serial_no <= 0 or not name:
            return jsonify({'success': False, 'error': 'serial_no and name are required'}), 400

        total_amount = int(round(float(data.get('total_amount', 0) or 0) * 100))
        if total_amount < 0:
            return jsonify({'success': False, 'error': 'total_amount cannot be negative'}), 400

        if using_supabase():
            existing = _one(get_client().table('flatholders').select('paid_amount').eq('id', id).execute())
            if not existing:
                return jsonify({'success': False, 'error': 'Flatholder not found'}), 404
            if total_amount < existing.get('paid_amount', 0):
                return jsonify({'success': False, 'error': 'total_amount cannot be less than already paid amount'}), 400

            sb_update('flatholders', {
                'serial_no': serial_no, 'name': name,
                'phone': str(data.get('phone', '') or '').strip(),
                'email': str(data.get('email', '') or '').strip(),
                'address': str(data.get('address', '') or '').strip(),
                'flat_unit': str(data.get('flat_unit', '') or '').strip(),
                'total_amount': total_amount,
            }, {'id': id})
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('SELECT id, paid_amount FROM flatholders WHERE id = ?', (id,))
            existing = cur.fetchone()
            if not existing:
                return jsonify({'success': False, 'error': 'Flatholder not found'}), 404
            if total_amount < existing['paid_amount']:
                return jsonify({'success': False, 'error': 'total_amount cannot be less than already paid amount'}), 400
            cur.execute('''
                UPDATE flatholders SET serial_no=?, name=?, phone=?, email=?, address=?, flat_unit=?, total_amount=?
                WHERE id=?
            ''', (serial_no, name, str(data.get('phone', '') or '').strip(),
                  str(data.get('email', '') or '').strip(), str(data.get('address', '') or '').strip(),
                  str(data.get('flat_unit', '') or '').strip(), total_amount, id))
            conn.commit()
            conn.close()

        return jsonify({'success': True, 'message': 'Flatholder updated successfully'})
    except Exception as e:
        err = str(e).lower()
        if 'duplicate' in err or 'unique' in err:
            return jsonify({'success': False, 'error': 'This serial number already exists'}), 409
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/flatholder/<int:id>', methods=['DELETE'])
def delete_flatholder(id):
    try:
        if using_supabase():
            existing = _one(get_client().table('flatholders').select('id').eq('id', id).execute())
            if not existing:
                return jsonify({'success': False, 'error': 'Flatholder not found'}), 404
            sb_delete('flatholder_payments', {'flatholder_id': id})
            sb_delete('flatholders', {'id': id})
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('SELECT id FROM flatholders WHERE id = ?', (id,))
            if not cur.fetchone():
                return jsonify({'success': False, 'error': 'Flatholder not found'}), 404
            cur.execute('DELETE FROM flatholder_payments WHERE flatholder_id = ?', (id,))
            cur.execute('DELETE FROM flatholders WHERE id = ?', (id,))
            conn.commit()
            conn.close()
        return jsonify({'success': True, 'message': 'Flatholder deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flatholder/<int:id>/payment', methods=['POST'])
def add_payment(id):
    data = request.json or {}
    try:
        amount = int(round(float(data.get('amount', 0) or 0) * 100))
        if not data.get('payment_date') or not data.get('payment_type'):
            return jsonify({'success': False, 'error': 'payment_date and payment_type are required'}), 400
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Payment amount must be greater than zero'}), 400

        if using_supabase():
            client = get_client()
            holder = _one(client.table('flatholders').select('id,paid_amount,total_amount').eq('id', id).execute())
            if not holder:
                return jsonify({'success': False, 'error': 'Flatholder not found'}), 404
            if holder['paid_amount'] + amount > holder['total_amount']:
                return jsonify({'success': False, 'error': f"Payment would exceed total amount. Remaining: {holder['total_amount'] - holder['paid_amount']}"}), 400

            sb_insert('flatholder_payments', {
                'flatholder_id': id,
                'payment_date': data['payment_date'],
                'amount': amount,
                'payment_type': data['payment_type'],
                'notes': data.get('notes', ''),
            })
            sb_update('flatholders', {'paid_amount': holder['paid_amount'] + amount}, {'id': id})
        else:
            conn = _get_db()
            cur = conn.cursor()
            cur.execute('SELECT id, paid_amount, total_amount FROM flatholders WHERE id = ?', (id,))
            holder = cur.fetchone()
            if not holder:
                conn.close()
                return jsonify({'success': False, 'error': 'Flatholder not found'}), 404
            if holder['paid_amount'] + amount > holder['total_amount']:
                conn.close()
                return jsonify({'success': False, 'error': f"Payment would exceed total amount. Remaining: {holder['total_amount'] - holder['paid_amount']}"}), 400

            cur.execute('''
                INSERT INTO flatholder_payments (flatholder_id, payment_date, amount, payment_type, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (id, data['payment_date'], amount, data['payment_type'], data.get('notes', '')))
            cur.execute('UPDATE flatholders SET paid_amount = paid_amount + ? WHERE id = ?', (amount, id))
            conn.commit()
            conn.close()

        return jsonify({'success': True, 'message': 'Payment added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard/summary', methods=['GET'])
def dashboard_summary():
    today = _today_str()
    if using_supabase():
        client = get_client()
        today_v = _rows(client.table('vouchers').select('credit_amount,debit_amount').eq('date', today).execute())
        today_vouchers = len(today_v)
        today_income = sum(r.get('credit_amount', 0) for r in today_v if r.get('credit_amount', 0) > 0)
        today_expense = sum(r.get('debit_amount', 0) for r in today_v if r.get('debit_amount', 0) > 0)
        fhs = _rows(client.table('flatholders').select('id,paid_amount').execute())
        total_flatholders = len(fhs)
        total_collected = sum(r.get('paid_amount', 0) for r in fhs)
    else:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(*), COALESCE(SUM(credit_amount),0), COALESCE(SUM(debit_amount),0)
            FROM vouchers WHERE date = ?
        ''', (today,))
        row = cur.fetchone()
        today_vouchers, today_income, today_expense = row[0], row[1], row[2]
        cur.execute('SELECT COUNT(*), COALESCE(SUM(paid_amount),0) FROM flatholders')
        row = cur.fetchone()
        total_flatholders, total_collected = row[0], row[1]
        conn.close()

    return jsonify({'success': True, 'data': {
        'today_vouchers': today_vouchers, 'today_income': today_income,
        'today_expense': today_expense, 'total_flatholders': total_flatholders,
        'total_collected': total_collected
    }})

@app.route('/api/export', methods=['GET'])
def export_data():
    export_type = request.args.get('type', 'vouchers')
    if using_supabase():
        if export_type == 'vouchers':
            data = _rows(get_client().table('vouchers').select('*').order('date').execute())
        elif export_type == 'flatholders':
            data = _rows(get_client().table('flatholders').select('*').order('serial_no').execute())
        else:
            data = []
    else:
        conn = _get_db()
        cur = conn.cursor()
        if export_type == 'vouchers':
            cur.execute('SELECT * FROM vouchers ORDER BY date')
        elif export_type == 'flatholders':
            cur.execute('SELECT * FROM flatholders ORDER BY serial_no')
        else:
            cur.execute('SELECT 1')
        data = cur.fetchall()
        conn.close()

    return jsonify({'success': True, 'data': data})

@app.route('/api/import', methods=['POST'])
def import_data():
    return jsonify({'success': True, 'message': 'Import functionality - implement based on file type'})

@app.before_request
def before_request():
    public_endpoints = {'login', 'health', 'static'}
    if request.endpoint in public_endpoints:
        return None
    if request.path.startswith('/.well-known/'):
        return None
    if not session.get('authenticated'):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return redirect(url_for('login', next=request.path))

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=debug_mode, host=host, port=port)
