"""Launch cloud Endfield and verify in-world state."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from core.foundation.paths import ensure_src_path
ensure_src_path()

from core.service.runtime import IstinaRuntime

SERIAL = "127.0.0.1:16416"

rt = IstinaRuntime(config_path="config/client_config.json")
rt.connect(SERIAL)
print(f"[OK] connected={rt.connected}")

maa = rt.maaend(SERIAL)
print(f"[OK] maaend.connected={maa.connected}")

# Launch game via AndroidOpenGame pipeline
print("[STEP] launching game via AndroidOpenGame...")
result = maa.run_task("AndroidOpenGame", {"ClientVersion": "CN"})
print(f"[OK] AndroidOpenGame result={result}")

# Wait and check if game is running
import time
for i in range(12):
    time.sleep(5)
    android = rt.android(SERIAL)
    try:
        pid = android.shell("pidof com.hypergryph.cloud.endfield").strip()
        if pid:
            print(f"[OK] game running, pid={pid} (check {i+1}/12)")
            break
    except Exception:
        pass
    print(f"[WAIT] game not yet running, check {i+1}/12")

# Verify in-world via OCR
print("[STEP] verifying in-world via OCR...")
ocr = rt.execute("scene.elements", {"serial": SERIAL, "enable_ocr": True, "enable_template": False, "enable_color": False})
if isinstance(ocr, dict) and ocr.get("status") == "success":
    text = "".join(e.get("label", "") for e in ocr.get("elements", []) if isinstance(e, dict))
    kws = ["地区建设", "干员", "采购中心", "行动手册", "通行证", "好友", "装备加工", "编队", "百科", "档案库", "探索"]
    hits = [k for k in kws if k in text]
    print(f"[OK] in_world_hits={len(hits)}/{len(kws)}: {hits}")
    if len(hits) >= 2:
        print("[SUCCESS] Game is in the world!")
    else:
        print("[WARN] Not enough in-world keywords, game may still be loading")
        # Print what OCR found
        print(f"[OCR preview] {text[:300]}")
else:
    print(f"[FAIL] OCR failed: {ocr}")
