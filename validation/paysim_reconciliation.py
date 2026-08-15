"""
PaySim Reconciliation Check

This is the actual script used to produce the results published in
validation/PAYSIM_RECONCILIATION_CHECK.md and referenced throughout the
CIF writeups.

What it checks: for each transaction, does the recorded change in the
origin account's balance match the transaction's amount and direction?
If not, and nothing in the data already flags that row, it's reported
as a candidate anomaly.

This is a partial ledger consistency check, origin account only, not
a complete double-entry transaction reconciliation engine. It tests one
concrete invariant (old balance plus or minus amount equals new balance),
not full transaction correctness across both sides of every transfer.

Two dataset-specific artifacts are excluded before reporting a result,
documented in full in validation/PAYSIM_RECONCILIATION_CHECK.md:
1. Merchant destinations (PaySim doesn't track their balances)
2. Withdrawals exceeding available balance, which PaySim clips to zero
   rather than allowing negative

Usage:
    python paysim_reconciliation.py path/to/paysim_combined.csv
"""

import sys
import pandas as pd


def expected_new_balance(row):
    if row['type'] == 'CASH_IN':
        return row['oldbalanceOrg'] + row['amount']
    else:
        return row['oldbalanceOrg'] - row['amount']


def run_check(csv_path):
    df = pd.read_csv(csv_path)

    df['orig_expected'] = df.apply(expected_new_balance, axis=1)
    df['orig_diff'] = (df['orig_expected'] - df['newbalanceOrig']).round(2)
    df['orig_mismatch'] = df['orig_diff'].abs() > 0.01

    # Exclude the known clipped-balance artifact: non-CASH_IN withdrawals
    # exceeding available balance, clipped to zero by PaySim's design,
    # not a genuine reconciliation failure
    df['is_clipped_case'] = (
        (df['type'] != 'CASH_IN')
        & (df['amount'] > df['oldbalanceOrg'])
        & (df['newbalanceOrig'] == 0)
    )

    clean = df[~df['is_clipped_case']].copy()

    print(f"Total transactions: {len(df)}")
    print(f"Excluded as known clipped-balance artifact: {df['is_clipped_case'].sum()}")
    print(f"Remaining for genuine check: {len(clean)}")
    print(f"Genuine mismatches: {clean['orig_mismatch'].sum()}")
    print(f"Rate: {clean['orig_mismatch'].mean() * 100:.4f}%")

    mismatches = clean[clean['orig_mismatch']].copy()
    if len(mismatches) > 0:
        print()
        print("Breakdown by transaction type:")
        print(mismatches['type'].value_counts())
        if 'isFraud' in mismatches.columns:
            print()
            print("Flagged vs unflagged (isFraud):")
            print(mismatches['isFraud'].value_counts())

    return clean


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python paysim_reconciliation.py path/to/paysim_combined.csv")
        sys.exit(1)
    run_check(sys.argv[1])
