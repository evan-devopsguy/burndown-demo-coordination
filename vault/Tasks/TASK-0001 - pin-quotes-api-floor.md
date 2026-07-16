---
id: TASK-0001
title: Pin vulnerable transitive floor in quotes-api
initiative: phantom-findings-cleanup
priority: P1
status: done
claimed_by: session-alpha
claimed_at: 2026-07-14T15:02:11+00:00
done_at: 2026-07-14T16:40:03+00:00
---

# Pin vulnerable transitive floor in quotes-api

The one genuinely vulnerable service in the group. Added an explicit floor pin for the flagged transitive package and verified the restore graph.

Evidence: re-scan shows the finding cleared; CI validation build green.
