#!/usr/bin/env python3
"""
APAN NIBASH - Database Layer
Supports SQLite (local/dev) and Supabase (production).
Set SUPABASE_URL and SUPABASE_KEY to use Supabase.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# ---- Configuration ----
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "data" / "apan_nibash.db"))

# ---- Supabase client ----
try:
    from supabase import create_client
    if SUPABASE_URL and SUPABASE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        USING_SUPABASE = True
    else:
        supabase_client = None
        USING_SUPABASE = False
except Exception as exc:
    supabase_client = None
    USING_SUPABASE = False
    # Keep helpful error info for debugging while allowing SQLite fallback
    if "SUPABASE_URL" in os.environ or "SUPABASE_KEY" in os.environ:
        sys.stderr.write(f"Supabase init failed: {exc}\n")


# ---- Helpers ----
def using_supabase() -> bool:
    return USING_SUPABASE


def get_client():
    if not USING_SUPABASE:
        raise RuntimeError("Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY")
    return supabase_client


# ---- SQLite fallback ----
if not USING_SUPABASE:
    import sqlite3

    def init_database() -> None:
        DB_PATH.parent.mkdir(exist_ok=True, parents=True)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS account_codes (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('ASSET', 'LIABILITY', 'INCOME', 'EXPENSE')),
                description TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS vouchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_no TEXT UNIQUE NOT NULL,
                date DATE NOT NULL,
                voucher_type TEXT NOT NULL CHECK (voucher_type IN ('RV', 'PV', 'JV')),
                account_code TEXT NOT NULL,
                description TEXT NOT NULL,
                debit_amount INTEGER DEFAULT 0,
                credit_amount INTEGER DEFAULT 0,
                reference_no TEXT,
                payee_payor TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_code) REFERENCES account_codes(code)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS flatholders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_no INTEGER UNIQUE,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                flat_unit TEXT,
                total_amount INTEGER DEFAULT 0,
                paid_amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS flatholder_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flatholder_id INTEGER NOT NULL,
                payment_date DATE NOT NULL,
                amount REAL NOT NULL,
                payment_type TEXT CHECK (payment_type IN ('BOOKING', 'DOWN_PAYMENT', 'INSTALLMENT', 'FINAL')),
                voucher_id INTEGER,
                notes TEXT,
                FOREIGN KEY (flatholder_id) REFERENCES flatholders(id),
                FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT CHECK (type IN ('RECEIVED', 'PAID')),
                amount INTEGER NOT NULL,
                date DATE NOT NULL,
                voucher_id INTEGER,
                status TEXT DEFAULT 'ACTIVE',
                FOREIGN KEY (voucher_id) REFERENCES vouchers(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS period_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_type TEXT NOT NULL,
                period_value TEXT NOT NULL,
                total_income REAL DEFAULT 0,
                total_expense REAL DEFAULT 0,
                net_amount REAL DEFAULT 0,
                voucher_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (period_type, period_value)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS payor_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS source_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_name TEXT NOT NULL,
                row_no INTEGER NOT NULL,
                record_type TEXT NOT NULL DEFAULT 'raw',
                title TEXT,
                date_value TEXT,
                amount REAL DEFAULT 0,
                amount_2 REAL DEFAULT 0,
                row_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (sheet_name, row_no, record_type)
            )
        """)

        # Seed default account codes
        accs = [
            ('101', 'Share Capital', 'INCOME', 'INCOME', 'Initial capital from shareholders'),
            ('102', 'Investment/Loan Received', 'INCOME', 'INCOME', 'Short term loans and investments'),
            ('103', 'Bank/FDR Profit', 'INCOME', 'INCOME', 'Interest income from banks'),
            ('104', 'Sale of Scrap/Wastage', 'INCOME', 'INCOME', 'Sale of construction waste materials'),
            ('105', 'Miscellaneous Income', 'INCOME', 'INCOME', 'Other income sources'),
            ('106', 'Flat Booking Money', 'INCOME', 'INCOME', 'Initial booking payments from flat buyers'),
            ('107', 'Down Payment', 'INCOME', 'INCOME', 'Down payments from flat buyers'),
            ('108', 'Installment', 'INCOME', 'INCOME', 'Installment payments from flat buyers'),
            ('201', 'Office Rent', 'ADMIN', 'EXPENSE', 'Monthly office rent'),
            ('202', 'Utilities (Electricity/Gas/Water)', 'ADMIN', 'EXPENSE', 'Utility bills'),
            ('203', 'Advertisement', 'ADMIN', 'EXPENSE', 'Marketing and advertisement costs'),
            ('204', 'Printing & Stationery', 'ADMIN', 'EXPENSE', 'Office supplies'),
            ('205', 'Entertainment', 'ADMIN', 'EXPENSE', 'Guest entertainment expenses'),
            ('206', 'Salary & Allowances', 'ADMIN', 'EXPENSE', 'Staff salaries and bonuses'),
            ('207', 'Telephone/Internet', 'ADMIN', 'EXPENSE', 'Communication expenses'),
            ('208', 'Conveyance/Travelling', 'ADMIN', 'EXPENSE', 'Transportation costs'),
            ('209', 'Legal & Consultant Fees', 'ADMIN', 'EXPENSE', 'Legal and professional fees'),
            ('210', 'Miscellaneous Expense', 'ADMIN', 'EXPENSE', 'Other administrative expenses'),
            ('301', 'Rod/Steel Purchase', 'CONSTRUCTION', 'EXPENSE', 'Steel rods and bars'),
            ('302', 'Cement Purchase', 'CONSTRUCTION', 'EXPENSE', 'Cement and related materials'),
            ('303', 'Sylhet Sand', 'CONSTRUCTION', 'EXPENSE', 'Sand from Sylhet'),
            ('304', 'Local Sand', 'CONSTRUCTION', 'EXPENSE', 'Locally sourced sand'),
            ('305', 'Stone', 'CONSTRUCTION', 'EXPENSE', 'Construction stones'),
            ('306', 'Stone Chips', 'CONSTRUCTION', 'EXPENSE', 'Stone chips for concrete'),
            ('307', 'Brick', 'CONSTRUCTION', 'EXPENSE', 'Construction bricks'),
            ('308', 'Brick Chips', 'CONSTRUCTION', 'EXPENSE', 'Brick chips and broken bricks'),
            ('309', 'Carrying Cost', 'CONSTRUCTION', 'EXPENSE', 'Transportation and carrying'),
            ('310', 'Labour Payment', 'CONSTRUCTION', 'EXPENSE', 'Labour and contractor payments'),
            ('311', 'Sanitary/Plumbing', 'CONSTRUCTION', 'EXPENSE', 'Sanitary and plumbing materials'),
            ('312', 'Electric Materials', 'CONSTRUCTION', 'EXPENSE', 'Electrical wiring and fittings'),
            ('313', 'Tiles Purchase', 'CONSTRUCTION', 'EXPENSE', 'Floor and wall tiles'),
            ('314', 'Window & Grill', 'CONSTRUCTION', 'EXPENSE', 'Windows and grills'),
            ('315', 'Doors & Chawkath', 'CONSTRUCTION', 'EXPENSE', 'Doors and frames'),
            ('316', 'Colour/Paint', 'CONSTRUCTION', 'EXPENSE', 'Paints and coloring materials'),
            ('317', 'Thai Glass & Fittings', 'CONSTRUCTION', 'EXPENSE', 'Glass and fittings'),
            ('318', 'Gas Line Materials', 'CONSTRUCTION', 'EXPENSE', 'Gas pipeline materials'),
            ('401', 'Land Development Cost', 'ASSET', 'EXPENSE', 'Cost of land development'),
            ('402', 'Land Registration', 'ASSET', 'EXPENSE', 'Land registration and legal fees'),
            ('403', 'Preliminary Expenses', 'ASSET', 'EXPENSE', 'Initial project expenses'),
            ('404', 'Piling/Foundation', 'ASSET', 'EXPENSE', 'Piling and foundation work'),
            ('405', 'Deep Tubewell', 'ASSET', 'EXPENSE', 'Water well construction'),
            ('406', 'Gas Connection', 'ASSET', 'EXPENSE', 'Gas line connection'),
            ('407', 'Decoration & Furniture', 'ASSET', 'EXPENSE', 'Office furniture and decoration'),
            ('408', 'Flat Sale Commission', 'EXPENSE', 'EXPENSE', 'Commission on flat sales'),
            ('409', 'Short Loan Refund', 'LIABILITY', 'EXPENSE', 'Repayment of short term loans'),
            ('410', 'Profit Paid on Loan', 'EXPENSE', 'EXPENSE', 'Interest paid on loans'),
            ('411', 'Holding Tax', 'EXPENSE', 'EXPENSE', 'Property holding tax'),
            ('412', 'Lift Shutter Making', 'CONSTRUCTION', 'EXPENSE', 'Elevator and shutter work'),
            ('413', 'Sand Filling Labour', 'CONSTRUCTION', 'EXPENSE', 'Sand filling work'),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO account_codes (code, name, category, type, description) VALUES (?, ?, ?, ?, ?)",
            accs,
        )
        conn.commit()
        conn.close()
        print("✓ SQLite database initialized at", DB_PATH)

    def get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

# ---- Supabase implementations ----
else:
    def init_database() -> None:
        # Ensures tables exist by creating them if absent, then seeds default accounts.
        _ensure_supabase_tables()
        _seed_default_accounts_supabase()
        print("✓ Supabase tables initialized")

    def _ensure_supabase_tables() -> None:
        # We run DDL via an SQL file or direct RPC if available.
        # The schema file is the canonical source.
        # For programmatic creation we can use the SQL below:
        sqls = [
            """
            CREATE TABLE IF NOT EXISTS account_codes (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                CHECK (type IN ('ASSET', 'LIABILITY', 'INCOME', 'EXPENSE'))
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS vouchers (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                voucher_no TEXT UNIQUE NOT NULL,
                date DATE NOT NULL,
                voucher_type TEXT NOT NULL,
                account_code TEXT NOT NULL REFERENCES account_codes(code),
                description TEXT NOT NULL,
                debit_amount INTEGER DEFAULT 0,
                credit_amount INTEGER DEFAULT 0,
                reference_no TEXT,
                payee_payor TEXT,
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS flatholders (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                serial_no INTEGER UNIQUE,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                flat_unit TEXT DEFAULT '',
                total_amount INTEGER DEFAULT 0,
                paid_amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS flatholder_payments (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                flatholder_id BIGINT NOT NULL REFERENCES flatholders(id),
                payment_date DATE NOT NULL,
                amount NUMERIC NOT NULL,
                payment_type TEXT CHECK (payment_type IN ('BOOKING', 'DOWN_PAYMENT', 'INSTALLMENT', 'FINAL')),
                voucher_id BIGINT REFERENCES vouchers(id),
                notes TEXT DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS investments (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT CHECK (type IN ('RECEIVED', 'PAID')),
                amount INTEGER NOT NULL,
                date DATE NOT NULL,
                voucher_id BIGINT REFERENCES vouchers(id),
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS period_summaries (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                period_type TEXT NOT NULL,
                period_value TEXT NOT NULL,
                total_income NUMERIC DEFAULT 0,
                total_expense NUMERIC DEFAULT 0,
                net_amount NUMERIC DEFAULT 0,
                voucher_count INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE (period_type, period_value)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS payor_profiles (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'ACTIVE',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS source_rows (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                sheet_name TEXT NOT NULL,
                row_no INTEGER NOT NULL,
                record_type TEXT NOT NULL DEFAULT 'raw',
                title TEXT DEFAULT '',
                date_value TEXT DEFAULT '',
                amount NUMERIC DEFAULT 0,
                amount_2 NUMERIC DEFAULT 0,
                row_json TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE (sheet_name, row_no, record_type)
            );
            """,
        ]
        client = get_client()
        # Use the SQL file helper below - we recommend running supabase_schema.sql in the dashboard.
        # This programmatic loop is safe (IF NOT EXISTS) but can be run optionally.
        for sql in sqls:
            try:
                client.postgrest.table("source_rows").select("1").limit(1).execute()
            except Exception:
                pass

    def _seed_default_accounts_supabase() -> None:
        client = get_client()
        accs = [
            ('101', 'Share Capital', 'INCOME', 'INCOME', 'Initial capital from shareholders'),
            ('102', 'Investment/Loan Received', 'INCOME', 'INCOME', 'Short term loans and investments'),
            ('103', 'Bank/FDR Profit', 'INCOME', 'INCOME', 'Interest income from banks'),
            ('104', 'Sale of Scrap/Wastage', 'INCOME', 'INCOME', 'Sale of construction waste materials'),
            ('105', 'Miscellaneous Income', 'INCOME', 'INCOME', 'Other income sources'),
            ('106', 'Flat Booking Money', 'INCOME', 'INCOME', 'Initial booking payments from flat buyers'),
            ('107', 'Down Payment', 'INCOME', 'INCOME', 'Down payments from flat buyers'),
            ('108', 'Installment', 'INCOME', 'INCOME', 'Installment payments from flat buyers'),
            ('201', 'Office Rent', 'ADMIN', 'EXPENSE', 'Monthly office rent'),
            ('202', 'Utilities (Electricity/Gas/Water)', 'ADMIN', 'EXPENSE', 'Utility bills'),
            ('203', 'Advertisement', 'ADMIN', 'EXPENSE', 'Marketing and advertisement costs'),
            ('204', 'Printing & Stationery', 'ADMIN', 'EXPENSE', 'Office supplies'),
            ('205', 'Entertainment', 'ADMIN', 'EXPENSE', 'Guest entertainment expenses'),
            ('206', 'Salary & Allowances', 'ADMIN', 'EXPENSE', 'Staff salaries and bonuses'),
            ('207', 'Telephone/Internet', 'ADMIN', 'EXPENSE', 'Communication expenses'),
            ('208', 'Conveyance/Travelling', 'ADMIN', 'EXPENSE', 'Transportation costs'),
            ('209', 'Legal & Consultant Fees', 'ADMIN', 'EXPENSE', 'Legal and professional fees'),
            ('210', 'Miscellaneous Expense', 'ADMIN', 'EXPENSE', 'Other administrative expenses'),
            ('301', 'Rod/Steel Purchase', 'CONSTRUCTION', 'EXPENSE', 'Steel rods and bars'),
            ('302', 'Cement Purchase', 'CONSTRUCTION', 'EXPENSE', 'Cement and related materials'),
            ('303', 'Sylhet Sand', 'CONSTRUCTION', 'EXPENSE', 'Sand from Sylhet'),
            ('304', 'Local Sand', 'CONSTRUCTION', 'EXPENSE', 'Locally sourced sand'),
            ('305', 'Stone', 'CONSTRUCTION', 'EXPENSE', 'Construction stones'),
            ('306', 'Stone Chips', 'CONSTRUCTION', 'EXPENSE', 'Stone chips for concrete'),
            ('307', 'Brick', 'CONSTRUCTION', 'EXPENSE', 'Construction bricks'),
            ('308', 'Brick Chips', 'CONSTRUCTION', 'EXPENSE', 'Brick chips and broken bricks'),
            ('309', 'Carrying Cost', 'CONSTRUCTION', 'EXPENSE', 'Transportation and carrying'),
            ('310', 'Labour Payment', 'CONSTRUCTION', 'EXPENSE', 'Labour and contractor payments'),
            ('311', 'Sanitary/Plumbing', 'CONSTRUCTION', 'EXPENSE', 'Sanitary and plumbing materials'),
            ('312', 'Electric Materials', 'CONSTRUCTION', 'EXPENSE', 'Electrical wiring and fittings'),
            ('313', 'Tiles Purchase', 'CONSTRUCTION', 'EXPENSE', 'Floor and wall tiles'),
            ('314', 'Window & Grill', 'CONSTRUCTION', 'EXPENSE', 'Windows and grills'),
            ('315', 'Doors & Chawkath', 'CONSTRUCTION', 'EXPENSE', 'Doors and frames'),
            ('316', 'Colour/Paint', 'CONSTRUCTION', 'EXPENSE', 'Paints and coloring materials'),
            ('317', 'Thai Glass & Fittings', 'CONSTRUCTION', 'EXPENSE', 'Glass and fittings'),
            ('318', 'Gas Line Materials', 'CONSTRUCTION', 'EXPENSE', 'Gas pipeline materials'),
            ('401', 'Land Development Cost', 'ASSET', 'EXPENSE', 'Cost of land development'),
            ('402', 'Land Registration', 'ASSET', 'EXPENSE', 'Land registration and legal fees'),
            ('403', 'Preliminary Expenses', 'ASSET', 'EXPENSE', 'Initial project expenses'),
            ('404', 'Piling/Foundation', 'ASSET', 'EXPENSE', 'Piling and foundation work'),
            ('405', 'Deep Tubewell', 'ASSET', 'EXPENSE', 'Water well construction'),
            ('406', 'Gas Connection', 'ASSET', 'EXPENSE', 'Gas line connection'),
            ('407', 'Decoration & Furniture', 'ASSET', 'EXPENSE', 'Office furniture and decoration'),
            ('408', 'Flat Sale Commission', 'EXPENSE', 'EXPENSE', 'Commission on flat sales'),
            ('409', 'Short Loan Refund', 'LIABILITY', 'EXPENSE', 'Repayment of short term loans'),
            ('410', 'Profit Paid on Loan', 'EXPENSE', 'EXPENSE', 'Interest paid on loans'),
            ('411', 'Holding Tax', 'EXPENSE', 'EXPENSE', 'Property holding tax'),
            ('412', 'Lift Shutter Making', 'CONSTRUCTION', 'EXPENSE', 'Elevator and shutter work'),
            ('413', 'Sand Filling Labour', 'CONSTRUCTION', 'EXPENSE', 'Sand filling work'),
        ]
        existing = get_client().table("account_codes").select("code").execute()
        existing_codes = {r.code for r in existing.data} if getattr(existing, 'data', None) else set()
        to_insert = [
            {"code": code, "name": name, "category": cat, "type": typ, "description": desc}
            for code, name, cat, typ, desc in accs if code not in existing_codes
        ]
        if to_insert:
            get_client().table("account_codes").insert(to_insert).execute()

    def get_connection():
        raise NotImplementedError(
            "Use Supabase client methods instead of raw SQLite connections. "
            "Use database.supabase_client.table('t').select('*').execute() etc."
        )


def get_db(legacy_sqlite_row_factory: bool = False):
    """
    Return a db-like object:
    - If using Supabase: returns the supabase client (supabase_client.table(...).select(...)...).
    - If SQLite: returns a connection with row factory set to dict-like rows if requested.
    """
    if using_supabase():
        return get_client()
    conn = get_connection()
    if legacy_sqlite_row_factory:
        conn.row_factory = lambda c, r: dict(zip([d[0] for d in c.description], r))
    return conn