#!/usr/bin/env python3
"""claimboard — atomic task claims for concurrent agent sessions.

Two layers, deliberately boring:

  * The Obsidian vault (``vault/``) is the durable, human-readable truth.
    Task files carry frontmatter; every state change is written back to the
    file so it can be committed same-turn. Git history is the audit log.
  * SQLite (``.claims/board.db``, gitignored) is the machine-atomic arbiter
    so exactly one session owns a task at any moment.

Concurrency design: every write runs inside ``BEGIN IMMEDIATE`` so SQLite
takes the reserved write lock *before* the status read. The first version
used deferred transactions and corrupted claims under Windows file
contention — two sessions could both read ``status = unclaimed`` before
either upgraded to a write lock. IMMEDIATE serializes the read with the
write; combined with ``busy_timeout``, losers block briefly and then see the
winner's committed state.

Stdlib only. No SaaS. ``python3 claimboard.py --help``.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BUSY_TIMEOUT_MS = 10_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    initiative  TEXT,
    priority    TEXT,
    status      TEXT NOT NULL DEFAULT 'unclaimed',
    claimed_by  TEXT,
    claimed_at  TEXT,
    done_at     TEXT
);
CREATE TABLE IF NOT EXISTS claims_log (
    seq      INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  TEXT NOT NULL,
    session  TEXT NOT NULL,
    action   TEXT NOT NULL,
    at       TEXT NOT NULL
);
"""

PRIORITY_DEFAULT = "P2"


# ---------------------------------------------------------------- paths ---

def repo_root() -> Path:
    """Board root. Overridable so demos/tests can run in a sandbox copy."""
    return Path(os.environ.get("CLAIMBOARD_ROOT", Path(__file__).resolve().parent))


def vault_dir() -> Path:
    return repo_root() / "vault"


def tasks_dir() -> Path:
    return vault_dir() / "Tasks"


def db_path() -> Path:
    return repo_root() / ".claims" / "board.db"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------- database ---

def connect() -> sqlite3.Connection:
    db = db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: we manage transactions explicitly (BEGIN IMMEDIATE).
    conn = sqlite3.connect(db, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def immediate(conn: sqlite3.Connection):
    """A write transaction that takes the lock up front (the Windows fix)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


# ---------------------------------------------------------- frontmatter ---

def parse_frontmatter(text: str) -> dict:
    """Minimal ``key: value`` frontmatter parser (no YAML dependency)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def update_frontmatter(path: Path, updates: dict) -> None:
    """Rewrite selected frontmatter keys in place, preserving everything else."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"{path}: no frontmatter block")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    remaining = dict(updates)
    for i in range(1, end):
        key = lines[i].partition(":")[0].strip()
        if key in remaining:
            lines[i] = f"{key}: {remaining.pop(key)}\n"
    lines[end:end] = [f"{k}: {v}\n" for k, v in remaining.items()]
    path.write_text("".join(lines), encoding="utf-8")


def task_file(task_id: str) -> Path | None:
    matches = sorted(tasks_dir().glob(f"{task_id}*.md"))
    return matches[0] if matches else None


def writeback(task_id: str, **updates) -> None:
    path = task_file(task_id)
    if path is not None:
        update_frontmatter(path, updates)


# ------------------------------------------------------------- commands ---

def cmd_sync(_args) -> int:
    """Rebuild the claim DB from the task files (files are the truth)."""
    conn = connect()
    count = 0
    with immediate(conn):
        conn.execute("DELETE FROM tasks")
        for path in sorted(tasks_dir().glob("*.md")):
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
            if "id" not in fm:
                continue
            conn.execute(
                "INSERT INTO tasks (id, title, initiative, priority, status,"
                " claimed_by, claimed_at, done_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    fm["id"],
                    fm.get("title", path.stem),
                    fm.get("initiative", ""),
                    fm.get("priority", PRIORITY_DEFAULT),
                    fm.get("status", "unclaimed"),
                    fm.get("claimed_by") or None,
                    fm.get("claimed_at") or None,
                    fm.get("done_at") or None,
                ),
            )
            count += 1
    print(f"synced {count} tasks from {tasks_dir()}")
    return 0


def _pick_next(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT id FROM tasks WHERE status = 'unclaimed'"
        " ORDER BY priority, id LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def cmd_claim(args) -> int:
    conn = connect()
    now = utcnow()
    with immediate(conn):
        task_id = args.task_id or _pick_next(conn)
        if task_id is None:
            print("nothing unclaimed on the board")
            return 3
        row = conn.execute(
            "SELECT status, claimed_by FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            print(f"unknown task {task_id} — run `claimboard.py sync`?")
            return 2
        status, holder = row
        if status != "unclaimed":
            by = f" by {holder}" if holder else ""
            print(f"LOST {task_id}: already {status}{by}")
            return 1
        conn.execute(
            "UPDATE tasks SET status = 'claimed', claimed_by = ?, claimed_at = ?"
            " WHERE id = ?",
            (args.session, now, task_id),
        )
        conn.execute(
            "INSERT INTO claims_log (task_id, session, action, at) VALUES (?,?,?,?)",
            (task_id, args.session, "claim", now),
        )
    # Only the winner reaches this line — losers returned inside the txn.
    writeback(task_id, status="claimed", claimed_by=args.session, claimed_at=now)
    print(f"CLAIMED {task_id} by {args.session}")
    return 0


def _transition(args, action: str, from_status: str, to_status: str,
                stamp_field: str | None) -> int:
    conn = connect()
    now = utcnow()
    with immediate(conn):
        row = conn.execute(
            "SELECT status, claimed_by FROM tasks WHERE id = ?", (args.task_id,)
        ).fetchone()
        if row is None:
            print(f"unknown task {args.task_id}")
            return 2
        status, holder = row
        if status != from_status:
            print(f"REFUSED {args.task_id}: status is {status}, not {from_status}")
            return 1
        if holder != args.session and not args.force:
            print(f"REFUSED {args.task_id}: claimed by {holder}, you are"
                  f" {args.session} (use --force to override)")
            return 1
        sets = "status = ?, "
        params: list = [to_status]
        if stamp_field:
            sets += f"{stamp_field} = ?, "
            params.append(now)
        if to_status == "unclaimed":
            sets += "claimed_by = NULL, claimed_at = NULL, "
            fm_updates = {"status": to_status, "claimed_by": "", "claimed_at": ""}
        else:
            fm_updates = {"status": to_status, stamp_field: now}
        conn.execute(f"UPDATE tasks SET {sets.rstrip(', ')} WHERE id = ?",
                     (*params, args.task_id))
        conn.execute(
            "INSERT INTO claims_log (task_id, session, action, at) VALUES (?,?,?,?)",
            (args.task_id, args.session, action, now),
        )
    writeback(args.task_id, **fm_updates)
    print(f"{action.upper()} {args.task_id} by {args.session}")
    return 0


def cmd_done(args) -> int:
    return _transition(args, "done", "claimed", "done", "done_at")


def cmd_release(args) -> int:
    return _transition(args, "release", "claimed", "unclaimed", None)


def cmd_list(args) -> int:
    conn = connect()
    where, params = "", ()
    if args.status:
        where, params = "WHERE status = ?", (args.status,)
    rows = conn.execute(
        f"SELECT id, priority, status, claimed_by, title FROM tasks {where}"
        " ORDER BY status, priority, id", params
    ).fetchall()
    for task_id, priority, status, holder, title in rows:
        owner = f"  ← {holder}" if holder else ""
        print(f"{task_id}  [{priority}] {status:<9} {title}{owner}")
    return 0


def _waiting_on_human() -> list[str]:
    home = vault_dir() / "Home.md"
    if not home.exists():
        return []
    items, in_section = [], False
    for line in home.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.strip().lower() == "## waiting on a human"
            continue
        if in_section and line.strip().startswith("- [ ]"):
            items.append(line.strip()[5:].strip())
    return items


def cmd_board(_args) -> int:
    conn = connect()
    counts = dict(conn.execute(
        "SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
    total = sum(counts.values())
    if total == 0:
        print("board is empty — run `python3 claimboard.py sync` first")
        return 0
    print(f"== claimboard: {counts.get('unclaimed', 0)} unclaimed /"
          f" {counts.get('claimed', 0)} claimed /"
          f" {counts.get('done', 0)} done ({total} total) ==")
    unclaimed = conn.execute(
        "SELECT id, priority, title, initiative FROM tasks"
        " WHERE status = 'unclaimed' ORDER BY priority, id").fetchall()
    if unclaimed:
        print("\nUnclaimed, by priority:")
        for task_id, priority, title, initiative in unclaimed:
            print(f"  [{priority}] {task_id}  {title}  ({initiative})")
    claimed = conn.execute(
        "SELECT id, claimed_by, claimed_at, title FROM tasks"
        " WHERE status = 'claimed' ORDER BY claimed_at").fetchall()
    if claimed:
        print("\nIn flight:")
        for task_id, holder, at, title in claimed:
            print(f"  {task_id}  {title}  ← {holder} since {at}")
    waiting = _waiting_on_human()
    if waiting:
        print(f"\nWaiting on a human ({len(waiting)}):")
        for item in waiting:
            print(f"  [ ] {item}")
    return 0


def cmd_log(_args) -> int:
    conn = connect()
    for seq, task_id, session, action, at in conn.execute(
            "SELECT seq, task_id, session, action, at FROM claims_log ORDER BY seq"):
        print(f"{seq:>4}  {at}  {action:<8} {task_id}  {session}")
    return 0


# ------------------------------------------------------------------ cli ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claimboard",
        description="Atomic task claims over an Obsidian vault + SQLite.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="rebuild the claim DB from vault task files")
    sub.add_parser("board", help="print the board summary (session-start hook)")
    sub.add_parser("log", help="print the claim audit log")

    p_list = sub.add_parser("list", help="list tasks")
    p_list.add_argument("--status", choices=["unclaimed", "claimed", "done"])

    p_claim = sub.add_parser("claim", help="atomically claim a task")
    p_claim.add_argument("task_id", nargs="?",
                         help="task id; omit to claim the next unclaimed by priority")
    p_claim.add_argument("--session", required=True, help="your session name")

    for name in ("done", "release"):
        p = sub.add_parser(name, help=f"mark a claimed task {name}")
        p.add_argument("task_id")
        p.add_argument("--session", required=True)
        p.add_argument("--force", action="store_true",
                       help="override the claim-holder check")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = {
        "sync": cmd_sync,
        "board": cmd_board,
        "log": cmd_log,
        "list": cmd_list,
        "claim": cmd_claim,
        "done": cmd_done,
        "release": cmd_release,
    }[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
