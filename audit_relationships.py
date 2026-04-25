#!/usr/bin/env python3
"""Relationship audit using standard Supabase table queries only."""
import os
from collections import Counter
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_KEY"]
client = create_client(URL, KEY)

print("=== 1. All vouchers (sample) ===")
vouchers = client.table("vouchers").select("*").limit(20).execute()
print(f"  Total fetched: {len(vouchers.data)}")
for v in vouchers.data:
    print(f"  [{v['voucher_type']}] {v['voucher_no']} | payee={v.get('payee_payor','')!r} | acct={v['account_code']} | {v['description'][:40]}")

print("\n=== 2. Distinct payee_payor values in vouchers ===")
# Manual dedup since no GROUP BY via REST
all_v = client.table("vouchers").select("payee_payor").execute()
payees = Counter(v["payee_payor"] for v in all_v.data if v.get("payee_payor"))
for name, cnt in sorted(payees.items(), key=lambda x: -x[1]):
    print(f"  {name!r}: {cnt}")

print("\n=== 3. payor_profiles ===")
profiles = client.table("payor_profiles").select("*").execute()
print(f"  Count: {len(profiles.data)}")
for p in profiles.data[:20]:
    print(f"  {p['name']!r} (status={p['status']})")

print("\n=== 4. Flatholders ===")
fh = client.table("flatholders").select("id,serial_no,name,total_amount,paid_amount").order("serial_no").execute()
print(f"  Count: {len(fh.data)}")
for f in fh.data[:10]:
    print(f"  [{f['serial_no']}] {f['name']} | total={f['total_amount']} paid={f['paid_amount']}")

print("\n=== 5. flatholder_payments ===")
fhp = client.table("flatholder_payments").select("*").execute()
print(f"  Count: {len(fhp.data)}")
for p in fhp.data[:10]:
    print(f"  flatholder_id={p['flatholder_id']} amount={p['amount']} type={p['payment_type']}")

print("\n=== 6. Investments ===")
inv = client.table("investments").select("*").execute()
print(f"  Count: {len(inv.data)}")
for i in inv.data[:10]:
    print(f"  {i['name']} | type={i['type']} | amount={i['amount']} | voucher_id={i.get('voucher_id')}")

print("\n=== 7. account_codes ===")
ac = client.table("account_codes").select("*").execute()
print(f"  Count: {len(ac.data)}")
