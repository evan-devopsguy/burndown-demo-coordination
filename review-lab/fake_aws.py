#!/usr/bin/env python3
"""Deterministic simulated backend for the review lab.

Just enough of an autoscaling + approval-queue + notification surface for
``roll_fleet.py`` to run against, with a global ordered event log so a
verification pass can assert exactly what happened and in what order.
No network, no cloud account, fully deterministic.
"""

from __future__ import annotations


class Env:
    """Bundle of fakes handed to roll_fleet, sharing one ordered event log."""

    def __init__(self):
        self.events: list[tuple] = []
        self.autoscaling = FakeAutoScaling(self)
        self.approvals = FakeApprovals(self)
        self.prod_shell = ProdShell(self)
        self.notifier = Notifier(self)

    def record(self, kind: str, **details) -> None:
        self.events.append((len(self.events), kind, details))

    def tick(self) -> None:
        """Advance simulated time: every in-progress refresh updates one
        in-service instance."""
        self.autoscaling._advance()


class FakeAutoScaling:
    def __init__(self, env: Env):
        self._env = env
        self.fleets: dict[str, dict] = {}
        self._refresh_seq = 0

    def add_fleet(self, name: str, ami: str, instances: list[str]) -> None:
        """instances: lifecycle states, e.g. ["InService", "Standby"]."""
        self.fleets[name] = {
            "current_ami": ami,
            "instances": [
                {"InstanceId": f"i-{name}-{n}", "LifecycleState": state, "Ami": ami}
                for n, state in enumerate(instances)
            ],
            "refreshes": [],
        }

    def seed_refresh(self, fleet: str, status: str, target_ami: str) -> None:
        """Pre-existing refresh in an arbitrary state (e.g. Cancelling)."""
        self._refresh_seq += 1
        self.fleets[fleet]["refreshes"].append({
            "RefreshId": f"ir-{self._refresh_seq:04d}", "Status": status,
            "TargetAmi": target_ami, "InstancesUpdated": 0,
        })

    def describe_fleet(self, fleet: str) -> dict:
        f = self.fleets[fleet]
        return {
            "CurrentAmi": f["current_ami"],
            "Instances": [
                {"InstanceId": i["InstanceId"], "LifecycleState": i["LifecycleState"]}
                for i in f["instances"]
            ],
        }

    def describe_instance_refreshes(self, fleet: str) -> list[dict]:
        return [dict(r) for r in self.fleets[fleet]["refreshes"]]

    def start_instance_refresh(self, fleet: str, target_ami: str) -> str:
        self._refresh_seq += 1
        refresh_id = f"ir-{self._refresh_seq:04d}"
        self.fleets[fleet]["refreshes"].append({
            "RefreshId": refresh_id, "Status": "InProgress",
            "TargetAmi": target_ami, "InstancesUpdated": 0,
        })
        self._env.record("refresh-started", fleet=fleet, refresh_id=refresh_id,
                         target_ami=target_ami)
        return refresh_id

    def _advance(self) -> None:
        for name, f in self.fleets.items():
            for r in f["refreshes"]:
                if r["Status"] != "InProgress":
                    continue
                # The refresh replaces in-service instances only; Standby
                # instances are skipped, exactly like the real API.
                stale = [i for i in f["instances"]
                         if i["LifecycleState"] == "InService"
                         and i["Ami"] != r["TargetAmi"]]
                if stale:
                    stale[0]["Ami"] = r["TargetAmi"]
                    r["InstancesUpdated"] += 1
                if not [i for i in f["instances"]
                        if i["LifecycleState"] == "InService"
                        and i["Ami"] != r["TargetAmi"]]:
                    r["Status"] = "Successful"
                    f["current_ami"] = r["TargetAmi"]


class FakeApprovals:
    def __init__(self, env: Env):
        self._env = env
        self.pending: list[dict] = []
        self.consumed: list[str] = []

    def add(self, approval_id: str, fleet: str, target_ami: str,
            signed_by: str = "release-eng", source_branch: str = "main",
            hooks: list[str] | None = None) -> None:
        self.pending.append({
            "ApprovalId": approval_id, "Fleet": fleet, "TargetAmi": target_ami,
            "SignedBy": signed_by, "SourceBranch": source_branch,
            "PreDeployHooks": hooks or [],
        })

    def list_pending(self) -> list[dict]:
        return [dict(a) for a in self.pending]

    def mark_consumed(self, approval_id: str) -> None:
        self.pending = [a for a in self.pending if a["ApprovalId"] != approval_id]
        self.consumed.append(approval_id)
        self._env.record("approval-consumed", approval_id=approval_id)

    def requeue(self, approval: dict) -> None:
        if approval["ApprovalId"] not in [a["ApprovalId"] for a in self.pending]:
            self.pending.append(dict(approval))
        self._env.record("approval-requeued", approval_id=approval["ApprovalId"])


class ProdShell:
    """Command execution with production credentials. Everything is logged."""

    def __init__(self, env: Env):
        self._env = env

    def run(self, command: str, approval_id: str) -> None:
        self._env.record("prod-exec", command=command, approval_id=approval_id)


class Notifier:
    def __init__(self, env: Env):
        self._env = env
        self.sent: list[str] = []

    def notify(self, message: str) -> None:
        self.sent.append(message)
        self._env.record("notify", message=message)
