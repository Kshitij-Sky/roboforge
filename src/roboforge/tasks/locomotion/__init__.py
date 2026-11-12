"""Locomotion tasks (wheeled-legged velocity tracking: blind, height-scan teacher, depth student).

Plan: ../../TRACKER.md (P4/P6). Benchmark variants: benchmarks/TRACKER.md (B4).
Config modules are referenced by string so robot_lab is NOT imported here — importing it before
roboforge.compat has run would break physics=ovphysx (see compat.py).
"""

import gymnasium as gym

gym.register(
    id="RoboForge-Velocity-Flat-B2W-RealRange-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.real_range:B2WFlatRealRangeEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.real_range:B2WFlatRealRangePPORunnerCfg",
    },
)
