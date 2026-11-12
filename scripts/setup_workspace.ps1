# One-time setup on Windows. Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_workspace.ps1
# Prerequisites (TRACKER.md -> P0): Windows long paths enabled (+ reboot), git, uv.
# Upstreams (Isaac Lab, robot_lab) are git submodules pinned in this repo — see scripts/upstream.py.

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

. (Join-Path $PSScriptRoot "env.ps1")      # tools + caches inside the workspace folder
$lp = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
if ($lp -ne 1) { throw "Windows long paths are disabled. Enable them (admin) and reboot first - see TRACKER.md P0." }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv not found on PATH - install it first (TRACKER.md P0)." }

git config core.longpaths true
git submodule update --init --recursive

uv sync --extra importers --extra rsl-rl --extra ovphysx --extra video
uv run pytest -q
uv run isaaclab list_envs
