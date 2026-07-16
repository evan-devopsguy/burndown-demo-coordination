#!/usr/bin/env python3
"""Render the burndown chart into the vault dashboard.

Queries the (simulated) scanner API for the daily critical-count series and
rewrites the block between ``<!-- burndown:begin -->`` / ``<!-- burndown:end -->``
in ``vault/Home.md`` with a Mermaid chart, headline stats, and the event log.
Also writes the raw series to ``vault/Data/burndown-series.md``. Idempotent —
run it after every scan.

Simulate a mid-series disclosure re-baseline (the "number goes UP" beat):

    python3 burndown/update_dashboard.py \
        --disclosure "2026-07-08:+287:runtime vendor discloses container-escape batch"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scanner_api import DEFAULT_SCENARIO, ScannerAPI  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
BEGIN, END = "<!-- burndown:begin -->", "<!-- burndown:end -->"


def vault() -> Path:
    return Path(os.environ.get("CLAIMBOARD_ROOT", REPO)) / "vault"


def parse_disclosure(spec: str) -> dict:
    """``DATE:DELTA:LABEL`` → event dict (delta may carry an explicit +)."""
    date_s, delta_s, label = spec.split(":", 2)
    return {"date": date_s, "delta": int(delta_s), "label": label}


def mermaid_chart(series: list[dict]) -> str:
    labels = ", ".join(f'"{p["date"][5:]}"' for p in series)
    counts = ", ".join(str(p["count"]) for p in series)
    top = max(p["count"] for p in series)
    ceiling = (top // 500 + 1) * 500
    return (
        "```mermaid\n"
        "xychart-beta\n"
        '    title "Org-wide critical findings"\n'
        f"    x-axis [{labels}]\n"
        f'    y-axis "critical findings" 0 --> {ceiling}\n'
        f"    line [{counts}]\n"
        "```"
    )


def build_block(series: list[dict]) -> str:
    first, last = series[0], series[-1]
    net = last["count"] - first["count"]
    jumps = [(series[i]["count"] - series[i - 1]["count"], series[i])
             for i in range(1, len(series))]
    worst_delta, worst = max(jumps, key=lambda j: j[0])
    lines = [
        BEGIN,
        "",
        f"**{last['count']:,}** critical findings as of {last['date']} "
        f"(started {first['count']:,} on {first['date']}, net {net:+,}).",
        "",
        mermaid_chart(series),
        "",
    ]
    if worst_delta > 0:
        lines += [
            f"> [!note] The number went **up** on {worst['date']} ({worst_delta:+,}) — "
            f"{'; '.join(worst['events']) or 'new disclosures re-baselined the fleet'}. "
            "Disclosures are weather. Only automated refresh keeps you ahead of them.",
            "",
        ]
    lines += ["**Event log:**", ""]
    for point in series:
        for label in point["events"]:
            lines.append(f"- {point['date']}: {label}")
    lines += ["", END]
    return "\n".join(lines)


def series_table(series: list[dict]) -> str:
    rows = ["# Burndown series", "", "| date | critical findings | event |",
            "| --- | ---: | --- |"]
    for p in series:
        rows.append(f"| {p['date']} | {p['count']:,} | {'; '.join(p['events'])} |")
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--disclosure", action="append", default=[],
                        metavar="DATE:DELTA:LABEL",
                        help="inject a disclosure event into the series (repeatable)")
    args = parser.parse_args()

    api = ScannerAPI(args.scenario,
                     extra_events=[parse_disclosure(s) for s in args.disclosure])
    series = api.critical_count_series()

    home = vault() / "Home.md"
    text = home.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{home}: missing {BEGIN} / {END} markers")
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    home.write_text(pattern.sub(lambda _: build_block(series), text),
                    encoding="utf-8")

    data = vault() / "Data" / "burndown-series.md"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text(series_table(series), encoding="utf-8")

    print(f"dashboard updated: {series[-1]['count']:,} criticals as of"
          f" {series[-1]['date']} ({len(series)} data points)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
