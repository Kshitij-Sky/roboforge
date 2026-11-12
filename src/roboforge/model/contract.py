"""The robot contract: what every robot model must satisfy before any task may use it.

Task code depends only on this contract, so a model can be swapped (parametric -> SolidWorks
CAD -> sysid-refined) without touching a task file. Works on any MJCF, whatever its source.

Quadruped contract (humanoids will get their own joint map):
  * joints  {FL,FR,RL,RR}_{hip,thigh,calf,wheel}_joint  (wheel joints only for wheeled robots)
  * a free-floating root body named ``base`` and a site named ``imu``
  * an explicit <inertial> on every body (no mass inferred from geometry)
  * every actuated hinge has an actuator and armature > 0 (reflected rotor inertia)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

LEGS = ("FL", "FR", "RL", "RR")
LEG_JOINTS = ("hip", "thigh", "calf")


@dataclass
class ContractReport:
    errors: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        head = "CONTRACT PASS" if self.ok else f"CONTRACT FAIL ({len(self.errors)} errors)"
        return "\n".join([head, *[f"  - {e}" for e in self.errors]])


def required_joints(wheeled: bool = True) -> list[str]:
    joints = LEG_JOINTS + (("wheel",) if wheeled else ())
    return [f"{leg}_{j}_joint" for leg in LEGS for j in joints]


def check_mjcf(path_or_xml: str | Path, *, wheeled: bool = True) -> ContractReport:
    """Check an MJCF file (or XML string). Compiles it with MuJoCo for the numeric checks."""
    import mujoco  # local import: the rest of roboforge.model does not need MuJoCo

    rep = ContractReport()
    text = Path(path_or_xml).read_text(encoding="utf-8") if _is_path(path_or_xml) else str(path_or_xml)

    # --- structural checks on the XML itself -----------------------------------------
    root = ET.fromstring(text)
    bodies = root.iter("body")
    no_inertial = [b.get("name", "?") for b in bodies if b.find("inertial") is None]
    if no_inertial:
        rep.errors.append(f"bodies without explicit <inertial>: {no_inertial}")

    # --- compiled checks -----------------------------------------------------------------
    try:
        if _is_path(path_or_xml):
            model = mujoco.MjModel.from_xml_path(str(path_or_xml))  # resolves relative mesh paths
        else:
            model = mujoco.MjModel.from_xml_string(text)
    except ValueError as exc:
        rep.errors.append(f"MuJoCo failed to compile the model: {exc}")
        return rep
    names = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)}
    missing = [j for j in required_joints(wheeled) if j not in names]
    if missing:
        rep.errors.append(f"missing contract joints: {missing}")

    base_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "base")
    if base_id < 0:
        rep.errors.append("no body named 'base'")
    else:
        jadr = model.body_jntadr[base_id]
        if jadr < 0 or model.jnt_type[jadr] != mujoco.mjtJoint.mjJNT_FREE:
            rep.errors.append("body 'base' must carry a free joint")
    if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "imu") < 0:
        rep.errors.append("no site named 'imu'")

    actuated = {int(model.actuator_trnid[a, 0]) for a in range(model.nu)}
    for jn in required_joints(wheeled):
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, jn)
        if jid < 0:
            continue
        if jid not in actuated:
            rep.errors.append(f"joint {jn} has no actuator")
        if model.dof_armature[model.jnt_dofadr[jid]] <= 0:
            rep.errors.append(f"joint {jn} has armature <= 0 (reflected rotor inertia is mandatory)")

    rep.info = {
        "total_mass": float(sum(model.body_mass)),
        "nbody": model.nbody,
        "njnt": model.njnt,
        "nu": model.nu,
    }
    return rep


def _is_path(x) -> bool:
    if isinstance(x, Path):
        return True
    return isinstance(x, str) and not x.lstrip().startswith("<") and Path(x).exists()
