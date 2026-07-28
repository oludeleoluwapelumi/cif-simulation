#!/usr/bin/env python3
"""
CIF Scanner: a local, offline tool for checking transaction logs against
one specific CIF-shaped pattern, ledger state that does not reconcile with
its own recorded transaction, without any error or flag raised.

This runs entirely on your machine. No data leaves your computer, and this
tool does not send anything anywhere.

What this checks:
    For each row, does old_balance + / - amount (direction depends on
    transaction type) equal new_balance? If not, and nothing in the data
    flags that row as an error, it is reported as a candidate anomaly.

What this does NOT do:
    - It does not prove a bug exists. A flagged row is a starting point
      for investigation, not a conclusion.
    - It does not check validation-before-commit ordering directly, that
      requires separate validation and commit timestamps, which most
      transaction logs do not record. This is a narrower, related check:
      whether the recorded end state is internally consistent.
    - It will produce false positives on data with quirks it doesn't know
      about (see the PaySim writeup at the CIF repo for two real examples
      of this happening and how they were identified).

Usage:
    python cif_scanner.py --file transactions.csv \\
        --amount-col amount \\
        --old-balance-col old_balance \\
        --new-balance-col new_balance \\
        --type-col type \\
        --credit-types CASH_IN,DEPOSIT \\
        --flag-cols isFraud,isFlagged

Only --file, --amount-col, --old-balance-col, and --new-balance-col are
required. Everything else has a sensible default or can be omitted.
"""

import argparse
import sys
import csv


def parse_args():
    p = argparse.ArgumentParser(
        description="Scan a transaction log for unflagged balance mismatches, "
                    "a pattern consistent with CIF (Chronological Input Failure)."
    )
    p.add_argument("--file", required=True, help="Path to the CSV file to scan")
    p.add_argument("--amount-col", required=True, help="Column name for transaction amount")
    p.add_argument("--old-balance-col", required=True, help="Column name for balance before the transaction")
    p.add_argument("--new-balance-col", required=True, help="Column name for balance after the transaction")
    p.add_argument("--type-col", default=None,
                   help="Column name for transaction type (optional, but improves accuracy)")
    p.add_argument("--credit-types", default="",
                   help="Comma-separated transaction type values where the amount is ADDED "
                        "to the balance rather than subtracted (e.g. deposits, cash-in). "
                        "If --type-col is not given, all transactions are assumed to subtract.")
    p.add_argument("--flag-cols", default="",
                   help="Comma-separated column names that indicate a known error/fraud flag. "
                        "Rows where any of these are truthy are excluded from the 'unflagged' count "
                        "but still reported separately.")
    p.add_argument("--tolerance", type=float, default=0.01,
                   help="Numeric tolerance for considering balances equal (default 0.01)")
    p.add_argument("--output", default=None,
                   help="Optional path to write flagged rows to as a CSV. If omitted, "
                        "flagged rows are only summarized, not written out.")
    return p.parse_args()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_truthy_flag(value):
    if value is None:
        return False
    v = str(value).strip().lower()
    return v not in ("", "0", "0.0", "false", "no", "none")


def scan(args):
    credit_types = set(t.strip() for t in args.credit_types.split(",") if t.strip())
    flag_cols = [c.strip() for c in args.flag_cols.split(",") if c.strip()]

    total = 0
    skipped_bad_data = 0
    mismatches = []
    flagged_mismatches = []

    with open(args.file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = [args.amount_col, args.old_balance_col, args.new_balance_col]
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            print(f"ERROR: column(s) not found in file: {missing}")
            print(f"Columns available: {reader.fieldnames}")
            sys.exit(1)

        for row in reader:
            total += 1
            amount = to_float(row.get(args.amount_col))
            old_bal = to_float(row.get(args.old_balance_col))
            new_bal = to_float(row.get(args.new_balance_col))

            if amount is None or old_bal is None or new_bal is None:
                skipped_bad_data += 1
                continue

            row_type = row.get(args.type_col) if args.type_col else None
            is_credit = row_type in credit_types if args.type_col else False

            expected = old_bal + amount if is_credit else old_bal - amount
            diff = round(expected - new_bal, 6)

            if abs(diff) > args.tolerance:
                is_flagged = any(is_truthy_flag(row.get(c)) for c in flag_cols)
                record = dict(row)
                record["_expected_balance"] = expected
                record["_actual_balance"] = new_bal
                record["_difference"] = diff

                if is_flagged:
                    flagged_mismatches.append(record)
                else:
                    mismatches.append(record)

    return {
        "total": total,
        "skipped_bad_data": skipped_bad_data,
        "checkable": total - skipped_bad_data,
        "unflagged_mismatches": mismatches,
        "flagged_mismatches": flagged_mismatches,
    }


def print_report(results, args):
    checkable = results["checkable"]
    unflagged = len(results["unflagged_mismatches"])
    flagged = len(results["flagged_mismatches"])

    print("=" * 60)
    print("CIF SCANNER REPORT")
    print("=" * 60)
    print(f"Total rows read:              {results['total']}")
    print(f"Skipped (missing/bad data):   {results['skipped_bad_data']}")
    print(f"Checkable rows:               {checkable}")
    print()
    print(f"Unflagged balance mismatches: {unflagged}", end="")
    if checkable > 0:
        print(f"  ({unflagged / checkable * 100:.4f}% of checkable rows)")
    else:
        print()
    print(f"Flagged balance mismatches:   {flagged}  (already caught by existing error/fraud flags)")
    print()

    if unflagged == 0:
        print("No unflagged mismatches found. This does not confirm your system is free of")
        print("CIF-shaped issues, only that this specific check, on this sample, found none.")
    else:
        print(f"Found {unflagged} row(s) where the recorded transaction does not reconcile")
        print("with the balance change, and nothing in the data flags it as an error.")
        print("This is a starting point for investigation, not a confirmed bug.")
        print()
        print("IMPORTANT: before concluding anything, check whether your data has its own")
        print("quirks that could explain this innocently, similar to what was found scanning")
        print("PaySim: untracked balances for certain account types, or balances clipped to")
        print("zero instead of going negative. Read the flagged rows before drawing conclusions.")

    if args.output and unflagged > 0:
        fieldnames = list(results["unflagged_mismatches"][0].keys())
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results["unflagged_mismatches"])
        print()
        print(f"Flagged rows written to: {args.output}")

    print("=" * 60)


def main():
    args = parse_args()
    results = scan(args)
    print_report(results, args)


if __name__ == "__main__":
    main()
