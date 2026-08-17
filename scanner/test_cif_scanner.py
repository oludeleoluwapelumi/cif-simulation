"""
Test suite for cif_scanner.py, covering known-good cases, known mismatches,
flagged mismatches, credits, debits, tolerance boundaries, malformed input,
and the two real dataset quirks discovered scanning PaySim. Run with:

    python test_cif_scanner.py
"""

import csv
import json
import os
import subprocess
import sys
import tempfile

SCANNER = os.path.join(os.path.dirname(__file__), "cif_scanner.py")


def run_scanner(rows, file_format="csv", extra_args=None):
    extra_args = extra_args or []
    suffix = {"csv": ".csv", "jsonl": ".jsonl", "json": ".json"}[file_format]
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, newline="") as f:
        path = f.name
        if file_format == "csv":
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        elif file_format == "jsonl":
            for row in rows:
                f.write(json.dumps(row) + "\n")
        elif file_format == "json":
            json.dump(rows, f)
    result = subprocess.run([sys.executable, SCANNER, "--file", path] + extra_args,
                             capture_output=True, text=True)
    os.unlink(path)
    return result.stdout


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return condition


BASE_ARGS = ["--amount-col", "amount", "--old-balance-col", "old_balance", "--new-balance-col", "new_balance"]


def test_known_good_debit():
    rows = [{"amount": 50, "old_balance": 500, "new_balance": 450, "type": "WITHDRAWAL"}]
    out = run_scanner(rows, extra_args=BASE_ARGS)
    return check("known-good debit produces zero candidate anomalies",
                 "Candidate anomalies:          0" in out)


def test_known_good_credit():
    rows = [{"amount": 50, "old_balance": 500, "new_balance": 550, "type": "DEPOSIT"}]
    out = run_scanner(rows, extra_args=BASE_ARGS + ["--type-col", "type", "--credit-types", "DEPOSIT"])
    return check("known-good credit produces zero candidate anomalies",
                 "Candidate anomalies:          0" in out)


def test_case_insensitive_credit_type():
    rows = [{"amount": 50, "old_balance": 500, "new_balance": 550, "type": "deposit"}]
    out = run_scanner(rows, extra_args=BASE_ARGS + ["--type-col", "type", "--credit-types", "DEPOSIT"])
    return check("lowercase 'deposit' still matches credit-types DEPOSIT (case-insensitive)",
                 "Candidate anomalies:          0" in out)


def test_genuine_anomaly_unflagged():
    rows = [{"amount": 500, "old_balance": 1000, "new_balance": 1000, "type": "WITHDRAWAL", "is_flagged": 0}]
    out = run_scanner(rows, extra_args=BASE_ARGS + ["--type-col", "type", "--flag-cols", "is_flagged"])
    return check("unchanged balance despite recorded withdrawal is caught as candidate anomaly",
                 "Candidate anomalies:          1" in out)


def test_anomaly_already_flagged():
    rows = [{"amount": 500, "old_balance": 1000, "new_balance": 1000, "type": "WITHDRAWAL", "is_flagged": 1}]
    out = run_scanner(rows, extra_args=BASE_ARGS + ["--type-col", "type", "--flag-cols", "is_flagged"])
    return check("pre-flagged anomaly counted as known_flagged, not candidate anomaly",
                 "Candidate anomalies:          0" in out and "Known flagged mismatches:     1" in out)


def test_tolerance_boundary():
    rows = [{"amount": 50, "old_balance": 500, "new_balance": 450.005, "type": "WITHDRAWAL"}]
    out = run_scanner(rows, extra_args=BASE_ARGS)
    return check("difference within tolerance is not flagged", "Candidate anomalies:          0" in out)


def test_no_type_col_warns():
    rows = [{"amount": 50, "old_balance": 500, "new_balance": 450}]
    out = run_scanner(rows, extra_args=BASE_ARGS)
    return check("omitting --type-col produces an explicit warning",
                 "WARNING: no --type-col supplied" in out)


def test_jsonl_format():
    rows = [{"amount": 500, "old_balance": 1000, "new_balance": 1000, "type": "WITHDRAWAL"}]
    out = run_scanner(rows, file_format="jsonl", extra_args=BASE_ARGS + ["--type-col", "type"])
    return check("JSONL format detected and scanned correctly",
                 "Input format detected:        jsonl" in out and "Candidate anomalies:          1" in out)


def test_json_array_format():
    rows = [{"amount": 500, "old_balance": 1000, "new_balance": 1000, "type": "WITHDRAWAL"}]
    out = run_scanner(rows, file_format="json", extra_args=BASE_ARGS + ["--type-col", "type"])
    return check("plain JSON array format detected and scanned correctly",
                 "Input format detected:        json" in out and "Candidate anomalies:          1" in out)


def test_malformed_jsonl_line_skipped():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
        f.write(json.dumps({"amount": 50, "old_balance": 500, "new_balance": 450, "type": "WITHDRAWAL"}) + "\n")
        f.write("this is not valid json\n")
        f.write(json.dumps({"amount": 500, "old_balance": 1000, "new_balance": 1000, "type": "WITHDRAWAL"}) + "\n")
    result = subprocess.run([sys.executable, SCANNER, "--file", path] + BASE_ARGS + ["--type-col", "type"],
                             capture_output=True, text=True)
    os.unlink(path)
    out = result.stdout
    return check("malformed JSONL line skipped with warning, valid lines still processed",
                 "WARNING: skipping malformed JSON" in out and "Total rows read:              2" in out)


def test_paysim_quirk_clipped_balance():
    rows = [{"amount": 800, "old_balance": 500, "new_balance": 0, "type": "CASH_OUT"}]
    out = run_scanner(rows, extra_args=BASE_ARGS + ["--type-col", "type"])
    return check("withdrawal exceeding balance (clipped to zero) correctly identified as a mismatch, "
                 "matching the real PaySim artifact", "Candidate anomalies:          1" in out)


def test_direction_metadata_in_output():
    rows = [{"amount": 500, "old_balance": 1000, "new_balance": 1000, "type": "DEPOSIT"}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        path = f.name
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    output_path = path + ".out.csv"
    subprocess.run([sys.executable, SCANNER, "--file", path] + BASE_ARGS +
                    ["--type-col", "type", "--credit-types", "DEPOSIT", "--output", output_path],
                    capture_output=True, text=True)
    passed = False
    if os.path.exists(output_path):
        with open(output_path) as f:
            content = f.read()
            passed = "_direction_used" in content and "credit" in content
        os.unlink(output_path)
    os.unlink(path)
    return check("output CSV includes _direction_used metadata for manual investigation", passed)


def main():
    tests = [
        test_known_good_debit, test_known_good_credit, test_case_insensitive_credit_type,
        test_genuine_anomaly_unflagged, test_anomaly_already_flagged, test_tolerance_boundary,
        test_no_type_col_warns, test_jsonl_format, test_json_array_format,
        test_malformed_jsonl_line_skipped, test_paysim_quirk_clipped_balance,
        test_direction_metadata_in_output,
    ]
    results = [t() for t in tests]
    passed, total = sum(results), len(results)
    print(f"\n{passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
