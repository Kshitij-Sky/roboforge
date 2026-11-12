# deploy/ — sub-tracker (P7: deploy runtime and sim-in-the-loop)

← [Master tracker](../TRACKER.md) · The robot-side runtime. It must **not** depend on Isaac
Lab: numpy + onnxruntime (+ MuJoCo for `hal_sim`) only.

| Folder | Purpose | Status |
|---|---|---|
| `runtime/` | ONNX policy runner, observation builder, action mapper, safety layer | ⬜ |
| `hal_sim/` | MuJoCo CPU "robot" at MBD-grade dt (0.5 ms), P3 actuator model at driver rate, latency + noise, wall-clock real time | ⬜ |
| `hal_real/` | Interface only: `read_state()` / `write_command()` with timestamps. Sky owns drivers and buses | ⬜ |

## P7 — Steps

- [ ] **Decide: adopt rl_sar or write our own runtime.** rl_sar is Apache-2.0, C++, ROS optional, libtorch/onnxruntime, MuJoCo/Gazebo sim-to-sim, with real Go2/Go2-W deploys.
  - Gaps: Linux/macOS only; no latency injection or golden obs tests that we found; MuJoCo 3.2.7.
  - Decision criterion: can we add our actuator, latency and obs-parity layer to rl_sar more cheaply than writing ~1k lines of Python?
- [ ] Policy export from Isaac Lab: rsl_rl ONNX, or LEAPP if observation semantics should travel with the model.
- [ ] Safety layer: joint and torque limits, tilt cutoff, command watchdog, e-stop.
- [ ] Golden test fixture: log Isaac Lab states plus the observations it built; the runtime must rebuild identical observations.

## Gates `[EST]`

| Gate | Criterion |
|---|---|
| G7.1 | Runtime observation vector = Isaac Lab observation vector for the same logged states, ≤ 1e-5. Prevents obs order, scale and frame mismatches. |
| G7.2 | Sim-in-the-loop: the policy completes the eval course in `hal_sim` with fall rate ≤ 2× its training-engine fall rate, across latency ∈ [0, 20 ms] |
| G7.3 | Inference latency on the target computer ≤ 2 ms (MLP) / ≤ 10 ms (depth student). Needs master N6 |

## Done

- 2026-11-12 Folders created.
