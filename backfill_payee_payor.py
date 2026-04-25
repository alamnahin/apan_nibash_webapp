#!/usr/bin/env python3
"""Backfill payee/payor for imported vouchers where possible.

This script updates only imported vouchers (voucher_no like %-IMP-%)
that currently have an empty payee_payor.
"""

from __future__ import annotations

import re

from database import get_connection


MONTH_WORDS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december",
}


def clean_text(value: str) -> str:
    return " ".join((value or "").strip().strip("-:,. ").split())


def looks_like_person_or_party(value: str) -> bool:
    text = clean_text(value)
    if len(text) < 3:
        return False

    lower = text.lower()
    if not re.search(r"[a-z]", lower):
        return False

    blocked_tokens = {
        "total", "subtotal", "grand total", "taka", "cumulative", "income",
        "expense", "expenses", "payment", "service charge", "bank profit",
        "fdr profit", "sale", "rent",
    }
    if any(token in lower for token in blocked_tokens):
        return False

    if any(month in lower for month in MONTH_WORDS):
        return False

    return True


def infer_payee_payor(description: str) -> str:
    text = clean_text(description)
    if not text:
        return ""

    m = re.match(r"^Investment\s+(?:received|repayment)\s*:\s*(.+)$", text, flags=re.IGNORECASE)
    if m:
        candidate = clean_text(m.group(1))
        return candidate if looks_like_person_or_party(candidate) else ""

    m = re.match(r"^Service\s+Charge\s+Account\s*-\s*(.+)$", text, flags=re.IGNORECASE)
    if m:
        candidate = clean_text(m.group(1))
        return candidate if looks_like_person_or_party(candidate) else ""

    m = re.search(r"\(([^()]*)\)\s*$", text)
    if m:
        candidate = clean_text(m.group(1))
        if looks_like_person_or_party(candidate):
            return candidate

    m = re.match(r"^Advance\s*:?[\s-]*(.+)$", text, flags=re.IGNORECASE)
    if m:
        candidate = clean_text(m.group(1).split("-")[0])
        if looks_like_person_or_party(candidate):
            return candidate

    return ""


def main() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, description
        FROM vouchers
        WHERE voucher_no LIKE '%-IMP-%'
          AND TRIM(COALESCE(payee_payor, '')) = ''
        """
    )
    rows = cur.fetchall()

    updated = 0
    for voucher_id, description in rows:
        payee = infer_payee_payor(description or "")
        if not payee:
            continue
        cur.execute("UPDATE vouchers SET payee_payor = ? WHERE id = ?", (payee, voucher_id))
        updated += 1

    conn.commit()

    cur.execute(
        "SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE '%-IMP-%' AND TRIM(COALESCE(payee_payor, '')) <> ''"
    )
    with_payee = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vouchers WHERE voucher_no LIKE '%-IMP-%'")
    total_imp = cur.fetchone()[0]

    conn.close()

    print(f"Updated imported vouchers with payee/payor: {updated}")
    print(f"Imported vouchers with payee/payor now: {with_payee}/{total_imp}")


if __name__ == "__main__":
    main()
