"""
Migrate MaaEnd task definitions into modular assets/tasks/ directories.

Copies task JSON files from SampleProgram/MaaEnd_Release/tasks/
into assets/tasks/, preserving the preset/ subdirectory structure.
"""
import json
import shutil
from pathlib import Path

maaend_tasks = Path("SampleProgram/MaaEnd_Release/tasks")
target_root = Path("assets/tasks")
target_root.mkdir(parents=True, exist_ok=True)

copied = 0
skipped = 0

for json_path in maaend_tasks.rglob("*.json"):
    rel = json_path.relative_to(maaend_tasks)
    target = target_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        shutil.copy2(json_path, target)
        copied += 1
    else:
        skipped += 1

# Create task index
index = {"tasks": [], "presets": []}
for json_path in sorted(target_root.rglob("*.json")):
    if json_path.name == "task_index.json":
        continue
    rel = str(json_path.relative_to(target_root))
    is_preset = "preset" in json_path.parts
    entry = {"name": json_path.stem, "path": rel}
    if is_preset:
        index["presets"].append(entry)
    else:
        index["tasks"].append(entry)

with open(target_root / "task_index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print(f"Copied {copied} task files, skipped {skipped}")
print(f"Tasks: {len(index['tasks'])}, Presets: {len(index['presets'])}")
