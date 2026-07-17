#!/usr/bin/env python3
"""Live-race demo: N sessions claim the same task at the same instant.

Each worker is a real separate OS process. A multiprocessing barrier lines
them all up, then releases them simultaneously against one task id. Exactly
one wins; the rest lose cleanly with the winner's name.

By default the race runs in a **sandbox** — a temp copy of the vault with a
fresh claim DB — so it is repeatable mid-shoot without touching real board
state. Pass ``--live`` to race against the actual vault.

    python3 demos/race.py                 # 2 sessions, sandbox
    python3 demos/race.py --sessions 8    # pile-up
    python3 demos/race.py --stress        # every worker drains the board;
                                          # asserts no task is claimed twice
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows pipes default to cp1252, which can't encode the result marks.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
CLAIMBOARD = REPO / "claimboard.py"


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAIMBOARD_ROOT": str(root)}
    return subprocess.run(
        [sys.executable, str(CLAIMBOARD), *args],
        env=env, capture_output=True, text=True,
    )


def race_worker(root_str: str, task_id: str, session: str,
                barrier, results) -> None:
    barrier.wait()  # everyone launches on the same tick
    proc = run_cli(Path(root_str), "claim", task_id, "--session", session)
    results.put((session, proc.returncode, proc.stdout.strip()))


def stress_worker(root_str: str, session: str, barrier, results) -> None:
    barrier.wait()
    won = []
    while True:
        proc = run_cli(Path(root_str), "claim", "--session", session)
        if proc.returncode == 0:
            won.append(proc.stdout.strip().split()[1])
        elif proc.returncode == 3:   # board drained
            break
        # returncode 1 = lost a specific race; go around again
    results.put((session, won))


def make_sandbox() -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="claimboard-race-"))
    shutil.copytree(REPO / "vault", sandbox / "vault")
    return sandbox


def print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--task", help="task id to race for (default: next unclaimed)")
    parser.add_argument("--live", action="store_true",
                        help="race against the real vault instead of a sandbox")
    parser.add_argument("--stress", action="store_true",
                        help="every worker drains the board with claim --next")
    args = parser.parse_args()

    root = REPO if args.live else make_sandbox()
    if not args.live:
        print(f"(sandbox: {root})")
    run_cli(root, "sync")

    if args.stress:
        return run_stress(root, max(args.sessions, 4))
    return run_race(root, args)


def run_race(root: Path, args) -> int:
    task_id = args.task
    if task_id is None:
        conn = sqlite3.connect(root / ".claims" / "board.db")
        row = conn.execute("SELECT id FROM tasks WHERE status='unclaimed'"
                           " ORDER BY priority, id LIMIT 1").fetchone()
        conn.close()
        if row is None:
            print("no unclaimed tasks to race for")
            return 1
        task_id = row[0]

    names = [f"session-{chr(ord('a') + i)}" for i in range(args.sessions)]
    print_header(f"{len(names)} sessions racing to claim {task_id}")

    barrier = mp.Barrier(len(names))
    results: mp.Queue = mp.Queue()
    procs = [mp.Process(target=race_worker,
                        args=(str(root), task_id, name, barrier, results))
             for name in names]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    outcomes = sorted(results.get() for _ in names)
    winners = [s for s, code, _ in outcomes if code == 0]
    for session, code, message in outcomes:
        print(f"  {session}: {'WON ' if code == 0 else 'lost'}  ({message})")

    print_header("result")
    if len(winners) == 1:
        print(f"  exactly one winner: {winners[0]} ✓")
        return 0
    print(f"  ATOMICITY VIOLATION: {len(winners)} winners: {winners}")
    return 1


def run_stress(root: Path, n_workers: int) -> int:
    print_header(f"{n_workers} sessions draining the whole board concurrently")
    barrier = mp.Barrier(n_workers)
    results: mp.Queue = mp.Queue()
    procs = [mp.Process(target=stress_worker,
                        args=(str(root), f"session-{chr(ord('a') + i)}",
                              barrier, results))
             for i in range(n_workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    all_claims: list[str] = []
    for _ in range(n_workers):
        session, won = results.get()
        print(f"  {session}: claimed {len(won)} task(s) {won}")
        all_claims.extend(won)

    print_header("result")
    duplicates = {t for t in all_claims if all_claims.count(t) > 1}
    if duplicates:
        print(f"  ATOMICITY VIOLATION: double-claimed {sorted(duplicates)}")
        return 1
    print(f"  {len(all_claims)} tasks claimed, zero double-claims ✓")
    return 0


if __name__ == "__main__":
    mp.set_start_method("spawn")  # match Windows semantics everywhere
    sys.exit(main())
