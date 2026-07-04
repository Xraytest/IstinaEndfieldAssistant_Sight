"""
Migrate MaaEnd pipeline nodes into modular assets/pipelines/ JSON files.

Extracts pipeline nodes by name prefix from MaaEnd nodes.json
and writes per-module files to assets/pipelines/.
"""
import json
from pathlib import Path

maaend_nodes = Path("3rd-part/maaend/resource/pipeline/nodes.json")
pipelines_dir = Path("assets/pipelines")
pipelines_dir.mkdir(parents=True, exist_ok=True)

with open(maaend_nodes, "r", encoding="utf-8") as f:
    nodes = json.load(f)

modules = {
    "common_buttons": lambda n: isinstance(nodes[n].get("template"), str) and "Common/Button" in nodes[n]["template"],
    "auto_essence": lambda n: n.startswith("AutoEssence"),
    "auto_sell": lambda n: n.startswith("AutoSell"),
    "auto_collect": lambda n: n.startswith("AutoCollect"),
    "daily_rewards": lambda n: n.startswith("DailyReward"),
    "open_game": lambda n: n.startswith("OpenGame"),
    "credit_shopping": lambda n: n.startswith("CreditShopping"),
    "scene_navigation": lambda n: n.startswith("Scene"),
    "close_info": lambda n: n.startswith("Close"),
    "environment_monitoring": lambda n: n.startswith("EnvironmentMonitoring"),
    "real_time_task": lambda n: n.startswith("RealTimeTask"),
    "delivery_jobs": lambda n: n.startswith("Delivery"),
    "puzzle_solver": lambda n: n.startswith("Puzzle"),
}

module_index = {"modules": []}

for mod_name, filter_fn in modules.items():
    mod_nodes = {}
    for name in nodes:
        if not isinstance(nodes[name], dict):
            continue
        try:
            if filter_fn(name):
                mod_nodes[name] = nodes[name]
        except Exception:
            pass

    out_path = pipelines_dir / f"{mod_name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mod_nodes, f, ensure_ascii=False, indent=2)

    module_index["modules"].append({
        "name": mod_name,
        "path": str(out_path),
        "node_count": len(mod_nodes),
    })
    print(f"  {mod_name}: {len(mod_nodes)} nodes")

with open(pipelines_dir / "pipeline_index.json", "w", encoding="utf-8") as f:
    json.dump(module_index, f, ensure_ascii=False, indent=2)

print(f"\nDone. {len(module_index['modules'])} modules saved to {pipelines_dir}/")
