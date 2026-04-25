## Table `account_codes`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `code` | `text` | Primary |
| `name` | `text` |  |
| `category` | `text` |  |
| `type` | `text` |  |
| `description` | `text` |  Nullable |

## Table `flatholder_payments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `flatholder_id` | `int8` |  |
| `payment_date` | `date` |  |
| `amount` | `numeric` |  |
| `payment_type` | `text` |  Nullable |
| `voucher_id` | `int8` |  Nullable |
| `notes` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `flatholders`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `serial_no` | `int4` |  Unique |
| `name` | `text` |  |
| `phone` | `text` |  Nullable |
| `email` | `text` |  Nullable |
| `address` | `text` |  Nullable |
| `flat_unit` | `text` |  Nullable |
| `total_amount` | `int4` |  Nullable |
| `paid_amount` | `int4` |  Nullable |
| `status` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `investments`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `name` | `text` |  |
| `type` | `text` |  Nullable |
| `amount` | `int4` |  |
| `date` | `date` |  |
| `voucher_id` | `int8` |  Nullable |
| `status` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `payor_profiles`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `name` | `text` |  Unique |
| `phone` | `text` |  Nullable |
| `email` | `text` |  Nullable |
| `address` | `text` |  Nullable |
| `notes` | `text` |  Nullable |
| `status` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  Nullable |

## Table `period_summaries`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `period_type` | `text` |  |
| `period_value` | `text` |  |
| `total_income` | `numeric` |  Nullable |
| `total_expense` | `numeric` |  Nullable |
| `net_amount` | `numeric` |  Nullable |
| `voucher_count` | `int4` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

## Table `source_rows`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `sheet_name` | `text` |  |
| `row_no` | `int4` |  |
| `record_type` | `text` |  |
| `title` | `text` |  Nullable |
| `date_value` | `text` |  Nullable |
| `amount` | `numeric` |  Nullable |
| `amount_2` | `numeric` |  Nullable |
| `row_json` | `text` |  |
| `created_at` | `timestamptz` |  Nullable |

## Table `vouchers`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int8` | Primary Identity |
| `voucher_no` | `text` |  Unique |
| `date` | `date` |  |
| `voucher_type` | `text` |  |
| `account_code` | `text` |  |
| `description` | `text` |  |
| `debit_amount` | `int4` |  Nullable |
| `credit_amount` | `int4` |  Nullable |
| `reference_no` | `text` |  Nullable |
| `payee_payor` | `text` |  Nullable |
| `notes` | `text` |  Nullable |
| `created_at` | `timestamptz` |  Nullable |

