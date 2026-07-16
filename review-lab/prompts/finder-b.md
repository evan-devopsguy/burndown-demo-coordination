# Finder B — correctness and production-safety review

You are reviewing `review-lab/roll_fleet.py`, a cron-driven automation that
starts production instance refreshes when a hardened AMI is approved. It
will run unattended with production credentials. Assume it has already
passed a general review; your job is the failure modes that reviews miss.

Work these lenses explicitly, one at a time:

1. **Staleness and TOCTOU.** For every piece of state the code reads, ask:
   can it change between the read and the action that depends on it? What
   happens if the same work item appears twice?
2. **State-machine completeness.** For every status/enum the code compares
   against, enumerate the *full* set of states the real API can return. What
   do the unhandled states do?
3. **Privilege ordering.** Trace every side effect that runs with production
   credentials. Does anything execute *before* the authorization decision
   that is supposed to gate it? Who controls the inputs to that side effect?
4. **Lifecycle edge cases.** For every collection the code counts or
   iterates, ask which membership states exist (in service, standby,
   detached, unhealthy) and whether counts and completions agree on them.
   What happens on repeat when they don't?

For each finding: a one-line summary, the exact code path, a concrete
failure scenario (inputs/state → wrong behavior), and severity. Findings
without a concrete failure scenario don't count.

Do not look at `harness.py` scenarios, the answer key, or any other review's
output. You are independent by design.
