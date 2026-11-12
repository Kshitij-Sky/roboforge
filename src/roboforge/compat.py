"""Workarounds for known upstream issues in the pinned Isaac Lab / robot_lab versions.

Each workaround names the upstream versions it targets. Remove it when the pins move past the fix
(scripts/upstream.py). Workarounds must be inert unless their trigger condition holds.
"""

from __future__ import annotations

import os
import sys
import warnings


def register_ovphysx_schemas_early() -> bool:
    """Isaac Lab v3.0.0 + robot_lab v3.0.0: make ``physics=ovphysx`` work alongside the kit-less importers.

    robot_lab imports ``isaacsim.asset.importer.urdf`` at package import. That registers a USD plugin
    'physxSchemaFallback' with the PhysX schema types. Later, Isaac Lab's OVPhysX manager registers
    OVPhysX's 'physxSchema' plugin, which declares the same types, and pxr raises
    ``Tf.ErrorException: ... previously provided by plugin 'physxSchemaFallback'``.

    The importer skips its fallback when a plugin named 'physxSchema' is already loaded, and the
    OVPhysX manager skips plugins whose names are already registered. So registering OVPhysX's
    schema plugin *before* robot_lab is imported avoids the clash and leaves both happy.

    Trigger: the command line selects ovphysx (``physics=ovphysx``), or ROBOFORGE_EARLY_PHYSX_SCHEMAS=1.
    Newton-only runs are untouched. Requires the roboforge entry point to load before robot_lab's.
    """
    wanted = os.environ.get("ROBOFORGE_EARLY_PHYSX_SCHEMAS") == "1" or any("ovphysx" in a for a in sys.argv)
    if not wanted:
        return False
    try:
        import ovphysx
        from pxr import Plug
    except ImportError:
        return False
    registry = Plug.Registry()
    if registry.GetPluginWithName("physxSchemaFallback") is not None:
        warnings.warn(
            "robot_lab registered the importer's 'physxSchemaFallback' before roboforge could register "
            "OVPhysX's schemas; physics=ovphysx will likely fail. See roboforge/compat.py.",
            stacklevel=2,
        )
        return False
    registered = {p.name.casefold() for p in registry.GetAllPlugins()}
    paths = [str(p) for p in ovphysx.codeless_schema_paths() if p.parent.name.casefold() not in registered]
    if paths:
        registry.RegisterPlugins(paths)
    return True
