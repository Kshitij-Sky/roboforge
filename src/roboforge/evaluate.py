"""Capability benchmark (B4/B5): drive a trained policy through a fixed speed sweep.

    uv run rf eval <run> [--checkpoint latest|<iter>] [--physics ovphysx] [--speeds 0.5 1 2 3 4.17]

Every parallel robot is pinned to one forward-speed command (lateral and yaw 0) for the whole run,
including speeds above the training command range. Per speed: achieved mean forward speed (body
frame, after a settling window, robots that have not fallen), tracking RMSE, fall fraction (base tipped past 60 deg;
robots start upright with no pushes). The
result is compared with the real robot's rated top speed (benchmarks/reference_robots.yaml) and
saved to <run>/eval/<checkpoint>_<physics>.json, so every evaluation stays attached to the run
and checkpoint it describes.

Cross-engine evaluation (--physics other than the training engine) re-applies the run's frozen
joint/body ordering automatically.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--checkpoint", default="latest")
    ap.add_argument("--physics", default=None)
    ap.add_argument("--axis", choices=("forward", "lateral", "yaw"), default="forward",
                    help="which command to sweep (others held at 0); yaw values are rad/s")
    ap.add_argument("--speeds", "--values", type=float, nargs="+", default=None,
                    help="command values (default: forward/lateral 0.5..3 m/s, yaw 0.25..1.5 rad/s)")
    ap.add_argument("--envs-per-speed", type=int, default=64)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--settle-seconds", type=float, default=2.0)
    ap.add_argument("--set", nargs="*", default=[], help="extra overrides for this evaluation only")
    a = ap.parse_args(argv)

    import yaml

    from roboforge.runs import REPO, find_run

    run = find_run(a.run)
    m = run.manifest
    physics = a.physics or m["physics"]
    model = run.checkpoint(a.checkpoint)
    axis = {"forward": 0, "lateral": 1, "yaw": 2}[a.axis]
    speeds = a.speeds or ([0.25, 0.5, 1.0, 1.5] if a.axis == "yaw" else [0.5, 1.0, 1.5, 2.0, 3.0])
    unit = "rad/s" if a.axis == "yaw" else "m/s"

    def hook(cfg):
        cfg.scene.num_envs = len(speeds) * a.envs_per_speed
        cfg.episode_length_s = a.seconds + 5.0
        c = cfg.commands.base_velocity
        c.heading_command = False
        c.rel_standing_envs = 0.0
        c.resampling_time_range = (1.0e6, 1.0e6)
        validation_conditions(cfg)  # upright start, no pushes: measure speed, not self-righting

    import torch

    from roboforge.isaac_session import as_torch, session, tilted, validation_conditions

    with session(m["task"], model, physics=physics, overrides=[*run.play_args(), *a.set], env_cfg_hook=hook) as s:
        u = s.unwrapped
        term = u.command_manager.get_term("base_velocity")
        robot = u.scene["robot"]
        cmd = torch.tensor(speeds, device=s.device).repeat_interleave(a.envs_per_speed)
        n = cmd.numel()
        steps, settle = int(a.seconds / u.step_dt), int(a.settle_seconds / u.step_dt)
        fallen = torch.zeros(n, dtype=torch.bool, device=s.device)
        vsum, e2sum, cnt = (torch.zeros(n, device=s.device) for _ in range(3))

        def pin():
            term.vel_command_b[:] = 0.0
            term.vel_command_b[:, axis] = cmd

        pin()
        obs = s.env.get_observations()
        with torch.inference_mode():
            for k in range(steps):
                pin()
                obs, _, dones, _ = s.env.step(s.policy(obs))
                s.policy.reset(dones)
                fallen |= tilted(robot)  # tipped past 60 deg; robot_lab never terminates on a flip
                if k >= settle:
                    vel = robot.data.root_ang_vel_b if axis == 2 else robot.data.root_lin_vel_b
                    vx = as_torch(vel)[:, 2 if axis == 2 else axis]
                    ok = ~fallen
                    vsum += torch.where(ok, vx, 0.0)
                    e2sum += torch.where(ok, (vx - cmd) ** 2, 0.0)
                    cnt += ok.float()
        rows = []
        for i, sp in enumerate(speeds):
            sl = slice(i * a.envs_per_speed, (i + 1) * a.envs_per_speed)
            c = cnt[sl].sum().clamp(min=1)
            rows.append({
                "cmd_mps": sp,
                "achieved_mps": round(float(vsum[sl].sum() / c), 3),
                "tracking_rmse_mps": round(float((e2sum[sl].sum() / c).sqrt()), 3),
                "fall_fraction": round(float(fallen[sl].float().mean()), 3),
            })

    ref = yaml.safe_load((REPO / "benchmarks" / "reference_robots.yaml").read_text(encoding="utf-8"))
    key = next((k for k in ref if k.split("_")[-1] in m["task"].lower()), None)
    real_max = ref[key]["real"]["max_speed_mps"] if (key and a.axis == "forward") else None
    good = [r for r in rows if r["fall_fraction"] <= 0.05
            and abs(r["achieved_mps"] - r["cmd_mps"]) <= 0.25 * abs(r["cmd_mps"])
            and r["tracking_rmse_mps"] <= 0.5 * abs(r["cmd_mps"])]
    res = {
        "timestamp": dt.datetime.now().strftime("%Y%m%d-%H%M%S"),
        "run": run.id, "experiment": run.experiment, "checkpoint": model.name,
        "trained_on": m["physics"], "physics": physics, "axis": a.axis, "unit": unit, "extra_overrides": a.set,
        "envs_per_speed": a.envs_per_speed, "seconds": a.seconds, "rows": rows,
        "max_tracked_speed_mps": max((r["cmd_mps"] for r in good), default=None),
        "real_rated_max_speed_mps": real_max, "reference_key": key,
        "criterion": "tracked = falls <= 5%, mean within 25% of cmd, RMSE <= 50% of cmd",
    }
    out = run.dir / "eval" / (f"{model.stem}_{physics}" + ("" if a.axis == "forward" else f"_{a.axis}") + ".json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(f"\n{run.id}  {model.name}  trained on {m['physics']}, evaluated on {physics}  [{a.axis}, {unit}]")
    print(f"{'cmd':>8} {'achieved':>9} {'rmse':>6} {'falls':>6}")
    for r in rows:
        print(f"{r['cmd_mps']:8.2f} {r['achieved_mps']:9.2f} {r['tracking_rmse_mps']:6.2f} {r['fall_fraction']:6.1%}")
    print(f"max tracked: {res['max_tracked_speed_mps']} {unit}" + (f"   real rated: {real_max} m/s" if real_max else ""))
    print(f"saved {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
