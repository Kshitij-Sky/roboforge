"""Capability benchmark (B4): drive a trained RSL-RL policy through a fixed speed sweep.

    uv run python scripts/eval_policy.py --task RobotLab-Isaac-Velocity-Flat-Unitree-B2W-v0 \
        --model logs/rsl_rl/unitree_b2w_flat/<run>/model_1499.pt \
        --speeds 0.5 1.0 2.0 3.0 4.17 --envs-per-speed 64 --seconds 10 physics=newton_mjwarp

Every parallel robot is pinned to one forward-speed command (lateral and yaw = 0) for the whole
run, including speeds above the training command range. Per speed it reports the achieved mean
forward speed (body frame, after a 2 s settling window, robots that have not fallen), tracking
RMSE, and the fall fraction. The result is compared against the real robot's rated top speed
from benchmarks/reference_robots.yaml. Results go to benchmarks/results/<stamp>_eval_*.json.

Mirrors Isaac Lab v3.0.0's `isaaclab play --rl_library rsl_rl` (isaaclab_rl/entrypoints/backends/
play_rsl_rl.py); only the command handling and the measurement are ours.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import importlib.metadata
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_task_entry_points() -> None:
    """Register external tasks the way the `isaaclab` CLI does, roboforge first (see roboforge/compat.py)."""
    eps = sorted(importlib.metadata.entry_points(group="isaaclab.tasks"), key=lambda e: e.name != "roboforge")
    for ep in eps:
        ep.load()


def _t(x):
    """Isaac Lab 3.0 asset data are ProxyArrays; take the torch view."""
    return x.torch if hasattr(x, "torch") else x


def main(argv: list[str]) -> int:
    _load_task_entry_points()

    import torch
    import yaml

    from isaaclab.app import add_launcher_args, launch_simulation
    from isaaclab.utils.string import list_intersection
    from isaaclab_rl.entrypoints.backends import cli_args_rsl_rl as cli_args
    from isaaclab_rl.entrypoints.common import add_common_play_args, close_env, create_isaaclab_env, set_hydra_args
    from isaaclab_rl.rsl_rl import (
        RslRlVecEnvWrapper,
        check_rsl_rl_version,
        create_rsl_rl_runner,
        handle_deprecated_rsl_rl_cfg,
    )
    from isaaclab_tasks.utils import resolve_task_config, setup_preset_cli

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_play_args(ap, agent_default="rsl_rl_cfg_entry_point", agent_help="RL agent config entry point.")
    ap.add_argument("--model", required=True, help="path to an RSL-RL model_*.pt")
    ap.add_argument("--speeds", type=float, nargs="+", default=[0.5, 1.0, 1.5, 2.0, 3.0])
    ap.add_argument("--envs-per-speed", type=int, default=64)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--settle-seconds", type=float, default=2.0)
    ap.add_argument("--robot", default=None, help="key in reference_robots.yaml (default: guessed from task)")
    cli_args.add_rsl_rl_args(ap)
    add_launcher_args(ap)
    reg_args = cli_args.register_external_tasks(argv)
    a, remaining = setup_preset_cli(ap, argv)
    set_hydra_args(list_intersection(remaining, reg_args))
    physics = next((x.split("=", 1)[1] for x in argv if x.startswith("physics=")), "default")

    installed = check_rsl_rl_version()
    env_cfg, agent_cfg = resolve_task_config(a.task, a.agent, play_mode=True)
    n_speeds = len(a.speeds)
    env_cfg.scene.num_envs = n_speeds * a.envs_per_speed
    env_cfg.episode_length_s = a.seconds + 5.0
    cmd_cfg = env_cfg.commands.base_velocity
    cmd_cfg.heading_command = False
    cmd_cfg.rel_standing_envs = 0.0
    cmd_cfg.resampling_time_range = (1.0e6, 1.0e6)
    vmax = max(abs(s) for s in a.speeds)
    cmd_cfg.ranges.lin_vel_x = (-vmax, vmax)

    with launch_simulation(env_cfg, a), contextlib.ExitStack() as cleanup:
        agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, a)
        agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, installed)
        env = create_isaaclab_env(a.task, env_cfg, a, convert_marl_to_single_agent=False)
        cleanup.callback(lambda: close_env(env))
        env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
        runner = create_rsl_rl_runner(env, agent_cfg)
        runner.load(str(Path(a.model).resolve()))
        dev = env.unwrapped.device
        policy = runner.get_inference_policy(device=dev)

        u = env.unwrapped
        term = u.command_manager.get_term("base_velocity")
        robot = u.scene["robot"]
        speed_of_env = torch.tensor(a.speeds, device=dev).repeat_interleave(a.envs_per_speed)
        n = speed_of_env.numel()
        steps = int(a.seconds / u.step_dt)
        settle = int(a.settle_seconds / u.step_dt)
        fallen = torch.zeros(n, dtype=torch.bool, device=dev)
        vx_sum = torch.zeros(n, device=dev)
        err2_sum = torch.zeros(n, device=dev)
        count = torch.zeros(n, device=dev)

        def pin():
            term.vel_command_b[:, 0] = speed_of_env
            term.vel_command_b[:, 1:] = 0.0

        pin()
        obs = env.get_observations()
        with torch.inference_mode():
            for k in range(steps):
                pin()
                obs, _, dones, _ = env.step(policy(obs))
                policy.reset(dones)
                fell = dones.bool() & ~u.termination_manager.time_outs.bool()
                fallen |= fell
                if k >= settle:
                    vx = _t(robot.data.root_lin_vel_b)[:, 0]
                    ok = ~fallen
                    vx_sum += torch.where(ok, vx, 0.0)
                    err2_sum += torch.where(ok, (vx - speed_of_env) ** 2, 0.0)
                    count += ok.float()

        rows = []
        for i, s in enumerate(a.speeds):
            sl = slice(i * a.envs_per_speed, (i + 1) * a.envs_per_speed)
            c = count[sl].sum().clamp(min=1)
            rows.append({
                "cmd_mps": s,
                "achieved_mps": round(float(vx_sum[sl].sum() / c), 3),
                "tracking_rmse_mps": round(float((err2_sum[sl].sum() / c).sqrt()), 3),
                "fall_fraction": round(float(fallen[sl].float().mean()), 3),
            })

    key = a.robot or next((k for k in ("unitree_b2w", "unitree_go2w") if k.split("_")[1] in a.task.lower()), None)
    ref = yaml.safe_load((REPO / "benchmarks" / "reference_robots.yaml").read_text(encoding="utf-8"))
    real_max = (ref.get(key) or {}).get("real", {}).get("max_speed_mps") if key else None
    good = [r for r in rows if r["fall_fraction"] <= 0.05 and r["tracking_rmse_mps"] <= 0.25 * max(r["cmd_mps"], 1.0)]
    res = {
        "timestamp": dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
        "task": a.task, "physics": physics, "checkpoint": str(a.model),
        "argv": argv, "envs_per_speed": a.envs_per_speed, "seconds": a.seconds, "rows": rows,
        "max_tracked_speed_mps": max((r["cmd_mps"] for r in good), default=None),
        "real_rated_max_speed_mps": real_max, "reference_key": key,
        "criterion": "tracked = fall_fraction <= 5% and RMSE <= 25% of max(cmd, 1 m/s)",
    }
    out = REPO / "benchmarks" / "results" / f"{res['timestamp']}_eval_{a.task.replace('RobotLab-Isaac-Velocity-', '').replace('-v0', '')}_{physics}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\n{'cmd m/s':>8} {'achieved':>9} {'rmse':>6} {'falls':>6}")
    for r in rows:
        print(f"{r['cmd_mps']:8.2f} {r['achieved_mps']:9.2f} {r['tracking_rmse_mps']:6.2f} {r['fall_fraction']:6.1%}")
    print(f"max tracked speed: {res['max_tracked_speed_mps']} m/s   real rated: {real_max} m/s   -> {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
