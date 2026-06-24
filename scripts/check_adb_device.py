#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
ADB 璁惧淇℃伅璇婃柇
"""

import subprocess, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = str(PROJECT / '3rd-part' / 'adb' / 'adb.exe')
SERIAL = 'localhost:16512'

def run_adb(cmd):
    r = subprocess.run([ADB, '-s', SERIAL] + cmd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

print("\n" + "="*70)
print("ADB 璁惧淇℃伅")
print("="*70)

# 璁惧鍒楄〃
print("\n[璁惧鍒楄〃]")
print(run_adb(['devices']))

# 鍒嗚鲸鐜?print("\n[鍒嗚鲸鐜嘳")
print(run_adb(['shell', 'wm', 'size']))

# 瀵嗗害
print("\n[瀵嗗害]")
print(run_adb(['shell', 'wm', 'density']))

# 鏄剧ず淇℃伅
print("\n[鏄剧ず淇℃伅]")
print(run_adb(['shell', 'dumpsys', 'display', 'display', '0']))

# 褰撳墠娲诲姩
print("\n[褰撳墠娲诲姩]")
output = run_adb(['shell', 'dumpsys', 'window', 'window'])
for line in output.split('\n')[:50]:
    if 'mCurrentFocus' in line or 'mFocusedApp' in line or 'ActivityRecord' in line:
        print(line)

# 娴嬭瘯鐐瑰嚮
print("\n[鐐瑰嚮娴嬭瘯]")
print("鐐瑰嚮 (860, 80)...")
subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', '860', '80'], capture_output=True, timeout=10)
print("瀹屾垚")

