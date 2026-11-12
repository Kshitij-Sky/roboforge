# tools/ — sub-tracker (P1 import/convert · P2 validation · P8 sysid)

← [Master tracker](../TRACKER.md) · Offline tools that turn sources into validated models and
logs into better models.

| Folder | Phase | Status |
|---|---|---|
| `cad_import/` | P1.C — SolidWorks URDF + STL + sidecar → canonical MJCF (MjSpec) | ⬜ |
| `convert/` | P1 — MJCF → USD via Isaac Lab `MjcfConverter`, plus round-trip check | ⬜ |
| `validate/` | P2 — gate scripts G1.2, G1.3, G2.1–G2.3 | ⬜ |
| `sysid/` | P8 — `mujoco.sysid` wrappers: logs → spec parameters | ⬜ |

## P1 — Import and conversion

- [ ] **`cad_import`**: parse the SolidWorks URDF (MuJoCo reads URDF natively), then use MjSpec to:
  - add armature, actuators, the `imu` site, contact primitives (cylinder wheels) and `condim`
  - write `build/model.xml`, a derived URDF, and an HTML report (per-link mass/CoM/inertia, diff vs the last build)
- [ ] Fallback extractor, *only if the official exporter fails*: Python + pywin32 against the SolidWorks API. It reads per-component mass properties (honouring overrides), named coordinate systems, materials, and writes an STL per link.
- [ ] **`convert`**: MJCF → USD via `isaaclab.sim.converters.MjcfConverter`, which wraps `mujoco-usd-converter`. Settings: `collision_from_visuals=False`, self-collision per spec. Newton reads MuJoCo `mjc:` attributes through its schema resolvers; G1.3 verifies that rather than trusting it.

| Gate | Criterion `[EST]` |
|---|---|
| G1.2 | Total mass = SolidWorks assembly ±0.5%; each link ±0.5%; inertia positive-definite and triangle-inequality valid; CoM inside the link's bounding box; joint axes within 0.1°; zero default-material parts |
| G1.3 | USD read back through Newton reproduces mass, CoM, inertia, limits, armature, damping, frictionloss to relative error ≤ 1e-5; any dropped attribute is a fail |

## P2 — Model validation (before training on our robot)

- [ ] **G2.1 Conversion round-trip, same engine.** MuJoCo CPU (from MJCF) vs Isaac Lab `newton_mjwarp` (from USD), identical open-loop torques, matched dt and solver.
  - Fixed-base 2 s chirp: joint RMS difference ≤ 0.5°.
  - Floating drop-and-settle: base height difference ≤ 5 mm.
- [ ] **G2.2 RL-grade vs MBD-grade** (dt 5 ms vs 0.5 ms, `reference_solver` in `robot.yaml`).
  - Stand sag difference ≤ 2 mm; stand torques ≤ 3%; wheel coast-down ≤ 10%.
  - Drop tests reported **with the `solref` spread**.
  - If it fails at 5 ms, try 2 ms with decimation 10. This gate sets the training dt.
- [ ] **G2.3 PhysX equivalence (not identity).**
  - Static-stand torques PhysX vs MuJoCo-Warp within 5%. Statics depend only on mass and geometry, so a miss means lost mass data.
  - Constant-torque wheel terminal speed within 10%.
  - Record how each engine represents the cylinder wheel. A structural difference is logged as a known bias, not chased as a bug.

## P8 — Real-to-sim loop

- [ ] Log schema in MCAP: timestamped commands, joint states, IMU, depth frames, policy I/O.
- [ ] `sysid` wrapper around `mujoco.sysid`. It fits mass, CoM, full inertia (pseudo-inertia, physically consistent), friction, damping, PD gains and sensor delays, with an HTML report. Results write back to `robot.yaml` with new provenance (`[MEAS]`) and fidelity.
- [ ] Replay: a logged hardware command sequence through `deploy/hal_sim`; the trajectory diff becomes the tracked model-error metric.

## Done

- 2026-11-12 Folders created. The contract checker (G1.1) lives in `src/roboforge/model/contract.py` and is done.
