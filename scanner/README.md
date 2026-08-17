# CIF Scanner

A small, local, offline command-line tool for checking transaction logs for one specific pattern: a recorded transaction whose amount and direction do not reconcile with the account's recorded balance change, without an existing error or fraud flag.

This is part of the **CIF (Chronological Input Failure)** project. If you're new to CIF, start with the main repo. This tool is one piece of it, not the whole framework.

## What this actually checks

For each transaction row, does:

**old_balance ± amount = new_balance?**

If not, and nothing in your data already flags that row as an error or fraud case, it gets reported.

That's it. That's the whole check.

It is a narrower, more limited test than the original CIF mechanism (validation completing before commit), which needs separate validation and commit timestamps that most transaction logs don't record.

This tool checks something related but smaller: whether the recorded end state is internally consistent with the transaction that supposedly produced it.

## Supported formats

* **CSV (`.csv`)**
* **JSON array (`.json`)** — a file containing a single JSON list of records, or an object with the list under a key like `transactions`, `records`, `data`, `rows`, or `logs`
* **JSON Lines (`.jsonl` or `.ndjson`)** — one JSON object per line, common in real production log exports, streamed line by line rather than loaded fully into memory

Format is auto-detected from the file extension, or can be set explicitly with:

```bash
--format csv
--format json
--format jsonl
```

## What this does NOT do

### It does not prove a bug exists

A candidate anomaly is a starting point for investigation, not a conclusion.

### It does not know your data's specific quirks

Every real dataset has some.

When this tool was first tested against the public PaySim dataset, the very first run flagged **75.92% of transactions** — not because there were that many real problems, but because of two dataset-specific artifacts:

* untracked merchant balances
* balances clipped to zero instead of going negative

Those artifacts had to be identified and excluded by hand.

The honest writeup of that process is here:

https://dev.to/oludeleoluwapelumi/testing-cifs-pattern-against-real-payment-data-and-getting-it-wrong-twice-before-getting-it-right-2n3

### It does not send your data anywhere

Everything runs locally, on your machine, using Python's standard library only.

Nothing is uploaded, logged externally, or transmitted.

### It does not modify the input file

The scanner only reads the input data and optionally writes candidate anomalies to a separate CSV file.

### It does not replace judgment

Read the flagged rows. Ask why.

Most of the time, a high mismatch rate on a first run means the check needs refining for your specific data, not that your system is broken.

## Requirements

* Python 3.7 or later
* No external dependencies
* Python standard library only

## Usage

### CSV

```bash
python cif_scanner.py \
  --file transactions.csv \
  --amount-col amount \
  --old-balance-col old_balance \
  --new-balance-col new_balance \
  --type-col type \
  --credit-types DEPOSIT,CASH_IN \
  --flag-cols isFraud,isFlagged
```

### JSON Lines

```bash
python cif_scanner.py \
  --file transactions.jsonl \
  --amount-col amount \
  --old-balance-col old_balance \
  --new-balance-col new_balance
```

## Required arguments

`--file`
Path to your log file.

`--amount-col`
Field name for the transaction amount.

`--old-balance-col`
Field name for the balance before the transaction.

`--new-balance-col`
Field name for the balance after the transaction.

## Optional arguments

`--format`
`csv`, `json`, or `jsonl`. Auto-detected from the file extension if omitted.

`--type-col`
Field name for transaction type.

**Strongly recommended:** without it, every transaction is assumed to subtract from the balance, which will misclassify any deposit-type transaction as an anomaly.

`--credit-types`
Comma-separated list of type values where the amount should be added to the balance rather than subtracted.

Matching is case-insensitive.

`--flag-cols`
Comma-separated list of fields that already indicate a known error or fraud case.

Rows matching these are reported separately as **known flagged mismatches**, and are not counted in the candidate anomaly total.

`--tolerance`
Numeric tolerance for floating-point comparison.

Default: `0.01`

`--output`
Path to write candidate anomaly rows to a CSV file for review.

## Try it first on the included sample

A small, obviously fake sample file is included so you can see what the tool does before pointing it at anything real:

```bash
python cif_scanner.py \
  --file sample_transactions.csv \
  --amount-col amount \
  --old-balance-col old_balance \
  --new-balance-col new_balance \
  --type-col type \
  --credit-types DEPOSIT \
  --flag-cols is_flagged
```

## Running the test suite

A synthetic test suite covers:

* known-good transactions
* genuine anomalies
* pre-flagged mismatches
* credits
* debits
* tolerance boundaries
* malformed input
* the real PaySim clipped-balance artifact

Run it with:

```bash
python test_cif_scanner.py
```

## If it flags something on your real data

Read the flagged rows before concluding anything.

If you think you've found something genuinely interesting, or if the tool behaves in a way that seems wrong for your data structure, open an issue on the repo, or see the main README for how to reach me.

I'm specifically interested in hearing about both **real findings** and **cases where the tool got it wrong**.

The second one is just as useful as the first.

