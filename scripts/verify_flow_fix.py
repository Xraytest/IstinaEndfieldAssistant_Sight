#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏍囧噯娴佷慨澶嶉獙璇佽剼鏈?
楠岃瘉鍐呭锛?1. 鏂伴〉闈㈠垎鏋愬櫒鑳藉惁姝ｇ‘璇嗗埆涓栫晫椤甸潰鍜屼换鍔￠潰鏉?2. 鏍囧噯娴佸紩鎿庡墠缃〉闈㈤獙璇侀€昏緫鏄惁姝ｅ父宸ヤ綔
3. 閫€鍑哄璇濇澶勭悊鏄惁鍙潬
"""

import subprocess
import time
import cv2
import numpy as np
from pathlib import Path
import sys

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.service.page_analyzer import HighPrecisionPageAnalyzer

PROJECT = PROJECT_ROOT

ADB_EXE = PROJECT / '3rd-part' / 'adb' / 'adb.exe'
SERIAL = 'localhost:16512'


def adb_cmd(args):
    """鎵ц ADB 鍛戒护"""
    return subprocess.run(
        [str(ADB_EXE), '-s', SERIAL] + args,
        capture_output=True, timeout=15
    )


def screencap():
    """鎴浘"""
    r = adb_cmd(['exec-out', 'screencap', '-p'])
    if len(r.stdout) < 1000:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def tap(x, y):
    """鐐瑰嚮"""
    adb_cmd(['shell', 'input', 'tap', str(int(x)), str(int(y))])


def keyevent(key):
    """鎸夐敭"""
    adb_cmd(['shell', 'input', 'keyevent', str(key)])


def test_page_analyzer():
    """娴嬭瘯椤甸潰鍒嗘瀽鍣?""
    print("\n" + "="*70)
    print("娴嬭瘯 1: 椤甸潰鍒嗘瀽鍣?)
    print("="*70)
    
    analyzer = HighPrecisionPageAnalyzer()
    correct = 0
    total = 0
    
    # 娴嬭瘯涓栫晫椤甸潰
    print("\n[娴嬭瘯] 涓栫晫椤甸潰璇嗗埆...")
    for i in range(3):
        # 鎸夎繑鍥為敭鐩村埌涓栫晫椤甸潰锛堟渶澶?10 娆★級
        for attempt in range(10):
            keyevent(4)
            time.sleep(0.3)
            
            img = screencap()
            if img is None:
                continue
            
            result = analyzer.analyze(img)
            if result['page_type'] == "world":
                break
        
        img = screencap()
        if img is None:
            print(f"  鏍锋湰 {i+1}: 鎴浘澶辫触")
            continue
        
        result = analyzer.analyze(img)
        page_type = result['page_type']
        confidence = result['confidence']
        features = result['features']
        
        total += 1
        if page_type == "world":
            correct += 1
            status = "鉁?
        else:
            status = "鉂?
        
        print(f"  {status} 鏍锋湰 {i+1}: {page_type} (缃俊搴?{confidence:.2f})")
        print(f"       left_bar={features['left_bar_brightness']:.1f} green={features['green_pixels_top_right']:.0f}")
    
    # 娴嬭瘯浠诲姟闈㈡澘
    print("\n[娴嬭瘯] 浠诲姟闈㈡澘璇嗗埆...")
    tap(860, 80)  # 浠诲姟鍥炬爣
    time.sleep(2)
    
    for i in range(3):
        img = screencap()
        if img is None:
            print(f"  鏍锋湰 {i+1}: 鎴浘澶辫触")
            continue
        
        result = analyzer.analyze(img)
        page_type = result['page_type']
        confidence = result['confidence']
        features = result['features']
        
        # 楠岃瘉鏄惁鐪熺殑鍦ㄤ换鍔￠潰鏉匡紙left_bar > 120锛?        actual_quest_panel = features['left_bar_brightness'] > 120 and features['green_pixels_top_right'] < 30
        
        total += 1
        if actual_quest_panel:
            # 纭疄鍦ㄤ换鍔￠潰鏉匡紝妫€鏌ヨ瘑鍒槸鍚︽纭?            if page_type == "quest_panel":
                correct += 1
                status = "鉁?
            else:
                status = "鉂?璇嗗埆閿欒)"
        else:
            # 涓嶅湪浠诲姟闈㈡澘锛岃瘑鍒负鍏朵粬椤甸潰鏄纭殑
            if page_type != "quest_panel":
                correct += 1
                status = "鉁?姝ｇ‘璇嗗埆涓洪潪浠诲姟闈㈡澘)"
            else:
                status = "鉂?閿欒璇嗗埆涓轰换鍔￠潰鏉?"
        
        print(f"  {status} 鏍锋湰 {i+1}: {page_type} (缃俊搴?{confidence:.2f})")
        print(f"       left_bar={features['left_bar_brightness']:.1f} green={features['green_pixels_top_right']:.0f} 瀹為檯鍦ㄤ换鍔￠潰鏉?{actual_quest_panel}")
    
    # 杩斿洖涓栫晫
    for _ in range(3):
        keyevent(4)
        time.sleep(0.3)
    
    accuracy = correct / total if total > 0 else 0
    print(f"\n[缁撴灉] 鍑嗙‘鐜囷細{correct}/{total} ({accuracy*100:.1f}%)")
    
    return accuracy > 0.8


def test_exit_dialog_handling():
    """娴嬭瘯閫€鍑哄璇濇澶勭悊"""
    print("\n" + "="*70)
    print("娴嬭瘯 2: 閫€鍑哄璇濇澶勭悊")
    print("="*70)
    
    analyzer = HighPrecisionPageAnalyzer()
    
    # 纭繚鍦ㄤ笘鐣岄〉闈?    print("\n[姝ラ 1] 纭繚鍦ㄤ笘鐣岄〉闈?..")
    for _ in range(5):
        keyevent(4)
        time.sleep(0.3)
    time.sleep(1)
    
    img = screencap()
    if img is None:
        print("  [澶辫触] 鎴浘澶辫触")
        return False
    
    result = analyzer.analyze(img)
    print(f"  褰撳墠椤甸潰锛歿result['page_type']} (缃俊搴?{result['confidence']:.2f})")
    
    if result['page_type'] != "world":
        print("  [璀﹀憡] 涓嶅湪涓栫晫椤甸潰锛屾祴璇曞彲鑳戒笉鍑嗙‘")
    
    # 瑙﹀彂閫€鍑哄璇濇
    print("\n[姝ラ 2] 瑙﹀彂閫€鍑哄璇濇...")
    keyevent(4)
    time.sleep(1)
    
    img = screencap()
    if img is None:
        print("  [澶辫触] 鎴浘澶辫触")
        return False
    
    result = analyzer.analyze(img)
    print(f"  褰撳墠椤甸潰锛歿result['page_type']} (缃俊搴?{result['confidence']:.2f})")
    
    # 灏濊瘯鐐瑰嚮鍙栨秷鎸夐挳
    print("\n[姝ラ 3] 灏濊瘯鍏抽棴瀵硅瘽妗?..")
    tap(600, 750)
    time.sleep(1.5)
    
    img = screencap()
    if img is None:
        print("  [澶辫触] 鎴浘澶辫触")
        return False
    
    result = analyzer.analyze(img)
    print(f"  褰撳墠椤甸潰锛歿result['page_type']} (缃俊搴?{result['confidence']:.2f})")
    
    if result['page_type'] == "world":
        print("  [鎴愬姛] 瀵硅瘽妗嗗凡鍏抽棴锛屽洖鍒颁笘鐣岄〉闈?)
        return True
    else:
        print("  [澶辫触] 瀵硅瘽妗嗘湭鍏抽棴鎴栭〉闈㈣瘑鍒敊璇?)
        return False


def main():
    print("\n" + "="*70)
    print("鏍囧噯娴佷慨澶嶉獙璇?)
    print("="*70)
    
    results = {}
    
    # 娴嬭瘯 1: 椤甸潰鍒嗘瀽鍣?    results['page_analyzer'] = test_page_analyzer()
    
    # 娴嬭瘯 2: 閫€鍑哄璇濇澶勭悊
    results['exit_dialog'] = test_exit_dialog_handling()
    
    # 鎬荤粨
    print("\n" + "="*70)
    print("楠岃瘉鎬荤粨")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "鉁?閫氳繃" if passed else "鉂?澶辫触"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[缁撹] 鎵€鏈夋祴璇曢€氳繃锛屾爣鍑嗘祦淇鏈夋晥")
        return 0
    else:
        print("\n[缁撹] 閮ㄥ垎娴嬭瘯澶辫触锛岄渶瑕佽繘涓€姝ヨ皟璇?)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[閿欒] 楠岃瘉澶辫触锛歿e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

