"""Robot spec loader: ``robots/<name>/robot.yaml`` -> typed, resolved ``RobotSpec``.

This is model source A (parametric). It has no Isaac Lab dependency: numpy, PyYAML and the
standard library only, so it runs in any environment.

Resolution contract: derived quantities (joint limits, armature, friction) are computed
here from the motor library, never written by hand into the YAML. A value that cannot be
resolved raises; nothing silently falls back to a default.

Ported from the earlier parametric MBD pipeline (rough work, 2026-07/11) and cleaned up:
contract joint names, linkage/variant machinery removed, motor data folded into the spec.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ROBOTS_DIR = REPO_ROOT / "robots"

PROVENANCE_TAGS = ("[U]", "[DR]", "[3P]", "[URDF]", "[EST]", "[WB]", "[MEAS]")
FIDELITY_LEVELS = ("M0", "M1", "M2", "M3", "M4")
LEG_JOINTS = ("hip", "thigh", "calf", "wheel")


@dataclass(frozen=True)
class Geometry:
    l1: float
    l2: float
    abd: float
    hip_x: float
    body_w: float
    body_h: float
    crouch_nominal: float
    link_w: float
    link_h: float
    link_wall: float


@dataclass(frozen=True)
class Motor:
    """One motor-library entry. Torques and speeds are at the motor's own output shaft."""

    name: str
    tau_peak: float
    tau_cont: float
    gear_ratio: float
    rotor_inertia: float
    mass: float
    vel_max: float
    eta_fwd: float
    km2: float
    v_max: float

    def copper_loss(self, tau_out: float) -> float:
        """Copper loss (W) to hold ``tau_out`` at the output: P = (tau_out / (N*eta))^2 / km2."""
        tau_rotor = tau_out / (self.gear_ratio * self.eta_fwd)
        return tau_rotor * tau_rotor / self.km2


@dataclass(frozen=True)
class JointActuator:
    """A resolved joint actuator. All fields are joint-level (after any transmission)."""

    joint: str
    motor: Motor
    transmission: float
    tau_peak: float
    tau_cont: float
    vel_max: float
    armature: float
    damping: float
    frictionloss: float


@dataclass
class RobotSpec:
    name: str
    fidelity: str
    geometry: Geometry
    mass: dict[str, float]
    actuators: dict[str, JointActuator]
    joint_range: dict[str, tuple[float, float]]
    wheel: dict[str, float]
    power: dict[str, float]
    reference_solver: dict
    contact: dict
    source_path: Path
    extra: dict = field(default_factory=dict)


def frictionloss_estimate(m: Motor, transmission: float = 1.0) -> float:
    """Coulomb output friction [EST], N.m — placeholder until bench data (fidelity M3).

    Katz-style tau_f = 0.09 + 0.04 * tau_rotor_peak, scaled by reduction and module size.
    """
    tau_rotor = m.tau_peak / (m.gear_ratio * m.eta_fwd)
    return (0.09 + 0.04 * tau_rotor) * (m.gear_ratio / 6.0) * (m.mass / 0.48) * transmission


def resolve_actuator(joint: str, cfg: dict, motors: dict[str, Motor], damping: float) -> JointActuator:
    if cfg.get("motor") not in motors:
        raise ValueError(f"joint '{joint}': motor '{cfg.get('motor')}' not in the motor library {list(motors)}")
    m = motors[cfg["motor"]]
    n = float(cfg.get("transmission", 1.0))
    return JointActuator(
        joint=joint,
        motor=m,
        transmission=n,
        tau_peak=m.tau_peak * n,
        tau_cont=m.tau_cont * n,
        vel_max=m.vel_max / n,
        armature=(n * m.gear_ratio) ** 2 * m.rotor_inertia,
        damping=damping,
        frictionloss=frictionloss_estimate(m, n),
    )


def spec_path(name_or_path: str | Path) -> Path:
    p = Path(name_or_path)
    if p.suffix in (".yaml", ".yml"):
        return p if p.is_absolute() else (REPO_ROOT / p)
    return ROBOTS_DIR / str(name_or_path) / "robot.yaml"


def load(name_or_path: str | Path = "v1_wheeled_quad") -> RobotSpec:
    path = spec_path(name_or_path)
    with open(path, encoding="utf-8") as fh:
        d = yaml.safe_load(fh)

    fidelity = d["meta"]["fidelity"]
    if fidelity not in FIDELITY_LEVELS:
        raise ValueError(f"meta.fidelity must be one of {FIDELITY_LEVELS}, got {fidelity!r}")

    motors = {k: Motor(name=k, **v) for k, v in d["motors"].items()}
    missing = [j for j in LEG_JOINTS if j not in d["actuators"]]
    if missing:
        raise ValueError(f"actuators missing for joints {missing}")
    actuators = {
        j: resolve_actuator(j, d["actuators"][j], motors, float(d["damping"][j])) for j in LEG_JOINTS
    }

    return RobotSpec(
        name=d["meta"]["name"],
        fidelity=fidelity,
        geometry=Geometry(**d["geometry"]),
        mass={k: float(v) for k, v in d["mass"].items()},
        actuators=actuators,
        joint_range={k: (float(v[0]), float(v[1])) for k, v in d["joint_range"].items()},
        wheel={k: float(v) for k, v in d["wheel"].items()},
        power=dict(d["power"]),
        reference_solver=dict(d["reference_solver"]),
        contact=dict(d["contact"]),
        source_path=path,
    )


# --- provenance check ------------------------------------------------------------------

_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE]-?\d+)?(?![\w])")


def untagged_numbers(path: str | Path) -> list[tuple[int, str]]:
    """Return (line_no, line) for every YAML line holding a numeric value without a provenance tag."""
    bad = []
    for i, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        body, _, comment = raw.partition("#")
        if ":" not in body:
            continue
        value = body.split(":", 1)[1]
        if _NUM.search(value) and not any(t in comment for t in PROVENANCE_TAGS):
            bad.append((i, raw.rstrip()))
    return bad
