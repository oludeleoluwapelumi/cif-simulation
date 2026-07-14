# Causality Violation Simulator
### Measuring ordering failures in async event-driven financial pipelines

---

## What This Is

A minimal, honest Python simulation of a real distributed systems problem:  
**commits processing before their corresponding validations complete.**

This happens in high-throughput payment pipelines when network jitter or retry delays cause the validation event to arrive late — after the ledger has already committed the transaction state.

This is not a new bug. It is a known failure mode in async architectures.  
What this repo provides is a **reproducible, measurable model** of how often it occurs and what safeguards reduce it.

---

## The Two Scripts

### `baseline_simulation.py`
Models the failure with no safeguards in place.

- Async validation and commit events scheduled independently
- 8% of validations experience simulated network delay
- Violations recorded when commit processes before validation completes

**Typical output:**
```
=== BASELINE SIMULATION (No Safeguards) ===
Total Transactions : 5000
Total Violations   : 416
Violation Rate     : 8.32%
```

---

### `safeguarded_simulation.py`
Same pipeline with three production-grade controls added:

| Safeguard | What It Does |
|---|---|
| Partition-aware routing | Same transaction always hits the same worker |
| Exponential backoff | Out-of-order commits retry instead of failing immediately |
| Idempotency registry | Duplicate commits are deduplicated on retry |

**Typical output:**
```
=== SAFEGUARDED SIMULATION (With Controls) ===
Total Transactions : 5000
Causality Violations: 0
Violation Rate     : 0.0%
Dropped (exhausted): 0
```

---

## Why This Matters

At 1 million daily transactions with an 8% network retry rate:

- **~83,000 causality violations per day** in an unprotected pipeline
- Each violation creates a ledger state that requires manual review or patching
- At scale, this becomes a measurable operational cost in engineering hours

---

## How to Run

No dependencies beyond the Python standard library.

```bash
# Run the baseline (shows the problem)
python baseline_simulation.py

# Run the safeguarded version (shows the fix)
python safeguarded_simulation.py
```

---

## Assumptions

This simulation is deliberately minimal. It does not model:

- Real Kafka brokers or consumer groups
- Actual database writes
- Network topology
- Production retry policies

It models **causal ordering behavior** only. Results reflect simulation parameters, not production benchmarks.

---

## Progression (If You Want to Extend This)

1. Add realistic Kafka partition behavior
2. Add consumer group rebalancing
3. Add duplicate detection across partitions
4. Compare idempotency strategies side by side

---

## Context

This simulation was built to support research into causality violation rates in async payment pipelines and their operational impact.

