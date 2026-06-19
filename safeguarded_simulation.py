import random
import heapq

"""
Safeguarded Event Ordering Simulation
=======================================
Extends the baseline model with three production-grade safeguards:

1. Partition-aware routing  — events for the same transaction always
                              hit the same worker (consistent hashing).
2. Exponential backoff      — out-of-order commits are retried with
                              increasing wait times instead of failing.
3. Idempotency registry     — duplicate commit attempts are deduplicated,
                              preventing double-processing on retries.

Compare output with baseline_simulation.py to see the impact.
"""

NUM_TRANSACTIONS    = 5000
VALIDATION_DELAY_PROB = 0.08
MAX_DELAY           = 5.0
NUM_WORKERS         = 4
NUM_PARTITIONS      = 4
MAX_RETRIES         = 3
INITIAL_BACKOFF     = 0.2

# --- System State ---
idempotency_registry = {}
validated_db         = set()
total_commits        = 0
causality_violations = 0
dropped_transactions = 0

# --- Generate Events ---
events = []

for tx_id in range(NUM_TRANSACTIONS):
    base_time = float(tx_id)

    validation_time = base_time
    if random.random() < VALIDATION_DELAY_PROB:
        validation_time += random.uniform(1, MAX_DELAY)

    commit_time = base_time + 0.5

    # Format: (timestamp, event_type, tx_id, retry_count)
    events.append((validation_time, "VALIDATE", tx_id, 0))
    events.append((commit_time,     "COMMIT",   tx_id, 0))

heapq.heapify(events)

# --- Worker Routines ---

def handle_validate(tx_id):
    validated_db.add(tx_id)


def handle_commit(tx_id, current_time, retry_count):
    global causality_violations, dropped_transactions, total_commits

    # 1. Idempotency check — ignore duplicate commits
    if tx_id in idempotency_registry:
        return None

    # 2. Causality check — commit only if validation is complete
    if tx_id in validated_db:
        idempotency_registry[tx_id] = "COMMITTED"
        total_commits += 1
        return None

    # 3. Exponential backoff — retry if validation not yet seen
    if retry_count < MAX_RETRIES:
        backoff = INITIAL_BACKOFF * (2 ** retry_count)
        return (current_time + backoff, "COMMIT", tx_id, retry_count + 1)

    # 4. Drop after exhausting retries — record as violation
    causality_violations += 1
    dropped_transactions += 1
    total_commits += 1
    return None


# --- Main Simulation Loop ---
worker_clocks = [0.0] * NUM_WORKERS

while events:
    time, event_type, tx_id, retry_count = heapq.heappop(events)

    # Consistent hashing — same tx always goes to same worker
    assigned_worker = (tx_id % NUM_PARTITIONS) % NUM_WORKERS
    worker_clocks[assigned_worker] = max(worker_clocks[assigned_worker], time)
    current_time = worker_clocks[assigned_worker]

    if event_type == "VALIDATE":
        handle_validate(tx_id)

    elif event_type == "COMMIT":
        retry_event = handle_commit(tx_id, current_time, retry_count)
        if retry_event:
            heapq.heappush(events, retry_event)

# --- Output ---
print("=== SAFEGUARDED SIMULATION (With Controls) ===")
print(f"Total Transactions : {NUM_TRANSACTIONS}")
print(f"Causality Violations: {causality_violations}")
print(f"Violation Rate     : {round((causality_violations / NUM_TRANSACTIONS) * 100, 4)}%")
print(f"Dropped (exhausted): {dropped_transactions}")
