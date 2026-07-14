"""Fix NAVMESH waypoint format for MapTrackerMoveCompatible.

MapTrackerMoveCompatible (move_compatible.go) ignores NAVMESH waypoints and
HEADING-only waypoints (no target). This script converts:

  [{"action": "NAVMESH", "target": [x, y], "zone_id"|"target_tier"?},
   {"action": "HEADING", "angle": N}]

to the supported object format:

  [{"x": x, "y": y, "zone_id": "..."}]

HEADING-only waypoints (no target) are dropped.

Only modifies files under 3rd-part/maaend/resource/pipeline/ (runtime copy).
"""
import json
import os
import sys

PIPELINE_DIR = r"c:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\maaend\resource\pipeline"

# Files containing NAVMESH waypoints (relative to PIPELINE_DIR)
NAVMESH_FILES = [
    # EnvironmentMonitoring Outskirts (zone inferred from StartPos node: Wuling_Base)
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\CisternOriginiumSlugs.json",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\VigorousCisternOriginiumSlug.json",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\IndoorCrops.json",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\CollapsedTianshiPillar.json",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\AncientTree.json",
    # EnvironmentMonitoring MarkerStone (has target_tier field)
    r"EnvironmentMonitoring\MarkerStoneMonitoringTerminal\TreeOfTheOldCourtyard.json",
    r"EnvironmentMonitoring\MarkerStoneMonitoringTerminal\FloraObservationPoint.json",
    # AutoEcoFarm (zone_id on waypoint)
    r"AutoEcoFarm\RegionNodes\AutoEcoFarmInitValleyIV.json",
    r"AutoEcoFarm\RegionNodes\AutoEcoFarmInitWulin.json",
    # AutoCollect (zone_id on waypoint)
    r"AutoCollect\AutoCollectRoute4.json",
    r"AutoCollect\AutoCollectCommonRoute8.json",
    r"AutoCollect\AutoCollectCommonRoute4.json",
    r"AutoCollect\AutoCollectCommonRoute6.json",
    r"AutoCollect\AutoCollectCommonRoute1.json",
    r"AutoCollect\AutoCollectCommonRoute2.json",
]

# Default zone for files where NAVMESH waypoint has no zone_id/target_tier
# (inferred from the file's GoTo*StartPos node which uses MapTrackerAssertLocationCompatible)
FILE_DEFAULT_ZONE = {
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\CisternOriginiumSlugs.json": "Wuling_Base",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\VigorousCisternOriginiumSlug.json": "Wuling_Base",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\IndoorCrops.json": "Wuling_Base",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\CollapsedTianshiPillar.json": "Wuling_Base",
    r"EnvironmentMonitoring\OutskirtsMonitoringTerminal\AncientTree.json": "Wuling_Base",
    r"EnvironmentMonitoring\MarkerStoneMonitoringTerminal\TreeOfTheOldCourtyard.json": "Wuling_Base",
    r"EnvironmentMonitoring\MarkerStoneMonitoringTerminal\FloraObservationPoint.json": "Wuling_Base",
}

# Map zone to map_name hint (used by convertCompatiblePoints as preferredMapName)
ZONE_MAP_NAME = {
    "Wuling_Base": "map02_lv002",
    "ValleyIV_Base": "map01_lv001",
}


def convert_navmesh_path(path_list, default_zone=None):
    """Convert NAVMESH/HEADING waypoints to supported {x, y, zone_id} format.

    Returns (new_path, changed).
    """
    new_path = []
    changed = False
    for waypoint in path_list:
        if isinstance(waypoint, dict):
            action = waypoint.get("action", "")
            if action == "NAVMESH":
                target = waypoint.get("target", [])
                if isinstance(target, list) and len(target) >= 2:
                    new_waypoint = {"x": target[0], "y": target[1]}
                    # Determine zone_id: waypoint.zone_id > waypoint.target_tier > default_zone
                    zone_id = waypoint.get("zone_id")
                    if not zone_id:
                        zone_id = waypoint.get("target_tier")
                    if not zone_id:
                        zone_id = default_zone
                    if zone_id:
                        new_waypoint["zone_id"] = zone_id
                    new_path.append(new_waypoint)
                    changed = True
                else:
                    # NAVMESH without target — drop
                    changed = True
            elif action == "HEADING":
                target = waypoint.get("target", [])
                if isinstance(target, list) and len(target) >= 2:
                    new_waypoint = {"x": target[0], "y": target[1]}
                    zone_id = waypoint.get("zone_id") or default_zone
                    if zone_id:
                        new_waypoint["zone_id"] = zone_id
                    new_path.append(new_waypoint)
                    changed = True
                else:
                    # HEADING-only (angle only) — drop
                    changed = True
            else:
                # Keep ZONE waypoints and other formats as-is
                new_path.append(waypoint)
        else:
            # Array format [x, y, ...] — keep as-is
            new_path.append(waypoint)
    return new_path, changed


def find_and_fix_paths(obj, default_zone, path_prefix="", modifications=None):
    """Recursively find dicts with 'path' key containing NAVMESH waypoints and fix them."""
    if modifications is None:
        modifications = []
    if isinstance(obj, dict):
        # Check if this dict has a 'path' key with NAVMESH waypoints
        path = obj.get("path")
        if isinstance(path, list) and any(
            isinstance(w, dict) and w.get("action") == "NAVMESH" for w in path
        ):
            new_path, changed = convert_navmesh_path(path, default_zone)
            if changed:
                obj["path"] = new_path
                # Add map_name hint if not present and we know the zone
                if "map_name" not in obj and default_zone and default_zone in ZONE_MAP_NAME:
                    obj["map_name"] = ZONE_MAP_NAME[default_zone]
                    modifications.append(
                        f"{path_prefix}.path (converted, added map_name={obj['map_name']})"
                    )
                else:
                    modifications.append(f"{path_prefix}.path (converted)")
        # Recurse into all values
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                find_and_fix_paths(value, default_zone, f"{path_prefix}.{key}", modifications)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                find_and_fix_paths(item, default_zone, f"{path_prefix}[{i}]", modifications)
    return modifications


def process_file(file_rel_path):
    file_path = os.path.join(PIPELINE_DIR, file_rel_path)
    default_zone = FILE_DEFAULT_ZONE.get(file_rel_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    modifications = find_and_fix_paths(data, default_zone, file_rel_path)

    if modifications:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"MODIFIED: {file_rel_path}")
        for m in modifications:
            print(f"  - {m}")
        return True
    else:
        print(f"UNCHANGED: {file_rel_path}")
        return False


def main():
    print(f"Pipeline dir: {PIPELINE_DIR}")
    print(f"Files to process: {len(NAVMESH_FILES)}")
    print()

    modified_count = 0
    for file_rel_path in NAVMESH_FILES:
        file_path = os.path.join(PIPELINE_DIR, file_rel_path)
        if not os.path.exists(file_path):
            print(f"MISSING: {file_rel_path}")
            continue
        if process_file(file_rel_path):
            modified_count += 1
        print()

    print(f"Done. Modified {modified_count}/{len(NAVMESH_FILES)} files.")


if __name__ == "__main__":
    main()
