#!/usr/bin/env python3
"""Simulated scanner findings API.

Stands in for the vulnerability scanner's REST API in the metrics episodes:
``critical_count_series()`` is the query a real deployment would make against
its scanner ("critical findings, org-wide, by day"). The series is generated
deterministically from a scenario file so every render — and every re-shoot —
produces identical numbers.

The shape it models: a large starting count worked steadily downward by
automation (daily drift), punctuated by cliffs (decommission waves, rebuild
campaigns) and by the occasional *upward* jump when a vendor disclosure
re-baselines the world overnight. Burndown against a moving target.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SCENARIO = Path(__file__).resolve().parent / "scenario.json"


class ScannerAPI:
    def __init__(self, scenario_path: Path | str = DEFAULT_SCENARIO,
                 extra_events: list[dict] | None = None):
        self.scenario = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
        if extra_events:
            self.scenario["events"] = self.scenario["events"] + list(extra_events)

    def critical_count_series(self) -> list[dict]:
        """Daily org-wide critical-finding counts: [{date, count, events}]."""
        s = self.scenario
        start = date.fromisoformat(s["start_date"])
        events_by_date: dict[str, list[dict]] = {}
        for event in s["events"]:
            events_by_date.setdefault(event["date"], []).append(event)

        rng = random.Random(s["jitter_seed"])
        lo, hi = s["jitter_range"]
        series: list[dict] = []
        count = float(s["start_count"])
        for day in range(s["days"]):
            d = start + timedelta(days=day)
            if day > 0:
                count += s["daily_drift"] + rng.randint(lo, hi)
                for event in events_by_date.get(d.isoformat(), []):
                    count += event["delta"]
            series.append({
                "date": d.isoformat(),
                "count": max(0, round(count)),
                "events": [e["label"] for e in events_by_date.get(d.isoformat(), [])]
                          if day > 0 else [],
            })
        return series


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for point in ScannerAPI().critical_count_series():
        flag = f"   <-- {'; '.join(point['events'])}" if point["events"] else ""
        print(f"{point['date']}  {point['count']:>6}{flag}")
