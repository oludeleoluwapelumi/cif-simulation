#!/usr/bin/env python3
"""
CIF Scanner: a local, offline tool for checking transaction logs against
one specific CIF-shaped pattern, a recorded transaction whose amount and
direction do not reconcile with the account's recorded balance change,
without an existing error or fraud flag.

This runs entirely on your machine. No data leaves your computer, and
this tool does not send anything anywhere. It also does not modify the
input file.

Supports CSV, JSON array (a file containing a single JSON list of records),
and JSON Lines (one JSON object per line, common in real production log
exports). CSV and JSON Lines are streamed row by row; a plain JSON array
must be fully parsed by the json module first, that's an inherent property
of the format, not a design choice here.

What this checks:
    For each row, does old_balance + / - amount (direction depends on
    transaction type) equal new_balance? If not, and nothing in the data
    flags that row as an error, it is reported as a candidate anomaly.

What this does NOT do:
    - It does not prove a bug exists. A candidate anomaly is a starting
      point for investigation, not a conclusion.
    - It does not check validation-before-commit ordering directly, that
      requires separate validation and commit timestamps, which most
      transaction logs do not record. This is a narrower, related check:
      whether the recorded end state is internally consistent.
    - It will produce false positives on data with quirks it doesn't know
      about (see the PaySim writeup at the CIF repo for two real examples
      of this happening and how they were identified).

Usage:
    python cif_scanner.py --file transactions.csv \
        --amount-col amount \
        --old-balance-col old_balance \
        --new-balance-col new_balance \
        --type-col type \
        --credit-types CASH_IN,DEPOSIT \
        --flag-cols isFraud,isFlagged

    python cif_scanner.py --file transactions.jsonl \
        --amount-col amount \
        --old-balance-col old_balance \
        --new-balance-col new_balance

Only --file, --amount-col, --old-balance-col, and --new-balance-col are
required. Everything else has a sensible default or can be omitted.
"""

import argparse
import sys
import csv
import json


def parse_args():
    p = argparse.ArgumentParser(
        description="Scan a transaction log for candidate balance anomalies, "
                    "a pattern consistent with CIF (Chronological Input Failure)."
    )
    p.add_argument("--file", required=True, help="Path to the file to scan (CSV, JSON, or JSON Lines)")
    p.add_argument("--format", default=None, choices=["csv", "json", "jsonl"],
                   help="File format. If omitted, auto-detected from the file extension "
                        "(.csv, .json, .jsonl/.ndjson)")
    p.add_argument("--amount-col", required=True, help="Field name for transaction amount")
    p.add_argument("--old-balance-col", required=True, help="Field name for balance before the transaction")
    p.add_argument("--new-balance-col", required=True, help="Field name for balance after the transaction")
    p.add_argument("--type-col", default=None,
                   help="Field name for transaction type. Strongly recommended: without it, "
                        "every transaction is assumed to subtract from the balance, which will "
                        "misclassify any deposit-type transaction as an anomaly.")
    p.add_argument("--credit-types", default="",
                   help="Comma-separated transaction type values where the amount is ADDED "
                        "to the balance rather than subtracted (e.g. deposits, cash-in). "
                        "Matching is case-insensitive.")
    p.add_argument("--flag-cols", default="",
                   help="Comma-separated field names that indicate a known error/fraud flag. "
                        "Rows where any of these are truthy are excluded from the candidate "
                        "anomaly count but still reported separately as known_flagged.")
    p.add_argument("--tolerance", type=float, default=0.01,
                   help="Numeric tolerance for considering balances equal (default 0.01)")
    p.add_argument("--output", default=None,
                   help="Optional path to write candidate anomaly rows to as a CSV. If omitted, "
                        "they are only summarized, not written out.")
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


def detect_format(file_path, explicit_format):
    if explicit_format:
        return explicit_format
    lower = file_path.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".jsonl") or lower.endswith(".ndjson"):
        return "jsonl"
    if lower.endswith(".json"):
        return "json"
    return "csv"


def read_records(file_path, file_format):
    """
    A generator yielding dict-like records regardless of source format, so
    the rest of the scanner treats CSV, JSON array, and JSON Lines input
    identically. CSV and JSONL are streamed line by line. A plain JSON
    array is fully parsed into memory first, that's a property of the
    JSON array format itself (it's one top-level structure), not
    something avoidable while still accepting standard JSON.
    """
    if file_format == "csv":
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    elif file_format == "jsonl":
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"WARNING: skipping malformed JSON on line {line_num}: {e}")
                    continue

    elif file_format == "json":
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in ("transactions", "records", "data", "rows", "logs"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                print("ERROR: JSON file is an object, but no list found under a key "
                      "like 'transactions', 'records', 'data', 'rows', or 'logs'.")
                print("Wrap your records in a plain JSON array instead, or use one of those key names.")
                sys.exit(1)
        if not isinstance(data, list):
            print("ERROR: expected a JSON array of transaction records.")
            sys.exit(1)
        for record in data:
            yield record

    else:
        print(f"ERROR: unrecognized format '{file_format}'")
        sys.exit(1)


def scan(args):
    credit_types = {t.strip().upper() for t in args.credit_types.split(",") if t.strip()}
    flag_cols = [c.strip() for c in args.flag_cols.split(",") if c.strip()]
    file_format = detect_format(args.file, args.format)

    if not args.type_col:
        print("WARNING: no --type-col supplied. Every transaction will be assumed to")
        print("subtract from the balance. If your data includes deposits, credits, or")
        print("cash-in transactions, this will misclassify them as anomalies.")
        print()

    total = 0
    skipped_bad_data = 0
    candidate_anomalies = []
    known_flagged = []
    required = [args.amount_col, args.old_balance_col, args.new_balance_col]
    checked_columns = False

    for row in read_records(args.file, file_format):
        total += 1

        if not checked_columns:
            missing = [c for c in required if c not in row]
            if missing:
                print(f"ERROR: field(s) not found in first record: {missing}")
                print(f"Fields available: {sorted(row.keys())}")
                sys.exit(1)
            checked_columns = True

        amount = to_float(row.get(args.amount_col))
        old_bal = to_float(row.get(args.old_balance_col))
        new_bal = to_float(row.get(args.new_balance_col))

        if amount is None or old_bal is None or new_bal is None:
            skipped_bad_data += 1
            continue

        row_type_raw = row.get(args.type_col) if args.type_col else None
        row_type_normalized = str(row_type_raw).strip().upper() if row_type_raw is not None else None
        is_credit = row_type_normalized in credit_types if args.type_col else False

        expected = old_bal + amount if is_credit else old_bal - amount
        diff = round(expected - new_bal, 6)

        if abs(diff) > args.tolerance:
            is_flagged = any(is_truthy_flag(row.get(c)) for c in flag_cols)
            record = dict(row)
            record["_expected_balance"] = expected
            record["_actual_balance"] = new_bal
            record["_difference"] = diff
            record["_direction_used"] = "credit" if is_credit else "debit"
            record["_transaction_type"] = row_type_raw
            record["_flag_status"] = "known_flagged" if is_flagged else "candidate_anomaly"

            if is_flagged:
                known_flagged.append(record)
            else:
                candidate_anomalies.append(record)

    return {
        "format_used": file_format,
        "total": total,
        "skipped_bad_data": skipped_bad_data,
        "checkable": total - skipped_bad_data,
        "candidate_anomalies": candidate_anomalies,
        "known_flagged": known_flagged,
    }


def print_report(results, args):
    checkable = results["checkable"]
    candidates = len(results["candidate_anomalies"])
    known = len(results["known_flagged"])

    print("=" * 60)
    print("CIF SCANNER REPORT")
    print("=" * 60)
    print(f"Input format detected:        {results['format_used']}")
    print(f"Total rows read:              {results['total']}")
    print(f"Skipped (missing/bad data):   {results['skipped_bad_data']}")
    print(f"Checkable rows:               {checkable}")
    print()
    print(f"Candidate anomalies:          {candidates}", end="")
    if checkable > 0:
        print(f"  ({candidates / checkable * 100:.4f}% of checkable rows)")
    else:
        print()
    print(f"Known flagged mismatches:     {known}  (already caught by existing error/fraud flags)")
    print()

    if candidates == 0:
        print("No candidate anomalies found. This does not confirm your system is free of")
        print("CIF-shaped issues, only that this specific check, on this sample, found none.")
    else:
        print(f"Found {candidates} candidate anomaly row(s), where the recorded transaction")
        print("does not reconcile with the balance change, and nothing in the data flags it")
        print("as an error. This is a starting point for investigation, not a confirmed bug.")
        print()
        print("IMPORTANT: before concluding anything, check whether your data has its own")
        print("quirks that could explain this innocently, similar to what was found scanning")
        print("PaySim: untracked balances for certain account types, or balances clipped to")
        print("zero instead of going negative. Read the flagged rows before drawing conclusions.")

    if args.output and candidates > 0:
        fieldnames = list(results["candidate_anomalies"][0].keys())
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results["candidate_anomalies"])
        print()
        print(f"Candidate anomaly rows written to: {args.output}")

    print("=" * 60)


def main():
    args = parse_args()
    results = scan(args)
    print_report(results, args)


if __name__ == "__main__":
    main()
SCANNER_EOF
echo "scanner written"
