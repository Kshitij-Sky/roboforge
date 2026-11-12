"""Isaac Lab task registry (entry point ``isaaclab.tasks``). Tasks are registered by the subpackages."""

from ..compat import register_ovphysx_schemas_early

# Must run before robot_lab is imported (see compat.py); Isaac Lab loads the roboforge entry point first.
register_ovphysx_schemas_early()

from . import locomotion  # noqa: E402, F401
