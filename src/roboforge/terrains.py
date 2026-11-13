"""Terrain presets for playback/evaluation (`rf play --terrain ...`).

Built from Isaac Lab's terrain generator (the same sub-terrains as its ROUGH_TERRAINS_CFG). One
row of tiles, one tile per robot, so every robot gets its own patch. Each tile has a flat centre
platform where the robot spawns:
  stairs_down / slope_down : start on top, the terrain falls away outward
  stairs_up   / slope_up   : start in a pit, the terrain rises outward
`difficulty` (0..1) picks the point in each range: step height, slope, roughness, box height.

Changing terrain needs a relaunch: the ground is part of the physics scene built at startup.
"""

from __future__ import annotations

PRESETS = ("flat", "rough", "slope_up", "slope_down", "stairs_up", "stairs_down", "boxes", "mixed")


def _sub_terrains(name: str) -> dict:
    from isaaclab import terrains as tg

    stairs = dict(step_height_range=(0.05, 0.25), step_width=0.3, platform_width=3.0, border_width=1.0, holes=False)
    slope = dict(slope_range=(0.0, 0.6), platform_width=3.0, border_width=0.25)  # 0.6 = ~31 deg
    table = {
        "rough": {"rough": tg.HfRandomUniformTerrainCfg(proportion=1.0, noise_range=(0.02, 0.10), noise_step=0.02,
                                                       border_width=0.25)},
        "slope_down": {"slope": tg.HfPyramidSlopedTerrainCfg(proportion=1.0, **slope)},
        "slope_up": {"slope": tg.HfInvertedPyramidSlopedTerrainCfg(proportion=1.0, **slope)},
        "stairs_down": {"stairs": tg.MeshPyramidStairsTerrainCfg(proportion=1.0, **stairs)},
        "stairs_up": {"stairs": tg.MeshInvertedPyramidStairsTerrainCfg(proportion=1.0, **stairs)},
        "boxes": {"boxes": tg.MeshRandomGridTerrainCfg(proportion=1.0, grid_width=0.45,
                                                       grid_height_range=(0.05, 0.20), platform_width=3.0)},
    }
    if name == "mixed":
        mixed = {}
        for k in ("rough", "slope_up", "slope_down", "stairs_up", "stairs_down", "boxes"):
            (sub_key, cfg), = table[k].items()
            cfg.proportion = 1.0 / 6
            mixed[k] = cfg
        return mixed
    return table[name]


def apply(cfg, name: str, difficulty: float, n_tiles: int) -> None:
    """Swap the scene's ground for a generated terrain (no-op for 'flat')."""
    if name == "flat":
        return
    if name not in PRESETS:
        raise ValueError(f"unknown terrain '{name}' (have: {', '.join(PRESETS)})")
    from isaaclab.terrains import TerrainGeneratorCfg

    d = min(max(difficulty, 0.0), 1.0)
    cfg.scene.terrain.terrain_type = "generator"
    cfg.scene.terrain.terrain_generator = TerrainGeneratorCfg(
        size=(8.0, 8.0), border_width=20.0, num_rows=1, num_cols=max(1, n_tiles),
        horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75, use_cache=False,
        curriculum=False, difficulty_range=(d, d), sub_terrains=_sub_terrains(name),
    )
    cfg.scene.terrain.max_init_terrain_level = None
    # playback never ends an episode at the tile edge; the robot only resets on request
    terms = getattr(cfg, "terminations", None)
    if terms is not None and getattr(terms, "terrain_out_of_bounds", None) is not None:
        terms.terrain_out_of_bounds = None
    curr = getattr(cfg, "curriculum", None)
    if curr is not None and getattr(curr, "terrain_levels", None) is not None:
        curr.terrain_levels = None
