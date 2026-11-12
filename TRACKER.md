# RoboForge — master tracker

The **only** status document in this repo. It is the at-a-glance view; details live in the
linked sub-trackers. **Update protocol:** when you finish a task, tick it in its sub-tracker,
update its row in the status board here and add a line to the Done log. All three go in the
same commit.

**Last updated:** 2026-11-12

---

## Snapshot

**Where we are:** the repo skeleton exists. The robot-description layer is ported and tested:
the v1 parametric model builds, passes the robot contract, and holds a stand in MuJoCo (8/8
tests). The training stack is not installed yet.

**Next actions**

| # | Who | Action | Sub-tracker |
|---|---|---|---|
| 1 | Sky | Decide the GitHub setup: fresh repo or force-push into the Newton fork; public or private (see Needs §) | — |
| 2 | Sky | Enable Windows long paths (admin, one command, then reboot) | [scripts](scripts/TRACKER.md#p0--toolchain-and-machine-qualification) |
| 3 | Claude | Install uv, clone pinned upstreams, first `uv sync` | [scripts](scripts/TRACKER.md#p0--toolchain-and-machine-qualification) |
| 4 | Claude | Benchmark robot_lab B2-W / Go2-W and Isaac Lab Go2-rough on `newton_mjwarp`, ≥ 30 min sustained (G0.2) | [scripts](scripts/TRACKER.md#gates) |
| 5 | Sky | Request an AWS G-instance quota (new accounts often start at 0) | [scripts](scripts/TRACKER.md#aws) |

## Status board

⬜ not started · 🟨 in progress · ✅ done (all gates pass) · ⛔ blocked

| Phase | What | Status | Gates | Sub-tracker |
|---|---|---|---|---|
| P0 | Toolchain + machine qualification (local vs AWS) | ⬜ | G0.1–G0.5 | [scripts/](scripts/TRACKER.md) |
| P1 | Robot description pipeline: parametric ✅ · SolidWorks ⬜ · MJCF→USD ⬜ | 🟨 | G1.1 ✅ · G1.2–G1.3 ⬜ | [robots/](robots/TRACKER.md), [tools/](tools/TRACKER.md) |
| P2 | Model validation: conversion round-trip, RL-grade vs MBD-grade, PhysX equivalence | ⬜ | G2.1–G2.3 | [tools/](tools/TRACKER.md) |
| P3 | Actuator + sensor models (incl. thermal) | ⬜ | G3.1–G3.3 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P4 | Blind wheeled-legged locomotion (B2-W reference → v1) | ⬜ | G4.1–G4.2 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P5 | Cross-engine evaluation harness | ⬜ | G5 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P6 | Depth perception (height-scan teacher → depth student) | ⬜ | G6 | [src/roboforge/](src/roboforge/TRACKER.md) |
| P7 | Deploy runtime + sim-in-the-loop | ⬜ | G7.1–G7.3 | [deploy/](deploy/TRACKER.md) |
| P8 | Real-to-sim loop (MCAP logs, sysid, refit) | ⬜ | — | [tools/](tools/TRACKER.md) |
| P9 | Humanoid generality check | ⬜ | — | [src/roboforge/](src/roboforge/TRACKER.md) |

## Needs from Sky

| # | Question | Blocks | Default until answered |
|---|---|---|---|
| N1 | GitHub: the target repo is a **fork of newton-physics/newton**. Forks stay labelled "forked from…", can't be made private, and live in Newton's fork network. Delete the fork and create a fresh empty `roboforge`, or force-push into the fork? | Push | Hold the push |
| N2 | Public or private repo? A public repo publishes the v1 design parameters in `robots/v1_wheeled_quad/robot.yaml`. | Push | Private |
| N3 | Enable Windows long paths; OK to install uv (user-level)? | P0 | — |
| N4 | SolidWorks version (2021 / 2024 / 2025 / 3DEXPERIENCE)? | P1 SolidWorks path | Try the official exporter first |
| N5 | Depth camera model, mount position and tilt? | P6 | RealSense D435i-class, front, pitched down |
| N6 | Onboard computer and OS (Jetson Orin? x86? ROS 2?) | P7 | Generic Linux + onnxruntime |
| N7 | Driver control modes: RS04 / QDD MIT-mode PD over CAN? Hub motor in torque or velocity mode? | P3, P7 | MIT PD legs, velocity-loop wheels |
| N8 | AWS region and monthly cap | P0 (cloud) | ap-south-1 if G-instances are available there |

## Building blocks — what we reuse vs build

| Gap the pipeline needs | Covered by | Coverage | Our work |
|---|---|---|---|
| RL framework, multi-engine (MuJoCo-Warp ↔ PhysX), RSL-RL, distillation, ray caster, depth cameras, ONNX/LEAPP export | **Isaac Lab 3.0.0** | ✅ | Configure |
| Isaac Lab 3.0 external-project template; wheeled-legged velocity tasks (B2-W, Go2-W, M20, Tita…) and MDP terms; humanoid tasks | **robot_lab v3.0.0** (dependency) | ✅ | Subclass for v1 |
| Robot-side runtime, MuJoCo/Gazebo sim-to-sim, real Unitree deploys (libtorch/onnxruntime) | **rl_sar** | 🟨 Linux/ROS, no latency or golden obs tests | Evaluate in P7 |
| Fair cross-robot benchmarking, multi-seed analysis | **quadrrl** (Isaac Lab 2.3.2) | 🟨 needs port to 3.0 | Port the idea in P5 |
| Robot contract, parametric model, provenance enforcement | ours | ✅ M0 done | — |
| SolidWorks → MJCF importer + CAD conventions | — | ❌ | P1 |
| MJCF → USD with round-trip proof | Isaac Lab converter, no verification | 🟨 | P1/P2 |
| Actuator thermal model, randomized delay, driver PD at real rate | Isaac Lab DCMotor (clamp only) | 🟨 | P3 |
| IMU / encoder / depth noise models | Isaac Lab additive noise only | 🟨 | P3/P6 |
| Cross-engine eval harness with pass thresholds | — | ❌ | P5 |
| Golden obs-parity tests, sim-in-the-loop at MBD-grade dt | — | ❌ | P7 |
| Log format + real-to-sim refit loop | `mujoco.sysid` (fitting only) | 🟨 | P8 |

## Pinned versions

| Component | Version |
|---|---|
| Isaac Lab | v3.0.0 |
| robot_lab | v3.0.0 |
| Python | 3.12 |
| Newton | 1.6.1 |
| MuJoCo / MuJoCo-Warp | ~3.12 |
| PyTorch | 2.11 (cu130) |
| RSL-RL | 5.5.1 (via Isaac Lab) |

Source of truth: `pyproject.toml`. Upgrades are deliberate and re-run every gate.

## Decisions

Dated, newest first. A decided entry is never edited; it is superseded by a new one.

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

1. **Every number carries a provenance tag:** `[U]` `[DR]` `[3P]` `[URDF]` `[EST]` `[WB]`
   `[MEAS]`. An untagged number is a bug; tests enforce this for `robot.yaml`.
2. **Peak is not continuous.** Use datasheet continuous ratings until our own bench measures them.
3. **Every public claim must be reproducible on a bench we own.**
4. **Never quote an absolute impact force from MuJoCo** without its `solref` spread.
5. **Generated files are never hand-edited:** `robots/*/build/`. Change the spec or the
   generator instead.
6. **Correct yourself out loud.** A wrong number is retracted in the Decisions or Done log, not
   quietly fixed.
7. **Third-party code** keeps its license header and gets a credits line in the README.
8. **No new documents.** Status goes here and in the sub-trackers. Explanations go in code
   docstrings or the README.

## Done log

Newest first.

- **2026-11-12** Repo created at `D:\RoboForge\roboforge`.
  - Ported the parametric v1 generator from the earlier rough work, cleaned: contract names,
    IMU site, explicit inertials enforced, linkage/variant machinery dropped, motor library
    folded into `robot.yaml` with supplier prices removed.
  - **Fixed an inherited modelling bug:** MuJoCo takes the max of two geoms' friction, so the
    tyre's μ=0.8 was silently overridden by the floor's 1.0. The tyre now has contact priority,
    and a test checks it.
  - G1.1 passes. 8/8 tests pass (MuJoCo 3.10, run with the old venv until P0).
  - v1 at M0 = 65.06 kg [EST/3P mix].
- **2026-11-12** Framework survey and implementation plan done as rough work in `D:\Robots`.
  It is not carried over; its conclusions are D-001 to D-004.
