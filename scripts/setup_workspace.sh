#!/usr/bin/env bash
# One-time setup on Linux (local or AWS). Run from the repo root: bash scripts/setup_workspace.sh
# Prerequisites (TRACKER.md -> P0): NVIDIA driver >= 580.65, git, uv.
# Upstreams (Isaac Lab, robot_lab) are git submodules pinned in this repo — see scripts/upstream.py.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "uv not found - install it first (TRACKER.md P0)"; exit 1; }
git submodule update --init --recursive
uv sync --extra importers --extra rsl-rl --extra ovphysx --extra video
uv run pytest -q
uv run isaaclab list_envs
