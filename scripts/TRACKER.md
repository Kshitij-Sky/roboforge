# scripts/ — sub-tracker (P0: toolchain and machine qualification)

← [Master tracker](../TRACKER.md) · Contents: environment setup, model build, training
benchmark, policy evaluation, upstream version switching. Benchmark *results* live in
[benchmarks/](../benchmarks/TRACKER.md).

## P0 — Toolchain and machine qualification

Goal: decide **on numbers** whether this laptop trains locally or we go to AWS.

### Machine `[MEAS]` (2026-11-12)

| Item | Value | Requirement `[3P]` | OK? |
|---|---|---|---|
| GPU | RTX 3070 Ti **Laptop**, 8 GB, CC 8.6 | Turing+ | ✅ but reaches 85 °C within 3 min of rough-terrain training |
| Driver | 616.64 (CUDA 13.4) | ≥ 580.88 on Windows | ✅ |
| RAM | 15.7 GB | Isaac Sim path wants 32 GB | ✅ kit-less: peak 5.8 GB measured |
| Disk | Environment 5 GB + cache 5 GB, both on D: | — | ✅ |
| Windows long paths | enabled (Sky); reboot pending | required | ✅ |
| uv | 0.13.7 in `<workspace>\.tools` | required | ✅ |

### Windows gotcha: app sandbox (MSIX) redirects AppData

The Claude desktop app is an MSIX-packaged app. Anything it writes under `C:\Users\<you>\AppData`
lands in the app's private store, not where your own terminal looks. So **every tool, cache and
Python runtime lives inside the workspace folder**:
- `<workspace>\.tools\uv.exe`
- `<workspace>\.cache\{uv,python,warp}`

Dot-source `scripts\env.ps1` in every PowerShell before working. Your terminal and agent
sessions then see the same files.

### Steps

- [x] Sky: long paths enabled.
- [x] uv 0.13.7 into `D:\RoboForge\.tools`. Caches and Python in `D:\RoboForge\.cache` (`scripts/env.ps1`).
- [x] Upstreams as git submodules: `third_party/IsaacLab` @ v3.0.0, `third_party/robot_lab` @ v3.0.0.
- [x] `uv sync --extra importers --extra rsl-rl --extra ovphysx --extra video`: 184 packages, `uv.lock` committed. Resolved versions: torch 2.11+cu130, Newton 1.6.1, MuJoCo 3.12.0, Warp 1.17.0, OVPhysX 0.6.4, RSL-RL 5.5.1.
- [x] `pytest` inside the uv env (MuJoCo 3.12): 9/9.
- [x] G0.1 via B0 (B2-W zero-agent) on both backends. That is a stronger check than Cartpole.
  - PhysX needed `roboforge/compat.py` for the upstream schema clash; see master D-010.
- [x] B1 throughput matrix: [benchmarks/](../benchmarks/TRACKER.md#results).
- [ ] B2 sustained ≥ 30 min, and B3 1500-iteration B2-W flat (running).
- [ ] Depth probe at 256 / 512 / 1024 envs (G0.4).
- [ ] Seeds variance (G0.5).
- [ ] Sky: reboot (long paths fully active for all processes), then from your own terminal: `. .\scripts\env.ps1; uv run pytest -q`.

### Gates

| Gate | Criterion `[EST]` | Result |
|---|---|---|
| G0.1 | Both backends run Windows-native | ✅ newton_mjwarp; ✅ ovphysx (with compat shim) |
| G0.2 | 4096 envs: VRAM ≤ 7.5 GB, RAM ≤ 13 GB, full rough run ≤ 3 h | VRAM ✅ 3.2 GB, RAM ✅ 3.4 GB. ❌ **time**: robot_lab's default 20 000 rough iterations ≈ 20 h at 27k steps/s. Flat 5 000 iterations ≈ 2.4 h ✅. Verdict pending B3: if policies converge well below the default budget, rough stays local overnight; otherwise production rough runs go to AWS |
| G0.3 | `ovphysx` runs locally | ✅ (compat shim) |
| G0.4 | Depth env ≥ 512 envs in 7.5 GB | ⬜ |
| G0.5 | Seed variance recorded | ⬜ |

### AWS

- [ ] Sky: account and IAM, **request a G-instance vCPU quota**, S3 bucket for runs, budget alarm.
- [ ] One `g6e.xlarge` (L40S 48 GB) or `g5.xlarge` (A10G 24 GB), Ubuntu 24.04, driver ≥ 580.65. Run `bash scripts/setup_workspace.sh` and the B1 matrix to calibrate.
- Prices `[EST, verify]`: g5.xlarge ≈ $1.0/h, g6e.xlarge ≈ $1.9/h on-demand; spot ~60–70% cheaper.

## Scripts in this folder

| Script | Purpose | Status |
|---|---|---|
| `env.ps1` | Workspace environment (PATH to uv, caches on the workspace drive, UTF-8) | ✅ |
| `setup_workspace.ps1` / `.sh` | Submodules + uv sync + tests + list tasks | ✅ (Windows path exercised step by step) |
| `build_robot.py` | Robot spec → canonical MJCF + contract check (+ `--view`) | ✅ |
| `bench_training.py` | Runs `isaaclab train`, samples GPU/RAM every 2 s, writes `benchmarks/results/*.json` | ✅ |
| *(moved)* | Policy evaluation and playback now live in the package: `uv run rf eval` / `rf play` (see [experiments/](../experiments/TRACKER.md)) | — |
| `upstream.py` | `status` / `available` / `try` newer Isaac Lab or robot_lab on its own branch | ✅ `status` verified; `try` untested |

## Done

- 2026-11-12 Toolchain up. B0 and B1 done (results in benchmarks/). Eval and upstream scripts written.
- 2026-11-12 `build_robot.py` and setup scripts written; machine facts measured.
