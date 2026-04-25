-- ============================================================
-- STEP 1: Fix column types
-- ============================================================

ALTER TABLE vouchers ALTER COLUMN debit_amount TYPE BIGINT;
ALTER TABLE vouchers ALTER COLUMN credit_amount TYPE BIGINT;

ALTER TABLE flatholders ALTER COLUMN total_amount TYPE BIGINT;
ALTER TABLE flatholders ALTER COLUMN paid_amount TYPE BIGINT;

ALTER TABLE investments ALTER COLUMN amount TYPE BIGINT;

-- ============================================================
-- STEP 2: Clear any partial data from failed migrations
-- ============================================================
DELETE FROM source_rows;
DELETE FROM period_summaries;
DELETE FROM investments;
DELETE FROM flatholder_payments;
DELETE FROM vouchers;
DELETE FROM flatholders;
DELETE FROM payor_profiles;

-- ============================================================
-- STEP 3: Remove test data from payor_profiles
-- ============================================================
DELETE FROM payor_profiles WHERE name ILIKE '%test%';

-- ============================================================
-- STEP 4: Add Foreign Key Constraints
-- ============================================================

-- Drop existing constraints if they already exist, then add
ALTER TABLE vouchers DROP CONSTRAINT IF EXISTS fk_vouchers_account_code;
ALTER TABLE vouchers
  ADD CONSTRAINT fk_vouchers_account_code
  FOREIGN KEY (account_code) REFERENCES account_codes(code);

ALTER TABLE flatholder_payments DROP CONSTRAINT IF EXISTS fk_fhp_flatholder_id;
ALTER TABLE flatholder_payments
  ADD CONSTRAINT fk_fhp_flatholder_id
  FOREIGN KEY (flatholder_id) REFERENCES flatholders(id);

ALTER TABLE flatholder_payments DROP CONSTRAINT IF EXISTS fk_fhp_voucher_id;
ALTER TABLE flatholder_payments
  ADD CONSTRAINT fk_fhp_voucher_id
  FOREIGN KEY (voucher_id) REFERENCES vouchers(id);

ALTER TABLE investments DROP CONSTRAINT IF EXISTS fk_investments_voucher_id;
ALTER TABLE investments
  ADD CONSTRAINT fk_investments_voucher_id
  FOREIGN KEY (voucher_id) REFERENCES vouchers(id);
