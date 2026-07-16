#!/usr/bin/env python3
"""roll-fleet: auto-queue production instance rolls when a hardened AMI is approved.

Runs unattended from cron. Each invocation drains the pending approval
queue: for every approval it validates authorization, checks the target
fleet for an active refresh, starts the roll, and waits for it to complete
before moving on. Approvals that can't proceed are requeued for the next
cron cycle.

This is the script under review in the adversarial-review episode. It is
written sincerely and works on the happy path — review it before reading
review-lab/ANSWER-KEY.md.
"""

from __future__ import annotations

import logging

log = logging.getLogger("roll-fleet")

TRUSTED_APPROVERS = {"release-eng", "sec-oncall"}
ACTIVE_REFRESH_STATES = {"Pending", "InProgress"}
MAX_WAIT_POLLS = 20


def has_active_refresh(autoscaling, fleet: str) -> bool:
    """A fleet must never have two rolls in flight at once."""
    return any(r["Status"] in ACTIVE_REFRESH_STATES
               for r in autoscaling.describe_instance_refreshes(fleet))


def run_predeploy_hooks(env, approval: dict) -> None:
    """Run the fleet's pre-deploy hooks (smoke checks, cache warmers)."""
    for command in approval.get("PreDeployHooks", []):
        log.info("hook: %s", command)
        env.prod_shell.run(command, approval_id=approval["ApprovalId"])


def approval_is_authorized(env, approval: dict) -> bool:
    """Only trusted approvers, and only rolls cut from main."""
    env.record("gate-check", approval_id=approval["ApprovalId"])
    if approval.get("SignedBy") not in TRUSTED_APPROVERS:
        log.warning("%s: untrusted approver %s",
                    approval["ApprovalId"], approval.get("SignedBy"))
        return False
    if approval.get("SourceBranch") != "main":
        log.warning("%s: refusing roll cut from branch %s",
                    approval["ApprovalId"], approval.get("SourceBranch"))
        return False
    return True


def wait_for_refresh(env, fleet: str, refresh_id: str) -> bool:
    """Poll until every instance in the fleet is on the new image."""
    expected = len(env.autoscaling.describe_fleet(fleet)["Instances"])
    for _ in range(MAX_WAIT_POLLS):
        env.tick()
        for refresh in env.autoscaling.describe_instance_refreshes(fleet):
            if (refresh["RefreshId"] == refresh_id
                    and refresh["InstancesUpdated"] >= expected):
                return True
    return False


def process_approval(env, approval: dict) -> None:
    fleet = approval["Fleet"]
    approval_id = approval["ApprovalId"]

    run_predeploy_hooks(env, approval)

    if not approval_is_authorized(env, approval):
        log.warning("%s: rejected by gate", approval_id)
        return

    if has_active_refresh(env.autoscaling, fleet):
        env.notifier.notify(f"{fleet}: refresh already active,"
                            f" deferring {approval_id}")
        env.approvals.requeue(approval)
        return

    refresh_id = env.autoscaling.start_instance_refresh(
        fleet, approval["TargetAmi"])
    env.approvals.mark_consumed(approval_id)

    if wait_for_refresh(env, fleet, refresh_id):
        env.notifier.notify(f"{fleet}: rolled to {approval['TargetAmi']}"
                            f" (refresh {refresh_id})")
    else:
        env.notifier.notify(f"{fleet}: refresh {refresh_id} incomplete —"
                            f" re-requesting approval")
        env.approvals.requeue(approval)


def run_once(env) -> None:
    """One cron invocation: drain the pending approval queue."""
    approvals = env.approvals.list_pending()
    log.info("processing %d pending approval(s)", len(approvals))
    for approval in approvals:
        process_approval(env, approval)
