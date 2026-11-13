"""Experiments and runs, without a database.

* An **experiment** is a YAML file in ``experiments/``: base task + physics + training budget +
  config overrides (reward weights, command ranges, network size, ...). It is the thing you edit.
* A **run** is one training of an experiment: ``logs/rsl_rl/<experiment>/<run_id>/``. It holds
  RSL-RL's checkpoints (``model_<iter>.pt``), Isaac Lab's resolved configs (``params/``), the
  training log (``train.log``), and our manifest (``roboforge_run.json``). The manifest freezes
  everything needed to replay the run exactly: the experiment as it was at launch, the full
  override list, the joint/body ordering, the git commit and an uncommitted-changes patch.

Editing an experiment or the task code never touches a run that already exists: a running
training has already imported its config, and every later play/eval of that run re-applies the
overrides frozen in its manifest. ``code_drift()`` warns when the code has moved since launch.

No Isaac Lab import here — usable from any Python.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
EXPERIMENTS = REPO / "experiments"
LOGS = REPO / "logs" / "rsl_rl"
MANIFEST = "roboforge_run.json"


# --------------------------------------------------------------------------- experiments

@dataclass
class Experiment:
    name: str
    task: str
    physics: str = "newton_mjwarp"
    num_envs: int = 4096
    max_iterations: int = 1500
    seed: int = 42
    description: str = ""
    overrides: dict = field(default_factory=dict)
    raw_text: str = ""

    def override_args(self) -> list[str]:
        return [f"{k}={hydra_value(v)}" for k, v in self.overrides.items()]


def hydra_value(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(hydra_value(x) for x in v) + "]"
    return str(v)


def list_experiments() -> list[str]:
    return sorted(p.stem for p in EXPERIMENTS.glob("*.yaml"))


def load_experiment(name: str) -> Experiment:
    path = EXPERIMENTS / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no experiment '{name}' (have: {', '.join(list_experiments())})")
    text = path.read_text(encoding="utf-8")
    d = yaml.safe_load(text) or {}
    unknown = set(d) - {"task", "physics", "num_envs", "max_iterations", "seed", "description", "overrides"}
    if unknown:
        raise ValueError(f"{path.name}: unknown keys {sorted(unknown)}")
    return Experiment(name=name, raw_text=text, overrides=dict(d.pop("overrides", None) or {}), **d)


def ordering_for(physics: str) -> str:
    """One joint/body ordering convention per run, kept for every later playback (Isaac Lab guidance)."""
    return "physx" if "physx" in physics else "mjwarp"


# --------------------------------------------------------------------------- git snapshot

def _git(*args: str, cwd: Path = REPO) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def code_state() -> dict:
    diff = _git("diff", "HEAD", "--", "src", "experiments", "robots", "benchmarks/reference_robots.yaml")
    return {
        "commit": _git("rev-parse", "--short", "HEAD"),
        "dirty_diff_sha1": hashlib.sha1(diff.encode()).hexdigest()[:12] if diff else None,
        "isaaclab": _git("describe", "--tags", "--always", cwd=REPO / "third_party" / "IsaacLab"),
        "robot_lab": _git("describe", "--tags", "--always", cwd=REPO / "third_party" / "robot_lab"),
        "_diff": diff,
    }


# --------------------------------------------------------------------------- runs

@dataclass
class Run:
    dir: Path
    manifest: dict

    @property
    def id(self) -> str:
        return f"{self.dir.parent.name}/{self.dir.name}"

    @property
    def experiment(self) -> str:
        return self.manifest.get("experiment", self.dir.parent.name)

    def checkpoints(self) -> list[tuple[int, Path]]:
        out = []
        for p in self.dir.glob("model_*.pt"):
            m = re.match(r"model_(\d+)\.pt$", p.name)
            if m:
                out.append((int(m.group(1)), p))
        return sorted(out)

    def checkpoint(self, which: str | int = "latest") -> Path:
        ck = self.checkpoints()
        if not ck:
            raise FileNotFoundError(f"{self.id}: no checkpoints yet")
        if which in ("latest", None):
            return ck[-1][1]
        it = int(which)
        for i, p in ck:
            if i == it:
                return p
        raise FileNotFoundError(f"{self.id}: no model_{it}.pt (have {[i for i, _ in ck]})")

    def status(self) -> str:
        pid = self.manifest.get("pid")
        if pid and _pid_alive(pid) and (dt.datetime.now().timestamp() - self._log_mtime()) < 600:
            return "running"
        ck = self.checkpoints()
        target = self.manifest.get("max_iterations")
        if ck and target and ck[-1][0] >= target - 1:
            return "done"
        return "stopped" if ck else "failed"

    def _log_mtime(self) -> float:
        p = self.dir / "train.log"
        return p.stat().st_mtime if p.exists() else 0.0

    def metrics(self) -> dict:
        return parse_log(self.dir / "train.log")

    def evals(self) -> list[dict]:
        out = []
        for p in sorted((self.dir / "eval").glob("*.json")):
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        return out

    def play_args(self) -> list[str]:
        """Everything a play/eval needs to rebuild this run's environment exactly."""
        m = self.manifest
        return [*m.get("overrides", []), *m.get("ordering_overrides", [])]


def _pid_alive(pid: int) -> bool:
    try:
        import psutil

        return psutil.pid_exists(int(pid))
    except Exception:
        return False


def all_runs(experiment: str | None = None) -> list[Run]:
    runs = []
    for mf in LOGS.glob(f"*/*/{MANIFEST}"):
        try:
            runs.append(Run(mf.parent, json.loads(mf.read_text(encoding="utf-8"))))
        except Exception:
            pass
    if experiment:
        runs = [r for r in runs if r.experiment == experiment]
    return sorted(runs, key=lambda r: r.manifest.get("started") or "")


def find_run(key: str) -> Run:
    """Resolve 'exp/run_id', 'run_id', 'exp' (-> its latest run) or a run directory path."""
    p = Path(key)
    if (p / MANIFEST).exists():
        return Run(p.resolve(), json.loads((p / MANIFEST).read_text(encoding="utf-8")))
    runs = all_runs()
    hits = [r for r in runs if r.id == key or r.dir.name == key]
    if not hits:
        hits = [r for r in runs if r.experiment == key]
    if not hits:
        raise LookupError(f"no run matches '{key}'. `rf runs` lists them.")
    return hits[-1]


def new_run_dir(experiment: str) -> tuple[str, Path]:
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    d = LOGS / experiment / run_id
    d.mkdir(parents=True, exist_ok=False)
    return run_id, d


def write_manifest(run_dir: Path, data: dict) -> None:
    (run_dir / MANIFEST).write_text(json.dumps(data, indent=2), encoding="utf-8")


def relevant_paths(task: str) -> list[str]:
    """Code that can change what a run's environment looks like to its policy."""
    paths = ["third_party", "src/roboforge/compat.py"]
    if task.startswith("RoboForge-"):
        paths += ["src/roboforge/tasks", "robots", "benchmarks/reference_robots.yaml"]
    return paths


def relevant_diff_sha1(task: str) -> str | None:
    diff = _git("diff", "HEAD", "--", *relevant_paths(task))
    return hashlib.sha1(diff.encode()).hexdigest()[:12] if diff else None


def code_drift(run: Run) -> list[str]:
    """Reasons the code that defines this run's environment differs from the code it trained with.

    Only paths that can change the policy's environment are checked (upstream pins, our compat
    shims, and for RoboForge tasks our task/robot code), so unrelated edits stay silent.
    """
    rec, task = run.manifest.get("code", {}), run.manifest.get("task", "")
    paths = relevant_paths(task)
    msgs = []
    head = _git("rev-parse", "--short", "HEAD")
    if rec.get("commit") and rec["commit"] != head:
        changed = _git("diff", "--name-only", rec["commit"], "HEAD", "--", *paths)
        if changed:
            msgs.append(f"changed since commit {rec['commit']}: {', '.join(changed.splitlines()[:6])}")
    if "relevant_diff_sha1" in rec and rec["relevant_diff_sha1"] != relevant_diff_sha1(task):
        msgs.append("uncommitted changes to this task's code differ from those at launch (see code.patch)")
    return msgs


# --------------------------------------------------------------------------- RSL-RL log parsing

_RE_ITER = re.compile(r"Learning iteration\s+(\d+)\s*/\s*(\d+)")
_RE_KV = re.compile(r"^\s*([A-Za-z_][\w/ .\-]*?):\s+(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)s?\s*$")


def parse_log(path: Path) -> dict:
    """Last complete iteration block of an RSL-RL log: {'iteration', 'max', 'Mean reward', ...}."""
    if not path.exists():
        return {}
    last, cur = {}, {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = re.sub(r"\x1b\[[0-9;]*m", "", raw)
            if m := _RE_ITER.search(line):
                if cur:
                    last = cur
                cur = {"iteration": int(m.group(1)), "max": int(m.group(2))}
            elif cur and (m := _RE_KV.match(line)):
                cur[m.group(1).strip()] = float(m.group(2))
    return cur if "Mean reward" in cur else (last or cur)


def tee_to(path: Path):
    """Line-buffered append handle for a training log."""
    return open(path, "a", encoding="utf-8", errors="replace", buffering=1)


def env_for_subprocess() -> dict:
    return {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
