#!/usr/bin/env python3
"""
ADB 设备信息诊断
"""

import subprocess, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-party' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'

def run_adb(cmd):
    r = subprocess.run([ADB, '-s', SERIAL] + cmd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

print("\n" + "="*70)
print("ADB 设备信息")
print("="*70)

# 设备列表
print("\n[设备列表]")
print(run_adb(['devices']))

# 分辨率
print("\n[分辨率]")
print(run_adb(['shell', 'wm', 'size']))

# 密度
print("\n[密度]")
print(run_adb(['shell', 'wm', 'density']))

# 显示信息
print("\n[显示信息]")
print(run_adb(['shell', 'dumpsys', 'display', 'display', '0']))

# 当前活动
print("\n[当前活动]")
output = run_adb(['shell', 'dumpsys', 'window', 'window'])
for line in output.split('\n')[:50]:
    if 'mCurrentFocus' in line or 'mFocusedApp' in line or 'ActivityRecord' in line:
        print(line)

# 测试点击
print("\n[点击测试]")
print("点击 (860, 80)...")
subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', '860', '80'], capture_output=True, timeout=10)
print("完成")
