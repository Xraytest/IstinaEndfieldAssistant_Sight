"""Test in-world detection and pipeline on local Endfield."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from core.foundation.paths import ensure_src_path
ensure_src_path()

from core.service.runtime import IstinaRuntime

SERIAL = "127.0.0.1:16416"

rt = IstinaRuntime(config_path="config/client_config.json")
rt.connect(SERIAL)
print(f"connected={rt.connected}")

maa = rt.maaend(SERIAL)
print(f"maaend.connected={maa.connected}")

# 1. Test EnterGame pipeline directly
print("\n=== Test 1: EnterGame pipeline ===")
for i in range(5):
    ok = maa.run_pipeline("EnterGame", {})
    print(f"  attempt {i+1}: {ok}")
    if ok:
        break

# 2. Test _wait_for_in_world
print("\n=== Test 2: _wait_for_in_world ===")
result = rt._wait_for_in_world(maa, interval=2, max_attempts=5)
print(f"_wait_for_in_world: {result}")

# 3. Test _verify_in_world_by_ocr
print("\n=== Test 3: _verify_in_world_by_ocr ===")
result = rt._verify_in_world_by_ocr(SERIAL)
print(f"_verify_in_world_by_ocr: {result}")

# 4. Get OCR labels (write to file for encoding safety)
print("\n=== Test 4: OCR labels ===")
ocr = rt.execute("scene.elements", {"serial": SERIAL, "enable_ocr": True, "enable_template": False, "enable_color": False})
if isinstance(ocr, dict) and ocr.get("status") == "success":
    labels = [e.get("label", "") for e in ocr.get("elements", []) if isinstance(e, dict)]
    # Write to file for clean UTF-8 output
    with open("cache/ocr_labels.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(labels))
    print(f"Wrote {len(labels)} labels to cache/ocr_labels.txt")
    # Print first 20
    for label in labels[:20]:
        print(f"  {label}")

    # Check keywords
    kws = ["地区建设", "干员", "采购中心", "行动手册", "通行证", "好友", "装备加工", "编队", "百科", "档案库", "探索"]
    hits = [k for k in kws if k in "".join(labels)]
    print(f"in_world hits: {len(hits)}/{len(kws)}: {hits}")
else:
    print(f"OCR failed: {ocr}")
