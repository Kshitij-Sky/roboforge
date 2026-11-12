"""Build a robot's canonical MJCF from its spec and run the contract check.

    python scripts/build_robot.py v1_wheeled_quad            # -> robots/v1_wheeled_quad/build/
    python scripts/build_robot.py v1_wheeled_quad --view     # also open the MuJoCo viewer (stand pose)

Writes build/model.xml (asset: torque actuators, no floor) and build/model_scene.xml
(floor + position servos, for viewing). Files in build/ are generated: never hand-edit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from roboforge.model import contract, parametric_quad, spec  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("robot", nargs="?", default="v1_wheeled_quad")
    ap.add_argument("--view", action="store_true", help="open the MuJoCo viewer on the scene model")
    args = ap.parse_args()

    s = spec.load(args.robot)
    bad = spec.untagged_numbers(s.source_path)
    if bad:
        print("Untagged numbers in robot.yaml (add a provenance tag):")
        for ln, line in bad:
            print(f"  line {ln}: {line}")
        return 1

    out = s.source_path.parent / "build"
    out.mkdir(exist_ok=True)
    asset, scene = out / "model.xml", out / "model_scene.xml"
    asset.write_text(parametric_quad.build_mjcf(s, actuator_mode="motor", scene=False), encoding="utf-8")
    scene.write_text(parametric_quad.build_mjcf(s, actuator_mode="servo", scene=True), encoding="utf-8")

    rep = contract.check_mjcf(asset)
    print(f"{s.name}  fidelity {s.fidelity}  ->  {asset.relative_to(spec.REPO_ROOT)}")
    print(f"  total mass {rep.info['total_mass']:.3f} kg (spec {parametric_quad.expected_total_mass(s):.3f} kg)")
    print("  joint    motor          tau_peak  vel_max  armature")
    for j, a in s.actuators.items():
        print(f"  {j:<8} {a.motor.name:<14} {a.tau_peak:8.1f} {a.vel_max:8.1f} {a.armature:9.4f}")
    print(rep)

    if args.view and rep.ok:
        import mujoco
        import mujoco.viewer

        m = mujoco.MjModel.from_xml_path(str(scene))
        d = mujoco.MjData(m)
        mujoco.mj_resetDataKeyframe(m, d, 0)
        mujoco.viewer.launch(m, d)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
