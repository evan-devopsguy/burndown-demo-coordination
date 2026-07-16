# Verifier — confirm or refute every finding

You receive the merged findings from the independent review passes over
`review-lab/roll_fleet.py`. Your job is adversarial verification: assume
each finding is wrong until it reproduces.

For each finding:

1. Restate it as a falsifiable claim: "given state X, the code does Y, and
   Y is wrong because Z."
2. Build the state X against the fake backend (`fake_aws.py`) — add a
   scenario to `harness.py` if none of the existing ones covers it — and run
   `roll_fleet` the way cron would.
3. Read the ordered event log the harness prints. The claim is **CONFIRMED**
   only if the wrong behavior appears in the observed events or tallies;
   otherwise it is **REFUTED** with the transcript as evidence.

Rules:

- No fixes until every finding has a verdict. Fixing before confirming
  destroys the reproduction you need to prove the fix.
- A finding that is real but has a different mechanism than claimed gets
  re-stated, then confirmed under the corrected mechanism.
- Findings that only reproduce under states the real API cannot produce are
  refuted — note why.

Output a table: finding, verdict, scenario used, one-line evidence.
