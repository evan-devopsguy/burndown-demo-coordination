"""Claim CLI: frontmatter round-trips, transitions, and atomicity under
real multi-process contention (the property the whole system exists for)."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLAIMBOARD = REPO / "claimboard.py"

sys.path.insert(0, str(REPO))
import claimboard  # noqa: E402


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAIMBOARD_ROOT": str(root)}
    # encoding pinned: Windows would otherwise decode the pipe as cp1252
    return subprocess.run([sys.executable, str(CLAIMBOARD), *args],
                          env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


class ClaimboardTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="claimboard-test-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        shutil.copytree(REPO / "vault", self.root / "vault")
        run_cli(self.root, "sync")

    def frontmatter(self, task_id: str) -> dict:
        path = next((self.root / "vault" / "Tasks").glob(f"{task_id}*.md"))
        return claimboard.parse_frontmatter(path.read_text(encoding="utf-8"))

    def test_sync_reads_seed_state(self):
        proc = run_cli(self.root, "list", "--status", "unclaimed")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(proc.stdout.strip().splitlines()), 8)

    def test_claim_writes_db_and_frontmatter(self):
        proc = run_cli(self.root, "claim", "TASK-0003", "--session", "s-test")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("CLAIMED TASK-0003 by s-test", proc.stdout)
        fm = self.frontmatter("TASK-0003")
        self.assertEqual(fm["status"], "claimed")
        self.assertEqual(fm["claimed_by"], "s-test")

    def test_second_claim_loses(self):
        run_cli(self.root, "claim", "TASK-0003", "--session", "s-one")
        proc = run_cli(self.root, "claim", "TASK-0003", "--session", "s-two")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("already claimed by s-one", proc.stdout)

    def test_claim_next_takes_priority_order(self):
        proc = run_cli(self.root, "claim", "--session", "s-test")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("TASK-0003", proc.stdout)  # first unclaimed P1

    def test_done_requires_claim_holder(self):
        run_cli(self.root, "claim", "TASK-0003", "--session", "s-owner")
        proc = run_cli(self.root, "done", "TASK-0003", "--session", "s-other")
        self.assertEqual(proc.returncode, 1)
        proc = run_cli(self.root, "done", "TASK-0003", "--session", "s-owner")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.frontmatter("TASK-0003")["status"], "done")

    def test_release_returns_task_to_board(self):
        run_cli(self.root, "claim", "TASK-0003", "--session", "s-test")
        proc = run_cli(self.root, "release", "TASK-0003", "--session", "s-test")
        self.assertEqual(proc.returncode, 0)
        fm = self.frontmatter("TASK-0003")
        self.assertEqual(fm["status"], "unclaimed")
        self.assertEqual(fm["claimed_by"], "")

    def test_unknown_task_is_distinct_error(self):
        proc = run_cli(self.root, "claim", "TASK-9999", "--session", "s-test")
        self.assertEqual(proc.returncode, 2)

    def test_board_shows_waiting_on_human(self):
        proc = run_cli(self.root, "board")
        self.assertIn("Waiting on a human (2):", proc.stdout)

    def test_concurrent_claims_have_exactly_one_winner(self):
        """8 real processes hammer one task; IMMEDIATE must arbitrate."""
        env = {**os.environ, "CLAIMBOARD_ROOT": str(self.root)}
        procs = [subprocess.Popen(
            [sys.executable, str(CLAIMBOARD), "claim", "TASK-0005",
             "--session", f"s-{n}"],
            env=env, stdout=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace") for n in range(8)]
        codes = []
        for p in procs:
            p.communicate()
            codes.append(p.returncode)
        self.assertEqual(codes.count(0), 1, f"exit codes: {codes}")
        self.assertEqual(codes.count(1), 7, f"exit codes: {codes}")

    def test_concurrent_drain_never_double_claims(self):
        """6 processes drain the board with claim --next; no task twice."""
        env = {**os.environ, "CLAIMBOARD_ROOT": str(self.root)}
        script = (
            "import subprocess, sys\n"
            "while True:\n"
            "    p = subprocess.run([sys.executable, sys.argv[1], 'claim',"
            " '--session', sys.argv[2]], capture_output=True, text=True)\n"
            "    if p.returncode == 3: break\n"
        )
        procs = [subprocess.Popen(
            [sys.executable, "-c", script, str(CLAIMBOARD), f"s-{n}"],
            env=env) for n in range(6)]
        for p in procs:
            self.assertEqual(p.wait(), 0)
        conn = claimboard.sqlite3.connect(self.root / ".claims" / "board.db")
        total, distinct = conn.execute(
            "SELECT COUNT(task_id), COUNT(DISTINCT task_id) FROM claims_log"
            " WHERE action = 'claim'").fetchone()
        conn.close()
        self.assertEqual((total, distinct), (8, 8))


if __name__ == "__main__":
    unittest.main()
