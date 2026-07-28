# CIF Scanner

A small, local, offline command-line tool for checking a transaction log
against one specific pattern: a transaction recorded as complete while the
account's balance does not actually reflect it, with nothing flagging that
as an error.

This is part of the [CIF (Chronological Input Failure)](https://github.com/oludeleoluwapelumi/cif-simulation)
project. If you're new to CIF, start with the main repo, this tool is one
piece of it, not the whole framework.

## What this actually checks

For each transaction row, does `old_balance` plus or minus `amount` equal
`new_balance`? If not, and nothing in your data already flags that row as
an error or fraud case, it gets reported.

That's it. That's the whole check. It is a narrower, more limited test than
the original CIF mechanism (validation completing before commit), which
needs separate validation and commit timestamps that most transaction logs
don't record. This tool checks something related but smaller: whether the
recorded end state is internally consistent with the transaction that
supposedly produced it.

## What this does NOT do

- It does not prove a bug exists. A flagged row is a starting point for
  investigation, not a conclusion.
- It does not know your data's specific quirks. Every real dataset has
  some. When this tool was first tested against the public PaySim dataset,
  the very first run flagged 75.92% of transactions, not because there
  were that many real problems, but because of two dataset-specific
  artifacts (untracked merchant balances, and balances clipped to zero
  instead of going negative) that had to be identified and excluded by
  hand. The honest writeup of that process is here:
  https://dev.to/oludeleoluwapelumi/testing-cifs-pattern-against-real-payment-data-and-getting-it-wrong-twice-before-getting-it-right-2n3
- It does not send your data anywhere. Everything runs locally, on your
  machine, using Python's standard library only. Nothing is uploaded,
  logged externally, or transmitted.
- It does not replace judgment. Read the flagged rows. Ask why. Most of
  the time, a high mismatch rate on a first run means the check needs
  refining for your specific data, not that your system is broken.

## Requirements

Python 3.7 or later. No external dependencies, only the standard library.

## Usage

```bash
python cif_scanner.py \
  --file transactions.csv \
  --amount-col amount \
  --old-balance-col old_balance \
  --new-balance-col new_balance \
  --type-col type \
  --credit-types DEPOSIT,CASH_IN \
  --flag-cols isFraud,isFlagged

Try the scanner: run CIF's core check against your own transaction data, entirely on your own machine, no data leaves your computer. See [scanner/README.md](scanner/README.md).
