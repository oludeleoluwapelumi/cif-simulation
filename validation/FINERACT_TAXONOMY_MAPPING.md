CIF Taxonomy Validation: Apache Fineract

This document maps CIF's severity taxonomy against real, publicly documented defects in Apache Fineract, an open source core banking platform used by financial institutions in dozens of countries.

What this is

A retrospective check of whether CIF's categories describe failure patterns that already occur in a real, independently built financial system. Each ticket below was read directly on Apache's JIRA tracker, not summarized secondhand, and linked so it can be independently verified.

What this is not

This is not a case study and not a CIF diagnosis. Fineract's own engineers found, discussed, and resolved these issues, in most cases years before this mapping was done. CIF was not applied to a live system here. See the main README for what a real case study would require.
Verified mappings

FINERACT-2304: Batch retry issue, duplicate records
Link:https://issues.apache.org/jira/browse/FINERACT-2304
Status: Resolved, Fixed
Summary: A batch API call with an open transaction could trigger retry logic within that same open transaction, producing duplicate entries. If a transaction had already completed but an exception still occurred inside the retry boundary, a retry could still fire on an already completed operation.

CIF classification: Level 2, Event Replay. Direct match: duplicate write caused by retry logic firing after a completed operation.

FINERACT-1744: System idempotency
Link:https://issues.apache.org/jira/browse/FINERACT-1744
Status: Resolved, Implemented
Summary: Not a bug report. A proactive systemic fix. Fineract identified that in high availability deployments, retried API operations could execute twice when a prior execution had already completed, and built dedicated infrastructure against it: an Idempotency-Key API header, idempotency handling for external events, and new command statuses (UNDER_PROCESSING, ERROR) to track execution state.

CIF classification: Does not map to a single severity level. Stronger evidence than an individual bug ticket, since it shows the failure pattern was significant enough to justify permanent architecture, not a one-off patch.

FINERACT-2188: Duplicate repayments reported via mobile app
Link:https://issues.apache.org/jira/browse/FINERACT-2188
Status: Closed, Resolution: Abandoned
Summary: A user reported repayments duplicating within milliseconds through a mobile app. Root cause was never formally established; could be a core platform issue, a client side integration problem, or a duplicated third party callback.

CIF classification: Level 2, Event Replay, symptom consistent, root cause unconfirmed. Included because the symptom matches, not because it was proven.

FINERACT-2457: Share transaction chronological validation
Link:https://issues.apache.org/jira/browse/FINERACT-2457
Status: Confirmed ticket and merged PR
Summary: Share transaction validation blocked new transactions dated earlier than any existing transaction on the account, including transactions that had already been rejected or reversed. The system's record of transaction history included events that were no longer financially real, and enforced ordering rules against that stale history.

CIF classification: Does not cleanly fit the existing four levels. A genuine chronological integrity problem, distinct in mechanism from the retry and duplication pattern the four levels were built around. Candidate for a future taxonomy revision rather than forced into an existing category.

Checked and ruled out
FINERACT-1876: Concurrent update serialization error
Link:https://issues.apache.org/jira/browse/FINERACT-1876
Status: Resolved, Fixed
Summary: Intermittent PostgreSQL error (could not serialize access due to concurrent update) during scheduled job execution, caused by strict transaction isolation under concurrent access.

Why this is not CIF: CIF describes silent divergence, where the system reports success while state has quietly diverged from truth, with no alert. This is the opposite: PostgreSQL's isolation guarantees caught the conflict and threw a hard, visible error. The job failed loudly. That is a safeguard working as intended, not a CIF event. Included here to show the taxonomy is being applied critically, not stretched to fit every available ticket.

Limitations of this mapping
Four confirmed matches out of five tickets originally reviewed; one ticket (FINERACT-1876) was ruled out on direct reading.

Two of the four matches (FINERACT-1744, FINERACT-2457) do not fit a single existing severity level cleanly and are flagged as such rather than forced.

This is retrospective. No live system was assessed. No new finding was produced. The value here is external validation of the taxonomy's categories, not a demonstration of CIF's diagnostic capability.

Next step
A live case study: applying CIF to a real system's current transaction or event logs, with the team's permission, producing a new finding rather than reclassifying an old one.
If you run fintech infrastructure and are open to a free, confidential pass, see the contact info in the main README.
