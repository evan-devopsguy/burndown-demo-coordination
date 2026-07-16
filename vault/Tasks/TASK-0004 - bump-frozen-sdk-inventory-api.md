---
id: TASK-0004
title: Bump the frozen platform SDK in inventory-api
initiative: phantom-findings-cleanup
priority: P2
status: unclaimed
claimed_by: 
claimed_at: 
done_at: 
---

# Bump the frozen platform SDK in inventory-api

inventory-api pins the internal platform SDK at a 2019-era version that drags the old vulnerable package into its manifest. Bump to the current SDK and re-run the validation build.
