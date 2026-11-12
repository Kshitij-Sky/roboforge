# scripts/ — sub-tracker (P0: toolchain and machine qualification)

← [Master tracker](../TRACKER.md) · Contents: workspace setup, model build, benchmarks.

## P0 — Toolchain and machine qualification

Goal: decide **on numbers** whether this laptop trains locally or we go to AWS.

### Machine (measured 2026-11-12) `[MEAS]`

| Item | Value | Requirement `[3P]` | OK? |
|---|---|---|---|
| GPU | RTX 3070 Ti **Laptop**, 8 GB, CC 8.6 | Turing+ | ✅ (throttles under sustained load) |
| Driver | 616.64 | ≥ 580.88 on Windows | ✅ |
| RAM | 15.7 GB | Isaac Sim path wants 32 GB | ⚠ kit-less only |
| Disk | C: 51 GB free, D: 174 GB free | ~10–15 GB of wheels + cache `[EST]` | ⚠ keep `UV_CACHE_DIR` on D: |
| Windows long paths | disabled | required | ❌ |
| uv | not installed | required | ❌ |
| WSL2 | enabled, no distro | optional fallback | — |

### Steps

- [ ] Sky: enable long paths (admin PowerShell), then reboot:
  `New-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force`
- [ ] Install uv. Set `UV_CACHE_DIR=D:\uv-cache`.
- [ ] Run `scripts/setup_workspace.ps1`, which clones IsaacLab v3.0.0 and robot_lab v3.0.0 beside this repo.
- [ ] Run `uv sync --extra importers --extra rsl-rl --extra ovphysx` and commit `uv.lock`. This also verifies `pyproject.toml`.
- [ ] Re-run `pytest` inside the uv env, which has MuJoCo 3.12. Model tests so far ran on 3.10 in the old venv.
- [ ] Train Cartpole on `newton_mjwarp` and on `ovphysx` (G0.1).
- [ ] Benchmark at 1024 / 2048 / 4096 envs: steps/s, peak VRAM and RAM, GPU clock and temperature over **≥ 30 min**, plugged in, max-performance power plan.
  - Tasks: robot_lab `RobotLab-Isaac-Velocity-Rough-Unitree-B2W-v0`, plus Isaac Lab Go2 rough.
  - Write a `scripts/bench_training.py` that logs these.
- [ ] One full default-length training run: wall time and final terrain level (G0.2).
- [ ] Repeat at 4096 envs on `ovphysx` (G0.3).
- [ ] Depth probe at 256 / 512 / 1024 envs with `newton_renderer`: Isaac Lab ANYmal-D distillation or the contrib `g1_terrain` depth task (G0.4).
- [ ] Two seeds on the same backend; record the variance (G0.5).

### Gates

| Gate | Criterion `[EST]` | If it fails |
|---|---|---|
| G0.1 | Cartpole trains on both backends, Windows native | WSL2 Ubuntu 24.04, then AWS |
| G0.2 | 4096 envs: VRAM ≤ 7.5 GB, RAM ≤ 13 GB, full rough-terrain run ≤ 3 h | 3–8 h: local for debug, AWS for production runs. > 8 h or OOM at 2048: AWS primary |
| G0.3 | `ovphysx` runs locally | Cross-engine eval on AWS |
| G0.4 | Depth env ≥ 512 envs in 7.5 GB | Depth training on AWS |
| G0.5 | Seeds within each other's ±1σ band | Always report mean ± std over ≥ 3 seeds; MuJoCo-Warp is not run-to-run deterministic |

### AWS

- [ ] Sky: account and IAM, **request a G-instance vCPU quota**, S3 bucket for runs, budget alarm.
- [ ] One `g6e.xlarge` (L40S 48 GB) or `g5.xlarge` (A10G 24 GB), Ubuntu 24.04, driver ≥ 580.65.
  - Run `scripts/setup_workspace.sh` and the same `uv.lock`.
  - Re-run the benchmark to calibrate local against cloud.
- Prices `[EST, verify on the AWS pricing page]`: g5.xlarge ≈ $1.0/h, g6e.xlarge ≈ $1.9/h on-demand. Spot is ~60–70% cheaper; use checkpoint resume.

## Scripts in this folder

| Script | Purpose | Status |
|---|---|---|
| `build_robot.py` | Robot spec → canonical MJCF + contract check (+ `--view`) | ✅ |
| `setup_workspace.ps1` / `.sh` | Clone pinned IsaacLab + robot_lab beside the repo | written, untested until P0 |
| `bench_training.py` | P0 benchmark logger | ⬜ |

## Done

- 2026-11-12 `build_robot.py` and the setup scripts written; machine facts measured.
