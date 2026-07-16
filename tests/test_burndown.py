"""Burndown generator: determinism, scenario shape, disclosure injection,
and idempotent dashboard rendering."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "burndown"))
from scanner_api import ScannerAPI  # noqa: E402

UPDATE = REPO / "burndown" / "update_dashboard.py"


class ScannerAPITest(unittest.TestCase):
    def test_series_is_deterministic(self):
        self.assertEqual(ScannerAPI().critical_count_series(),
                         ScannerAPI().critical_count_series())

    def test_series_shape(self):
        series = ScannerAPI().critical_count_series()
        self.assertEqual(len(series), 30)
        self.assertEqual(series[0]["count"], 8014)
        # Ends in the mid-5k range, per the episode's story.
        self.assertTrue(5300 <= series[-1]["count"] <= 5900, series[-1])

    def test_disclosure_event_bumps_count_upward(self):
        series = ScannerAPI().critical_count_series()
        disclosure = next(p for p in series if p["date"] == "2026-06-24")
        before = series[series.index(disclosure) - 1]
        self.assertGreater(disclosure["count"], before["count"])
        self.assertTrue(any("disclos" in e for e in disclosure["events"]))

    def test_extra_event_injection(self):
        base = ScannerAPI().critical_count_series()
        bumped = ScannerAPI(extra_events=[
            {"date": "2026-07-08", "delta": 287, "label": "injected"}
        ]).critical_count_series()
        self.assertEqual(bumped[-1]["count"], base[-1]["count"] + 287)


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="burndown-test-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        shutil.copytree(REPO / "vault", self.root / "vault")
        self.home = self.root / "vault" / "Home.md"

    def render(self, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "CLAIMBOARD_ROOT": str(self.root)}
        return subprocess.run([sys.executable, str(UPDATE), *args],
                              env=env, capture_output=True, text=True)

    def test_render_writes_chart_and_series(self):
        proc = self.render()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = self.home.read_text(encoding="utf-8")
        self.assertIn("xychart-beta", text)
        self.assertIn("The number went **up**", text)
        self.assertTrue(
            (self.root / "vault" / "Data" / "burndown-series.md").exists())

    def test_render_is_idempotent_and_preserves_rest_of_home(self):
        self.render()
        first = self.home.read_text(encoding="utf-8")
        self.render()
        second = self.home.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertIn("## Waiting on a human", second)
        self.assertIn("## Initiatives", second)

    def test_disclosure_flag_changes_the_series(self):
        self.render()
        base = self.home.read_text(encoding="utf-8")
        proc = self.render("--disclosure", "2026-07-08:+287:injected batch")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        bumped = self.home.read_text(encoding="utf-8")
        self.assertNotEqual(base, bumped)
        self.assertIn("injected batch", bumped)


if __name__ == "__main__":
    unittest.main()
