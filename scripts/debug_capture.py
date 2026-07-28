"""捕获当前屏幕到文件并分析。"""
from __future__ import annotations

import sys
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
    job = controller.post_screencap()
    if not maaend._wait_job(job, timeout_s=10.0):
        print("截图失败")
        return 4
    img = controller.cached_image
    if img is None:
        print("cached_image 为空")
        return 5
    print(f"图像尺寸: {img.shape}")

    # 保存为 PNG
    try:
        from PIL import Image
        import numpy as np
        # numpy 数组 (H, W, C) BGR -> RGB
        arr = np.asarray(img)
        if arr.ndim == 3 and arr.shape[2] == 3:
            # MaaFW 返回 BGR，转 RGB
            arr = arr[:, :, ::-1]
        out_path = r"C:\Users\cheng\AppData\Local\Temp\iea_maa_capture.png"
        Image.fromarray(arr).save(out_path)
        print(f"截图已保存: {out_path}")

        # 计算图像统计
        gray = arr.mean(axis=2)
        print(f"均值: {gray.mean():.2f} 标准差: {gray.std():.2f}")
        print(f"最小值: {gray.min()} 最大值: {gray.max()}")
        print(f"唯一值数量: {len(np.unique(gray))}")
    except Exception as e:
        print(f"保存失败: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
