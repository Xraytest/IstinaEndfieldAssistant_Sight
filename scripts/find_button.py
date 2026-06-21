#!/usr/bin/env python3
"""模板匹配找按钮 — 不靠像素分析"""
import subprocess, cv2, numpy as np
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ADB = PROJECT / '3rd-party' / 'adb' / 'adb.exe'
ASSETS = PROJECT / 'assets'

# 截图
r = subprocess.run([str(ADB), '-s', 'localhost:16512', 'exec-out', 'screencap', '-p'],
                  capture_output=True, timeout=10)
img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
print(f'截图: {img.shape}')

# 加载模板
templates = [
    ('CancelButtonType1', ASSETS / 'Common/Button/CancelButtonType1.png'),
    ('CancelButtonType2', ASSETS / 'Common/Button/CancelButtonType2.png'),
    ('WorldMenu', ASSETS / 'SceneManager/WorldMenu.png'),
    ('TaskIcon', ASSETS / 'SceneManager/TaskIcon.png'),
]

for name, path in templates:
    tmpl = cv2.imread(str(path))
    if tmpl is None:
        print(f'{name}: 模板加载失败')
        continue
    print(f'{name} 模板: {tmpl.shape[1]}x{tmpl.shape[0]}')
    
    for th in [0.9, 0.85, 0.8, 0.75, 0.7]:
        result = cv2.matchTemplate(img, tmpl, cv2.TM_CCOEFF_NORMED)
        max_val = float(np.max(result))
        max_loc = np.unravel_index(np.argmax(result), result.shape)
        loc = (max_loc[1] + tmpl.shape[1]//2, max_loc[0] + tmpl.shape[0]//2)
        
        if max_val >= th:
            print(f'  ✅ {name} @ ({loc[0]},{loc[1]}) conf={max_val:.3f} (th={th})')
            break
        else:
            print(f'  ❌ {name} max_conf={max_val:.3f} (needs {th})')
