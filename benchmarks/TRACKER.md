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
| B2 | Sustained (thermal) throughput | One ≥ 30 min run; compare first-quarter vs last-quarter steps/s | ✅ |
| B3 | Training to a usable policy | Flat B2-W and Go2-W, time-boxed; record wall time to plateau | 🟨 B2-W flat (Newton) done; Go2-W ⬜ |
| B4 | Capability vs real (`scripts/eval_policy.py`) | Command sweep up to the *real* top speed (slope/step tests later). "Real-range" variant `RoboForge-Velocity-Flat-B2W-RealRange-v0`: commands to 4.17 m/s, wheels 40 N·m `[U]` | 🟨 default policy done; real-range ⬜ |
| B5 | Cross-engine | Train on `newton_mjwarp`, play on `ovphysx`, and the reverse | 🟨 NP done (fails to drive); PhysX-trained run in progress |

**Benchmark robots:** Unitree B2-W (our class: 85 kg `[U]`) and Go2-W (18 kg `[U]`), with
robot_lab v3.0.0 tasks unchanged.

**Already known before running anything** (from `reference_robots.yaml`): robot_lab's default
commands are ±1 m/s, but the real B2-W is rated 4.17 m/s and the Go2-W 2.5 m/s `[U]`. Its B2-W
wheel torque limit is 20 N·m `[CFG]` against 40 N·m real `[U]`. Default-config policies
therefore can't show real top-speed capability; B4 exists to measure that gap.

## Version and backend compatibility matrix

| Isaac Lab | robot_lab | Physics | B0 | B1 | B3 | Notes |
|---|---|---|---|---|---|---|
| v3.0.0 | v3.0.0 | `newton_mjwarp` | ✅ | ✅ | ✅ flat | Pinned pair (default) |
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

### B2 — sustained throughput `[MEAS]` (B2-W flat, Newton, 4096 envs, 1 500 iterations)

| Wall time | Median steps/s | vs 30-iteration burst | Peak °C | VRAM | RAM |
|---|---|---|---|---|---|
| 51.5 min | 49 340 | −12% (burst 55 951) | 87 | 3.1 GB | 2.6 GB |

The GPU sits at its thermal limit (86–87 °C, ~97–121 W) and loses ~12% throughput. Plan with
the **sustained** numbers: ≈ 2.0 s/iteration flat, so robot_lab's default 5 000 flat
iterations ≈ 2.8 h.

### B3 — learning curve, B2-W flat on Newton (robot_lab defaults, seed 42)

| Iteration | 0 | 50 | 200 | 400 | 600 | 1000 | 1500 |
|---|---|---|---|---|---|---|---|
| Wall time | 0 | ~2 min | ~7 min | ~14 min | ~20 min | ~34 min | 51.5 min |
| Mean episode length (of 1000) | 12 | 1000 | 1000 | 1000 | 1000 | 1000 | 1000 |
| Linear tracking reward | 0.00 | 0.16 | 0.45 | 1.11 | 1.35 | 1.62 | 1.72 |
| Yaw tracking reward | 0.00 | 0.18 | 0.29 | 0.39 | 0.34 | 0.39 | 0.44 |

No falls after ~50 iterations. Tracking is still rising at 1 500 (not plateaued). One seed only.

### B4 — capability vs the real B2-W (policy above, 384 robots, 10 s per speed)

| Command (m/s) | 0.5 | 1.0 | 1.5 | 2.0 | 3.0 | 4.17 (real rated `[U]`) |
|---|---|---|---|---|---|---|
| Achieved on Newton (m/s) | 0.38 | 0.69 | 1.16 | 1.33 | 1.81 | 1.82 |
| Falls | 0% | 0% | 0% | 0% | 0% | 0% |

- The sim policy undershoots by 25–30% even inside its ±1 m/s training range, and **tops out at
  ~1.8 m/s**, against the real machine's rated **4.17 m/s**.
- Expected causes, in order:
  1. Trained on ±1 m/s commands only `[CFG]`.
  2. Wheel torque at half the real value (20 vs 40 N·m).
  3. Training not converged (1 500 of the default 5 000 iterations).
- The real-range variant isolates causes 1 and 2.

### B5 — cross-engine (same checkpoint played on PhysX)

| Command (m/s) | 0.5 | 1.0 | 2.0 | 4.17 |
|---|---|---|---|---|
| Newton (trained here) | 0.38 | 0.69 | 1.33 | 1.82 |
| PhysX, default ordering | 0.06 | 0.06 | 0.12 | 0.24 |
| PhysX, `mjwarp` joint/body ordering | 0.04 | 0.05 | 0.14 | 0.27 |
| PhysX, ordering + robot friction pinned to 1.0 | 0.06 | 0.07 | 0.19 | 0.27 |

Result files, in table order: `20261112-203941` (Newton), `-204106`, `-204326`, `-204654`.
Later eval files also record their full argv.

- **The Newton-trained policy does not transfer to PhysX.** It stays upright (0 falls) but barely
  drives.
- **Ruled out:** joint/body ordering. Both engines report identical joint and body lists with the
  override.
- **Not sufficient alone:** the friction max-vs-multiply difference (Isaac Lab #8869; robot_lab
  randomizes robot μ 0.3–1.0, which Newton masks to 1.0).
- **Wheels spin at similar speeds and torques on both engines**, so the remaining suspects are
  wheel–ground contact (cylinder vs convex representation, contact softness) and drive semantics.
- Gate G2.3 (constant-torque wheel test, both engines) is the controlled experiment that isolates
  this. Until it passes, **no wheeled policy is trusted on either engine alone**.
- Next: a PhysX-trained policy played on Newton gives the PN direction, and tells us which engine
  can learn to drive at all.

## Done

- 2026-11-12 B2 (sustained −12%), B3 (B2-W flat learning curve), B4 (tops out at 1.8 vs 4.17 m/s real), B5 NP (does not transfer; ordering ruled out).
- 2026-11-12 B0 (both backends) and B1 (9 configurations) on the pinned pair.
- 2026-11-12 Protocol, reference data and harness (`scripts/bench_training.py`) written.
