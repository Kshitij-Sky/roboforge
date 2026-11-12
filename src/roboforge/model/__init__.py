"""Robot description: spec loading, parametric MJCF generation, contract checks.

No Isaac Lab dependency — runs in any Python env with numpy, PyYAML and (for checks) MuJoCo.
Status and next steps: ../TRACKER.md (P1).
"""

from . import contract, inertia, kinematics, parametric_quad, spec

__all__ = ["contract", "inertia", "kinematics", "parametric_quad", "spec"]
