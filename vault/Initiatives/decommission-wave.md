---
id: INIT-03
title: Decommission wave
status: active
---

# Decommission wave

The cheapest fix for a finding is deleting the thing that carries it.
Stopped and orphaned instances still show up in scanner results; snapshot, verify nothing references them, then terminate.

**Definition of done:** every stopped/orphaned instance is either terminated (with a pre-delete snapshot) or explicitly adopted by an owner.
