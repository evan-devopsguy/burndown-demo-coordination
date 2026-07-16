---
id: INIT-02
title: Base image rebuilds
status: active
---

# Base image rebuilds

Services still on end-of-life base images (netcoreapp3.1-era and older) get rebuilt onto the current hardened base, then re-scanned to confirm the finding cliff.

**Definition of done:** no service in the fleet builds from an end-of-life base image; re-scan shows the expected drop.
