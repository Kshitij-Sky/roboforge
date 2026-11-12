"""Model-layer tests: run without Isaac Lab (numpy + PyYAML + MuJoCo only).

    python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

mujoco = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

from roboforge.model import contract, parametric_quad, spec  # noqa: E402

ROBOT = "v1_wheeled_quad"


@pytest.fixture(scope="module")
def s():
    return spec.load(ROBOT)


def test_every_number_has_provenance(s):
    assert spec.untagged_numbers(s.source_path) == []


def test_benchmark_reference_numbers_have_provenance():
    ref = Path(__file__).resolve().parents[1] / "benchmarks" / "reference_robots.yaml"
    assert spec.untagged_numbers(ref) == []


def test_joint_limits_derive_from_motors(s):
    for a in s.actuators.values():
        assert a.tau_peak == pytest.approx(a.motor.tau_peak * a.transmission)
        assert a.vel_max == pytest.approx(a.motor.vel_max / a.transmission)
        assert a.armature == pytest.approx((a.transmission * a.motor.gear_ratio) ** 2 * a.motor.rotor_inertia)
        assert a.tau_cont < a.tau_peak, "peak is not continuous"


def test_asset_mjcf_compiles_and_passes_contract(s):
    rep = contract.check_mjcf(parametric_quad.build_mjcf(s, actuator_mode="motor", scene=False))
    assert rep.ok, str(rep)
    assert rep.info["total_mass"] == pytest.approx(parametric_quad.expected_total_mass(s), rel=1e-9)


def test_contract_catches_a_missing_inertial(s):
    """Remove the base <inertial> and let MuJoCo infer mass from geometry: the contract must flag it."""
    import re

    xml = parametric_quad.build_mjcf(s).replace(' inertiafromgeom="false"', "")
    xml, n = re.subn(r'\s*<inertial pos="0 0 0" mass="31\.6"[^>]*/>', "", xml, count=1)
    assert n == 1
    rep = contract.check_mjcf(xml)
    assert not rep.ok
    assert any("without explicit <inertial>" in e and "base" in e for e in rep.errors)


def test_contract_catches_missing_joint_and_armature(s):
    import re

    xml = parametric_quad.build_mjcf(s).replace("FL_wheel_joint", "FL_spin")
    xml = re.sub(r'armature="[^"]+"', 'armature="0"', xml, count=1)  # first joint = FL_hip_joint
    rep = contract.check_mjcf(xml)
    assert any("missing contract joints" in e and "FL_wheel_joint" in e for e in rep.errors)
    assert any("armature <= 0" in e for e in rep.errors)


def test_stand_pose_is_physical(s):
    p = parametric_quad.stand_pose(s)
    g = s.geometry
    assert 0 < p["d"] < g.l1 + g.l2
    assert p["base_z"] == pytest.approx(p["d"] + s.wheel["radius"])
    assert 0 < p["knee_interior_deg"] < 180


def test_servo_stand_settles(s):
    """Drop onto the floor in the stand pose and hold it with the position servos for 3 s."""
    m = mujoco.MjModel.from_xml_string(parametric_quad.build_mjcf(s, actuator_mode="servo", scene=True))
    d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, 0)
    for _ in range(int(3.0 / m.opt.timestep)):
        mujoco.mj_step(m, d)
    z_expected = parametric_quad.stand_pose(s)["base_z"]
    assert np.all(np.isfinite(d.qpos))
    assert abs(d.qpos[2] - z_expected) < 0.03, f"base z {d.qpos[2]:.3f} vs {z_expected:.3f}"
    up = d.xmat[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "base")].reshape(3, 3)[2, 2]
    assert up > 0.99, "base tipped"


def test_tyre_friction_is_the_spec_value(s):
    """The tyre's mu must govern the ground contact (MuJoCo would otherwise take the max)."""
    m = mujoco.MjModel.from_xml_string(parametric_quad.build_mjcf(s, actuator_mode="servo", scene=True))
    d = mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m, d, 0)
    for _ in range(200):
        mujoco.mj_step(m, d)
    tyres = {mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, f"{leg}_tyre") for leg in contract.LEGS}
    mus = [d.contact[i].friction[0] for i in range(d.ncon) if {d.contact[i].geom1, d.contact[i].geom2} & tyres]
    assert mus, "no tyre contacts"
    assert all(mu == pytest.approx(s.wheel["mu"]) for mu in mus)
