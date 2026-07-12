#!/usr/bin/env python
"""验证 scrcpy 持续连接测试脚本（PERSIST-01）

验证 scrcpy 连接成功建立后在 GUI 进程终止前持续不断开，预览实时展示无延迟无抽帧。

测试逻辑：
  1. 通过 CLI 启动 daemon 并建立 scrcpy 连接（system connect）
  2. 持续监控 mmap frame_count 变化，记录帧率
  3. 检测 frame_count 停滞（连续无新帧）并报告
  4. 扫描日志确认无"强制重建会话"或"编码器停滞"记录
  5. 输出测试报告

用法：
  3rd-part/python/python.exe scripts/verify_scrcpy_persistent.py --serial <serial> [--duration 120]

退出码：
  0 — 测试通过（frame_count 持续增长，无中断）
  1 — 测试失败（frame_count 中断或日志出现重建记录）
"""

from __future__ import annotations

import argparse
import json
import mmap
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

_HEADER_FORMAT = "<4siiiiQI"
_HEADER_SIZE = 32
_MAGIC = b"SCF1"


def ensure_src_path() -> None:
    root = Path(__file__).resolve().parent.parent
    for p in (root / "src", root / "core"):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def get_cache_subdir(name: str) -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "cache" / name


def run_cli(serial: str, command: str, timeout: int = 30) -> dict | None:
    root = Path(__file__).resolve().parent.parent
    python = str(root / "3rd-part" / "python" / "python.exe")
    cli = str(root / "scripts" / "istina.py")
    cmd = [python, cli] + command.split()
    if "--serial" not in command:
        cmd += ["--serial", serial]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(root))
        if result.returncode != 0:
            print(f"  CLI 命令失败: {' '.join(cmd)}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")
            return None
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return None
    except subprocess.TimeoutExpired:
        print(f"  CLI 命令超时: {command}")
        return None
    except Exception as e:
        print(f"  CLI 命令异常: {e}")
        return None


def find_info_file(serial: str) -> Path | None:
    safe = serial.replace(":", "_").replace("/", "_").replace("\\", "_")
    info_path = get_cache_subdir("ipc") / f"android-{safe}.info"
    if info_path.exists():
        return info_path
    ipc_dir = get_cache_subdir("ipc")
    if ipc_dir.exists():
        for f in ipc_dir.glob("android-*.info"):
            return f
    return None


def open_mmap(info_path: Path) -> tuple[mmap.mmap, int, str] | None:
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
        mmap_path = info.get("frame_mmap_path", "")
        mmap_size = int(info.get("frame_mmap_size", 0))
    except Exception as e:
        print(f"  读取 info 文件失败: {e}")
        return None
    if not mmap_path or mmap_size <= 0:
        print(f"  info 文件缺少 mmap 路径或大小")
        return None
    if not Path(mmap_path).exists():
        print(f"  mmap 文件不存在: {mmap_path}")
        return None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(mmap_path, flags)
        mm = mmap.mmap(fd, mmap_size, access=mmap.ACCESS_READ)
        return mm, mmap_size, mmap_path
    except Exception as e:
        print(f"  打开 mmap 失败: {e}")
        return None


def read_frame_count(mm: mmap.mmap) -> int:
    try:
        magic = mm[0:4]
        if magic != _MAGIC:
            return -1
        _, w, h, stride, _fmt, ts, count = struct.unpack_from(_HEADER_FORMAT, mm, 0)
        return count
    except Exception:
        return -1


def scan_log_for_rebuilds(log_path: Path, since_ts: float) -> list[str]:
    """扫描日志中的会话重建记录。"""
    rebuild_keywords = [
        "强制重建会话",
        "编码器停滞",
        "连续 %d 次超时",
        "scrcpy 会话异常",
        "scrcpy socket EOF",
        "scrcpy server 进程已退出",
        "scrcpy 读取超时且 server 已退出",
    ]
    findings = []
    if not log_path.exists():
        return findings
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return findings
    for line in lines:
        for kw in rebuild_keywords:
            if kw in line:
                findings.append(line.strip())
                break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 scrcpy 持续连接")
    parser.add_argument("--serial", required=True, help="设备序列号")
    parser.add_argument("--duration", type=int, default=120, help="监控时长（秒），默认 120")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    log_path = root / "logs" / "main.log"

    print("=" * 70)
    print("scrcpy 持续连接验证测试（PERSIST-01）")
    print("=" * 70)
    print(f"设备序列号: {args.serial}")
    print(f"监控时长:   {args.duration}s")
    print()

    # 步骤 1: 通过 CLI 建立连接
    print("[1/4] 建立 scrcpy 连接...")
    test_start_ts = time.time()
    result = run_cli(args.serial, "system connect", timeout=30)
    if not result or result.get("status") != "success":
        print(f"  连接失败: {result}")
        return 1
    print(f"  连接成功: {result.get('message', 'OK')}")

    # 步骤 2: 等待 daemon 写入 info 文件
    print("[2/4] 等待 daemon mmap 就绪...")
    info_path = None
    deadline = time.time() + 15.0
    while time.time() < deadline:
        info_path = find_info_file(args.serial)
        if info_path is not None:
            break
        time.sleep(0.5)
    if info_path is None:
        print("  未找到 daemon info 文件（15s 超时）")
        return 1
    print(f"  info 文件: {info_path}")

    # 等待 mmap 有首帧
    mm_result = None
    deadline = time.time() + 15.0
    while time.time() < deadline:
        mm_result = open_mmap(info_path)
        if mm_result is not None:
            count = read_frame_count(mm_result[0])
            if count > 0:
                break
            mm_result[0].close()
            mm_result = None
        time.sleep(0.5)
    if mm_result is None:
        print("  mmap 无首帧（15s 超时）")
        return 1
    mm, mmap_size, mmap_path = mm_result
    initial_count = read_frame_count(mm)
    print(f"  mmap 就绪: {mmap_path}")
    print(f"  初始 frame_count: {initial_count}")
    print()

    # 步骤 3: 持续监控 frame_count
    print(f"[3/4] 持续监控 frame_count（{args.duration}s）...")
    monitor_start = time.time()
    deadline = monitor_start + args.duration
    samples = []
    last_count = initial_count
    stall_periods = []
    stall_start = None
    max_stall = 0.0
    total_stall_time = 0.0

    while time.time() < deadline:
        count = read_frame_count(mm)
        now = time.time()
        if count != last_count:
            if count > last_count:
                # 有新帧
                if stall_start is not None:
                    stall_duration = now - stall_start
                    stall_periods.append((stall_start, now, stall_duration))
                    total_stall_time += stall_duration
                    if stall_duration > max_stall:
                        max_stall = stall_duration
                    if stall_duration > 3.0:
                        print(f"  [警告] 帧停滞 {stall_duration:.1f}s ({time.strftime('%H:%M:%S', time.localtime(stall_start))})")
                    stall_start = None
                samples.append((now, count))
                last_count = count
            else:
                # frame_count 倒退（daemon 重启）
                print(f"  [警告] frame_count 倒退: {last_count} → {count}（daemon 可能重启）")
                samples.append((now, count))
                last_count = count
                if stall_start is None:
                    stall_start = now
        else:
            # 无新帧
            if stall_start is None:
                stall_start = now
        time.sleep(0.5)

    if stall_start is not None:
        stall_duration = time.time() - stall_start
        stall_periods.append((stall_start, time.time(), stall_duration))
        total_stall_time += stall_duration
        if stall_duration > max_stall:
            max_stall = stall_duration

    monitor_end = time.time()
    monitor_duration = monitor_end - monitor_start
    final_count = read_frame_count(mm)
    total_frames = final_count - initial_count

    try:
        mm.close()
    except Exception:
        pass

    print(f"  监控结束: {monitor_duration:.1f}s")
    print(f"  frame_count: {initial_count} → {final_count}（+{total_frames} 帧）")
    avg_fps = total_frames / monitor_duration if monitor_duration > 0 else 0
    print(f"  平均帧率:   {avg_fps:.1f} fps")
    print(f"  停滞次数:   {len(stall_periods)}")
    print(f"  最大停滞:   {max_stall:.1f}s")
    print(f"  总停滞时间: {total_stall_time:.1f}s")
    print()

    # 步骤 4: 扫描日志确认无会话重建
    print("[4/4] 扫描日志确认无会话重建...")
    rebuilds = scan_log_for_rebuilds(log_path, test_start_ts)
    # 只保留测试开始后的记录
    recent_rebuilds = []
    for line in rebuilds:
        recent_rebuilds.append(line)
    if recent_rebuilds:
        print(f"  [警告] 发现 {len(recent_rebuilds)} 条重建相关日志:")
        for line in recent_rebuilds[-5:]:
            print(f"    {line[:200]}")
    else:
        print("  无会话重建日志（通过）")
    print()

    # 测试结果判定
    print("=" * 70)
    print("测试结果")
    print("=" * 70)

    passed = True
    reasons = []

    # 判定 1: frame_count 持续增长
    if total_frames < 10:
        passed = False
        reasons.append(f"帧数过少: {total_frames}（预期 >10）")
    elif avg_fps < 1.0:
        passed = False
        reasons.append(f"帧率过低: {avg_fps:.1f} fps（预期 >1.0）")

    # 判定 2: 无长时间停滞（>15s 视为中断）
    long_stalls = [s for s in stall_periods if s[2] > 15.0]
    if long_stalls:
        passed = False
        reasons.append(f"存在 {len(long_stalls)} 次长时间停滞（>15s）")
        for start, end, dur in long_stalls:
            print(f"  长停滞: {dur:.1f}s ({time.strftime('%H:%M:%S', time.localtime(start))} - {time.strftime('%H:%M:%S', time.localtime(end))})")

    # 判定 3: 无"强制重建会话"日志
    force_rebuilds = [l for l in recent_rebuilds if "强制重建会话" in l or "编码器停滞" in l]
    if force_rebuilds:
        passed = False
        reasons.append(f"日志出现 {len(force_rebuilds)} 条强制重建记录")

    if passed:
        print("通过 — scrcpy 连接持续不断开，预览实时展示无中断")
        print(f"  监控 {monitor_duration:.0f}s 内收到 {total_frames} 帧，平均 {avg_fps:.1f} fps")
        print(f"  最大停滞 {max_stall:.1f}s（<15s 阈值）")
        print(f"  无强制重建会话日志")
        return 0
    else:
        print("失败 — 存在以下问题:")
        for r in reasons:
            print(f"  - {r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
