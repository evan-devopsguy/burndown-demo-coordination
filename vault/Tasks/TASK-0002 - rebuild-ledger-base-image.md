---
id: TASK-0002
title: Rebuild ledger-service onto the current hardened base image
initiative: base-image-rebuilds
priority: P1
status: claimed
claimed_by: session-alpha
claimed_at: 2026-07-15T20:12:44+00:00
done_at: 
---

# Rebuild ledger-service onto the current hardened base image

ledger-service still builds from a netcoreapp3.1-era base and genuinely ships the vulnerable DLL. Rebuild onto the hardened net8.0 base, then re-scan.

Blocked-adjacent: maintenance window approval is in the Waiting-on-a-human box on [[Home]].
