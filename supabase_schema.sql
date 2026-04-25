-- Supabase SQL schema (run in the SQL editor / dashboard)
-- Tables and constraints mirroring the original SQLite schema, using Supabase/PostgreSQL types.

-- 1) Account codes (seed initial values from insert_default_accounts below)
CREATE TABLE IF NOT EXISTS account_codes (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('ASSET', 'LIABILITY', 'INCOME', 'EXPENSE')),
    description TEXT
);

-- 2) Vouchers (core financial transactions)
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

-- 3) Flat holders (buyers)
CREATE TABLE IF NOT EXISTS flatholders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    serial_no INTEGER UNIQUE NOT NULL,
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

-- 4) Flat holder payments
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

-- 5) Investments (received / paid)
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

-- 6) Period summaries
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

-- 7) Payor / payee profiles (backfilled from vouchers)
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

-- 8) Source rows archival (full workbook rows)
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

-- 9) Seed default account codes (same as SQLite init)
INSERT INTO account_codes (code, name, category, type, description) VALUES
('101','Share Capital','INCOME','INCOME','Initial capital from shareholders'),
('102','Investment/Loan Received','INCOME','INCOME','Short term loans and investments'),
('103','Bank/FDR Profit','INCOME','INCOME','Interest income from banks'),
('104','Sale of Scrap/Wastage','INCOME','INCOME','Sale of construction waste materials'),
('105','Miscellaneous Income','INCOME','INCOME','Other income sources'),
('106','Flat Booking Money','INCOME','INCOME','Initial booking payments from flat buyers'),
('107','Down Payment','INCOME','INCOME','Down payments from flat buyers'),
('108','Installment','INCOME','INCOME','Installment payments from flat buyers'),
('201','Office Rent','ADMIN','EXPENSE','Monthly office rent'),
('202','Utilities (Electricity/Gas/Water)','ADMIN','EXPENSE','Utility bills'),
('203','Advertisement','ADMIN','EXPENSE','Marketing and advertisement costs'),
('204','Printing & Stationery','ADMIN','EXPENSE','Office supplies'),
('205','Entertainment','ADMIN','EXPENSE','Guest entertainment expenses'),
('206','Salary & Allowances','ADMIN','EXPENSE','Staff salaries and bonuses'),
('207','Telephone/Internet','ADMIN','EXPENSE','Communication expenses'),
('208','Conveyance/Travelling','ADMIN','EXPENSE','Transportation costs'),
('209','Legal & Consultant Fees','ADMIN','EXPENSE','Legal and professional fees'),
('210','Miscellaneous Expense','ADMIN','EXPENSE','Other administrative expenses'),
('301','Rod/Steel Purchase','CONSTRUCTION','EXPENSE','Steel rods and bars'),
('302','Cement Purchase','CONSTRUCTION','EXPENSE','Cement and related materials'),
('303','Sylhet Sand','CONSTRUCTION','EXPENSE','Sand from Sylhet'),
('304','Local Sand','CONSTRUCTION','EXPENSE','Locally sourced sand'),
('305','Stone','CONSTRUCTION','EXPENSE','Construction stones'),
('306','Stone Chips','CONSTRUCTION','EXPENSE','Stone chips for concrete'),
('307','Brick','CONSTRUCTION','EXPENSE','Construction bricks'),
('308','Brick Chips','CONSTRUCTION','EXPENSE','Brick chips and broken bricks'),
('309','Carrying Cost','CONSTRUCTION','EXPENSE','Transportation and carrying'),
('310','Labour Payment','CONSTRUCTION','EXPENSE','Labour and contractor payments'),
('311','Sanitary/Plumbing','CONSTRUCTION','EXPENSE','Sanitary and plumbing materials'),
('312','Electric Materials','CONSTRUCTION','EXPENSE','Electrical wiring and fittings'),
('313','Tiles Purchase','CONSTRUCTION','EXPENSE','Floor and wall tiles'),
('314','Window & Grill','CONSTRUCTION','EXPENSE','Windows and grills'),
('315','Doors & Chawkath','CONSTRUCTION','EXPENSE','Doors and frames'),
('316','Colour/Paint','CONSTRUCTION','EXPENSE','Paints and coloring materials'),
('317','Thai Glass & Fittings','CONSTRUCTION','EXPENSE','Glass and fittings'),
('318','Gas Line Materials','CONSTRUCTION','EXPENSE','Gas pipeline materials'),
('401','Land Development Cost','ASSET','EXPENSE','Cost of land development'),
('402','Land Registration','ASSET','EXPENSE','Land registration and legal fees'),
('403','Preliminary Expenses','ASSET','EXPENSE','Initial project expenses'),
('404','Piling/Foundation','ASSET','EXPENSE','Piling and foundation work'),
('405','Deep Tubewell','ASSET','EXPENSE','Water well construction'),
('406','Gas Connection','ASSET','EXPENSE','Gas line connection'),
('407','Decoration & Furniture','ASSET','EXPENSE','Office furniture and decoration'),
('408','Flat Sale Commission','EXPENSE','EXPENSE','Commission on flat sales'),
('409','Short Loan Refund','LIABILITY','EXPENSE','Repayment of short term loans'),
('410','Profit Paid on Loan','EXPENSE','EXPENSE','Interest paid on loans'),
('411','Holding Tax','EXPENSE','EXPENSE','Property holding tax'),
('412','Lift Shutter Making','CONSTRUCTION','EXPENSE','Elevator and shutter work'),
('413','Sand Filling Labour','CONSTRUCTION','EXPENSE','Sand filling work');

-- Optional: Indexes to speed up joins / lookups
CREATE INDEX IF NOT EXISTS idx_vouchers_account_code ON vouchers(account_code);
CREATE INDEX IF NOT EXISTS idx_vouchers_date ON vouchers(date);
CREATE INDEX IF NOT EXISTS idx_flatholders_serial ON flatholders(serial_no);
CREATE INDEX IF NOT EXISTS idx_investments_voucher ON investments(voucher_id);
CREATE INDEX IF NOT EXISTS idx_flatholder_payments_flatholder ON flatholder_payments(flatholder_id);
CREATE INDEX IF NOT EXISTS idx_flatholder_payments_voucher ON flatholder_payments(voucher_id);