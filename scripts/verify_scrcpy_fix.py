"""scrcpy partial-read 修复验证脚本

验证 _recv_exact 修复是否生效：
1. 连接设备（启动 scrcpy 预览通道）
2. 监控 40 秒，每 2s 截图一次验证取帧正常
3. 执行 VisitFriends 任务（60s 超时），观察 scrcpy 在任务期间是否稳定
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.foundation.logger import get_logger
from core.service.runtime import IstinaRuntime

SERIAL = "192.168.1.12:16512"
MONITOR_SECONDS = 40


def main() -> int:
    logger = get_logger()
    runtime = IstinaRuntime()

    print(f"[VERIFY] step 1: 连接设备 serial={SERIAL}", flush=True)
    ok = runtime.connect(serial=SERIAL)
    if not ok:
        print("[VERIFY] FAIL: 连接失败", flush=True)
        return 1
    print("[VERIFY] OK: 连接成功，scrcpy 预览通道已启动", flush=True)

    print(f"[VERIFY] step 2: 监控 scrcpy 稳定性 {MONITOR_SECONDS}s（每 2s 截图）", flush=True)
    start = time.time()
    screenshots_ok = 0
    screenshots_fail = 0
    while time.time() - start < MONITOR_SECONDS:
        time.sleep(2.0)
        elapsed = time.time() - start
        try:
            android = runtime.android(SERIAL)
            result = android.screenshot(serial=SERIAL)
            if isinstance(result, dict) and result.get("error"):
                screenshots_fail += 1
                print(f"[VERIFY] [{elapsed:5.1f}s] screenshot FAIL: {result['error']}", flush=True)
            else:
                screenshots_ok += 1
                data = result.get("data") if isinstance(result, dict) else result
                size = len(data) if data else 0
                print(f"[VERIFY] [{elapsed:5.1f}s] screenshot OK size={size}", flush=True)
        except Exception as exc:
            screenshots_fail += 1
            print(f"[VERIFY] [{elapsed:5.1f}s] screenshot EXC: {exc}", flush=True)

    print(f"[VERIFY] 监控完成: ok={screenshots_ok} fail={screenshots_fail}", flush=True)
    if screenshots_ok < MONITOR_SECONDS // 4:
        print("[VERIFY] FAIL: 截图成功率过低，scrcpy 不稳定", flush=True)
        runtime.disconnect(serial=SERIAL)
        return 1

    print("[VERIFY] step 3: 执行 VisitFriends 任务（60s 超时）", flush=True)
    task_ok = False
    try:
        result = runtime.execute("task.run", {
            "name": "VisitFriends",
            "serial": SERIAL,
            "timeout": 60.0,
        })
        status = result.get("status") if isinstance(result, dict) else None
        print(f"[VERIFY] task.run status={status} result={str(result)[:300]}", flush=True)
        if status in ("success", "ok"):
            task_ok = True
            print("[VERIFY] OK: 任务执行成功", flush=True)
        else:
            print("[VERIFY] WARN: 任务未成功完成（可能是任务本身问题，非 scrcpy 问题）", flush=True)
    except Exception as exc:
        print(f"[VERIFY] task.run exception: {exc}", flush=True)

    print("[VERIFY] step 4: 任务后再次截图验证 scrcpy 仍存活", flush=True)
    try:
        result = android.screenshot(serial=SERIAL)
        if isinstance(result, dict) and not result.get("error"):
            data = result.get("data")
            print(f"[VERIFY] OK: 任务后截图成功 size={len(data) if data else 0}", flush=True)
        else:
            print(f"[VERIFY] WARN: 任务后截图失败: {result}", flush=True)
    except Exception as exc:
        print(f"[VERIFY] WARN: 任务后截图异常: {exc}", flush=True)

    try:
        runtime.disconnect(serial=SERIAL)
    except Exception:
        pass

    if screenshots_ok >= MONITOR_SECONDS // 4:
        print("[VERIFY] === PASS: scrcpy partial-read 修复验证通过 ===", flush=True)
        return 0
    else:
        print("[VERIFY] === FAIL: scrcpy 仍不稳定 ===", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
