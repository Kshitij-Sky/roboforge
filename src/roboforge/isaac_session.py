"""Build an Isaac Lab environment + a trained RSL-RL policy, the way `isaaclab play` does.

Shared by `roboforge.play` (interactive viewer) and `roboforge.evaluate` (benchmarks).
Mirrors Isaac Lab v3.0.0 isaaclab_rl/entrypoints/backends/play_rsl_rl.py; only the hooks are ours.
Requires the Isaac Lab runtime (uv environment).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any


def load_task_entry_points() -> None:
    """Register external tasks like the `isaaclab` CLI does — roboforge first (see roboforge/compat.py)."""
    eps = sorted(importlib.metadata.entry_points(group="isaaclab.tasks"), key=lambda e: e.name != "roboforge")
    for ep in eps:
        ep.load()


def as_torch(x):
    """Isaac Lab 3.0 asset data are ProxyArrays; return the torch view."""
    return x.torch if hasattr(x, "torch") else x


def validation_conditions(cfg) -> None:
    """Clean conditions for watching or measuring a policy (not for training).

    robot_lab trains wheeled robots with resets in a random roll/pitch/yaw (self-righting), a
    constant random push wrench applied at reset, and periodic shoves. All three make a speed
    test or a visual check unreadable, so validation resets the robot upright, centred and facing
    +x, with no pushes.
    """
    ev = getattr(cfg, "events", None)
    if ev is None:
        return
    reset = getattr(ev, "randomize_reset_base", None) or getattr(ev, "reset_base", None)
    if reset is not None and "pose_range" in reset.params:
        reset.params["pose_range"] = {}
        reset.params["velocity_range"] = {}
    for name in ("randomize_push_robot", "push_robot", "randomize_apply_external_force_torque",
                 "base_external_force_torque"):
        if getattr(ev, name, None) is not None:
            setattr(ev, name, None)


def tilted(robot, limit_deg: float = 60.0):
    """True where the base is tilted more than `limit_deg` from upright (a fall, measured directly)."""
    import math

    return as_torch(robot.data.projected_gravity_b)[:, 2] > -math.cos(math.radians(limit_deg))


@dataclass
class Session:
    env: Any  # RslRlVecEnvWrapper
    runner: Any
    policy: Any
    device: Any

    @property
    def unwrapped(self):
        return self.env.unwrapped

    def load(self, model_path: str) -> None:
        """Swap in another checkpoint of the same run (same network shape)."""
        self.runner.load(str(model_path))
        self.policy = self.runner.get_inference_policy(device=self.device)


@contextlib.contextmanager
def session(
    task: str,
    model_path: str,
    *,
    physics: str,
    overrides: list[str] | None = None,
    viz: str = "none",
    env_cfg_hook: Callable[[Any], None] | None = None,
    play_mode: bool = True,
) -> Iterator[Session]:
    load_task_entry_points()

    from isaaclab.app import add_launcher_args, launch_simulation
    from isaaclab.utils.string import list_intersection
    from isaaclab_rl.entrypoints.backends import cli_args_rsl_rl as cli_args
    from isaaclab_rl.entrypoints.common import (
        add_common_play_args,
        close_env,
        create_isaaclab_env,
        set_hydra_args,
    )
    from isaaclab_rl.rsl_rl import (
        RslRlVecEnvWrapper,
        check_rsl_rl_version,
        create_rsl_rl_runner,
        handle_deprecated_rsl_rl_cfg,
    )
    from isaaclab_tasks.utils import resolve_task_config, setup_preset_cli

    argv = ["--task", task, "--viz", viz, f"physics={physics}", *(overrides or [])]
    ap = argparse.ArgumentParser()
    add_common_play_args(ap, agent_default="rsl_rl_cfg_entry_point", agent_help="RL agent config entry point.")
    cli_args.add_rsl_rl_args(ap)
    add_launcher_args(ap)
    reg_args = cli_args.register_external_tasks(argv)
    args, remaining = setup_preset_cli(ap, argv)
    set_hydra_args(list_intersection(remaining, reg_args))

    installed = check_rsl_rl_version()
    env_cfg, agent_cfg = resolve_task_config(task, args.agent, play_mode=play_mode)
    if env_cfg_hook:
        env_cfg_hook(env_cfg)

    with launch_simulation(env_cfg, args), contextlib.ExitStack() as cleanup:
        agent_cfg = handle_deprecated_rsl_rl_cfg(cli_args.update_rsl_rl_cfg(agent_cfg, args), installed)
        env = create_isaaclab_env(task, env_cfg, args, convert_marl_to_single_agent=False)
        cleanup.callback(lambda: close_env(env))
        env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
        runner = create_rsl_rl_runner(env, agent_cfg)
        runner.load(str(model_path))
        device = env.unwrapped.device
        yield Session(env=env, runner=runner, policy=runner.get_inference_policy(device=device), device=device)
