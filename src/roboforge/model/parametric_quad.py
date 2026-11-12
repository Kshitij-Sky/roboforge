"""Parametric wheeled-quadruped MJCF generator (model source A, fidelity M0).

Body tree (same as the shipping wheeled quadrupeds, e.g. Unitree B2-W / Go2-W):

    base                    free joint, ``imu`` site at the origin
      {L}_hip               {L}_hip_joint    roll (abduction), axis +X
        {L}_thigh           {L}_thigh_joint  pitch (hip),      axis +Y
          {L}_calf          {L}_calf_joint   pitch (knee),     axis +Y
            {L}_wheel       {L}_wheel_joint  spin (hub drive), axis +Y

with L in FL, FR, RL, RR. Names follow the robot contract (see ``contract.py``).

Modelling choices, all deliberate:
  * primitive geoms + explicit ``<inertial>`` on every body; ``inertiafromgeom="false"``
    makes MuJoCo refuse a body without one.
  * the knee motor rides at the hip end of the thigh (1:1 proximal drive): joint torque
    equals motor output torque.
  * the hub motor mass sits in the wheel body (distal mass modelled honestly).
  * armature = (transmission * N)^2 * J_rotor on every actuated joint — mandatory, both
    physically and numerically.
  * robot geoms use contype=2 / conaffinity=1: they hit the world (floor, obstacles) but
    never each other.
  * the tyre geom has priority="1" so its friction is the one used at the ground contact.
    MuJoCo otherwise takes the element-wise MAX of the two geoms' friction, which silently
    overrode mu = 0.8 with the floor's 1.0 in the earlier version of this generator.
"""

from __future__ import annotations

import math

from . import inertia as _I
from . import kinematics as _K
from .spec import RobotSpec

LEGS = (("FL", +1, +1), ("FR", +1, -1), ("RL", -1, +1), ("RR", -1, -1))

# Position-servo gains and settling damping for the "servo" mode (standing / viewing only).
STAND_KP = {"hip": 250.0, "thigh": 350.0, "calf": 450.0, "wheel": 5.0}
STAND_KV = {"hip": 6.0, "thigh": 8.0, "calf": 10.0, "wheel": 1.0}
STAND_JDAMP = {"hip": 2.0, "thigh": 2.5, "calf": 3.0, "wheel": 0.5}
SPAWN_DZ = 0.010  # spawn slightly high so the wheels settle without an initial penetration impulse

_ROBOT_GEOM = 'contype="2" conaffinity="1"'
_MOT = f'{_ROBOT_GEOM} rgba=".24 .26 .30 1"'
_STR = f'{_ROBOT_GEOM} rgba=".62 .66 .70 1"'


def _v(x) -> str:
    return " ".join(f"{c:.6g}" for c in x)


def joint_name(leg: str, joint: str) -> str:
    return f"{leg}_{joint}_joint"


def stand_pose(spec: RobotSpec) -> dict[str, float]:
    """Standing joint angles and base height (wheels on flat ground, abduction 0)."""
    g = spec.geometry
    d = _K.d_from_crouch(g.l1, g.l2, g.crouch_nominal)
    p = _K.leg_pose(g.l1, g.l2, d)
    # MuJoCo +Y hinge sign mapping (the only place it is applied):
    #   thigh qpos = -q1 ; calf qpos = q1 - angS ; zero pose = leg straight down.
    return {
        "d": d,
        "base_z": d + spec.wheel["radius"],
        "hip": 0.0,
        "thigh": -p.q1,
        "calf": p.q1 - p.angS,
        "wheel": 0.0,
        "knee_interior_deg": math.degrees(p.thK),
    }


def wheel_body_mass(spec: RobotSpec) -> float:
    """Tyre + rim plus the hub motor module."""
    return spec.mass["wheel"] + spec.actuators["wheel"].motor.mass


def _joint_attrs(spec: RobotSpec, j: str, damping: float) -> str:
    a = spec.actuators[j]
    return f'armature="{a.armature:.6g}" damping="{damping:.6g}" frictionloss="{a.frictionloss:.6g}"'


def _leg_xml(spec: RobotSpec, leg: str, sx: int, sy: int, links: dict, jdamp: dict) -> str:
    g, w = spec.geometry, spec.wheel
    th, cf = links["thigh"], links["calf"]
    hip_m, wheel_m = spec.mass["hip"], wheel_body_mass(spec)
    rng = spec.joint_range
    r, wdt, mu = w["radius"], w["width"], w["mu"]
    ax, ay, ty = sx * g.hip_x, sy * g.body_w / 2.0, sy * g.abd
    o_tire, o_hub = sy * 0.035, -sy * 0.020  # tyre outboard of the leg plane, hub motor inboard
    hip_cube = 0.10
    hip_i = hip_m * (2 * hip_cube * hip_cube) / 12.0
    l1, l2 = g.l1, g.l2

    def rng_attr(j):
        lo, hi = rng[j]
        return f'range="{lo:.4g} {hi:.4g}"'

    return f"""
      <body name="{leg}_hip" pos="{ax:.6g} {ay:.6g} 0">
        <joint name="{joint_name(leg, "hip")}" axis="1 0 0" {rng_attr("hip")} {_joint_attrs(spec, "hip", jdamp["hip"])}/>
        <inertial pos="0 {0.02 * sy:.4g} 0" mass="{hip_m:.6g}" diaginertia="{hip_i:.6g} {hip_i:.6g} {hip_i:.6g}"/>
        <geom type="cylinder" fromto="-0.055 0 0  0.055 0 0" size="0.050" {_MOT}/>
        <geom type="cylinder" fromto="0 {sy * 0.015:.4g} 0  0 {ty:.6g} 0" size="0.047" {_MOT}/>
        <body name="{leg}_thigh" pos="0 {ty:.6g} 0">
          <joint name="{joint_name(leg, "thigh")}" axis="0 1 0" {rng_attr("thigh")} {_joint_attrs(spec, "thigh", jdamp["thigh"])}/>
          <inertial pos="0 0 {-th.com_z:.6g}" mass="{th.mass:.6g}" diaginertia="{_v(th.diag)}"/>
          <geom type="cylinder" fromto="0 -0.038 -0.005  0 0.038 -0.005" size="0.052" {_MOT}/>
          <geom type="box" pos="0 0 {-l1 / 2:.6g}" size="0.020 0.028 {l1 / 2 - 0.05:.6g}" {_STR}/>
          <body name="{leg}_calf" pos="0 0 {-l1:.6g}">
            <joint name="{joint_name(leg, "calf")}" axis="0 1 0" {rng_attr("calf")} {_joint_attrs(spec, "calf", jdamp["calf"])}/>
            <inertial pos="0 0 {-cf.com_z:.6g}" mass="{cf.mass:.6g}" diaginertia="{_v(cf.diag)}"/>
            <geom type="box" pos="0 0 {-l2 / 2:.6g}" size="0.016 0.022 {l2 / 2 - 0.02:.6g}" {_STR}/>
            <body name="{leg}_wheel" pos="0 0 {-l2:.6g}">
              <joint name="{joint_name(leg, "wheel")}" axis="0 1 0" {_joint_attrs(spec, "wheel", jdamp["wheel"])}/>
              <inertial pos="0 {sy * 0.012:.4g} 0" mass="{wheel_m:.6g}" diaginertia="{_v(_I.solid_cylinder_diag_y(wheel_m, r, wdt))}"/>
              <geom type="cylinder" pos="0 {o_hub:.4g} 0" quat="0.707107 0.707107 0 0" size="0.042 0.022" {_MOT}/>
              <geom name="{leg}_tyre" type="cylinder" pos="0 {o_tire:.4g} 0" quat="0.707107 0.707107 0 0" size="{r:.6g} {wdt / 2:.6g}" friction="{mu:.4g} 0.02 0.001" priority="1" {_ROBOT_GEOM} rgba=".10 .10 .10 1"/>
            </body>
          </body>
        </body>
      </body>"""


def build_mjcf(spec: RobotSpec, *, actuator_mode: str = "motor", scene: bool = False, timestep: float = 0.002) -> str:
    """Return the robot MJCF as a string.

    actuator_mode:
      "motor" (default) — torque sources, ctrlrange = joint peak torque. The asset form:
               downstream frameworks attach their own actuator models.
      "servo" — position servos holding the stand pose (viewing / standing checks only).
    scene: add a floor and a light (standalone viewing). Robot assets for Isaac Lab use scene=False.
    """
    if actuator_mode not in ("motor", "servo"):
        raise ValueError(f"actuator_mode must be 'motor' or 'servo', got {actuator_mode!r}")
    servo = actuator_mode == "servo"
    jdamp = STAND_JDAMP if servo else {j: a.damping for j, a in spec.actuators.items()}

    links = _I.leg_link_inertials(spec)
    g = spec.geometry
    body_m = spec.mass["body"]
    bL, bW, bH = 2 * g.hip_x, g.body_w, g.body_h
    pose = stand_pose(spec)
    base_z = pose["base_z"] + SPAWN_DZ
    legs = "".join(_leg_xml(spec, leg, sx, sy, links, jdamp) for leg, sx, sy in LEGS)

    acts, stand_q = [], []
    for leg, _, _ in LEGS:
        for j in ("hip", "thigh", "calf", "wheel"):
            jn, a = joint_name(leg, j), spec.actuators[j]
            stand_q.append(pose[j])
            if servo:
                acts.append(
                    f'<position name="{jn}_act" joint="{jn}" kp="{STAND_KP[j]:.6g}" kv="{STAND_KV[j]:.6g}" '
                    f'ctrlrange="-1000 1000" forcerange="{-a.tau_peak:.6g} {a.tau_peak:.6g}"/>'
                )
            else:
                acts.append(f'<motor name="{jn}_act" joint="{jn}" ctrlrange="{-a.tau_peak:.6g} {a.tau_peak:.6g}"/>')

    floor = (
        '<light pos="0 0 2.0" dir="0 0 -1" directional="true"/>\n'
        '    <geom name="floor" type="plane" size="0 0 0.05" rgba=".3 .35 .4 1"/>'
        if scene
        else ""
    )
    key_qpos = _v([0.0, 0.0, base_z, 1.0, 0.0, 0.0, 0.0] + stand_q)
    key_ctrl = f' ctrl="{_v(stand_q)}"' if servo else ""

    return f"""<mujoco model="{spec.name}">
  <!-- GENERATED by roboforge.model.parametric_quad from {spec.source_path.name} (fidelity {spec.fidelity}). Do not hand-edit. -->
  <compiler angle="radian" autolimits="true" inertiafromgeom="false"/>
  <option gravity="0 0 -9.81" timestep="{timestep:.6g}" integrator="implicitfast"/>
  <worldbody>
    {floor}
    <body name="base" pos="0 0 {base_z:.6g}">
      <freejoint name="root"/>
      <inertial pos="0 0 0" mass="{body_m:.6g}" diaginertia="{_v(_I.solid_box_diag(body_m, bL, bW, bH))}"/>
      <geom name="base_box" type="box" size="{bL / 2:.6g} {bW / 2:.6g} {bH / 2:.6g}" {_ROBOT_GEOM} rgba=".40 .45 .50 1"/>
      <site name="imu" pos="0 0 0" size="0.01"/>
      {legs}
    </body>
  </worldbody>
  <actuator>
    {chr(10).join("    " + a for a in acts).strip()}
  </actuator>
  <keyframe>
    <key name="stand" qpos="{key_qpos}"{key_ctrl}/>
  </keyframe>
</mujoco>
"""


def expected_total_mass(spec: RobotSpec) -> float:
    m = spec.mass
    return m["body"] + 4 * (m["hip"] + m["thigh"] + m["calf"] + wheel_body_mass(spec))
