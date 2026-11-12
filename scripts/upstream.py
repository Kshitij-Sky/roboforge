"""Inspect and switch the pinned upstreams (git submodules in third_party/).

    python scripts/upstream.py status
    python scripts/upstream.py available                 # tags newer than the current pins
    python scripts/upstream.py try --isaaclab v3.0.1 --robot-lab v3.0.1
    python scripts/upstream.py try --isaaclab main       # bleeding edge, on its own branch

`try` never touches the current branch. It:
  1. refuses to run with uncommitted changes,
  2. creates branch try/isaaclab-<ref>_robot_lab-<ref>,
  3. checks out the requested refs in the submodules,
  4. re-locks and re-syncs the uv environment, runs the tests,
  5. commits the new pins + uv.lock on that branch.
Then benchmark it (benchmarks/TRACKER.md protocol) and merge only if it beats the pinned pair.
Going back is `git checkout main && git submodule update && uv sync ...`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUBS = {"isaaclab": REPO / "third_party" / "IsaacLab", "robot_lab": REPO / "third_party" / "robot_lab"}
SYNC_EXTRAS = ["--extra", "importers", "--extra", "rsl-rl", "--extra", "ovphysx", "--extra", "video"]


def sh(*cmd, cwd=REPO, check=True) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"command failed: {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def describe(path: Path) -> str:
    return sh("git", "-C", str(path), "describe", "--tags", "--always", check=False) or "?"


def status() -> None:
    for name, p in SUBS.items():
        sha = sh("git", "-C", str(p), "rev-parse", "--short", "HEAD", check=False)
        print(f"{name:10s} {describe(p):28s} {sha}")


def available() -> None:
    for name, p in SUBS.items():
        sh("git", "-C", str(p), "fetch", "--tags", "--quiet", "origin", check=False)
        cur = describe(p).split("-")[0]
        tags = sh("git", "-C", str(p), "tag", "--sort=-v:refname", check=False).splitlines()
        newer = [t for t in tags if t.startswith("v") and t != cur][:8]
        print(f"{name:10s} current {cur:12s} recent tags: {', '.join(newer)}")


def try_refs(isaaclab: str | None, robot_lab: str | None) -> None:
    if sh("git", "status", "--porcelain", "--ignore-submodules=dirty"):
        sys.exit("working tree has uncommitted changes — commit or stash first")
    uv = shutil.which("uv") or sys.exit("uv not on PATH")
    refs = {"isaaclab": isaaclab, "robot_lab": robot_lab}
    branch = "try/" + "_".join(f"{k}-{v}" for k, v in refs.items() if v).replace("/", "-")
    sh("git", "checkout", "-b", branch)
    for name, ref in refs.items():
        if not ref:
            continue
        p = SUBS[name]
        sh("git", "-C", str(p), "fetch", "--tags", "origin")
        target = f"origin/{ref}" if ref in ("main", "master", "devel") else ref
        sh("git", "-C", str(p), "checkout", "--quiet", target)
        print(f"{name} -> {describe(p)}")
    print("re-locking and syncing (this can take a while)...")
    subprocess.run([uv, "lock"], cwd=REPO, check=True)
    subprocess.run([uv, "sync", *SYNC_EXTRAS], cwd=REPO, check=True)
    tests = subprocess.run([uv, "run", "pytest", "-q"], cwd=REPO)
    sh("git", "add", "third_party", "uv.lock")
    sh("git", "commit", "-m", f"Try upstreams: {', '.join(f'{k}={v}' for k, v in refs.items() if v)}")
    print(f"\nOn branch {branch}. Tests {'passed' if tests.returncode == 0 else 'FAILED'}.")
    print("Next: run the benchmark protocol (benchmarks/TRACKER.md) and compare against the pinned pair.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("available")
    t = sub.add_parser("try")
    t.add_argument("--isaaclab")
    t.add_argument("--robot-lab")
    a = ap.parse_args()
    if a.cmd == "status":
        status()
    elif a.cmd == "available":
        available()
    else:
        if not (a.isaaclab or a.robot_lab):
            sys.exit("give --isaaclab and/or --robot-lab")
        try_refs(a.isaaclab, a.robot_lab)


if __name__ == "__main__":
    main()
