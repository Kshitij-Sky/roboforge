"""Planar serial 2-link leg kinematics (thigh + calf), used to set the standing pose.

Convention (leg plane, +x forward, z up, foot below the hip):
  - ``d`` is the hip height: vertical distance from the hip-pitch axis to the wheel axle.
  - angles are measured from vertical (0 = straight down).
  knee = ( l1*sin(q1),          -l1*cos(q1) )
  foot = knee + ( l2*sin(angS), -l2*cos(angS) )

Note: MuJoCo's +Y hinge rotates opposite to the planar atan2(y, x) convention. The sign
mapping to joint coordinates lives in ``parametric_quad.stand_pose`` and nowhere else.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def knee_interior_angle(l1: float, l2: float, d: float) -> float:
    """Interior knee angle (rad) by the law of cosines. pi = straight leg."""
    return math.acos(_clamp((l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2)))


def d_from_crouch(l1: float, l2: float, crouch: float) -> float:
    """Hip height from the crouch fraction d / reach, clamped to the reachable band."""
    reach = l1 + l2
    return min(max(crouch * reach, abs(l1 - l2) * 1.001), reach * 0.995)


@dataclass(frozen=True)
class LegPose:
    d: float  # hip height
    x_off: float  # fore/aft foot offset
    thK: float  # interior knee angle, rad
    q1: float  # thigh angle from vertical, rad
    angS: float  # calf angle from vertical, rad
    knee_xz: tuple[float, float]
    foot_xz: tuple[float, float]
    kx: float  # knee lever arm for a vertical foot force, m (l2*|sin angS|)


def leg_pose(l1: float, l2: float, d: float, x_off_frac: float = 0.0) -> LegPose:
    """Leg configuration at hip height ``d`` with the foot offset ``x_off_frac * d`` forward."""
    reach = l1 + l2
    x_off = x_off_frac * d
    d_off = min(math.hypot(d, x_off), reach * 0.995)
    thK = knee_interior_angle(l1, l2, d_off)
    beta = math.acos(_clamp((l1 * l1 + d_off * d_off - l2 * l2) / (2 * l1 * d_off)))
    q1 = math.atan2(x_off, d) - beta
    angS = q1 + (math.pi - thK)
    knee = (l1 * math.sin(q1), -l1 * math.cos(q1))
    foot = (knee[0] + l2 * math.sin(angS), knee[1] - l2 * math.cos(angS))
    return LegPose(d=d, x_off=x_off, thK=thK, q1=q1, angS=angS, knee_xz=knee, foot_xz=foot, kx=l2 * abs(math.sin(angS)))
