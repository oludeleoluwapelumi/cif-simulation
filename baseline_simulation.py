import random
import heapq

"""
Baseline Event Ordering Simulation
====================================
Models causality violations in an async event-driven financial pipeline.

GOAL:
- Simulate transactions requiring validation before commit.
- Inject asynchronous delay into the validation path.
- Observe and measure cases where commit processes before validation completes.

ASSUMPTIONS:
1. Each transaction has exactly two events: VALIDATE and COMMIT.
2. The system is asynchronous — events are scheduled independently.
3. Network delay affects VALIDATION only.
4. A violation occurs when COMMIT is processed before VALIDATE completes.

This is NOT a full Kafka model. It is a minimal causality-breaking abstraction.
"""

NUM_TRANSACTIONS = 5000
VALIDATION_DELAY_PROB = 0.08   # 8% of validations experience network delay
MAX_DELAY = 5.0                # Maximum delay units injected

events = []
validated = set()
violations = 0

# --- Generate Events ---
for tx_id in range(NUM_TRANSACTIONS):
    base_time = tx_id

    validation_time = base_time
    if random.random() < VALIDATION_DELAY_PROB:
        validation_time += random.uniform(1, MAX_DELAY)

    commit_time = base_time + 0.5

    events.append((validation_time, "VALIDATE", tx_id))
    events.append((commit_time, "COMMIT", tx_id))

# --- Process Events by Arrival Time ---
heapq.heapify(events)

while events:
    time, event_type, tx_id = heapq.heappop(events)

    if event_type == "VALIDATE":
        validated.add(tx_id)

    elif event_type == "COMMIT":
        if tx_id not in validated:
            violations += 1

# --- Output ---
print("=== BASELINE SIMULATION (No Safeguards) ===")
print(f"Total Transactions : {NUM_TRANSACTIONS}")
print(f"Total Violations   : {violations}")
print(f"Violation Rate     : {round((violations / NUM_TRANSACTIONS) * 100, 4)}%")
