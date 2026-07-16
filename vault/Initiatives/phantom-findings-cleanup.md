---
id: INIT-01
title: Phantom findings cleanup
status: active
---

# Phantom findings cleanup

Scanner findings sourced from `deps.json` manifests where the flagged DLL never ships in the image.
Verify each finding against the shipped filesystem before touching code; most close as not-present, a few are real and get pinned.

**Definition of done:** every manifest-view finding for the affected services is either closed with evidence or fixed with a floor pin.
