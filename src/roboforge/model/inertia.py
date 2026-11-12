"""Section-derived inertia for parametric links (fidelity M0 only — CAD replaces this at M1).

A link is a hollow rectangular tube; its effective density is back-solved so the tensor keeps
the section's shape and the lumped mass from robot.yaml. Frame: long axis = local Z, section
w (X) x h (Y). Izz (about the long axis) is the small moment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkInertia:
    mass: float
    com_z: float  # CoM along the long axis, measured from the proximal end
    diag: tuple[float, float, float]  # (Ixx, Iyy, Izz) about the CoM


def solid_box_diag(m: float, a: float, b: float, c: float) -> tuple[float, float, float]:
    """Principal inertia of a solid box with dimensions (a, b, c) along (x, y, z)."""
    return (m * (b * b + c * c) / 12.0, m * (a * a + c * c) / 12.0, m * (a * a + b * b) / 12.0)


def solid_cylinder_diag_y(m: float, r: float, w: float) -> tuple[float, float, float]:
    """Solid cylinder with its axis along Y: (Ixx, Iyy = spin, Izz)."""
    trans = 0.25 * m * r * r + m * w * w / 12.0
    return (trans, 0.5 * m * r * r, trans)


def hollow_box(w: float, h: float, length: float, wall: float, mass: float) -> LinkInertia:
    """Hollow rectangular tube along Z with total mass ``mass``; CoM at mid-length."""
    wi, hi = max(w - 2 * wall, 1e-9), max(h - 2 * wall, 1e-9)
    vol_net = (w * h - wi * hi) * length
    if vol_net <= 0:
        raise ValueError(f"wall {wall} too thick for section {w} x {h}")
    rho = mass / vol_net
    outer = solid_box_diag(rho * w * h * length, w, h, length)
    inner = solid_box_diag(rho * wi * hi * length, wi, hi, length)
    return LinkInertia(mass=mass, com_z=length / 2.0, diag=tuple(o - i for o, i in zip(outer, inner)))


def combine_along_z(parts: list[tuple[float, float, tuple[float, float, float]]]) -> LinkInertia:
    """Combine (mass, com_z, diag) parts laid out along Z (parallel-axis on Ixx, Iyy only)."""
    total = sum(p[0] for p in parts)
    com = sum(p[0] * p[1] for p in parts) / total
    ixx = iyy = izz = 0.0
    for m, z, (ix, iy, iz) in parts:
        dz = z - com
        ixx += ix + m * dz * dz
        iyy += iy + m * dz * dz
        izz += iz
    return LinkInertia(mass=total, com_z=com, diag=(ixx, iyy, izz))


def leg_link_inertials(spec) -> dict[str, LinkInertia]:
    """Thigh and calf inertials. The thigh carries the proximal knee motor as a point mass
    at its hip end (z = 0); ``mass.thigh`` includes that motor."""
    g = spec.geometry
    knee_motor = spec.actuators["calf"].motor.mass
    calf = hollow_box(g.link_w * 0.72, g.link_h * 0.70, g.l2, g.link_wall, spec.mass["calf"])
    struct = spec.mass["thigh"] - knee_motor
    if struct <= 0:
        raise ValueError(f"knee motor mass {knee_motor} >= mass.thigh {spec.mass['thigh']}")
    box = hollow_box(g.link_w, g.link_h, g.l1, g.link_wall, struct)
    thigh = combine_along_z([(struct, box.com_z, box.diag), (knee_motor, 0.0, (0.0, 0.0, 0.0))])
    return {"thigh": thigh, "calf": calf}
