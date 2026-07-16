"""Review lab: the happy path must work and all four seeded bugs must
still reproduce — the bugs are load-bearing demo material, so CI guards
them like features."""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "review-lab"))
import harness  # noqa: E402


def refresh_starts(env, fleet):
    return [d for _, kind, d in env.events
            if kind == "refresh-started" and d["fleet"] == fleet]


class ReviewLabTest(unittest.TestCase):
    def run_scenario(self, name):
        env = harness.Env()
        cycles = harness.SCENARIOS[name](env)
        return env, cycles

    def test_clean_scenario_behaves_correctly(self):
        env, _ = self.run_scenario("clean")
        self.assertEqual(len(refresh_starts(env, "payments-edge")), 1)
        self.assertEqual(len(env.notifier.sent), 1)
        self.assertIn("rolled to ami-hardened-042", env.notifier.sent[0])

    def test_bug1_stacked_approvals_duplicate_refresh(self):
        env, _ = self.run_scenario("stacked-approvals")
        self.assertEqual(len(refresh_starts(env, "payments-edge")), 2,
                         "stale second approval must trigger a duplicate roll")

    def test_bug2_cancelling_refresh_not_treated_as_active(self):
        env, _ = self.run_scenario("cancelling-refresh")
        refreshes = env.autoscaling.describe_instance_refreshes("quotes-api")
        statuses = sorted(r["Status"] for r in refreshes)
        self.assertIn("Cancelling", statuses)
        self.assertEqual(len(refreshes), 2,
                         "a new roll must start on top of the cancelling one")

    def test_bug3_branch_hooks_execute_before_gate(self):
        env, _ = self.run_scenario("branch-hooks")
        kinds = [kind for _, kind, _ in env.events]
        self.assertIn("prod-exec", kinds)
        self.assertLess(kinds.index("prod-exec"), kinds.index("gate-check"),
                        "hook ran with prod creds before the gate decision")
        self.assertEqual(
            [d for _, k, d in env.events if k == "refresh-started"], [],
            "the gate itself must still reject the roll")

    def test_bug4_standby_instance_causes_approval_spam(self):
        env, cycles = self.run_scenario("standby-instances")
        incomplete = [m for m in env.notifier.sent if "incomplete" in m]
        self.assertEqual(len(incomplete), cycles,
                         "every cron cycle must re-spam the approvers")
        self.assertEqual(len(refresh_starts(env, "ledger-service")), cycles,
                         "every cron cycle must start a new no-op refresh")


if __name__ == "__main__":
    unittest.main()
