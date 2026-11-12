# Set up the RoboForge workspace on Windows: clones the pinned upstreams next to this repo.
#   <workspace>\IsaacLab  (v3.0.0)   <workspace>\robot_lab (v3.0.0)   <workspace>\roboforge
# Prerequisites (TRACKER.md -> P0): Windows long paths enabled, git, uv.
# Usage, from the repo root:   powershell -ExecutionPolicy Bypass -File scripts\setup_workspace.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Ws = Split-Path -Parent $Repo

$Pins = @(
    @{ Name = "IsaacLab";  Url = "https://github.com/isaac-sim/IsaacLab.git"; Ref = "v3.0.0" },
    @{ Name = "robot_lab"; Url = "https://github.com/fan-ziqi/robot_lab.git"; Ref = "v3.0.0" }
)

$lp = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
if ($lp -ne 1) { throw "Windows long paths are disabled. Enable them (admin) and reboot first - see TRACKER.md P0." }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv not found - install it first (TRACKER.md P0)." }
git config --global core.longpaths true

foreach ($p in $Pins) {
    $dst = Join-Path $Ws $p.Name
    if (Test-Path $dst) { Write-Host "exists: $dst (not touched)"; continue }
    git clone --branch $p.Ref --depth 1 $p.Url $dst
}

Write-Host "`nNext (from $Repo):"
Write-Host "  `$env:UV_CACHE_DIR = 'D:\uv-cache'   # keep the multi-GB cache off C:"
Write-Host "  uv sync --extra importers --extra rsl-rl --extra ovphysx"
Write-Host "  uv run isaaclab list_envs --show_presets"
