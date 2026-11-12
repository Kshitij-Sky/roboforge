# robots/ — sub-tracker (robot models, contract, fidelity)

← [Master tracker](../TRACKER.md) · One folder per robot: `robot.yaml` (or a CAD export) plus
`build/`, which is generated and never hand-edited.

## Robot inventory

| Robot | Source | Fidelity | Contract (G1.1) | Notes |
|---|---|---|---|---|
| `v1_wheeled_quad` | parametric `robot.yaml` | **M0** | ✅ | 65.06 kg; 1:1 knee, hub wheels, no closed loops |
| Unitree B2-W | robot_lab v3.0.0 (dependency) | vendor | n/a (robot_lab cfg) | P4 bring-up reference |
| Unitree Go2-W | robot_lab v3.0.0 (dependency) | vendor | n/a | Real-robot deploys exist via rl_sar |
| Unitree G1 | robot_lab / Isaac Lab | vendor | n/a | P9 humanoid check |

Vendor models are used through robot_lab and never copied here (master D-007).

## Robot contract

Implemented and enforced in [`src/roboforge/model/contract.py`](../src/roboforge/model/contract.py):
- joints `{FL,FR,RL,RR}_{hip,thigh,calf,wheel}_joint`
- free-floating `base` with an `imu` site
- explicit `<inertial>` on every body
- an actuator and armature > 0 on every leg joint

Humanoid joint map: ⬜, to be defined in P9.

## Fidelity levels

| Level | Model content | Gate to enter |
|---|---|---|
| M0 | Parametric spec, lumped / section inertia | contract passes |
| M1 | SolidWorks mass properties | G1.2 |
| M2 | M1 + every link weighed `[MEAS]` | masses within ±2% of the scale `[EST]` |
| M3 | M2 + actuator models fitted to bench data | G3.3 |
| M4 | M3 + whole-robot sysid from logs | P8 refit |

**Only ≥ M3 policies are hardware candidates** (master D-004).

## SolidWorks → model (P1.C) — CAD conventions for Sky

- [ ] Agree these conventions (one-time), then export:
  1. One sub-assembly per link, named per the contract (`base`, `FL_hip`, `FL_thigh`, …).
  2. A named reference coordinate system at each joint origin, with the joint axis as a named reference axis.
  3. Assign a material on **every** part. SolidWorks silently uses 1000 kg/m³ otherwise, and the importer will reject unassigned parts.
  4. Purchased parts (motors, battery, electronics): use **Override Mass Properties** with datasheet mass and CoM.
  5. Base frame X forward, Z up (SolidWorks defaults to Y-up; set it in the exporter). Units m.
- [ ] Export with the SolidWorks URDF Exporter 1.6.1 (MIT). If it fails on our SolidWorks version, fall back to our own pywin32 extractor (see [tools/](../tools/TRACKER.md)).
- [ ] Create `robots/v1_wheeled_quad_cad/`: `source/` (URDF + STL) + `robot.yaml` sidecar (actuators, collision primitives, sensors) → M1.

## Hardware data the models can consume (format contracts, not a schedule)

| Data | Raises fidelity to | Minimum content |
|---|---|---|
| Link weights | M2 | Per-link mass; CoM by suspension if practical |
| Actuator bench, per motor type | M3 | Torque vs current; torque-speed corners at 50.4 V and 58.8 V; slow-sweep friction; step responses at deployment kp/kd; winding temperature vs time at constant torque |
| Control-loop latency | M3 | Timestamped command-out vs motion onset |
| IMU / encoder static logs | M3 | ≥ 10 min stationary |
| Robot logs (MCAP) | M4 | Suspended-leg swings, standing, rolling |

## Known model limits (v1, M0)

- Inertias are section/lumped estimates. CAD replaces them at M1.
- Hub motor `wheel_hub` is a placeholder (`[EST]`/`[WB]` values); the real motor is not selected.
- Rotor inertias are `[EST]` for all motors, and armature depends on them directly.
- The 1:1 knee transmission (belt or link) is modelled rigid: no compliance, no backlash.
- Friction and damping are `[EST]` placeholders until bench data.

## Done

- 2026-11-12 `v1_wheeled_quad/robot.yaml`: cleaned from the earlier parametric spec.
  - Contract joint names.
  - Motor-derived joint limits.
  - Supplier prices removed.
  - Every number tagged (test-enforced).
