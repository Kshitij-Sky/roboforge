# RoboForge

**A CAD-to-real reinforcement-learning pipeline for legged robots.** You bring your own robot
design (SolidWorks, or a parametric spec). RoboForge turns it into a validated simulation
model and trains locomotion policies on GPU, blind or with depth vision. Each policy passes a
ladder of independent checks before it touches hardware.

Target robots: our own **wheeled-legged quadruped** first, humanoids later, in the same repo.

> **Status:** early. The repo skeleton and the robot-description layer exist and are tested.
> Training is not set up yet. Everything that is done, in progress, or open is in
> **[TRACKER.md](TRACKER.md)**.

---

## Why this exists

Good GPU simulators and RL frameworks now exist. What doesn't exist is a plug-and-play path
from *your own CAD* to *a policy that works on your own hardware*, with enough evidence along
the way to trust the result. Most sim-to-real failures don't come from the physics engine.
They come from the parts every framework leaves to you:
- wrong mass properties
- an idealised actuator (no torque-speed limit, friction, latency or heating)
- unmodelled sensor noise and delay
- observation mismatches between training code and robot code

RoboForge is the layer that handles those, built on established open-source tools.

## How it works

```
SolidWorks (URDF + meshes) ─┐
Parametric spec (robot.yaml) ┼─▶ canonical MJCF ─▶ robot contract check ─▶ USD (auto)
Reference robots (robot_lab) ┘                                              │
                                                                            ▼
          Isaac Lab 3.0 task ── train on Newton / MuJoCo-Warp ── re-test on PhysX
                                                                            │
                         ONNX policy ─▶ deploy runtime ─▶ MuJoCo CPU at 0.5 ms (sim-in-the-loop) ─▶ robot
                                                                            │
                                           robot logs ─▶ system identification ─▶ better model ─┘
```

**Verification ladder.** A policy reaches hardware only after passing every rung in order:
1. Train.
2. Held-out randomization.
3. A second, independent physics engine.
4. The real deploy code against a fine-timestep simulator with latency and noise.

**Model fidelity levels.** Every trained policy is stamped with the fidelity of the model it
was trained on:

| Level | Model contents |
|---|---|
| M0 | Parametric |
| M1 | CAD mass properties |
| M2 | Weighed parts |
| M3 | Bench-fitted actuators |
| M4 | Whole-robot system identification |

Only M3 and above are hardware candidates.

## Repository layout

```
TRACKER.md            the single status document (each folder below has a linked sub-tracker)
robots/               one folder per robot: spec + generated models (build/ is never hand-edited)
src/roboforge/        Python package
  model/              spec loading, parametric MJCF generator, robot contract (no Isaac Lab needed)
  actuators/ sensors/ actuator and sensor-noise models for training
  tasks/              Isaac Lab tasks (registered via the `isaaclab.tasks` entry point)
  eval/               cross-engine evaluation harness
tools/                CAD import, MJCF→USD conversion, validation gates, system identification
deploy/               robot-side runtime (no Isaac Lab dependency)
benchmarks/           real-robot reference values + benchmark results on our hardware
scripts/              workspace setup, model build, training benchmark, upstream version switching
third_party/          git submodules, pinned: Isaac Lab, robot_lab (not our code; not modified)
tests/
```

## Quickstart

**Robot model layer.** Works today; needs only Python with `numpy`, `pyyaml`, `mujoco`:

```bash
python scripts/build_robot.py v1_wheeled_quad          # generate + contract-check the MJCF
python scripts/build_robot.py v1_wheeled_quad --view   # inspect the standing pose in MuJoCo
python -m pytest tests -q
```

**Training stack.** Isaac Lab 3.0 and robot_lab are pinned as git submodules in
`third_party/`. You need Python 3.12 (uv fetches it), uv and an NVIDIA GPU (Turing or newer):

```bash
git clone --recursive https://github.com/Kshitij-Sky/roboforge.git && cd roboforge
bash scripts/setup_workspace.sh          # Windows: powershell -File scripts\setup_workspace.ps1
# Windows, every new terminal:  . .\scripts\env.ps1   (uv, caches and Python live in <workspace>\.tools / .cache)
uv run isaaclab train --rl_library rsl_rl --task RobotLab-Isaac-Velocity-Flat-Unitree-B2W-v0 \
    --viz none physics=newton_mjwarp     # or physics=ovphysx (PhysX) for the cross-check
uv run python scripts/bench_training.py --task RobotLab-Isaac-Velocity-Flat-Unitree-B2W-v0 --num-envs 4096
python scripts/upstream.py status        # pinned upstream versions; `try` tests newer ones on a branch
```

---

## Built on — credits

RoboForge stands on the work of these projects and authors. Where we adapt code, the original
license header is kept in the file and the project is listed here.

| Project | Authors | License | How RoboForge uses it |
|---|---|---|---|
| [Isaac Lab](https://github.com/isaac-sim/IsaacLab) | The Isaac Lab Project Developers (NVIDIA et al.) | BSD-3-Clause | Training framework (v3.0); `pyproject.toml` layout adapted from its external-project template |
| [Newton](https://github.com/newton-physics/newton) | Newton contributors; a Linux Foundation project initiated by Disney Research, Google DeepMind and NVIDIA | Apache-2.0 | GPU physics backend inside Isaac Lab |
| [MuJoCo](https://github.com/google-deepmind/mujoco) / [MuJoCo Warp](https://github.com/google-deepmind/mujoco_warp) | Google DeepMind (MuJoCo Warp with NVIDIA) | Apache-2.0 | Physics (training via Newton; CPU reference and validation); `mujoco.sysid` for system identification |
| [robot_lab](https://github.com/fan-ziqi/robot_lab) | Ziqi Fan and contributors | Apache-2.0 | Base library: Isaac Lab 3.0 wheeled-legged and humanoid tasks, external-project setup (dependency) |
| [rl_sar](https://github.com/fan-ziqi/rl_sar) | Ziqi Fan and contributors | Apache-2.0 | Reference for robot-side deployment and MuJoCo sim-to-sim (planned) |
| [quadrrl](https://github.com/lbnmahs/quadrrl) | Laban Njoroge, Manal Helal | BSD-3-Clause | Fair-Morph matched-reward benchmarking and multi-seed analysis approach (planned) |
| [RSL-RL](https://github.com/leggedrobotics/rsl_rl) | ETH Zurich (Robotic Systems Lab) and NVIDIA | BSD-3-Clause | PPO and student-teacher distillation |
| [mjlab](https://github.com/mujocolab/mjlab) | Kevin Zakka, Qiayuan Liao, Brent Yi, Louis Le Lay, Koushil Sreenath, Pieter Abbeel | Apache-2.0 | Fallback framework (same MJCF, same physics) |
| [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground) / [reaf-sim](https://github.com/google-deepmind/reaf-sim) | Google DeepMind | Apache-2.0 | Design inspiration: hardware/task layer split for sim-to-real (no code used) |
| [legged_gym](https://github.com/leggedrobotics/legged_gym) | Nikita Rudin, ETH Zurich and NVIDIA | BSD-3-Clause | Lineage of massively parallel locomotion RL (no code used) |
| [SolidWorks to URDF Exporter](https://github.com/ros/solidworks_urdf_exporter) | ROS community | MIT | Planned CAD export path |

Methods we build on:
- J. Hwangbo et al., *Learning agile and dynamic motor skills for legged robots*, Science
  Robotics 2019 (actuator modelling for sim-to-real).
- N. Rudin et al., *Learning to Walk in Minutes Using Massively Parallel Deep RL*, CoRL 2021.
- C. Rucker & P. Wensing, *Smooth Parameterization of Rigid-Body Inertia*, IEEE RA-L 2022
  (physically consistent inertia identification, used through `mujoco.sysid`).

## License

RoboForge's own code is licensed under the **Apache License 2.0** ([LICENSE](LICENSE)),
Copyright 2026 The RoboForge Authors.

- Third-party code adapted into this repository keeps its original license header (BSD-3-Clause, MIT
  or Apache-2.0). All are compatible with Apache-2.0.
- **Third-party robot models and meshes** (e.g. Unitree, Deep Robotics, ANYbotics descriptions
  shipped with robot_lab) are **not redistributed** here. They are fetched from their upstream
  repositories by the setup scripts and remain under their owners' terms.
- NVIDIA Isaac Sim is optional and not included; if you install it, its own license terms apply.
- Robot and company names are trademarks of their respective owners. Their use here is for
  identification only and implies no affiliation or endorsement.
