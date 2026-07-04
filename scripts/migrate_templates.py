"""
Migrate MaaEnd template images into modular assets/templates/ directories.

Copies PNG files from SampleProgram/MaaEnd_Release/resource/image/
into assets/templates/ organized by the same module/subdirectory naming.
"""
import shutil
from pathlib import Path

maaend_images = Path("3rd-part/maaend/resource/image")
target_root = Path("assets/templates")
target_root.mkdir(parents=True, exist_ok=True)

copied = 0
skipped = 0

for module_dir in sorted(maaend_images.iterdir()):
    if not module_dir.is_dir():
        continue

    target_dir = target_root / module_dir.name
    target_dir.mkdir(parents=True, exist_ok=True)

    for png in module_dir.glob("*.png"):
        target = target_dir / png.name
        if not target.exists():
            shutil.copy2(png, target)
            copied += 1
        else:
            skipped += 1

    # Also copy subdirectories (e.g., Common/Button/)
    for sub_dir in module_dir.iterdir():
        if not sub_dir.is_dir():
            continue
        target_sub = target_dir / sub_dir.name
        target_sub.mkdir(parents=True, exist_ok=True)
        for png in sub_dir.glob("*.png"):
            target = target_sub / png.name
            if not target.exists():
                shutil.copy2(png, target)
                copied += 1
            else:
                skipped += 1

# Create template index
index = {"modules": []}
for module_dir in sorted(target_root.iterdir()):
    if not module_dir.is_dir():
        continue
    png_count = len(list(module_dir.rglob("*.png")))
    if png_count > 0:
        index["modules"].append({
            "name": module_dir.name,
            "path": str(module_dir.relative_to(target_root)),
            "template_count": png_count,
        })

with open(target_root / "template_index.json", "w", encoding="utf-8") as f:
    import json
    json.dump(index, f, ensure_ascii=False, indent=2)

print(f"Copied {copied} templates, skipped {skipped}")
print(f"Total modules: {len(index['modules'])}")
