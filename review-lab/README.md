# Review lab — adversarial agent review

Demo material for the adversarial-review episode: independent,
differently-prompted review passes find **disjoint** bug sets.

## What's here

| File | Role |
| --- | --- |
| `roll_fleet.py` | The code under review: cron automation that starts production instance rolls off an approval queue. Works on the happy path. Seeded with 4 subtle bugs. |
| `fake_aws.py` | Deterministic simulated backend (fleets, refreshes, approvals, prod shell, notifier) with an ordered event log. |
| `harness.py` | Named scenarios that run `roll_fleet` against prepared backend state and print exactly what happened. The verification instrument. |
| `prompts/finder-a.md` | Review pass 1: general code review lens. |
| `prompts/finder-b.md` | Review pass 2: correctness/safety lens (staleness, enums, privilege ordering, lifecycle). Blind to pass 1. |
| `prompts/verifier.md` | Adversarial verification: every finding must reproduce against the harness or it's refuted. |
| `ANSWER-KEY.md` | Spoiler: the four seeded bugs and the scenario that demonstrates each. |

## The workflow being demonstrated

1. Run finder A against `roll_fleet.py` in one session. Modest list.
2. Run finder B in a second session, blind to the first. Different lens,
   different — serious — findings.
3. Run the verifier on the merged list: confirm or refute each finding by
   reproducing it against `harness.py`. No fixes until verdicts are in.
4. Diff the two finding sets. That diff is the argument for multi-pass
   review.

```
python3 review-lab/harness.py clean               # the script "works"
python3 review-lab/harness.py stacked-approvals   # bug 1
python3 review-lab/harness.py cancelling-refresh  # bug 2
python3 review-lab/harness.py branch-hooks        # bug 3
python3 review-lab/harness.py standby-instances   # bug 4
```

The test suite (`tests/test_review_lab.py`) asserts all four bugs still
reproduce — the bugs are load-bearing demo material, so CI protects them.
