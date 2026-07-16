#!/usr/bin/env bash
# Claude Code SessionStart hook: print the unclaimed-board summary so every
# session starts knowing the state of the fleet. Wire it up via
# examples/claude-settings.json (or your own .claude/settings.json).
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$REPO_DIR/claimboard.py" sync >/dev/null
python3 "$REPO_DIR/claimboard.py" board
