# src/roboforge/ — sub-tracker (model · P3 actuators/sensors · P4 tasks · P5 eval · P6 depth · P9 humanoid)

← [Master tracker](../../TRACKER.md) · The Python package. `model/` must never import Isaac
Lab; everything else may.

| Module | Phase | Status |
|---|---|---|
| `model/` | P1 source A: spec, parametric MJCF, robot contract | ✅ (M0) |
| `actuators/` | P3 | ⬜ |
| `sensors/` | P3 / P6 | ⬜ |
| `tasks/locomotion/` | P4 / P6 | ⬜ |
| `eval/` | P5 | 🟨 first piece lives in `scripts/eval_policy.py` (speed sweep vs real rated speed) |

## P3 — Actuator and sensor models

Approach:
- Explicit Isaac Lab actuator classes (`use_newton_actuators=False`), so **identical Python runs on both engines**.
- The native Newton path fixes the delay (no per-episode randomization).
- MuJoCo-Warp does not enforce `joint_velocity_limit`; the speed limit lives in our torque-speed envelope.

- [ ] Driver PD (MIT law τ = kp(q*−q) + kd(q̇*−q̇) + τ_ff) at the physics rate.
- [ ] Four-quadrant torque-speed envelope from `tau_peak`, `vel_max` and bus voltage (50.4 V nominal / 58.8 V charged).
- [ ] Coulomb + viscous friction (from `robot.yaml`, `[EST]` until bench).
- [ ] Command delay randomized per episode in [0, d_max]; d_max = 20 ms `[EST]` until measured.
- [ ] **Thermal model**: winding RC with P_cu = (τ / (N·η))² / km2, derated toward T_max. Calibrated so steady state at `tau_cont` lands on T_max, which makes continuous torque a simulated constraint.
- [ ] Sensors: IMU noise / bias walk / latency; encoder quantization (14-bit `[3P]`) and noise.

| Gate | Criterion `[EST]` |
|---|---|
| G3.1 | Unit tests reproduce stall torque and no-load speed within 2%; thermal steady state at `tau_cont` hits T_max within 5% |
| G3.2 | Same state input gives bit-identical torque on both backends |
| G3.3 | With bench data: step-response fit RMSE ≤ 5% of step size; latency identified → fidelity M3 |

## P4 — Blind wheeled-legged locomotion

- [ ] Run robot_lab `RobotLab-Isaac-Velocity-{Flat,Rough}-Unitree-B2W-v0` unchanged on `newton_mjwarp`. This is the baseline.
  - robot_lab's B2-W config sets no armature; expect MuJoCo-Warp to need it.
- [ ] Add task `roboforge.tasks.locomotion.velocity_wheeled` by subclassing robot_lab's wheeled velocity env.
  - v1 asset from `robots/v1_wheeled_quad/build/model.xml`.
  - Our P3 actuators.
  - Actions: 12 leg position targets + 4 wheel velocity targets.
- [ ] Domain randomization: friction, mass and CoM offset, motor strength, kp/kd, delay, pushes; terrain curriculum.
  - On Newton, randomize **terrain** friction (or lower terrain μ). Isaac Lab #8869: max-combine makes robot-friction DR a no-op.
- [ ] Command ranges up to the real robot's rated speed. robot_lab defaults to ±1 m/s; see benchmarks B4.
- [ ] Rewards stay config-only: one term per function, weights in config, per-term sums logged.

| Gate | Criterion `[EST]`, recalibrated against the B2-W baseline |
|---|---|
| G4.1 | B2-W: flat tracking RMSE ≤ 0.15 m/s at 1 m/s; falls ≤ 2% of 20-s episodes at terrain level ≥ 5; 3 seeds |
| G4.2 | v1: same, and thermal state never saturated over the eval set |

## P5 — Cross-engine evaluation harness

- [ ] Fixed scenario suite, runnable on any backend: command sweep, terrain levels, pushes, held-out DR.
  - Metrics: tracking RMSE, fall rate, cost of transport, joint torque RMS/peak, thermal headroom, slip.
  - Output: an HTML report.
- [ ] Policy transfer per Isaac Lab's procedure: explicit `joint_ordering` / `body_ordering`, identical MDP.
- [ ] Calibrate first: train Isaac Lab's Go2 on `newton_mjwarp`, evaluate on `ovphysx`, record degradation Δ_ref.
- [ ] Port quadrrl's Fair-Morph idea: matched reward weights and agents for v1 vs B2-W vs Go2-W comparisons.

**G5:** degradation on the second engine ≤ max(1.5·Δ_ref, 20%) in tracking RMSE; fall rate +≤ 5 pp `[EST]`.

**"Too complicated" rule:** if the v1 model cannot be made equivalent in PhysX after one
bounded attempt (G2.3 fails structurally), drop the PhysX rung for that robot. Replace it with
sim-in-the-loop (P7) plus a ±30% out-of-range parameter stress test, and log the decision in
the master tracker.

## P6 — Depth perception (after G4.2)

- [ ] Teacher = P4 policy + privileged height scan (Warp ray caster, works on both backends).
- [ ] Student = proprioception history + depth, trained by RSL-RL distillation. Defaults from Isaac Lab's G1 depth policy: 64×38 depth, 87° × 58.8° FOV, 3-frame stack.
- [ ] Depth noise model on from the start; camera pose and FOV from Sky's camera choice (master N5).

**G6:** student ≥ 90% of the teacher's terrain success with noise on, on both engines `[EST]`.

## P9 — Humanoid generality check (later)

- [ ] Run robot_lab's G1 velocity task through our robot folder, contract and eval harness. Proves nothing in `model/`, `eval/` or `deploy/` is quadruped-locked.

## Done

- 2026-11-12 `compat.py`: OVPhysX/importer USD-schema workaround (master D-010).
- 2026-11-12 `model/` ported and tested (8/8): spec, kinematics, inertia, parametric generator, contract.
