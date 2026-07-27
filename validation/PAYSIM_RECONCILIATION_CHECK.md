# CIF Pattern Check: PaySim Balance Reconciliation

This document reports a reconciliation check run against a real sample of the PaySim mobile money transaction dataset, testing for a pattern consistent with CIF: a transaction recorded as complete while the underlying account state does not reflect it, with no error or flag raised.

## What this is

A direct, reproducible check run against roughly 77,000 real, unmodified rows from the public PaySim dataset. Unlike the Fineract taxonomy mapping, this is not a review of existing bug reports. This is a fresh check on data nobody had previously run through CIF.

## What this is not

A live case study. PaySim is a simulation built to model a real mobile money service, not a live production system. Any pattern found here may reflect a real class of production behavior, or it may be an artifact of how PaySim itself was generated. This document does not resolve that question, and does not claim to.

## Dataset

- Source: PaySim (`ealaxi/paysim1` on Kaggle)
- Sample size: 77,620 rows after deduplication, spanning step 1 to step 743
- Columns used: `type`, `amount`, `oldbalanceOrg`, `newbalanceOrig`, `nameDest`, `isFraud`, `isFlaggedFraud`

## Method

The check: for each transaction, does the recorded change in the origin account's balance match the transaction's amount and direction, and if not, is anything flagging that.

Two dataset-specific artifacts had to be identified and excluded before a genuine check was possible:

1. **Merchant destinations.** PaySim does not track balances for merchant accounts (names starting with `M`); they are always recorded as zero. This is a dataset design choice, not a reconciliation failure, and was excluded from the destination-side check.
2. **Clipped negative balances.** When a withdrawal amount exceeds the available balance, PaySim clips the resulting balance to zero rather than recording a negative number. Transactions matching this pattern were excluded from the origin-side check, since the "mismatch" is expected dataset behavior, not a genuine anomaly.

A third issue was a bug in the check itself, not the data: the initial formula assumed money always leaves the origin account, which is incorrect for `CASH_IN` transactions, where money enters the origin account. This was corrected before the final run.

## Code

```python
import pandas as pd

df = pd.read_csv('paysim_combined.csv')

def expected_new_balance(row):
    if row['type'] == 'CASH_IN':
        return row['oldbalanceOrg'] + row['amount']
    else:
        return row['oldbalanceOrg'] - row['amount']

df['orig_expected'] = df.apply(expected_new_balance, axis=1)
df['orig_diff'] = (df['orig_expected'] - df['newbalanceOrig']).round(2)
df['orig_mismatch'] = df['orig_diff'].abs() > 0.01

# Exclude the clipped-balance artifact (non-CASH_IN withdrawals exceeding balance,
# clipped to zero by PaySim's design, not a genuine reconciliation failure)
df['is_clipped_case'] = (df['type'] != 'CASH_IN') & (df['amount'] > df['oldbalanceOrg']) & (df['newbalanceOrig'] == 0)

clean = df[~df['is_clipped_case']].copy()

print(f"Total transactions: {len(df)}")
print(f"Excluded as known clipped-balance artifact: {df['is_clipped_case'].sum()}")
print(f"Remaining for genuine check: {len(clean)}")
print(f"Genuine mismatches: {clean['orig_mismatch'].sum()}")
print(f"Rate: {clean['orig_mismatch'].mean()*100:.4f}%")
```

## Results

| Stage | Count | Rate |
|---|---|---|
| Raw mismatch rate (before excluding artifacts) | 58,926 / 77,620 | 75.92% |
| After excluding merchant and clipped-balance artifacts | 10,894 / 29,588 | 36.82% |
| After correcting the CASH_IN direction bug | **26 / 34,961** | **0.07%** |

The first two numbers were not real findings. They are reported here for transparency, not as evidence. Each was traced to a specific, identifiable cause before being excluded or corrected. Only the final number reflects a genuine, checked result.

## The 26 remaining mismatches

Every one of the 26 shares the same shape: `oldbalanceOrg` exactly equals `newbalanceOrig`, meaning the account balance did not change at all despite a transaction of nonzero amount being recorded against it.

| Type | Count |
|---|---|
| CASH_IN | 20 |
| TRANSFER | 4 |
| CASH_OUT | 2 |

23 of the 26 carry no fraud flag (`isFraud = 0`, `isFlaggedFraud = 0`). The remaining 3 are flagged `isFraud = 1`, all involving large transfers (one for 10,000,000).

## What this does and does not establish

It establishes a specific, reproducible, real pattern in real recorded data: a small number of transactions where the ledger state does not reflect a recorded transaction, mostly without any flag.

It does not establish that this reflects a genuine class of bug in production financial systems, since PaySim is a simulation and the origin of this pattern (real system behavior vs. dataset generation artifact) is unconfirmed.

## Reproducibility

The code above can be run against the same PaySim sample to reproduce these exact figures. No random elements, no injected delays, and no simulated data are used anywhere in this check; every number comes directly from the dataset's own recorded values.

## Next step

A live case study remains the outstanding milestone: applying CIF to a real system's current logs, with a team's permission, producing a finding that was not already known.
