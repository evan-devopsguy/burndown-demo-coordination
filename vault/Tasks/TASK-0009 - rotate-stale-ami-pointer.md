---
id: TASK-0009
title: Rotate the stale AMI pointer for the batch fleet
initiative: base-image-rebuilds
priority: P2
status: unclaimed
claimed_by: 
claimed_at: 
done_at: 
---

# Rotate the stale AMI pointer for the batch fleet

The batch fleet's SSM parameter still points at an image two bakes old. Update the pointer and let the next instance refresh pick it up.
