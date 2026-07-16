---
id: TASK-0008
title: Add the manifest-view scanner config to shipping-api
initiative: phantom-findings-cleanup
priority: P2
status: unclaimed
claimed_by: 
claimed_at: 
done_at: 
---

# Add the manifest-view scanner config to shipping-api

shipping-api is the last service in the group without the checked-in syft config, so its manifest view diverges from the rest of the fleet. Copy the standard config and verify the finding set matches.
