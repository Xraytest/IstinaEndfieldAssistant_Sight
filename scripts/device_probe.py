"""Quick device probe: connection, screenshot size, OCR keywords, process check."""
import sys, os
# scripts/ is at <root>/scripts/, src/ is at <root>/src/
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

img = maa.screenshot(timeout_s=8)
print(f"[OK] screenshot={len(img) if img else 0} bytes")

if img:
    import cv2, numpy as np
    arr = np.frombuffer(img, np.uint8)
    screen = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    print(f"[OK] screen_size={screen.shape[1]}x{screen.shape[0]}")

# OCR
ocr = rt.execute("scene.elements", {"serial": SERIAL, "enable_ocr": True, "enable_template": False, "enable_color": False})
if isinstance(ocr, dict) and ocr.get("status") == "success":
    text = "".join(e.get("label", "") for e in ocr.get("elements", []) if isinstance(e, dict))
    print(f"[OK] ocr_text_len={len(text)}")
    # Check in-world keywords
    kws = ["地区建设", "干员", "采购中心", "行动手册", "通行证", "好友", "装备加工", "编队", "百科", "档案库", "探索"]
    hits = [k for k in kws if k in text]
    print(f"[OK] in_world_hits={len(hits)}/{len(kws)}: {hits[:5]}")
    # Check collect success keywords
    ckws = ["获得", "采集成功", "收取成功", "已采集"]
    chits = [k for k in ckws if k in text]
    print(f"[OK] collect_keyword_hits={chits}")
else:
    print(f"[FAIL] ocr status={ocr.get('status') if isinstance(ocr, dict) else type(ocr)}")

# ADB process check
android = rt.android(SERIAL)
try:
    out = android.shell("ps -A 2>/dev/null | grep endfield; pidof com.hypergryph.endfield; pidof com.hypergryph.cloud.endfield").strip()
    print(f"[OK] process_check_output={out!r}")
except Exception as exc:
    print(f"[WARN] process check failed: {exc}")

# pidof alone
try:
    out = android.shell("pidof com.hypergryph.endfield").strip()
    print(f"[OK] pidof endfield={out!r}")
except Exception as exc:
    print(f"[WARN] pidof failed: {exc}")
