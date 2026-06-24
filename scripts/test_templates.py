#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娴嬭瘯妯℃澘鍖归厤鍜岃瘑鍒紩鎿?""
import sys, cv2, numpy as np
from pathlib import Path
from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path; ensure_path()
from core.capability.recognition import RecognitionEngine, PREDEFINED_STATES
from core.capability.adb_utils import ADB
import os; os.environ['PYTHONUNBUFFERED'] = '1'

adb = ADB()
img_bytes = adb.screencap(dedup=False)
if not img_bytes:
    print('[ERROR] 鎴浘澶辫触')
    sys.exit(1)

img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
print(f'[鎴浘] {img.shape}')

engine = RecognitionEngine()

# 1. CancelButton
print('\n[娴嬭瘯] CancelButton 妯℃澘鍖归厤...')
ok, result = engine.recognize(img, PREDEFINED_STATES['CancelButton'])
print(f'  result: {ok}, {result}')

# 2. TaskIcon
print('\n[娴嬭瘯] TaskIcon 妯℃澘鍖归厤...')
ok, result = engine.recognize(img, PREDEFINED_STATES['TaskIcon'])
print(f'  result: {ok}, {result}')

# 3. InWorld
print('\n[娴嬭瘯] InWorld 妯℃澘鍖归厤...')
ok, result = engine.recognize(img, PREDEFINED_STATES['InWorld'])
print(f'  result: {ok}, {result}')

# 4. YellowConfirmButton (color match)
print('\n[娴嬭瘯] 榛勮壊鎸夐挳棰滆壊鍖归厤...')
ok, result = engine.recognize(img, {
    "type": "ColorMatch",
    "lower": [28, 100, 100],
    "upper": [29, 255, 255],
    "count": 3000
})
print(f'  result: {ok}, {result}')

print('\n[瀹屾垚]')

