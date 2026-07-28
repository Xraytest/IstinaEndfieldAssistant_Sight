"""测试强制横屏后 maaend 截图的尺寸。"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from core.foundation.paths import ensure_src_path

ensure_src_path()

from core.foundation.logger import init_logger

init_logger()

from core.service.runtime import IstinaRuntime


def main() -> int:
    # 先用 ADB 设置横屏
    subprocess.run(
        ["3rd-part/adb/adb.exe", "-s", "127.0.0.1:16416", "shell",
         "settings", "put", "system", "user_rotation", "1"],
        text=True, timeout=5, capture_output=True,
    )
    print("已设置 user_rotation=1")
    # 等 2s 让设置生效
    time.sleep(2.0)

    runtime = IstinaRuntime()
    if not runtime.connect(serial="127.0.0.1:16416"):
        print("连接失败")
        return 1
    maaend = runtime.maaend()
    controller = maaend._controller
    if controller is None:
        print("controller 未就绪")
        return 2
    if not maaend._wait_for_tasker_ready(wait_s=5.0, rebuild_on_stuck=True):
        print("Tasker 未就绪")
        return 3

    # 截图 3 次，看尺寸是否稳定
    for i in range(3):
        job = controller.post_screencap()
        if not maaend._wait_job(job, timeout_s=10.0):
            print(f"截图 {i+1} 失败")
            continue
        img = controller.cached_image
        if img is None:
            print(f"截图 {i+1} cached_image 为空")
            continue
        print(f"截图 {i+1} 尺寸: {img.shape}")
        time.sleep(1.0)

    # 再用 ADB 直接截图对比
    r = subprocess.run(
        ["3rd-part/adb/adb.exe", "-s", "127.0.0.1:16416", "exec-out", "screencap", "-p"],
        capture_output=True,
    )
    out_path = r"C:\Users\cheng\AppData\Local\Temp\iea_adb_direct.png"
    Path(out_path).write_bytes(r.stdout)
    from PIL import Image
    img = Image.open(out_path)
    print(f"ADB 直接截图尺寸: {img.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
