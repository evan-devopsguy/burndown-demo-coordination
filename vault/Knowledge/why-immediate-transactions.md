# Why the claim CLI uses BEGIN IMMEDIATE

The first version of the claim CLI used SQLite's default deferred transactions and it failed under real contention on Windows.

With a deferred transaction, `SELECT status` takes only a read lock. Two sessions racing for the same task could both read `status = unclaimed`, then both attempt the upgrade to a write lock on `UPDATE`. Under Windows file locking this produced either `SQLITE_BUSY` storms or, worse, both sessions believing they had won.

`BEGIN IMMEDIATE` takes the reserved write lock *before* the read. The check-then-claim sequence becomes genuinely atomic: the second session blocks at `BEGIN` (bounded by `busy_timeout`), and when it proceeds it sees the winner's committed `claimed` status and loses cleanly.

See `claimboard.py` — the `immediate()` context manager wraps every write. `demos/race.py` reproduces the race on demand.
