#!/usr/bin/env python3
"""
Migrate all data from SQLite → Supabase.
Handles FK remapping, backfills payor_profiles, cleans test data.

Usage:
  SUPABASE_URL=... SUPABASE_KEY=... python migrate_to_supabase.py --dry-run
  SUPABASE_URL=... SUPABASE_KEY=... python migrate_to_supabase.py --apply
"""
import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path
from supabase import create_client

SQLITE_DB = Path(__file__).parent / "data" / "apan_nibash.db"
BATCH = 50

def get_sqlite():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def insert_batch(table, rows, client, on_conflict=None):
    """Insert rows in batches with retries."""
    if not rows:
        return 0
    total = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        for attempt in range(3):
            try:
                if on_conflict:
                    client.table(table).upsert(chunk, on_conflict=on_conflict).execute()
                else:
                    client.table(table).insert(chunk).execute()
                total += len(chunk)
                break
            except Exception:
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                else:
                    raise
        time.sleep(0.15)
    return total

def migrate(client, apply):
    src = get_sqlite()
    cur = src.cursor()
    counts = {}

    # ── 1. Account Codes ──
    rows = [dict(r) for r in cur.execute("SELECT * FROM account_codes").fetchall()]
    print(f"account_codes: {len(rows)}")
    if apply and rows:
        insert_batch("account_codes", rows, client, on_conflict="code")
    counts["account_codes"] = len(rows)

    # ── 2. Payor Profiles (skip test entries) ──
    all_profiles = [dict(r) for r in cur.execute("SELECT * FROM payor_profiles").fetchall()]
    clean_profiles = [p for p in all_profiles if "test" not in p["name"].lower()]
    # Remove id (GENERATED ALWAYS) and created_at
    for p in clean_profiles:
        p.pop("id", None)
        p.pop("created_at", None)
        p.pop("updated_at", None)
    print(f"payor_profiles: {len(clean_profiles)} real (skipped {len(all_profiles) - len(clean_profiles)} test)")
    if apply and clean_profiles:
        insert_batch("payor_profiles", clean_profiles, client, on_conflict="name")
    counts["payor_profiles"] = len(clean_profiles)

    # ── 3. Flatholders (one-by-one to track old→new ID) ──
    fh_raw = cur.execute("SELECT * FROM flatholders ORDER BY serial_no").fetchall()
    fh_rows = []
    for r in fh_raw:
        d = dict(r)
        d.pop("id", None)
        d.pop("created_at", None)
        fh_rows.append(d)
    print(f"flatholders: {len(fh_rows)}")
    old_to_new_fh = {}
    if apply and fh_rows:
        for i, r in enumerate(fh_rows):
            for attempt in range(3):
                try:
                    res = client.table("flatholders").insert(r).execute()
                    if res.data:
                        old_to_new_fh[fh_raw[i]["id"]] = res.data[0]["id"]
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        raise
            time.sleep(0.1)
    counts["flatholders"] = len(fh_rows)

    # ── 4. Vouchers (batch, then map by voucher_no) ──
    v_raw = cur.execute("SELECT * FROM vouchers ORDER BY id").fetchall()
    v_rows = []
    for r in v_raw:
        d = dict(r)
        d.pop("id", None)
        d.pop("created_at", None)
        v_rows.append(d)
    print(f"vouchers: {len(v_rows)}")
    old_to_new_voucher = {}
    if apply and v_rows:
        for i in range(0, len(v_rows), BATCH):
            chunk = v_rows[i:i + BATCH]
            for attempt in range(3):
                try:
                    client.table("vouchers").insert(chunk).execute()
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        raise
        # Map old_id → new_id via voucher_no
        all_v = client.table("vouchers").select("id,voucher_no").execute()
        no_to_new = {r["voucher_no"]: r["id"] for r in all_v.data}
        for old in v_raw:
            if old["voucher_no"] in no_to_new:
                old_to_new_voucher[old["id"]] = no_to_new[old["voucher_no"]]
    counts["vouchers"] = len(v_rows)

    # ── 5. Flatholder Payments (remap FKs) ──
    fp_raw = cur.execute("SELECT * FROM flatholder_payments ORDER BY id").fetchall()
    print(f"flatholder_payments: {len(fp_raw)}")
    if apply and fp_raw:
        fh_by_serial = {r["serial_no"]: r["id"]
                        for r in client.table("flatholders").select("id,serial_no").execute().data}
        v_by_no = {r["voucher_no"]: r["id"]
                   for r in client.table("vouchers").select("id,voucher_no").execute().data}

        payloads = []
        for r in fp_raw:
            rec = {
                "payment_date": r["payment_date"],
                "amount": float(r["amount"]),
                "payment_type": r["payment_type"],
                "notes": r["notes"] or "",
            }
            # Map flatholder_id
            old_fh_id = r["flatholder_id"]
            if old_fh_id in old_to_new_fh:
                rec["flatholder_id"] = old_to_new_fh[old_fh_id]
            else:
                old_fh = cur.execute("SELECT serial_no FROM flatholders WHERE id=?", (old_fh_id,)).fetchone()
                if old_fh and old_fh["serial_no"] in fh_by_serial:
                    rec["flatholder_id"] = fh_by_serial[old_fh["serial_no"]]

            # Map voucher_id
            old_vid = r.get("voucher_id")
            if old_vid:
                old_v = cur.execute("SELECT voucher_no FROM vouchers WHERE id=?", (old_vid,)).fetchone()
                if old_v and old_v["voucher_no"] in v_by_no:
                    rec["voucher_id"] = v_by_no[old_v["voucher_no"]]
            payloads.append(rec)

        insert_batch("flatholder_payments", payloads, client)
    counts["flatholder_payments"] = len(fp_raw)

    # ── 6. Investments (remap voucher_id) ──
    inv_raw = cur.execute("SELECT * FROM investments ORDER BY id").fetchall()
    print(f"investments: {len(inv_raw)}")
    if apply and inv_raw:
        v_by_no = {r["voucher_no"]: r["id"]
                   for r in client.table("vouchers").select("id,voucher_no").execute().data}
        payloads = []
        for r in inv_raw:
            rec = {
                "name": r["name"],
                "type": r["type"],
                "amount": r["amount"],
                "date": r["date"],
                "status": r["status"] or "ACTIVE",
            }
            old_vid = r.get("voucher_id")
            if old_vid:
                old_v = cur.execute("SELECT voucher_no FROM vouchers WHERE id=?", (old_vid,)).fetchone()
                if old_v and old_v["voucher_no"] in v_by_no:
                    rec["voucher_id"] = v_by_no[old_v["voucher_no"]]
            payloads.append(rec)
        insert_batch("investments", payloads, client)
    counts["investments"] = len(inv_raw)

    # ── 7. Period Summaries ──
    ps_raw = cur.execute("SELECT * FROM period_summaries").fetchall()
    ps_rows = []
    for r in ps_raw:
        d = dict(r)
        d.pop("id", None)
        d.pop("created_at", None)
        ps_rows.append(d)
    print(f"period_summaries: {len(ps_rows)}")
    if apply and ps_rows:
        insert_batch("period_summaries", ps_rows, client)
    counts["period_summaries"] = len(ps_rows)

    # ── 8. Source Rows ──
    sr_raw = cur.execute("SELECT * FROM source_rows ORDER BY id").fetchall()
    sr_rows = []
    for r in sr_raw:
        d = dict(r)
        d.pop("id", None)
        d.pop("created_at", None)
        sr_rows.append(d)
    print(f"source_rows: {len(sr_rows)}")
    if apply and sr_rows:
        insert_batch("source_rows", sr_rows, client, on_conflict="sheet_name,row_no,record_type")
    counts["source_rows"] = len(sr_rows)

    # ── 9. Backfill payor_profiles ──
    names = set()
    for r in cur.execute(
        "SELECT DISTINCT TRIM(payee_payor) as n FROM vouchers WHERE TRIM(COALESCE(payee_payor,'')) <> ''"
    ).fetchall():
        names.add(r["n"])
    for r in cur.execute("SELECT DISTINCT name as n FROM flatholders").fetchall():
        names.add(r["n"])
    for r in cur.execute("SELECT DISTINCT name as n FROM investments").fetchall():
        names.add(r["n"])

    existing = {r["name"] for r in client.table("payor_profiles").select("name").execute().data}
    new_names = sorted(names - existing)
    print(f"payor backfill: {len(new_names)} new names")
    if apply and new_names:
        insert_batch("payor_profiles", [{"name": n} for n in new_names], client, on_conflict="name")
    counts["payor_backfill"] = len(new_names)

    src.close()
    return counts

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.apply and not args.dry_run:
        print("Use --apply or --dry-run"); sys.exit(1)

    surl = os.environ.get("SUPABASE_URL")
    skey = os.environ.get("SUPABASE_KEY")
    if not surl or not skey:
        print("Set SUPABASE_URL and SUPABASE_KEY"); sys.exit(1)

    client = create_client(surl, skey)
    print("=" * 60)
    print(f"SQLite → Supabase Migration ({'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 60)

    counts = migrate(client, apply=args.apply)
    print("\nSummary:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    if not args.apply:
        print("\n(DRY-RUN — nothing written)")
    print("=" * 60)

if __name__ == "__main__":
    main()
