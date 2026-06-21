#!/usr/bin/env python3
"""
终极测试：用多种方法验证 MaaFw 点击是否真的发送 ADB 命令

方法1: adb shell dumpsys input - 检查最后触摸事件
方法2: adb shell getevent -t - 捕获原始输入事件（后台线程）
方法3: 直接对比 MaaFw click 和 ADB tap 的截图变化
"""
import sys, os, time, subprocess, threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

ADB = [str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"), "-s", "localhost:16512"]

def run_adb(cmd, timeout=10):
    r = subprocess.run(ADB + cmd, capture_output=True, timeout=timeout)
    return r.stdout.decode(errors='replace'), r.stderr.decode(errors='replace'), r.returncode

# ── 初始化 MaaFw ──
from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE
cfg = MaaFwTouchConfig(
    adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
    address="localhost:16512",
    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
    input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
)
_maafw = MaaFwTouchExecutor(cfg)
if not _maafw.connect():
    print("MaaFw 连接失败")
    sys.exit(1)
print(f"MaaFw 连接成功, uuid={_maafw._uuid}")
print(f"MaaFw 分辨率: {_maafw.get_resolution()}")

# ── 方法1: dumpsys input ──
print("\n" + "="*60)
print("方法1: dumpsys input - 检查最后触摸事件")
print("="*60)

# 先清空状态
print("\n[清空状态] 执行 ADB tap (1, 1) 重置触摸状态...")
run_adb(["shell", "input", "tap", "1", "1"])
time.sleep(0.5)

# 检查当前触摸状态
out, _, _ = run_adb(["shell", "dumpsys", "input"])
# 查找 Touch 相关行
touch_lines = [l for l in out.split("\n") if "Touch" in l or "touch" in l.lower() or "Stream" in l]
print(f"\n当前触摸状态 ({len(touch_lines)} 行):")
for l in touch_lines[-10:]:
    print(f"  {l.strip()}")

# 执行 MaaFw 点击
print(f"\n>>> 执行 MaaFw click (800, 40)...")
t0 = time.time()
ok = _maafw.click(800, 40)
t1 = time.time()
print(f"    结果: {ok}, 耗时: {t1-t0:.2f}s")
time.sleep(0.5)

# 再次检查触摸状态
out, _, _ = run_adb(["shell", "dumpsys", "input"])
touch_lines2 = [l for l in out.split("\n") if "Touch" in l or "touch" in l.lower() or "Stream" in l]
print(f"\nMaaFw 点击后触摸状态 ({len(touch_lines2)} 行):")
for l in touch_lines2[-10:]:
    print(f"  {l.strip()}")

# ── 方法2: getevent ──
print("\n" + "="*60)
print("方法2: getevent - 捕获原始输入事件")
print("="*60)

# 使用 Popen 实时读取 getevent 输出
event_data = []
event_lock = threading.Lock()

def capture_getevent(duration=3):
    """使用 Popen 实时读取 getevent 输出"""
    try:
        proc = subprocess.Popen(
            ADB + ["shell", "getevent", "-t"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        start = time.time()
        while time.time() - start < duration:
            line = proc.stdout.readline()
            if line:
                with event_lock:
                    event_data.append(line.rstrip())
            else:
                time.sleep(0.01)
        proc.kill()
        proc.wait(timeout=2)
    except Exception as e:
        with event_lock:
            event_data.append(f"Error: {e}")

print("启动 getevent 捕获 (3s)...")
t = threading.Thread(target=capture_getevent, args=(3,), daemon=True)
t.start()
time.sleep(0.5)

print("执行 MaaFw click (400, 960)...")  # 屏幕中心附近
t0 = time.time()
ok = _maafw.click(400, 960)
t1 = time.time()
print(f"  结果: {ok}, 耗时: {t1-t0:.2f}s")

time.sleep(2)
t.join(timeout=2)

with event_lock:
    print(f"\n捕获到 {len(event_data)} 条事件:")
    for l in event_data[-15:]:
        print(f"  {l}")

# ── 方法3: 对比截图变化 ──
print("\n" + "="*60)
print("方法3: 对比截图变化 (MaaFw click vs ADB tap)")
print("="*60)

def adb_screencap():
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    return r.stdout if r.returncode == 0 else b""

# 自然变化基线
print("\n[基线] 连续3次截图观察自然变化:")
hashes = []
for i in range(3):
    data = adb_screencap()
    h = hash(data) % 1000000
    hashes.append(h)
    print(f"  截图{i+1}: hash={h}, 大小={len(data)}")
    time.sleep(0.5)
print(f"  自然变化: {hashes[0]} -> {hashes[1]} -> {hashes[2]}")

# MaaFw click
print("\n[MaaFw click] 点击 (400, 960) 后截图:")
before = adb_screencap()
h_before = hash(before) % 1000000
print(f"  点击前: hash={h_before}")

ok = _maafw.click(400, 960)
print(f"  MaaFw click: {ok}")
time.sleep(2)

after = adb_screencap()
h_after = hash(after) % 1000000
print(f"  点击后: hash={h_after}")
print(f"  变化: {h_before} -> {h_after} (差={abs(h_after-h_before)})")

# ADB tap
print("\n[ADB tap] 点击 (400, 960) 后截图:")
before2 = adb_screencap()
h_before2 = hash(before2) % 1000000
print(f"  点击前: hash={h_before2}")

run_adb(["shell", "input", "tap", "400", "960"])
print(f"  ADB tap: 完成")
time.sleep(2)

after2 = adb_screencap()
h_after2 = hash(after2) % 1000000
print(f"  点击后: hash={h_after2}")
print(f"  变化: {h_before2} -> {h_after2} (差={abs(h_after2-h_before2)})")

print("\n" + "="*60)
print("结论分析")
print("="*60)
print(f"""
MaaFw click 状态: {'成功' if ok else '失败'}
MaaFw 分辨率: {_maafw.get_resolution()}

如果 MaaFw click 后截图 hash 变化与自然变化基线相近，
而 ADB tap 后截图 hash 变化明显更大，
则说明 MaaFw click 未产生实际触控事件。

如果两者变化幅度相似，
则说明 MaaFw click 确实发送了触控事件。
""")
