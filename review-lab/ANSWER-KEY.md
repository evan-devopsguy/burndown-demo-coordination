# Answer key — the four seeded bugs

> **Spoiler.** Run the review passes in `prompts/` before reading this.
> Each bug reproduces on demand via `python3 review-lab/harness.py <scenario>`.

## 1. Staleness race — stacked approvals trigger duplicate refreshes

`run_once()` fetches the pending-approval list **once**, then processes each
entry with long waits in between. Nothing re-checks that an approval is
still relevant before acting on it: if the same roll was approved twice
(a UI retry, an impatient second approver), the second, now-stale approval
starts a second refresh on a fleet that is already on the target image.

- Where: `run_once()` (single `list_pending()` snapshot) + `process_approval()`
  (no re-fetch, no "fleet already on target AMI" check).
- Reproduce: `harness.py stacked-approvals` → `refreshes started: payments-edge: 2`.
- Fix shape: re-validate against live state at action time — is the approval
  still pending, and is `CurrentAmi` already the target?

## 2. Missing enum states — `Cancelling` and `RollbackInProgress` aren't "active"

`ACTIVE_REFRESH_STATES = {"Pending", "InProgress"}`. The real API also has
`Cancelling` and `RollbackInProgress` — both mean a roll is still mutating
the fleet. The guard treats a cancelling refresh as inactive and starts a
new one on top of it.

- Where: `ACTIVE_REFRESH_STATES` + `has_active_refresh()`.
- Reproduce: `harness.py cancelling-refresh` → final state shows `Cancelling`
  and a new refresh coexisting on quotes-api.
- Fix shape: enumerate terminal states (`Successful`, `Failed`, `Cancelled`)
  and treat everything else as active.

## 3. Privilege ordering — branch-controlled hooks run before the gate

`process_approval()` calls `run_predeploy_hooks()` — arbitrary commands from
the approval payload, executed with production credentials — **before**
`approval_is_authorized()` checks the approver and source branch. Anyone who
can push a branch and generate an approval record gets pre-gate prod
execution, even though the gate then correctly rejects the roll.

- Where: `process_approval()` line order: hooks first, gate second.
- Reproduce: `harness.py branch-hooks` → `prod-exec` event (seq 0) precedes
  `gate-check`; 0 refreshes started, yet 1 prod command executed.
- Fix shape: authorize first; hooks only from trusted refs after the gate.

## 4. Lifecycle edge case — Standby instances counted but never refreshed

`wait_for_refresh()` sets `expected = len(Instances)` — **all** instances,
including `Standby`. Instance refresh only replaces in-service instances, so
`InstancesUpdated` tops out below `expected`, the wait times out, and the
approval is requeued with a fresh notification. Next cron cycle repeats it.
One instance parked in Standby for debugging = infinite approval spam and a
new no-op refresh every cycle.

- Where: `wait_for_refresh()` (count) + the requeue branch in
  `process_approval()`.
- Reproduce: `harness.py standby-instances` → 3 cycles, 3 refreshes, 3
  "incomplete — re-requesting approval" notifications.
- Fix shape: count only `InService` instances — or better, trust the
  refresh's own terminal `Status` instead of a hand-rolled count.

## The happy path works

`harness.py clean` rolls the fleet correctly: one refresh, completes, one
success notification. That's the point of the episode — a single review
pass shipped this.
