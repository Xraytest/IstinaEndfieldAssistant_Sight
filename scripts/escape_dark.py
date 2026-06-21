"""尝试多种方式退出当前暗色画面"""
import subprocess, time, os, cv2, numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJECT, '3rd-party', 'adb', 'adb.exe')
SERIAL = 'localhost:16512'
CACHE = os.path.join(PROJECT, 'cache')

def tap(x, y):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   timeout=10, capture_output=True)

def back():
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', '4'], timeout=5, capture_output=True)

def keyevent(code):
    subprocess.run([ADB, '-s', SERIAL, 'shell', 'input', 'keyevent', str(code)], timeout=5, capture_output=True)

def cap():
    r = subprocess.run([ADB, '-s', SERIAL, 'exec-out', 'screencap', '-p'], timeout=15, capture_output=True)
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

attempts = [
    ("center_tap", lambda: tap(960, 540)),
    ("cancel_dialog", lambda: tap(834, 717)),
    ("top_right_X", lambda: tap(1721, 49)),
    ("ESC_key", lambda: keyevent(111)),
    ("Home_key", lambda: keyevent(3)),
]

with open(os.path.join(CACHE, 'escape_log.txt'), 'w') as log:
    for name, action in attempts:
        img = cap()
        m = img.mean() if img is not None else -1
        msg = f'{name}: before mean={m:.1f}'
        print(msg, flush=True)
        log.write(msg + '\n')
        
        action()
        time.sleep(2)
        
        img2 = cap()
        m2 = img2.mean() if img2 is not None else -1
        msg = f'  after mean={m2:.1f}'
        print(msg, flush=True)
        log.write(msg + '\n')
        
        if img2 is not None:
            cv2.imwrite(os.path.join(CACHE, f'test_{name}.png'), img2)
        
        if m2 > 0 and m2 < 100:
            for _ in range(2):
                back()
                time.sleep(0.3)
            time.sleep(0.5)
            img3 = cap()
            m3 = img3.mean() if img3 is not None else -1
            msg = f'  after back mean={m3:.1f}'
            print(msg, flush=True)
            log.write(msg + '\n')
        
        log.flush()

print('\nDone', flush=True)
