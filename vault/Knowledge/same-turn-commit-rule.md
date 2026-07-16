# The same-turn commit rule

Every session commits vault state changes in the same turn it makes them — claim writes, status flips, notes. Never batched, never "at the end".

**Why:** the vault is shared state. A session that batches its updates is publishing stale state to every other session for the length of the batch. The collision that motivated this whole system was exactly that — two sessions produced the same fix twice because one of them was sitting on an uncommitted status change.

The SQLite side doesn't have this problem (claims commit atomically at claim time); the rule exists to make the *human-readable* layer keep up with the machine layer.
