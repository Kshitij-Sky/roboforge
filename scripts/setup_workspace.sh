#!/usr/bin/env bash
# Set up the RoboForge workspace on Linux (local or AWS): clones the pinned upstreams next to this repo.
#   <workspace>/IsaacLab (v3.0.0)   <workspace>/robot_lab (v3.0.0)   <workspace>/roboforge
# Prerequisites (TRACKER.md -> P0): NVIDIA driver >= 580.65, git, uv.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WS="$(dirname "$REPO")"

clone() {  # name url ref
  if [ -d "$WS/$1" ]; then echo "exists: $WS/$1 (not touched)"; return; fi
  git clone --branch "$3" --depth 1 "$2" "$WS/$1"
}
command -v uv >/dev/null || { echo "uv not found - install it first (TRACKER.md P0)"; exit 1; }
clone IsaacLab  https://github.com/isaac-sim/IsaacLab.git v3.0.0
clone robot_lab https://github.com/fan-ziqi/robot_lab.git v3.0.0

cat <<EOF

Next (from $REPO):
  uv sync --extra importers --extra rsl-rl --extra ovphysx
  uv run isaaclab list_envs --show_presets
EOF
