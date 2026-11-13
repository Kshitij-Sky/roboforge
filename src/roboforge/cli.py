"""`rf` — the RoboForge experiment tool.

    uv run rf experiments                      list experiment files
    uv run rf new <name> --from <experiment>   copy an experiment to edit
    uv run rf train <experiment> [--set k=v ...] [--iterations N] [--physics P] [--detach] [--note "..."]
    uv run rf runs [experiment]                every run: status, progress, metrics, latest eval
    uv run rf play <run> [--checkpoint N] [--physics P]   watch + drive it in Newton's viewer window
    uv run rf eval <run> [--axis forward|lateral|yaw] [--checkpoint N] [--physics P] [--speeds ...]
    uv run rf compare <run> <run> ...
    uv run rf adopt <run_dir> --experiment <name>   register a run trained without rf

<run> is "experiment/run_id", a run_id, or an experiment name (= its latest run).
Training, playing and evaluating can run at the same time on one GPU (8 GB is enough for one
4096-env training plus one playback); the training just slows down a little.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import runs as R


def _fmt(x, nd=2):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def cmd_experiments(_a) -> int:
    for name in R.list_experiments():
        e = R.load_experiment(name)
        n_runs = len(R.all_runs(name))
        print(f"{name:32s} {e.physics:14s} {e.max_iterations:6d} it  runs:{n_runs:<3d} {e.description[:60]}")
    return 0


def cmd_new(a) -> int:
    src = R.EXPERIMENTS / f"{a.source}.yaml"
    dst = R.EXPERIMENTS / f"{a.name}.yaml"
    if dst.exists():
        sys.exit(f"{dst.name} already exists")
    text = src.read_text(encoding="utf-8")
    dst.write_text(f"# copied from {a.source} on {dt.date.today()}\n{text}", encoding="utf-8")
    print(f"created {dst.relative_to(R.REPO)} — edit it, then: uv run rf train {a.name}")
    return 0


def cmd_train(a) -> int:
    exp = R.load_experiment(a.experiment)
    physics = a.physics or exp.physics
    iters = a.iterations or exp.max_iterations
    envs = a.envs or exp.num_envs
    conv = R.ordering_for(physics)
    ordering = [f"env.scene.robot.joint_ordering={conv}", f"env.scene.robot.body_ordering={conv}"]
    overrides = [*exp.override_args(), *a.set]
    exe = shutil.which("isaaclab") or sys.exit("`isaaclab` not found — run through `uv run rf ...`")

    run_id, run_dir = R.new_run_dir(exp.name)
    code = R.code_state()
    code["relevant_diff_sha1"] = R.relevant_diff_sha1(exp.task)
    diff = code.pop("_diff")
    if diff:
        (run_dir / "code.patch").write_text(diff, encoding="utf-8")
    cmd = [exe, "train", "--rl_library", "rsl_rl", "--task", exp.task, "--num_envs", str(envs),
           "--max_iterations", str(iters), "--seed", str(a.seed or exp.seed), "--viz", "none",
           "--run_timestamp", run_id, f"physics={physics}", f"agent.experiment_name={exp.name}",
           *overrides, *ordering]
    manifest = {
        "run_id": run_id, "experiment": exp.name, "task": exp.task, "physics": physics,
        "num_envs": envs, "max_iterations": iters, "seed": a.seed or exp.seed,
        "overrides": overrides, "ordering_overrides": ordering, "note": a.note,
        "experiment_yaml": exp.raw_text, "started": dt.datetime.now().isoformat(timespec="seconds"),
        "code": code, "command": cmd, "pid": None,
    }
    R.write_manifest(run_dir, manifest)
    log = run_dir / "train.log"
    print(f"[rf] run {exp.name}/{run_id}  ({physics}, {envs} envs, {iters} it)")
    print(f"[rf] folder {run_dir.relative_to(R.REPO)}   log {log.name}")
    if diff:
        print("[rf] note: uncommitted changes recorded in code.patch")

    if a.detach:
        flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | NEW_PROCESS_GROUP
        with open(log, "a", encoding="utf-8") as fh:
            p = subprocess.Popen(cmd, cwd=R.REPO, stdout=fh, stderr=subprocess.STDOUT, env=R.env_for_subprocess(),
                                 creationflags=flags, start_new_session=sys.platform != "win32")
        manifest["pid"] = p.pid
        R.write_manifest(run_dir, manifest)
        print(f"[rf] training in background (pid {p.pid}). Watch: uv run rf runs   Play: uv run rf play {exp.name}")
        return 0

    p = subprocess.Popen(cmd, cwd=R.REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", env=R.env_for_subprocess())
    manifest["pid"] = p.pid
    R.write_manifest(run_dir, manifest)
    try:
        with R.tee_to(log) as fh:
            for line in p.stdout:
                fh.write(line)
                if "Learning iteration" in line or "Mean reward" in line or "Error" in line or "Traceback" in line:
                    sys.stdout.write(line)
    except KeyboardInterrupt:
        p.terminate()
        print("\n[rf] stopped by user; checkpoints so far are kept")
    return p.wait()


def cmd_runs(a) -> int:
    runs = R.all_runs(a.experiment)
    if not runs:
        print("no runs yet — `uv run rf train <experiment>`")
        return 0
    hdr = f"{'RUN':40s} {'STATUS':8s} {'PHYSICS':14s} {'ITER':>11s} {'REWARD':>7s} {'TRK_LIN':>7s} {'CKPT':>6s}  EVAL max-tracked/real"
    print(hdr)
    for r in runs:
        m = r.metrics()
        ck = r.checkpoints()
        ev = r.evals()
        last_ev = ev[-1] if ev else None
        ev_s = (f"{_fmt(last_ev['max_tracked_speed_mps'])}/{_fmt(last_ev['real_rated_max_speed_mps'])} m/s "
                f"({last_ev['physics']}, {last_ev['checkpoint']})") if last_ev else "-"
        it = f"{m.get('iteration', '-')}/{r.manifest.get('max_iterations', '?')}"
        print(f"{r.id:40s} {r.status():8s} {r.manifest.get('physics', '?'):14s} {it:>11s} "
              f"{_fmt(m.get('Mean reward'), 1):>7s} {_fmt(m.get('Episode_Reward/track_lin_vel_xy_exp')):>7s} "
              f"{(ck[-1][0] if ck else '-'):>6}  {ev_s}")
        if r.manifest.get("note"):
            print(f"{'':40s} note: {r.manifest['note']}")
    return 0


def cmd_play(a) -> int:
    from .play import main as play_main

    argv = [a.run, "--checkpoint", a.checkpoint, "--envs", str(a.envs)]
    if a.physics:
        argv += ["--physics", a.physics]
    if a.vmax:
        argv += ["--vmax", str(a.vmax)]
    if a.train_conditions:
        argv += ["--train-conditions"]
    return play_main(argv)


def cmd_eval(a) -> int:
    from .evaluate import main as eval_main

    argv = [a.run, "--checkpoint", a.checkpoint, "--envs-per-speed", str(a.envs_per_speed), "--seconds", str(a.seconds), "--axis", a.axis]
    if a.physics:
        argv += ["--physics", a.physics]
    if a.speeds:
        argv += ["--speeds", *map(str, a.speeds)]
    if a.set:
        argv += ["--set", *a.set]
    return eval_main(argv)


def cmd_compare(a) -> int:
    rs = [R.find_run(k) for k in a.runs]
    rows = [("run", [r.id for r in rs]), ("experiment", [r.experiment for r in rs]),
            ("physics", [r.manifest.get("physics") for r in rs]),
            ("status", [r.status() for r in rs])]
    ms = [r.metrics() for r in rs]
    for key, label in (("iteration", "iteration"), ("Mean reward", "mean reward"),
                       ("Mean episode length", "episode length"),
                       ("Episode_Reward/track_lin_vel_xy_exp", "track lin"),
                       ("Episode_Reward/track_ang_vel_z_exp", "track yaw")):
        rows.append((label, [_fmt(m.get(key)) for m in ms]))
    all_ov = sorted({o.split("=")[0] for r in rs for o in r.manifest.get("overrides", [])})
    for k in all_ov:
        vals = [next((o.split("=", 1)[1] for o in r.manifest.get("overrides", []) if o.startswith(k + "=")), "-") for r in rs]
        rows.append((k, vals))
    for r_i, r in enumerate(rs):
        for e in r.evals():
            label = f"eval {e['checkpoint']} on {e['physics']}"
            vals = ["-"] * len(rs)
            vals[r_i] = " ".join(f"{row['cmd_mps']:g}->{row['achieved_mps']:.2f}" for row in e["rows"])
            rows.append((label, vals))
    w = max(len(lbl) for lbl, _ in rows)
    for lbl, vals in rows:
        print(f"{lbl:<{w}}  " + "  |  ".join(str(v) for v in vals))
    return 0


def cmd_adopt(a) -> int:
    d = Path(a.run_dir).resolve()
    if (d / R.MANIFEST).exists():
        sys.exit("already has a manifest")
    rj = json.loads((d / "run.json").read_text(encoding="utf-8")) if (d / "run.json").exists() else {}
    task = a.task or rj.get("task") or sys.exit("task unknown — pass --task")
    agent_yaml = (d / "params" / "agent.yaml").read_text(encoding="utf-8") if (d / "params" / "agent.yaml").exists() else ""
    iters = next((int(l.split(":")[1]) for l in agent_yaml.splitlines() if l.startswith("max_iterations:")), None)
    conv = R.ordering_for(a.physics)
    R.write_manifest(d, {
        "run_id": d.name, "experiment": a.experiment, "task": task, "physics": a.physics,
        "max_iterations": iters, "overrides": [], "note": a.note or "adopted (trained without rf)",
        # trained without explicit ordering = the training engine's native order
        "ordering_overrides": [f"env.scene.robot.joint_ordering={conv}", f"env.scene.robot.body_ordering={conv}"],
        "started": rj.get("created_at"), "code": {"commit": a.commit}, "adopted": True,
    })
    print(f"adopted {d.relative_to(R.REPO)} as experiment '{a.experiment}'")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rf", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("experiments").set_defaults(fn=cmd_experiments)
    p = sub.add_parser("new"); p.add_argument("name"); p.add_argument("--from", dest="source", required=True); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("train")
    p.add_argument("experiment"); p.add_argument("--set", nargs="*", default=[], help="extra overrides, e.g. env.rewards.upward.weight=0")
    p.add_argument("--iterations", type=int); p.add_argument("--envs", type=int); p.add_argument("--physics"); p.add_argument("--seed", type=int)
    p.add_argument("--note", default=""); p.add_argument("--detach", action="store_true", help="run in the background")
    p.set_defaults(fn=cmd_train)
    p = sub.add_parser("runs"); p.add_argument("experiment", nargs="?"); p.set_defaults(fn=cmd_runs)
    p = sub.add_parser("play"); p.add_argument("run"); p.add_argument("--checkpoint", default="latest")
    p.add_argument("--physics"); p.add_argument("--envs", type=int, default=1); p.add_argument("--vmax", type=float)
    p.add_argument("--train-conditions", action="store_true", help="keep random-flip resets and pushes"); p.set_defaults(fn=cmd_play)
    p = sub.add_parser("eval"); p.add_argument("run"); p.add_argument("--checkpoint", default="latest"); p.add_argument("--physics")
    p.add_argument("--axis", choices=("forward", "lateral", "yaw"), default="forward")
    p.add_argument("--speeds", type=float, nargs="+"); p.add_argument("--envs-per-speed", type=int, default=64)
    p.add_argument("--seconds", type=float, default=10.0); p.add_argument("--set", nargs="*", default=[]); p.set_defaults(fn=cmd_eval)
    p = sub.add_parser("compare"); p.add_argument("runs", nargs="+"); p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("adopt"); p.add_argument("run_dir"); p.add_argument("--experiment", required=True)
    p.add_argument("--physics", default="newton_mjwarp"); p.add_argument("--task"); p.add_argument("--commit", default=None)
    p.add_argument("--note", default=""); p.set_defaults(fn=cmd_adopt)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
