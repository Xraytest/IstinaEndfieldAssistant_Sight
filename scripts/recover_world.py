#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""娓告垙鐘舵€佸揩閫熸仮澶?鈥?鎸夐〉闈㈠绛栧鑸洖涓栫晫椤甸潰 v2"""
import subprocess, time, cv2, numpy as np, sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.service.page_analyzer import HighPrecisionPageAnalyzer
from core.capability.recognition import RecognitionEngine

ADB = Path(__file__).resolve().parent.parent / '3rd-part' / 'adb' / 'adb.exe'
SER = 'localhost:16512'

def sc():
    r = subprocess.run([str(ADB),'-s',SER,'exec-out','screencap','-p'],capture_output=True,timeout=10)
    return cv2.imdecode(np.frombuffer(r.stdout,np.uint8),cv2.IMREAD_COLOR)

def k(x):
    subprocess.run([str(ADB),'-s',SER,'shell','input','keyevent',str(x)],capture_output=True,timeout=5)

def tap(x,y):
    subprocess.run([str(ADB),'-s',SER,'shell','input','tap',str(x),str(y)],capture_output=True,timeout=5)

a = HighPrecisionPageAnalyzer()
engine = RecognitionEngine()

print('鑷姩瀵艰埅鍥炰笘鐣?..')
for attempt in range(40):
    img = sc()
    if img is None: continue
    r = a.analyze(img)
    pt = r['page_type']
    detail = r.get('detail', {})

    print(f'{attempt:2d}: {pt:18s} conf={r["confidence"]:.2f}')

    if pt == 'world':
        print('鉁?宸插洖鍒颁笘鐣岄〉闈紒')
        sys.exit(0)

    if pt == 'not_in_game':
        print('  閲嶅惎Endfield...')
        subprocess.run([str(ADB), '-s', SER, 'shell', 'am', 'force-stop',
                       'com.hypergryph.endfield'], capture_output=True, timeout=10)
        time.sleep(2)
        subprocess.run([str(ADB), '-s', SER, 'shell', 'monkey', '-p',
                       'com.hypergryph.endfield', '-c',
                       'android.intent.category.LAUNCHER', '1'],
                      capture_output=True, timeout=15)
        time.sleep(25)

    if pt == 'exit_dialog':
        # SIFT绮剧‘鍖归厤CancelButton浣嶇疆
        ok, r2 = engine.recognize(img, {
            "type": "TemplateMatch",
            "template": "Common/Button/CancelButtonType1.png",
            "roi": [200, 500, 700, 500],
            "threshold": 4
        })
        if ok:
            pos = r2.get("location", (538, 665))
            tap(pos[0], pos[1]); time.sleep(1)
        else:
            tap(538, 665); time.sleep(0.8)
    elif pt == 'quest_panel':
        k(4); time.sleep(1)
    elif pt == 'menu':
        k(4); time.sleep(1)
    elif pt == 'enter_game_prompt':
        for cx, cy in [(960, 540), (955, 400), (960, 1000)]:
            tap(cx, cy); time.sleep(2)
        k(66); time.sleep(1)  # ENTER
    elif pt == 'unknown':
        tap(960, 540); time.sleep(1)
        k(4); time.sleep(0.5)
    else:
        k(4); time.sleep(0.5)

print('鉂?鏈兘鎭㈠鍒颁笘鐣岄〉闈?)
sys.exit(1)

