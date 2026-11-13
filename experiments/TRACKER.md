# experiments/ â€” sub-tracker (experiment log)

â† [Master tracker](../TRACKER.md) Â· One YAML file per experiment: base task, physics engine,
budget, and overrides (reward weights, command ranges, actuator limits, network size). Runs of an
experiment live in `logs/rsl_rl/<experiment>/<run_id>/` (git-ignored). The `rf` tool ties them
together.

## Workflow

| Toâ€¦ | Command |
|---|---|
| See experiments / runs | `uv run rf experiments` Â· `uv run rf runs` |
| Make a variant | `uv run rf new my_variant --from b2w_flat_default`, then edit `experiments/my_variant.yaml` |
| Train (only when Sky says so) | `uv run rf train my_variant [--detach] [--note "why"]` |
| Try one change without a new file | `uv run rf train b2w_flat_default --set env.rewards.upward.weight=0.0 --note "..."` |
| Watch + drive a policy (native viewer window, RoboForge panel in the side bar) | `uv run rf play <run> [--envs 9] [--train-conditions]`. Keys: I/K forward/back, J/L sideways, U/O turn |
| Benchmark a checkpoint | `uv run rf eval <run> [--axis forward\|lateral\|yaw] [--checkpoint 1000] [--physics ovphysx]` |
| Side-by-side | `uv run rf compare <run> <run>` |

**Rules that keep it unconfusing:**
- An experiment file is edited freely. A **run** is frozen. Its manifest (`roboforge_run.json`)
  stores the experiment text at launch, every override, the joint/body ordering, the git commit
  and a patch of uncommitted changes.
- `rf play` and `rf eval` rebuild the environment from the run's frozen manifest, not from the
  current experiment file. Playing an old run after editing rewards is safe.
- If code that defines a run's environment changed since it trained, `rf play` and `rf eval`
  print a **code drift** warning. Unrelated edits stay silent.
- A training in progress is unaffected by edits: its config was resolved at launch. Checkpoints
  land every `save_interval` iterations (default 100), and `rf play` can open them mid-training
  ("Refresh checkpoints" in the panel).
- Evaluations are saved inside the run: `<run>/eval/<checkpoint>_<physics>.json`.

## Experiments

| Experiment | Question it answers | Runs | Result |
|---|---|---|---|
| `b2w_flat_default` | How good is robot_lab's B2-W, unchanged, on Newton? | `unitree_b2w_flat/2026-11-12_19-47-06` (adopted, 1500 it) | Forward 0.5→4.17 m/s tracked (+4–8%), 0 falls; sideways from 0.5 m/s; **does not turn in place**; drives at ~20–25% speed on PhysX (benchmarks B4/B5) |
| `b2w_flat_default_physx` | Same, trained on PhysX: which engine learns to drive? | 2026-11-12 attempt **crashed at iteration 122** (CUDA error 999 in OVPhysX's GPU contact view, then hung until timeout); see benchmarks known issues | â¬œ needs a retry (Sky's go) |
| `b2w_flat_realrange` | Does the real envelope (4.17 m/s, 40 NÂ·m) raise top speed? | `20261113-083721`: stopped at 110 it, **not a result** (started without OK) | â¬œ waiting for Sky's go |
| `go2w_flat_default` | Go2-W baseline (second robot class) | â€” | â¬œ waiting for Sky's go |

## Done

- 2026-11-13 `rf` tool:
  - experiments + frozen run manifests
  - `play` (native Newton viewer + RoboForge side panel: command sliders, checkpoint picker, readout)
  - `eval` saved per run, `compare`, `adopt`
  - Four experiment files.
