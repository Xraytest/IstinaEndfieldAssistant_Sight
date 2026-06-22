#!/usr/bin/env python3
"""对比world和menu页面特征"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()
from core.service.page_analyzer import HighPrecisionPageAnalyzer

ADB = Path(__file__).resolve().parent.parent / '3rd-party' / 'adb' / 'adb.exe'
a = HighPrecisionPageAnalyzer()

def sc():
    r = subprocess.run([str(ADB),'-s','localhost:16512','exec-out','screencap','-p'],capture_output=True,timeout=10)
    return cv2.imdecode(np.frombuffer(r.stdout,np.uint8),cv2.IMREAD_COLOR)

def tap(x,y):
    subprocess.run([str(ADB),'-s','localhost:16512','shell','input','tap',str(x),str(y)],capture_output=True,timeout=5)

# 当前状态
img = sc()
r = a.analyze(img)
f1 = r['features']
print(f'[当前] {r["page_type"]} conf={r["confidence"]:.2f}', flush=True)

# 打开菜单
tap(1392, 79)
time.sleep(3)
img2 = sc()
r2 = a.analyze(img2)
f2 = r2['features']
print(f'[菜单] {r2["page_type"]} conf={r2["confidence"]:.2f}', flush=True)

# 差异对比
print('\n特征差异:', flush=True)
for k in f1:
    d = f2[k] - f1[k]
    if abs(d) > 0.5:
        print(f'  {k}: {f1[k]:.1f} → {f2[k]:.1f} (Δ={d:+.1f})', flush=True)
