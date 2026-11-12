"""Training benchmark: run an Isaac Lab RSL-RL training job and record what the machine did.

    uv run python scripts/bench_training.py --task RobotLab-Isaac-Velocity-Flat-Unitree-B2W-v0 \
        --physics newton_mjwarp --num-envs 4096 --iterations 50

Records, per run, into benchmarks/results/<timestamp>_<task>_<physics>_<envs>.json:
  * throughput: env-steps/s per iteration (median over the second half -> excludes warm-up)
  * thermal drift: median steps/s of the first vs last quarter (laptop GPUs throttle)
  * peak GPU memory (nvidia-smi, minus the idle baseline), utilisation, temperature, SM clock, power
  * peak RAM of the training process tree
  * learning signal: mean reward / episode length / every "key: value" metric of the last iteration
  * status: ok | oom | crash | timeout, with the log tail on failure
and appends one row to benchmarks/results/summary.csv.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "benchmarks" / "results"

RE_ITER = re.compile(r"Learning iteration\s+(\d+)\s*/\s*(\d+)")
RE_STEPS = re.compile(r"(?:Steps per second:|Computation:)\s*([\d,.]+)")  # rsl_rl 5.x | older
RE_KV = re.compile(r"^\s*([A-Za-z_][\w/ .\-]*?):\s+(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*$")
OOM_MARKERS = ("out of memory", "CUDA_ERROR_OUT_OF_MEMORY", "cudaErrorMemoryAllocation", "OutOfMemoryError")


def gpu_query() -> dict | None:
    q = "memory.used,memory.total,utilization.gpu,temperature.gpu,clocks.sm,power.draw,name,driver_version"
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()[0]
    except Exception:
        return None
    f = [x.strip() for x in out.split(",")]

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None

    return {"mem_used_mb": num(f[0]), "mem_total_mb": num(f[1]), "util_pct": num(f[2]), "temp_c": num(f[3]),
            "sm_clock_mhz": num(f[4]), "power_w": num(f[5]), "name": f[6], "driver": f[7]}


class Sampler(threading.Thread):
    """Samples GPU state and process-tree RSS every `period` seconds."""

    def __init__(self, period: float = 2.0):
        super().__init__(daemon=True)
        self.period, self.samples, self.pid, self._halt = period, [], None, threading.Event()

    def run(self):
        try:
            import psutil
        except ImportError:
            psutil = None
        while not self._halt.is_set():
            s = gpu_query() or {}
            s["t"] = time.time()
            if psutil and self.pid:
                try:
                    p = psutil.Process(self.pid)
                    s["rss_mb"] = sum(c.memory_info().rss for c in [p, *p.children(recursive=True)]) / 2**20
                except Exception:
                    pass
            self.samples.append(s)
            self._halt.wait(self.period)

    def stop(self):
        self._halt.set()


def git_rev(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "describe", "--tags", "--always", "--dirty"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


def pkg_versions() -> dict:
    from importlib import metadata

    out = {}
    for p in ("torch", "warp-lang", "newton", "mujoco", "mujoco-warp", "rsl-rl-lib", "ovphysx"):
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--physics", default="newton_mjwarp", help="newton_mjwarp | ovphysx | newton_steel | ...")
    ap.add_argument("--num-envs", type=int, default=4096)
    ap.add_argument("--iterations", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--timeout-min", type=float, default=120.0)
    ap.add_argument("--label", default="", help="free-text tag stored with the result")
    ap.add_argument("extra", nargs="*", help="extra overrides passed through to `isaaclab train`")
    a = ap.parse_args()

    exe = shutil.which("isaaclab")
    if not exe:
        print("`isaaclab` not on PATH — run this with `uv run python scripts/bench_training.py ...`")
        return 2
    cmd = [exe, "train", "--rl_library", "rsl_rl", "--task", a.task, "--num_envs", str(a.num_envs),
           "--max_iterations", str(a.iterations), "--seed", str(a.seed), "--viz", "none",
           f"physics={a.physics}", *a.extra]

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    short = a.task.replace("RobotLab-Isaac-Velocity-", "").replace("Isaac-Velocity-", "").replace("-v0", "")
    RESULTS.mkdir(parents=True, exist_ok=True)
    log_path = RESULTS / f"{stamp}_{short}_{a.physics}_{a.num_envs}.log"

    baseline = gpu_query() or {}
    sampler = Sampler()
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    print("running:", " ".join(cmd))
    t0 = time.time()
    iters, steps, last_kv, status = [], [], {}, "ok"
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=env)
        sampler.pid = proc.pid
        sampler.start()
        cur = {}
        try:
            for line in proc.stdout:
                log.write(line)
                if m := RE_ITER.search(line):
                    if cur:
                        last_kv = cur
                    cur = {}
                    iters.append((int(m.group(1)), time.time()))
                if m := RE_STEPS.search(line):
                    steps.append(float(m.group(1).replace(",", "")))
                if m := RE_KV.match(line):
                    cur[m.group(1).strip()] = float(m.group(2))
                if any(k in line for k in OOM_MARKERS):
                    status = "oom"
                if time.time() - t0 > a.timeout_min * 60:
                    status = "timeout"
                    proc.kill()
                    break
            proc.wait()
        finally:
            sampler.stop()
        if cur:
            last_kv = cur
    wall = time.time() - t0
    if status == "ok" and proc.returncode != 0:
        status = "crash"

    smp = sampler.samples
    def peak(k):
        v = [s[k] for s in smp if s.get(k) is not None]
        return max(v) if v else None
    def med(k):
        v = [s[k] for s in smp if s.get(k) is not None]
        return statistics.median(v) if v else None

    half = steps[len(steps) // 2:] or steps
    q = max(1, len(steps) // 4)
    res = {
        "timestamp": stamp,
        "label": a.label,
        "task": a.task, "physics": a.physics, "num_envs": a.num_envs, "iterations_requested": a.iterations,
        "seed": a.seed, "status": status, "returncode": proc.returncode,
        "wall_s": round(wall, 1),
        "iterations_completed": len(iters),
        "steps_per_s_median": round(statistics.median(half)) if half else None,
        "steps_per_s_first_quarter": round(statistics.median(steps[:q])) if steps else None,
        "steps_per_s_last_quarter": round(statistics.median(steps[-q:])) if steps else None,
        "gpu_mem_peak_mb": peak("mem_used_mb"),
        "gpu_mem_baseline_mb": baseline.get("mem_used_mb"),
        "gpu_util_median_pct": med("util_pct"),
        "gpu_temp_peak_c": peak("temp_c"),
        "gpu_sm_clock_median_mhz": med("sm_clock_mhz"),
        "gpu_power_median_w": med("power_w"),
        "ram_peak_mb": peak("rss_mb"),
        "last_iteration_metrics": last_kv,
        "machine": {"gpu": baseline.get("name"), "driver": baseline.get("driver"),
                    "gpu_mem_total_mb": baseline.get("mem_total_mb"), "os": platform.platform(),
                    "python": platform.python_version()},
        "versions": {"roboforge": git_rev(REPO), "isaaclab": git_rev(REPO / "third_party" / "IsaacLab"),
                     "robot_lab": git_rev(REPO / "third_party" / "robot_lab"), **pkg_versions()},
        "command": cmd,
        "log": log_path.name,
    }
    if status != "ok":
        res["log_tail"] = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]

    out = log_path.with_suffix(".json")
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    summary = RESULTS / "summary.csv"
    cols = ["timestamp", "label", "task", "physics", "num_envs", "status", "iterations_completed", "wall_s",
            "steps_per_s_median", "steps_per_s_first_quarter", "steps_per_s_last_quarter", "gpu_mem_peak_mb",
            "gpu_temp_peak_c", "gpu_sm_clock_median_mhz", "ram_peak_mb"]
    new = not summary.exists()
    with open(summary, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(res)

    print(json.dumps({k: res[k] for k in cols if k in res}, indent=2))
    print("result:", out.relative_to(REPO))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
