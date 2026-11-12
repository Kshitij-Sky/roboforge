# RoboForge — master tracker

The **only** status document in this repo. It is the at-a-glance view; details live in the
linked sub-trackers. **Update protocol:** when you finish a task, tick it in its sub-tracker,
update its row in the status board here and add a line to the Done log. All three go in the
same commit.

**Last updated:** 2026-11-12

---

## Snapshot

**Where we are:** the training stack runs on the laptop.
- Isaac Lab 3.0.0 + robot_lab 3.0.0 are pinned as submodules; both physics engines (Newton
  MuJoCo-Warp and PhysX) train Windows-native.
- Benchmarks B0 and B1 are done:
  - B2-W/Go2-W train at ~56k steps/s on flat ground and ~26–27k on rough at 4096 envs, using
    ≤ 3.2 GB of VRAM.
  - Heat, not memory, is the limit (85 °C).
- A 1 500-iteration B2-W policy is training to measure time-to-usable-policy and sustained
  thermals.
- The capability evaluation against real-robot specs is written and its mechanics are verified.

**Next actions**

| # | Who | Action | Sub-tracker |
|---|---|---|---|
| 1 | Claude | Finish B2/B3: report the sustained-throughput drift and the learning curve of the 1 500-iteration run | [benchmarks](benchmarks/TRACKER.md) |
| 2 | Claude | B4: evaluate that policy against the real B2-W, then train the "real-range" variant (commands to 4.17 m/s, wheel torque 40 N·m `[U]`) | [benchmarks](benchmarks/TRACKER.md) |
| 3 | Claude | B5: same policy on PhysX (cross-engine) | [benchmarks](benchmarks/TRACKER.md) |
| 4 | Sky | Add what you have actually seen real B2-W / Go2-W do to `benchmarks/reference_robots.yaml` → `observed_by_sky` (`[OBS]`, with where/how) | [benchmarks](benchmarks/TRACKER.md) |
| 5 | Sky | Reboot once (long paths), then from your own terminal: `. .\scripts\env.ps1; uv run pytest -q` | [scripts](scripts/TRACKER.md) |
| 6 | Sky | Request an AWS G-instance quota (needed if rough-terrain budgets stay at ~20 h locally) | [scripts](scripts/TRACKER.md#aws) |

## Status board

⬜ not started · 🟨 in progress · ✅ done (all gates pass) · ⛔ blocked

| Phase | What | Status | Gates | Sub-tracker |
|---|---|---|---|---|
| P0 | Toolchain + machine qualification (local vs AWS) | 🟨 | G0.1 ✅ · G0.2 🟨 (time) · G0.3 ✅ · G0.4–G0.5 ⬜ | [scripts/](scripts/TRACKER.md) |
| B | Benchmarks: existing robots on this machine vs the real machines | 🟨 | B0 ✅ · B1 ✅ · B2–B3 🟨 · B4–B5 ⬜ | [benchmarks/](benchmarks/TRACKER.md) |
| P1 | Robot description pipeline: parametric ✅ · SolidWorks ⬜ · MJCF→USD ⬜ | 🟨 | G1.1 ✅ · G1.2–G1.3 ⬜ | [robots/](robots/TRACKER.md), [tools/](tools/TRACKER.md) |
| P2 | Model validation: conversion round-trip, RL-grade vs MBD-grade, PhysX equivalence | ⬜ | G2.1–G2.3 | [tools/](tools/TRACKER.md) |
| P3 | Actuator + sensor models (incl. thermal) | ⬜ | G3.1–G3.3 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P4 | Blind wheeled-legged locomotion (B2-W reference → v1) | ⬜ | G4.1–G4.2 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P5 | Cross-engine evaluation harness | 🟨 `eval_policy.py` speed sweep | G5 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P6 | Depth perception (height-scan teacher → depth student) | ⬜ | G6 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P7 | Deploy runtime + sim-in-the-loop | ⬜ | G7.1–G7.3 | [deploy/](deploy/TRACKER.md) |
| P8 | Real-to-sim loop (MCAP logs, sysid, refit) | ⬜ | — | [tools/](tools/TRACKER.md) |
| P9 | Humanoid generality check | ⬜ | — | [src/roboforge/](src/roboforge/TRACKER.md) |

## Needs from Sky

| # | Question | Blocks | Default until answered |
|---|---|---|---|
| N4 | SolidWorks version (2021 / 2024 / 2025 / 3DEXPERIENCE)? | P1 SolidWorks path | Try the official exporter first |
| N5 | Depth camera model, mount position and tilt? | P6 | RealSense D435i-class, front, pitched down |
| N6 | Onboard computer and OS (Jetson Orin? x86? ROS 2?) | P7 | Generic Linux + onnxruntime |
| N7 | Driver control modes: RS04 / QDD MIT-mode PD over CAN? Hub motor in torque or velocity mode? | P3, P7 | MIT PD legs, velocity-loop wheels |
| N8 | AWS region and monthly cap | Cloud runs | ap-south-1 if G-instances are available there |
| N9 | What you've observed real B2-W / Go2-W do (speed, slopes, steps, payload) | B4 comparison | Unitree spec sheet `[U]` only |

Closed: N1/N2 (fresh public repo `Kshitij-Sky/roboforge`), N3 (long paths enabled, uv installed).

## Building blocks — what we reuse vs build

| Gap the pipeline needs | Covered by | Coverage | Our work |
|---|---|---|---|
| RL framework, multi-engine (MuJoCo-Warp ↔ PhysX), RSL-RL, distillation, ray caster, depth cameras, ONNX/LEAPP export | **Isaac Lab 3.0.0** (submodule) | ✅ | Configure |
| Isaac Lab 3.0 external-project template; wheeled-legged velocity tasks (B2-W, Go2-W, M20, Tita…) and MDP terms; humanoid tasks | **robot_lab v3.0.0** (submodule) | ✅ | Subclass for v1 |
| Robot-side runtime, MuJoCo/Gazebo sim-to-sim, real Unitree deploys (libtorch/onnxruntime) | **rl_sar** | 🟨 Linux/ROS, no latency or golden obs tests | Evaluate in P7 |
| Fair cross-robot benchmarking, multi-seed analysis | **quadrrl** (Isaac Lab 2.3.2) | 🟨 needs port to 3.0 | Port the idea in P5 |
| Robot contract, parametric model, provenance enforcement | ours | ✅ M0 done | — |
| Training/hardware benchmark, capability-vs-real eval | ours (`bench_training.py`, `eval_policy.py`) | ✅ first version | Extend in B4/B5 |
| SolidWorks → MJCF importer + CAD conventions | — | ❌ | P1 |
| MJCF → USD with round-trip proof | Isaac Lab converter, no verification | 🟨 | P1/P2 |
| Actuator thermal model, randomized delay, driver PD at real rate | Isaac Lab DCMotor (clamp only) | 🟨 | P3 |
| IMU / encoder / depth noise models | Isaac Lab additive noise only | 🟨 | P3/P6 |
| Golden obs-parity tests, sim-in-the-loop at MBD-grade dt | — | ❌ | P7 |
| Log format + real-to-sim refit loop | `mujoco.sysid` (fitting only) | 🟨 | P8 |

## Pinned versions

| Component | Version | How pinned |
|---|---|---|
| Isaac Lab | v3.0.0 (`e3f7d9ff1`) | submodule `third_party/IsaacLab` |
| robot_lab | v3.0.0 (`26acb22`) | submodule `third_party/robot_lab` |
| Python | 3.12.16 (uv-managed) | `pyproject.toml` |
| Newton | 1.6.1 | `uv.lock` |
| MuJoCo / MuJoCo-Warp | 3.12.0 / 3.12.0 | `uv.lock` |
| Warp | 1.17.0 | `uv.lock` |
| OVPhysX | 0.6.4 | `uv.lock` |
| PyTorch | 2.11.0+cu130 | `uv.lock` |
| RSL-RL | 5.5.1 | `uv.lock` |

Change upstreams only with `scripts/upstream.py try …`. It works on its own branch and the
change is merged only if it wins on the benchmark protocol.

## Decisions

Dated, newest first. A decided entry is never edited; it is superseded by a new one.

- **D-011 (2026-11-12)** Every tool, cache and Python runtime lives inside the workspace folder
  (`<workspace>\.tools`, `<workspace>\.cache`), set by `scripts/env.ps1`. Reason: the Claude
  desktop app is MSIX-sandboxed, so its writes to `C:\Users\…\AppData` are redirected to a
  private store that the user's own terminal never sees.
- **D-010 (2026-11-12)** Upstream bugs are worked around in `src/roboforge/compat.py`, never by
  editing submodules. Each workaround names its target versions and is inert unless triggered.
  First entry: the importer/OVPhysX USD schema clash.
- **D-009 (2026-11-12)** Upstreams are **git submodules pinned to exact commits** in
  `third_party/`. Updating means bumping the pin; we never copy their code. robot_lab's own
  `../IsaacLab` path resolves to `third_party/IsaacLab` unchanged.
- **D-008 (2026-11-12)** Version choice: **Isaac Lab v3.0.0 + robot_lab v3.0.0** (robot_lab main
  = its v3.0.0 tag; it is the only robot_lab release for Isaac Lab 3).
  - *Why not stay on v2.3.2 for "proven" sim-to-real:* the proof lives in the **PhysX** engine,
    not the Isaac Lab version, and v3.0.0 still runs PhysX (`ovphysx` here, `isaacsim_physx`
    on AWS). v2.3.2 would need full Isaac Sim 5.1 (32 GB RAM plan vs our 16 GB), Python 3.11,
    and a later migration.
  - *Why not Isaac Lab main:* it has useful post-3.0.0 fixes (noise-bias accumulation, MJWarp
    resets) but is mid-refactor (Newton Manager redesign, Newton 1.9 bump).
  - *The "try which works best" provision* is the **physics backend** (Newton vs PhysX, same
    task code) plus `upstream.py try` for newer tags.
- **D-007 (2026-11-12)** License: Apache-2.0, "The RoboForge Authors". Third-party robot assets
  are never redistributed; they are fetched from upstream. Adapted code keeps its header and is
  credited in the README.
- **D-006 (2026-11-12)** Base on **robot_lab v3.0.0** (as a dependency), not quadrrl.
  - quadrrl is pinned to Isaac Lab 2.3.2.
  - Its wheeled-legged code is robot_lab's: the file headers say Ziqi Fan, Apache-2.0.
  - robot_lab already targets Isaac Lab 3.0 with Newton as the default backend.
  - Kept from quadrrl: the Fair-Morph benchmark idea, to be ported in P5.
- **D-005 (2026-11-12)** Robot contract uses Unitree joint naming,
  `{FL,FR,RL,RR}_{hip,thigh,calf,wheel}_joint`, so robot_lab tasks and rl_sar configs line up.
  v1 joint torque and speed limits are derived from motor datasheets.
  - This replaces the earlier hand-set targets.
  - The old hip speed target of 22 rad/s exceeded the RS04's 20.9 rad/s [3P].
- **D-004 (2026-11-12)** Model fidelity levels M0–M4 are stamped on every policy. Below M3,
  nothing goes to hardware.
- **D-003 (2026-11-12)** Single framework: **Isaac Lab 3.0**.
  - Train on `newton_mjwarp`.
  - Cross-check on `ovphysx` (kit-less PhysX).
  - Final sim gate: sim-in-the-loop against MuJoCo CPU.
  - mjlab is the fallback.
  - Isaac Sim (Kit) is not installed on the 8 GB laptop.
- **D-002 (2026-11-12)** SolidWorks is the CAD of record, exporting URDF + STL. Our importer
  turns that into the canonical MJCF; USD and URDF are generated from it. The parametric spec
  stays as the pre-CAD source.
- **D-001 (2026-11-12)** Quadruped first. Vision is depth-only. Humanoids come later in this
  same repo; VLA and world models go in separate repos.

## Rules

1. **Every number carries a provenance tag:**
   - `[U]` Unitree, `[DR]` Deep Robotics, `[3P]` third party, `[URDF]` robot description
   - `[EST]` our estimate, `[WB]` old design workbench, `[MEAS]` our bench
   - `[OBS]` observed by Sky on a real robot (informal; say where and how)
   - `[CFG]` read from an upstream sim config

   An untagged number is a bug; tests enforce this for `robot.yaml` and
   `benchmarks/reference_robots.yaml`.
2. **Peak is not continuous.** Use datasheet continuous ratings until our own bench measures them.
3. **Every public claim must be reproducible on a bench we own.**
4. **Never quote an absolute impact force from MuJoCo** without its `solref` spread.
5. **Generated files are never hand-edited:** `robots/*/build/`. Change the spec or the
   generator instead.
6. **Correct yourself out loud.** A wrong number is retracted in the Decisions or Done log, not
   quietly fixed.
7. **Third-party code** keeps its license header and gets a credits line in the README.
   Submodules are never edited.
8. **No new documents.** Status goes here and in the sub-trackers. Explanations go in code
   docstrings or the README.

## Done log

Newest first.

- **2026-11-12** Training stack and first benchmarks.
  - Submodules pinned: Isaac Lab v3.0.0, robot_lab v3.0.0.
  - `uv sync`: 184 packages, uv.lock committed. Tests 9/9 in the uv env.
  - **B0 ✅** B2-W loads and steps on Newton and on PhysX. PhysX required the compat shim for an
    upstream USD-schema clash.
  - **B1 ✅** 9 configurations (numbers in [benchmarks](benchmarks/TRACKER.md#results)).
  - `bench_training.py`, `eval_policy.py` (speed sweep vs real rated speed) and `upstream.py`
    written. The eval mechanics are verified.
  - **Found:** Isaac Lab #8869 (friction randomization is a no-op on Newton by default; the
    same max-friction rule we fixed in our own generator) and #8796 (Newton ray caster
    self-hits on a wheeled quadruped). Both are logged in benchmarks/ with mitigations.
  - **Found:** robot_lab's B2-W trains on ±1 m/s commands with 20 N·m wheels, against a real
    rated 4.17 m/s and 40 N·m `[U]`.
- **2026-11-12** Repo created at `D:\RoboForge\roboforge`.
  - Ported the parametric v1 generator from the earlier rough work, cleaned: contract names,
    IMU site, explicit inertials enforced, linkage/variant machinery dropped, motor library
    folded into `robot.yaml` with supplier prices removed.
  - **Fixed an inherited modelling bug:** MuJoCo takes the max of two geoms' friction, so the
    tyre's μ=0.8 was silently overridden by the floor's 1.0. The tyre now has contact priority,
    and a test checks it.
  - G1.1 passes. v1 at M0 = 65.06 kg [EST/3P mix].
- **2026-11-12** Framework survey and implementation plan done as rough work in `D:\Robots`.
  It is not carried over; its conclusions are D-001 to D-004.
