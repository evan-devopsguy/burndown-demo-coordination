# burndown-demo-coordination

Demo environment for the coordination and metrics episodes of the Burndown
channel: how a fleet of concurrent AI agent sessions works one vulnerability
backlog without collisions, and how the burndown gets measured honestly.

Everything here is boring on purpose: **markdown + SQLite + git. No SaaS.**
Python stdlib only — there is nothing to `pip install`.

## The pieces

| Piece | What it is |
| --- | --- |
| `vault/` | Obsidian-compatible vault: Home dashboard, initiatives, task files with frontmatter, knowledge notes. The durable, human-readable truth — git history is the audit log. |
| `claimboard.py` | Atomic task claims over SQLite (`claim` / `list` / `done` / `release` / `board`). `BEGIN IMMEDIATE` transactions so exactly one session wins a task — the design the Windows file-contention failure forced. |
| `hooks/session-start.sh` | Session-start hook that prints the unclaimed-board summary (wire-up example in `examples/claude-settings.json`). |
| `demos/race.py` | The live race: N real processes, barrier-released, claim the same task simultaneously. Exactly one wins. Sandboxed by default, so it's repeatable mid-shoot. |
| `burndown/` | Simulated scanner API + dashboard renderer: dated critical counts (~8k → mid-5k), a mermaid chart in `vault/Home.md`, and a disclosure event that bumps the count mid-series — because the number sometimes goes **up**, and that's normal. |
| `review-lab/` | Adversarial-review demo: a deploy automation seeded with 4 subtle bugs, two differently-lensed finder prompts, a verifier prompt, and a scenario harness that reproduces every bug on demand. See `review-lab/README.md`. |

## Quickstart

```bash
python3 claimboard.py sync          # build the claim DB from the vault
python3 claimboard.py board         # what every session sees at start
python3 claimboard.py claim --session me    # take the next task by priority
python3 claimboard.py done TASK-0003 --session me

python3 demos/race.py --sessions 4  # the race: exactly one winner
python3 demos/race.py --stress      # 6 sessions drain the board, no double-claims

python3 burndown/update_dashboard.py   # render the burndown chart into Home.md
python3 burndown/update_dashboard.py \
  --disclosure "2026-07-08:+287:runtime vendor discloses container-escape batch"

python3 review-lab/harness.py clean     # the automation "works"...
python3 review-lab/harness.py stacked-approvals   # ...until you look closer
```

Open `vault/` in Obsidian to see the board the way the humans do.

## Design rules the demos exist to prove

1. **Human-readable state + machine-atomic claims.** The vault is for people
   and git; SQLite arbitrates ownership. Neither layer does the other's job.
2. **`BEGIN IMMEDIATE`, not deferred.** Check-then-claim must hold the write
   lock across the check. `vault/Knowledge/why-immediate-transactions.md`.
3. **Commit state changes same-turn, never batched.**
   `vault/Knowledge/same-turn-commit-rule.md`.
4. **Burndown against a moving target.** Disclosures re-baseline the world;
   the chart shows them instead of hiding them.
5. **Independent review lenses find disjoint bugs.** And no finding counts
   until a verification pass reproduces it.

## Tests

```bash
python -m unittest discover -s tests -v
```

CI runs the suite plus the race demo on Ubuntu **and Windows** — Windows is
the platform whose file-locking behavior forced the IMMEDIATE-transaction
design, so it stays in the matrix.

Part of the Burndown demo-environment family
([burndown-demo-dotnet](https://github.com/evan-devopsguy/burndown-demo-dotnet)).
Built to be filmed against; steal anything.
