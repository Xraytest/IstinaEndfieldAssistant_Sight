"""测试 EmulatorExtras 截图方法并捕获详细日志。"""
from __future__ import annotations

import os
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

# 必须先 import runtime 以注入 MAAFW_BINARY_PATH，再 import maa.*
from core.service.maa_end import runtime as _runtime  # noqa: F401

from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
from maa.controller import AdbController

# 设置 debug 日志级别
os.environ["MAA_DEBUG"] = "1"


def main() -> int:
    print("=== 测试 EmulatorExtras (value=64) ===")
    try:
        controller = AdbController(
            adb_path=Path("3rd-part/adb/adb.exe").resolve(),
            address="127.0.0.1:16416",
            screencap_methods=int(MaaAdbScreencapMethodEnum.EmulatorExtras),
            input_methods=int(MaaAdbInputMethodEnum.Default),
            config={},
        )
        job = controller.post_connection()
        job.wait()
        cap_job = controller.post_screencap()
        cap_job.wait()
        img = controller.cached_image
        if img is None:
            print("EmulatorExtras: cached_image 为空")
            return 1
        print(f"EmulatorExtras: 图像尺寸 {img.shape}")
    except Exception as exc:
        print(f"EmulatorExtras: 异常 {exc}")

    print("\n=== 测试 Default (value=-57) ===")
    try:
        controller2 = AdbController(
            adb_path=Path("3rd-part/adb/adb.exe").resolve(),
            address="127.0.0.1:16416",
            screencap_methods=int(MaaAdbScreencapMethodEnum.Default),
            input_methods=int(MaaAdbInputMethodEnum.Default),
            config={},
        )
        job2 = controller2.post_connection()
        job2.wait()
        cap_job2 = controller2.post_screencap()
        cap_job2.wait()
        img2 = controller2.cached_image
        if img2 is None:
            print("Default: cached_image 为空")
            return 2
        print(f"Default: 图像尺寸 {img2.shape}")
    except Exception as exc:
        print(f"Default: 异常 {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
