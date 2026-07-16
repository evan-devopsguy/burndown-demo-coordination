# Remediation fleet board

Shared state for every agent session working the vulnerability backlog.
Human-readable here; machine-atomic claims live in SQLite via `claimboard.py`.

## Ground rules

- **Claim before you touch anything.** `python3 claimboard.py claim --session <you>` takes the next unclaimed task by priority.
- **Commit vault changes the same turn you make them.** Never batch state updates — a batched update is a stale read for every other session.
- **Blocked on a human?** Add it to the box below, release or park the task, and move on.

## Waiting on a human

- [ ] Approve the maintenance window for the ledger-service base-image rebuild
- [ ] Confirm decommission of the 2019-era reporting instances with the finance team

## Burndown

<!-- burndown:begin -->

**5,650** critical findings as of 2026-07-09 (started 8,014 on 2026-06-10, net -2,364).

```mermaid
xychart-beta
    title "Org-wide critical findings"
    x-axis ["06-10", "06-11", "06-12", "06-13", "06-14", "06-15", "06-16", "06-17", "06-18", "06-19", "06-20", "06-21", "06-22", "06-23", "06-24", "06-25", "06-26", "06-27", "06-28", "06-29", "06-30", "07-01", "07-02", "07-03", "07-04", "07-05", "07-06", "07-07", "07-08", "07-09"]
    y-axis "critical findings" 0 --> 8500
    line [8014, 7996, 7961, 7923, 7251, 7220, 7189, 7155, 7120, 6681, 6645, 6625, 6600, 6563, 6956, 6920, 6888, 6857, 6318, 6299, 6261, 6240, 6208, 6190, 6169, 6144, 5724, 5700, 5680, 5650]
```

> [!note] The number went **up** on 2026-06-24 (+393) — browser vendor discloses a new CVE batch — applies to every machine with the browser installed. Disclosures are weather. Only automated refresh keeps you ahead of them.

**Event log:**

- 2026-06-14: decommission wave 1 lands
- 2026-06-19: base-image rebuild cliff
- 2026-06-24: browser vendor discloses a new CVE batch — applies to every machine with the browser installed
- 2026-06-28: dependency pin wave merges
- 2026-07-06: decommission wave 2 lands

<!-- burndown:end -->

## Initiatives

- [[phantom-findings-cleanup]]
- [[base-image-rebuilds]]
- [[decommission-wave]]

## Knowledge

- [[same-turn-commit-rule]]
- [[why-immediate-transactions]]
