# Workspace environment for Windows. Dot-source it in every new PowerShell before working:
#   . .\scripts\env.ps1
# Keeps every tool, cache and Python runtime inside the workspace folder (<workspace>\.tools and
# <workspace>\.cache), so nothing large lands on C: and every terminal sees the same files.
$ws = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)          # e.g. D:\RoboForge
$env:UV_CACHE_DIR          = Join-Path $ws ".cache\uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $ws ".cache\python"
$env:WARP_CACHE_PATH       = Join-Path $ws ".cache\warp"             # compiled CUDA kernels
$env:PYTHONUTF8            = "1"                                     # Isaac Lab logs non-ASCII text
$tools = Join-Path $ws ".tools"
if ((Test-Path (Join-Path $tools "uv.exe")) -and -not (($env:Path -split ';') -contains $tools)) {
    $env:Path = "$tools;$env:Path"
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Warning "uv not found. Install it into $tools, or system-wide: https://docs.astral.sh/uv/"
}
