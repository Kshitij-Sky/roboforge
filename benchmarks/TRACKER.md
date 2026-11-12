# benchmarks/ — sub-tracker (existing robots on this machine vs the real machines)

← [Master tracker](../TRACKER.md) · What can this laptop train, how well, and how does it
compare with what the real robots do?

Files in this folder:
- `reference_robots.yaml`: real-robot values (`[U]`/`[3P]`/`[OBS]`) next to what the robot_lab sim configs assume (`[CFG]`).
- `results/`: one `.json` + `.log` per run from `scripts/bench_training.py`, plus `summary.csv`.

## Protocol

| ID | What | How | Status |
|---|---|---|---|
| B0 | Smoke: each task loads and steps on each backend | `isaaclab zero_agent`, 4 envs, 100 steps | ✅ B2-W flat, both backends |
| B1 | Throughput and memory at 1024 / 2048 / 4096 / 8192 envs | `bench_training.py`, 30 iterations, `newton_mjwarp` and `ovphysx` | ✅ |
| B2 | Sustained (thermal) throughput | One ≥ 30 min run; compare first-quarter vs last-quarter steps/s | 🟨 running |
| B3 | Training to a usable policy | Flat B2-W and Go2-W, time-boxed; record wall time to plateau | 🟨 B2-W flat 1500 it running |
| B4 | Capability vs real (`scripts/eval_policy.py`, mechanics verified) | Command sweep up to the *real* top speed, slope and step tests, using a P5-lite eval script. Also a "real-range" variant: commands up to `[U]` max speed and wheel torque at `[U]` 40 N·m (B2-W) | ⬜ |
| B5 | Cross-engine | Train on `newton_mjwarp`, play on `ovphysx`, and the reverse | ⬜ |

**Benchmark robots:** Unitree B2-W (our class: 85 kg `[U]`) and Go2-W (18 kg `[U]`), with
robot_lab v3.0.0 tasks unchanged.

**Already known before running anything** (from `reference_robots.yaml`): robot_lab's default
commands are ±1 m/s, but the real B2-W is rated 4.17 m/s and the Go2-W 2.5 m/s `[U]`. Its B2-W
wheel torque limit is 20 N·m `[CFG]` against 40 N·m real `[U]`. Default-config policies
therefore can't show real top-speed capability; B4 exists to measure that gap.

## Version and backend compatibility matrix

| Isaac Lab | robot_lab | Physics | B0 | B1 | B3 | Notes |
|---|---|---|---|---|---|---|
| v3.0.0 | v3.0.0 | `newton_mjwarp` | ✅ | ✅ | 🟨 | Pinned pair (default) |
| v3.0.0 | v3.0.0 | `ovphysx` | ✅ | ✅ | ⬜ | PhysX lineage = the engine with the long sim-to-real record. Needs `roboforge/compat.py` (importer schema clash, upstream bug) |
| v3.0.0 | v3.0.0 | `isaacsim_physx` | — | — | — | Needs full Isaac Sim 6.2 (16 GB VRAM / 32 GB RAM plan `[3P]`) — AWS only |
| v2.3.2 | v2.3.2 | PhysX (Isaac Sim 5.1) | — | — | — | Different Python (3.11) and API; needs full Isaac Sim — AWS only if ever needed |

Switch versions with `scripts/upstream.py try ...` (its own branch). Merge only if it beats the
pinned pair on B1/B3/B5.

## Known upstream issues that affect fidelity (v3.0.0)

| Issue | Effect | Our mitigation |
|---|---|---|
| [IsaacLab #8869](https://github.com/isaac-sim/IsaacLab/issues/8869) (open) | MJWarp combines friction with **max**: terrain μ=1.0 masks robot-friction randomization, so friction DR is silently a no-op on Newton | Randomize terrain friction, or set terrain μ to the bottom of the DR range. Fix PR #8877 not merged |
| [IsaacLab #8796](https://github.com/isaac-sim/IsaacLab/issues/8796) (closed 10-29, after v3.0.0) | Newton ray caster hits the robot's own geometry → corrupt height scans; reported on a **wheeled quadruped** | Check height scans on flat ground in B0; compare with `ovphysx` |
| IsaacLab #8634 (fixed on main 10-30, after v3.0.0) | Additive observation-noise bias accumulates across resets | Pick up via `upstream.py try` once a 3.0.x tag ships; until then, noise DR results are suspect |
| IsaacLab #8978 (open) | Startup screen raises UnicodeEncodeError when stdout is redirected on non-UTF-8 Windows locales | `bench_training.py` forces `PYTHONUTF8=1` |
| *(found by us, not yet filed)* | `importers` + `ovphysx` in one env: robot_lab imports the URDF importer at load, which registers `physxSchemaFallback`; OVPhysX then fails to register `physxSchema` (`Tf.ErrorException`). Isaac Lab main has the same name-based check | `roboforge/compat.py` registers OVPhysX's schemas first, only when `ovphysx` is requested |

## Results

### B1 — throughput on the RTX 3070 Ti Laptop `[MEAS]` (2026-11-12, 30 PPO iterations each)

One iteration = num_envs × 24 steps. Steps/s is the median of the second half of the run.
VRAM is the nvidia-smi peak, including ~0.2 GB idle.

| Task (robot_lab v3.0.0) | Physics | Envs | Steps/s | VRAM GB | RAM GB | Peak °C | s / iteration |
|---|---|---|---|---|---|---|---|
| B2-W flat | newton_mjwarp | 1024 | 23 592 | 0.9 | 2.4 | 64 | 1.04 |
| B2-W flat | newton_mjwarp | 2048 | 35 149 | 1.5 | 2.4 | 67 | 1.40 |
| B2-W flat | newton_mjwarp | 4096 | **55 951** | 2.7 | 2.6 | 72 | 1.76 |
| B2-W flat | newton_mjwarp | 8192 | 73 458 | 4.9 | 2.8 | 78 | 2.68 |
| B2-W flat | ovphysx | 4096 | 55 838 | 4.4 | 5.3 | 71 | 1.76 |
| B2-W rough | newton_mjwarp | 4096 | **27 152** | 3.2 | 3.4 | 82 | 3.62 |
| B2-W rough | ovphysx | 4096 | 19 227 | 5.5 | 5.8 | 85 | 5.11 |
| Go2-W flat | newton_mjwarp | 4096 | 55 119 | 2.4 | 2.6 | 82 | 1.78 |
| Go2-W rough | newton_mjwarp | 4096 | 25 680 | 3.2 | 2.9 | 85 | 3.83 |

**What this means at robot_lab's default training budgets** (4096 envs, no throttling assumed):

| Run | Default iterations `[CFG]` | Newton | PhysX |
|---|---|---|---|
| B2-W / Go2-W flat | 5 000 | ≈ 2.4 h | ≈ 2.4 h |
| B2-W rough | 20 000 | ≈ 20 h | ≈ 28 h |
| Go2-W rough | 20 000 | ≈ 21 h | — |

**Findings:**
- **Memory is not the limit.** 8 GB fits 8 192 flat envs. The GPU's compute and **heat** are the limits: 85 °C within 3 minutes on rough terrain.
- **Newton = PhysX on flat ground; Newton is 1.4× faster on rough** (terrain mesh + ray caster), with ~40% less VRAM and half the RAM.
- **Rough-terrain training at robot_lab's default budget is an overnight-plus job here.** Whether that budget is needed is what B3 measures.

## Done

- 2026-11-12 B0 (both backends) and B1 (9 configurations) on the pinned pair.
- 2026-11-12 Protocol, reference data and harness (`scripts/bench_training.py`) written.
