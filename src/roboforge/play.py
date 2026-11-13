"""Watch and drive a trained run in Newton's native viewer window.

    uv run rf play <run> [--checkpoint latest|<iter>] [--physics newton_mjwarp|ovphysx] [--envs 1]
                         [--terrain flat|rough|slope_up|slope_down|stairs_up|stairs_down|boxes|mixed] [--difficulty 0.5]

Opens a desktop window (Newton GL viewer, drawn straight from GPU memory). Isaac Lab's own
panel gives pause/reset; the "RoboForge" panel adds:
  * forward / lateral / yaw command sliders (every robot gets the same command)
  * a checkpoint picker; "Refresh" picks up checkpoints a still-running training has just saved
  * reset, and a readout of commanded vs actual velocity, falls (tilt > 60 deg) and steps/s
Robots reset upright with no random pushes (--train-conditions restores robot_lab's training
resets). The run's frozen overrides and joint/body ordering are applied, so the policy sees exactly
the observations it was trained on, even if experiments or task code changed since.
"""

from __future__ import annotations

import argparse
import time


def _guess_vmax(task: str) -> float:
    try:
        import yaml

        from roboforge.runs import REPO

        ref = yaml.safe_load((REPO / "benchmarks" / "reference_robots.yaml").read_text(encoding="utf-8"))
        for key, val in ref.items():
            if key.split("_")[-1] in task.lower():
                return float(val["real"]["max_speed_mps"])
    except Exception:
        pass
    return 2.0


def _ramp(current: float, target: float, max_step: float) -> float:
    """Move toward target by at most max_step (a gentle acceleration limit for keyboard commands)."""
    return current + max(-max_step, min(max_step, target - current))


def _gl_viewer(unwrapped):
    for viz in getattr(unwrapped.sim, "visualizers", []):
        viewer = getattr(viz, "_viewer", None)
        if viewer is not None and hasattr(viewer, "register_ui_callback"):
            return viewer
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--checkpoint", default="latest")
    ap.add_argument("--physics", default=None, help="play on another engine than the run trained on")
    ap.add_argument("--envs", type=int, default=1, help="robots to show")
    ap.add_argument("--vmax", type=float, default=None, help="forward slider max (default: real rated speed)")
    ap.add_argument("--train-conditions", action="store_true",
                    help="keep training resets (random flips) and pushes instead of clean upright resets")
    ap.add_argument("--terrain", default="flat", help="flat | rough | slope_up | slope_down | stairs_up | "
                    "stairs_down | boxes | mixed (see roboforge/terrains.py)")
    ap.add_argument("--difficulty", type=float, default=0.5, help="terrain difficulty 0..1 (step height, slope, ...)")
    a = ap.parse_args(argv)

    from roboforge.runs import code_drift, find_run

    run = find_run(a.run)
    m = run.manifest
    physics = a.physics or m["physics"]
    model = run.checkpoint(a.checkpoint)
    drift = code_drift(run)
    vmax = a.vmax or _guess_vmax(m["task"])
    print(f"[rf play] {run.id}  {model.name}  trained on {m['physics']}, playing on {physics}")
    for d in drift:
        print(f"[rf play] WARNING code drift: {d}")

    import torch

    from roboforge import terrains
    from roboforge.isaac_session import as_torch, session, tilted, validation_conditions

    scene_info = {}

    def hook(cfg):
        cfg.scene.num_envs = a.envs
        c = cfg.commands.base_velocity
        c.heading_command = False
        c.rel_standing_envs = 0.0
        c.resampling_time_range = (1.0e6, 1.0e6)
        # robot_lab ends every episode after 20 s and teleports the robot home; in playback the
        # robot only resets when you press "Reset robots".
        cfg.episode_length_s = 1.0e6
        if not a.train_conditions:
            validation_conditions(cfg)
        terrains.apply(cfg, a.terrain, a.difficulty, a.envs)
        scene_info["blind"] = getattr(cfg.scene, "height_scanner", None) is None

    with session(m["task"], model, physics=physics, overrides=run.play_args(), viz="newton_gl", env_cfg_hook=hook) as s:
        u = s.unwrapped
        term = u.command_manager.get_term("base_velocity")
        robot = u.scene["robot"]
        obs = s.env.get_observations()

        viewer = None
        for _ in range(200):  # the viewer starts with the first rendered steps
            with torch.inference_mode():
                obs, _, dones, _ = s.env.step(s.policy(obs))
            viewer = _gl_viewer(u)
            if viewer is not None:
                break
        if viewer is None:
            print("[rf play] Newton viewer not found; is a display available?")
            return 1

        ck_names = lambda: [p.name for _, p in run.checkpoints()]  # noqa: E731
        st = {
            "vx": 0.0, "vy": 0.0, "wz": 0.0, "names": ck_names(), "ckpt": model.name,
            "pending": {}, "readout": [], "kb": True, "kb_speed": min(1.0, vmax), "kb_yaw": 1.0,
        }

        def panel(imgui):
            """Runs inside the viewer's UI pass (main thread); heavy work is deferred to the loop."""
            imgui.separator()
            imgui.text("RoboForge")
            imgui.text(run.id)
            imgui.text(f"{st['ckpt']}  |  trained {m['physics']}, playing {physics}")
            imgui.text(f"terrain: {a.terrain}" + (f" (difficulty {a.difficulty:.2f})" if a.terrain != "flat" else "")
                       + ("  |  policy is BLIND (no height scan)" if scene_info.get("blind") else ""))
            for d in drift:
                imgui.text_colored(imgui.ImVec4(1.0, 0.6, 0.2, 1.0), f"code drift: {d}")
            _, st["kb"] = imgui.checkbox("Keyboard drive  I/K fwd-back  J/L sideways  U/O turn", st["kb"])
            if st["kb"]:
                _, st["kb_speed"] = imgui.slider_float("Key top speed m/s", st["kb_speed"], 0.1, vmax, "%.2f")
                _, st["kb_yaw"] = imgui.slider_float("Key turn rate rad/s", st["kb_yaw"], 0.1, 1.5, "%.2f")
                imgui.text("(click the 3D view first so the window has keyboard focus)")
            _, st["vx"] = imgui.slider_float("Forward m/s", st["vx"], -1.0, vmax, "%.2f")
            _, st["vy"] = imgui.slider_float("Lateral m/s", st["vy"], -1.0, 1.0, "%.2f")
            _, st["wz"] = imgui.slider_float("Yaw rad/s", st["wz"], -1.5, 1.5, "%.2f")
            if imgui.button("Zero commands"):
                st["vx"] = st["vy"] = st["wz"] = 0.0
            imgui.same_line()
            if imgui.button("Reset robots"):
                st["pending"]["reset"] = True
            names = st["names"]
            idx = names.index(st["ckpt"]) if st["ckpt"] in names else len(names) - 1
            changed, idx = imgui.combo("Checkpoint", idx, names)
            if changed and names:
                st["pending"]["checkpoint"] = names[idx]
            if imgui.button("Refresh checkpoints"):
                st["names"] = ck_names()
            for line in st["readout"]:
                imgui.text(line)

        viewer.register_ui_callback(panel, position="side")
        print("[rf play] viewer window open — RoboForge panel is in the side bar (close the window or Ctrl+C to stop)")

        falls, steps, frames, t_last = 0, 0, 0, time.time()
        was_down = tilted(robot)
        while True:
            t0 = time.time()
            todo, st["pending"] = st["pending"], {}
            if "checkpoint" in todo:
                s.load(run.dir / todo["checkpoint"])
                st["ckpt"] = todo["checkpoint"]
                print(f"[rf play] loaded {todo['checkpoint']}")
            if todo.get("reset"):
                u.reset()
                obs, falls = s.env.get_observations(), 0
                was_down = tilted(robot)
            if st["kb"]:  # held keys set the command; releasing ramps it back to zero
                key = viewer.is_key_down
                dt = u.step_dt
                st["vx"] = _ramp(st["vx"], (key("i") - key("k")) * st["kb_speed"], 2.0 * dt)
                st["vy"] = _ramp(st["vy"], (key("j") - key("l")) * min(1.0, st["kb_speed"]), 2.0 * dt)
                st["wz"] = _ramp(st["wz"], (key("u") - key("o")) * st["kb_yaw"], 3.0 * dt)
            term.vel_command_b[:, 0] = st["vx"]
            term.vel_command_b[:, 1] = st["vy"]
            term.vel_command_b[:, 2] = st["wz"]
            with torch.inference_mode():
                obs, _, dones, _ = s.env.step(s.policy(obs))
                s.policy.reset(dones)
            down = tilted(robot)  # robot_lab never ends an episode on a flip, so measure it directly
            falls += int((down & ~was_down).sum())
            was_down = down
            steps += 1
            frames += 1
            if time.time() - t_last > 0.5:
                v = as_torch(robot.data.root_lin_vel_b).mean(0)
                w = as_torch(robot.data.root_ang_vel_b).mean(0)
                fps = frames / (time.time() - t_last)
                st["readout"] = [
                    f"forward  cmd {st['vx']:+.2f}  actual {float(v[0]):+.2f} m/s",
                    f"lateral  cmd {st['vy']:+.2f}  actual {float(v[1]):+.2f} m/s",
                    f"yaw      cmd {st['wz']:+.2f}  actual {float(w[2]):+.2f} rad/s",
                    f"falls (tilt > 60 deg): {falls}" + ("   DOWN NOW" if bool(down.any()) else ""),
                    f"sim {steps * u.step_dt:.0f} s   {fps:.0f} steps/s (real time {1 / u.step_dt:.0f})",
                ]
                t_last, frames = time.time(), 0
            if not viewer.is_running():
                return 0
            time.sleep(max(0.0, u.step_dt - (time.time() - t0)))


if __name__ == "__main__":
    raise SystemExit(main())
