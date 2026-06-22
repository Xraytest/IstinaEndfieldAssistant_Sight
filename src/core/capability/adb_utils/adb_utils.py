"""
ADB 工具层 — 统一设备操作接口

提供 ADB 截图、设备检测和统一 ADB 接口类。

注意：
- 触控操作已迁移至 MaaFw TouchManager
- VLM 分析接口已迁移至 core.vlm_utils

用法:
  from core.capability.adb_utils import ADB
  adb = ADB()
  img = adb.screencap()
"""

import io, os, sys, time, json, hashlib, subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable

from core.foundation.utils.paths import get_project_root, get_adb_path


# ── 项目路径 ──────────────────────────────────────────────────────
ADB_PATH = get_adb_path(__file__)
DEVICE_SERIAL = "localhost:16512"


# ── 异常 ──────────────────────────────────────────────────────────
class ADBError(Exception):
    """ADB 操作异常"""
    pass

class ScreenshotError(ADBError):
    """截图异常"""
    pass

class TimeoutError(ADBError):
    """操作超时"""
    pass


# ── ADB 设备管理 ──────────────────────────────────────────────────
def _adb_cmd(args: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """执行 ADB 命令"""
    cmd = [ADB_PATH, "-s", DEVICE_SERIAL] + args
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"ADB 命令超时：{' '.join(args[:3])}")
    except FileNotFoundError:
        raise ADBError(f"ADB 未找到：{ADB_PATH}")


def check_device() -> bool:
    """检查 ADB 设备是否在线"""
    try:
        r = _adb_cmd(["get-state"], timeout=5)
        return r.returncode == 0 and r.stdout.decode().strip() == "device"
    except ADBError:
        return False


def list_devices() -> List[str]:
    """列出 ADB 设备"""
    r = _adb_cmd(["devices"], timeout=5)
    lines = r.stdout.decode().strip().split("\n")[1:]
    return [l.split("\t")[0] for l in lines if l.strip() and "device" in l]


# ── ADB 截图 ──────────────────────────────────────────────────────

def adb_screencap(serial: str = DEVICE_SERIAL, timeout: int = 15) -> Optional[bytes]:
    """ADB 截图，返回 PNG 字节"""
    try:
        cmd = [ADB_PATH, "-s", serial, "exec-out", "screencap", "-p"]
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        return None
    except Exception:
        return None


def adb_screencap_unique(serial: str = DEVICE_SERIAL, timeout: int = 15,
                          last_hash: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str]]:
    """截图并去重，返回 (image_bytes, md5_hash)

    如果画面与 last_hash 相同则返回 (None, same_hash)
    """
    img = adb_screencap(serial=serial, timeout=timeout)
    if img is None:
        return (None, None)

    h = hashlib.md5(img).hexdigest()
    if last_hash is not None and h == last_hash:
        return (None, h)

    return (img, h)


# ── 重试工具 ──────────────────────────────────────────────────────
def retry(max_attempts: int = 3, delay: float = 1.0,
          backoff: float = 2.0) -> Callable:
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (backoff ** attempt))
            raise last_exc  # type: ignore
        return wrapper
    return decorator


# ── 统一 ADB 接口类 ──────────────────────────────────────────────
class ADB:
    """统一 ADB 操作接口（便捷封装）
    
    注意：tap/swipe/keyevent 已迁移至 TouchManager/MaaFwTouchExecutor，
    此类仅保留截图和连接管理功能。
    """

    def __init__(self, serial: str = DEVICE_SERIAL):
        self.serial = serial
        self._last_screenshot_hash: Optional[str] = None

    def screencap(self, dedup: bool = True) -> Optional[bytes]:
        """截图（可选去重）

        去重启用时，如果画面与上次相同返回 None
        """
        if dedup:
            img, h = adb_screencap_unique(serial=self.serial, last_hash=self._last_screenshot_hash)
            if img is not None:
                self._last_screenshot_hash = h
            return img
        else:
            return adb_screencap(serial=self.serial)

    def wait(self, seconds: float):
        """等待"""
        time.sleep(seconds)

    def screenshot_path(self, session_dir: str, tag: str = "img") -> Optional[str]:
        """截图并保存到文件"""
        img = self.screencap(dedup=False)
        if img is None:
            return None
        os.makedirs(session_dir, exist_ok=True)
        h = hashlib.md5(img).hexdigest()[:8]
        path = os.path.join(session_dir, f"{tag}_{int(time.time())}_{h}.png")
        with open(path, "wb") as f:
            f.write(img)
        return path

    def check_connection(self) -> bool:
        """检查设备连接"""
        try:
            cmd = [ADB_PATH, "-s", self.serial, "get-state"]
            r = subprocess.run(cmd, capture_output=True, timeout=5)
            return r.returncode == 0 and r.stdout.decode().strip() == "device"
        except Exception:
            return False

    # ── 触控方法已移除 ──────────────────────────────────────
    # tap/swipe/back 已完全迁移至 MaaFw TouchManager
    # 此类仅保留截图和连接管理功能
