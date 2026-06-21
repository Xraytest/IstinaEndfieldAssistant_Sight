"""
Device CLI 模块 — 设备检测、截图、触控操作

用法（通过 istina.py）:
  istina.py device status           # 连接状态
  istina.py device screenshot       # 截图保存
  istina.py device info             # 设备详细信息
  istina.py device tap <x> <y>      # 点击坐标
  istina.py device swipe <x1> <y1> <x2> <y2> [duration]
  istina.py device keyevent <code>  # 按键事件
  istina.py device monitor          # 设备实时状态

独立运行:
  python -m src.cli.device_cli status
"""

import sys, os, json, time, subprocess, platform, argparse
from typing import Optional, List
from utils.paths import ensure_src_path, get_project_root

ensure_src_path(__file__)
PROJECT_ROOT = get_project_root(__file__)


def _get_adb():
    from core.adb_utils import ADB
    return ADB()


def _get_touch_manager():
    """获取 TouchManager 实例（用于 CLI 触控操作）"""
    try:
        from device.touch.touch_manager import TouchManager
        from device.touch.maafw_touch_adapter import MaaFwTouchConfig
        tm = TouchManager()
        config = MaaFwTouchConfig(
            adb_path=os.path.join(PROJECT_ROOT, "3rd-party", "adb", "adb.exe"),
            address="localhost:16512",
        )
        if tm.connect_android(
            adb_path=config.adb_path,
            address=config.address,
            screencap_methods=config.screencap_methods,
            input_methods=config.input_methods,
            config=config.config
        ):
            return tm
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"TouchManager 连接失败：{e}")
        return None


def _get_capture():
    try:
        from screenshot.screen_capture import ScreenCapture
        return ScreenCapture()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"ScreenCapture 初始化失败：{e}")
        return None


def cmd_status(args) -> int:
    """ADB 连接状态"""
    from core.adb_utils import check_device, list_devices
    ok = check_device()
    devices = list_devices()
    print(json.dumps({
        "connected": ok,
        "serial": "localhost:16512",
        "devices": devices,
        "device_count": len(devices),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_screenshot(args) -> int:
    """截图保存"""
    adb = _get_adb()
    out_dir = args.output or os.path.join(PROJECT_ROOT, "cache")
    tag = args.tag or "cli"
    path = adb.screenshot_path(out_dir, tag=tag)
    if path:
        size = os.path.getsize(path)
        print(f"截图已保存: {path}")
        print(f"大小: {size//1024} KB")
        from hashlib import md5
        with open(path, "rb") as f:
            h = md5(f.read()).hexdigest()[:8]
        print(f"哈希: {h}")
        return 0
    print("截图失败")
    return 1


def cmd_info(args) -> int:
    """设备详细信息"""
    from core.adb_utils import list_devices, _adb_cmd

    devices = list_devices()

    info = {
        "device_count": len(devices),
        "devices": devices,
        "current_serial": "localhost:16512",
        "adb_path": os.path.join(PROJECT_ROOT, "3rd-party", "adb", "adb.exe"),
    }

    # 分辨率
    try:
        r = _adb_cmd(["shell", "wm", "size"], timeout=5)
        info["resolution"] = r.stdout.decode().strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"获取分辨率失败：{e}")
        info["resolution"] = "unknown"

    # DPI
    try:
        r = _adb_cmd(["shell", "wm", "density"], timeout=5)
        info["density"] = r.stdout.decode().strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"获取 DPI 失败：{e}")
        info["density"] = "unknown"

    # Android 版本
    try:
        r = _adb_cmd(["shell", "getprop", "ro.build.version.release"], timeout=5)
        info["android_version"] = r.stdout.decode().strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"获取 Android 版本失败：{e}")
        info["android_version"] = "unknown"

    # 设备型号
    try:
        r = _adb_cmd(["shell", "getprop", "ro.product.model"], timeout=5)
        info["device_model"] = r.stdout.decode().strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"获取设备型号失败：{e}")
        info["device_model"] = "unknown"

    # 截图能力
    try:
        from core.adb_utils import adb_screencap
        t0 = time.time()
        img = adb_screencap(timeout=10)
        t1 = time.time()
        if img:
            info["screenshot_ok"] = True
            info["screenshot_ms"] = int((t1 - t0) * 1000)
            info["screenshot_bytes"] = len(img)
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"截图能力检测失败：{e}")
        info["screenshot_ok"] = False

    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_tap(args) -> int:
    """点击坐标"""
    tm = _get_touch_manager()
    if not tm:
        print("触控管理器初始化失败（需要 MaaFw 支持）")
        return 1
    x, y = args.x, args.y
    print(f"点击 ({x}, {y})...")
    ok = tm.safe_press(x, y)
    print(f"{'成功' if ok else '失败'}")
    return 0 if ok else 1


def cmd_swipe(args) -> int:
    """滑动"""
    tm = _get_touch_manager()
    if not tm:
        print("触控管理器初始化失败（需要 MaaFw 支持）")
        return 1
    dur = args.duration or 500
    print(f"滑动 ({args.x1},{args.y1}) -> ({args.x2},{args.y2}) duration={dur}ms...")
    ok = tm.safe_swipe(args.x1, args.y1, args.x2, args.y2, dur)
    print(f"{'成功' if ok else '失败'}")
    return 0 if ok else 1


def cmd_keyevent(args) -> int:
    """按键事件"""
    tm = _get_touch_manager()
    if not tm:
        print("触控管理器初始化失败（需要 MaaFw 支持）")
        return 1
    print(f"按键 {args.code}...")
    names = {3: "HOME", 4: "BACK", 26: "POWER", 66: "ENTER", 67: "DELETE", 82: "MENU"}
    name = names.get(args.code, f"KEY_{args.code}")
    ok = tm.execute_tool_call("pipeline_task", {"entry": f"Key{args.code}"})
    print(f"{name}: {'成功' if ok else '失败'}")
    return 0 if ok else 1


def cmd_wake(args) -> int:
    """设备唤醒 (keyevent 26 = POWER)"""
    import subprocess
    from pathlib import Path
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    adb_path = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")
    device_serial = args.device or "localhost:16512"

    print(f"[wake] 设备：{device_serial}")
    print("[wake] 发送唤醒按键 (KEYCODE_POWER = 26)...")
    cmd = [adb_path, "-s", device_serial, "shell", "input", "keyevent", "26"]
    result = subprocess.run(cmd, capture_output=True, timeout=10)
    ok = result.returncode == 0
    print(f"[wake]: {'成功' if ok else '失败'}")
    if not ok:
        print(f"[wake] 错误：{result.stderr.decode('utf-8', errors='replace')}")
    return 0 if ok else 1


def cmd_monitor(args) -> int:
    """设备实时监控"""
    interval = args.interval or 3
    print(f"设备状态监控 (刷新={interval}s, Ctrl+C 退出)")
    print(f"{'时间':<20} {'ADB':<8} {'截图(ms)':<12} {'截图大小':<12}")
    print("-" * 55)

    try:
        while True:
            ts = time.strftime("%H:%M:%S")
            from core.adb_utils import check_device, adb_screencap
            ok = check_device()
            status = "OK" if ok else "OFF"
            t0 = time.time()
            img = adb_screencap(timeout=5)
            t1 = time.time()
            if img:
                cap_ms = int((t1 - t0) * 1000)
                cap_sz = f"{len(img)//1024}KB"
            else:
                cap_ms = 0
                cap_sz = "FAIL"
            print(f"{ts:<20} {status:<8} {cap_ms:<12} {cap_sz:<12}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n监控已停止")
    return 0


# ── 独立入口 ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Device CLI 模块")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="连接状态")
    p_ss = sub.add_parser("screenshot", help="截图保存")
    p_ss.add_argument("--output", "-o", help="输出目录")
    p_ss.add_argument("--tag", help="文件名标签")

    sub.add_parser("info", help="设备详细信息")

    p_tap = sub.add_parser("tap", help="点击坐标")
    p_tap.add_argument("x", type=int)
    p_tap.add_argument("y", type=int)

    p_swipe = sub.add_parser("swipe", help="滑动")
    p_swipe.add_argument("x1", type=int)
    p_swipe.add_argument("y1", type=int)
    p_swipe.add_argument("x2", type=int)
    p_swipe.add_argument("y2", type=int)
    p_swipe.add_argument("duration", type=int, nargs="?", default=500)

    p_ke = sub.add_parser("keyevent", help="按键事件")
    p_ke.add_argument("code", type=int, help="按键码 (3=HOME, 4=BACK)")

    p_wake = sub.add_parser("wake", help="设备唤醒 (keyevent 26)")
    p_wake.add_argument("--device", "-d", help="设备序列号")

    p_mon = sub.add_parser("monitor", help="实时监控")
    p_mon.add_argument("--interval", "-i", type=float, default=3, help="刷新间隔")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmds = {
        "status": cmd_status,
        "screenshot": cmd_screenshot,
        "info": cmd_info,
        "tap": cmd_tap,
        "swipe": cmd_swipe,
        "keyevent": cmd_keyevent,
        "wake": cmd_wake,
        "monitor": cmd_monitor,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
