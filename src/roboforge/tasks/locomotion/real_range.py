"""Benchmark B4 tasks: robot_lab's wheeled tasks retargeted to the REAL robot's operating envelope.

robot_lab v3.0.0 trains B2-W on +-1 m/s commands with a 20 N.m wheel limit [CFG]. The real
machine is rated 4.17 m/s with 40 N.m wheels [U]. These variants change only the envelope:
  * forward command range up to the rated top speed (reverse kept at robot_lab's -1 m/s)
  * wheel effort limit = the real wheel torque
  * robot_lab's own (commented-out) command curriculum (0.2 -> 1.0) switched on, so the policy
    is not asked for 4 m/s on its first iteration
Everything else (rewards, observations, randomization, robot model) stays robot_lab's.
Real values come from benchmarks/reference_robots.yaml, the single source for them.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.utils import configclass

import robot_lab.tasks.manager_based.locomotion.velocity.mdp as mdp
from robot_lab.tasks.manager_based.locomotion.velocity.config.wheeled.unitree_b2w.agents.rsl_rl_ppo_cfg import (
    UnitreeB2WFlatPPORunnerCfg,
)
from robot_lab.tasks.manager_based.locomotion.velocity.config.wheeled.unitree_b2w.flat_env_cfg import (
    UnitreeB2WFlatEnvCfg,
)

_REF = yaml.safe_load(
    (Path(__file__).resolve().parents[4] / "benchmarks" / "reference_robots.yaml").read_text(encoding="utf-8")
)
B2W_REAL = _REF["unitree_b2w"]["real"]


@configclass
class B2WFlatRealRangeEnvCfg(UnitreeB2WFlatEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        vmax = float(B2W_REAL["max_speed_mps"])
        self.commands.base_velocity.ranges.lin_vel_x = (-1.0, vmax)
        self.scene.robot.actuators["wheel"].joint_effort_limit = float(B2W_REAL["max_wheel_torque_nm"])
        self.scene.robot.actuators["wheel"].joint_velocity_limit = float(B2W_REAL["max_wheel_speed_radps"])
        self.curriculum.command_levels_lin_vel = CurrTerm(
            func=mdp.command_levels_lin_vel,
            params={"reward_term_name": "track_lin_vel_xy_exp", "range_multiplier": (0.2, 1.0)},
        )
        self.disable_zero_weight_rewards()  # robot_lab only runs this for its exact class names


@configclass
class B2WFlatRealRangePPORunnerCfg(UnitreeB2WFlatPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "b2w_flat_real_range"
