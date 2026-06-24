#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鏂拌瘑鍒柟娉曟祴璇曡剼鏈?
闂锛氶噾鑹插厓绱犺鏁版棤娉曞尯鍒嗕笘鐣岄〉闈㈠拰浠诲姟闈㈡澘锛堥兘鏄?26-27 涓級
瑙ｅ喅锛氫娇鐢?MaaEnd 寮忓婧愯瀺鍚堣瘑鍒?
娴嬭瘯鍐呭锛?1. 妯℃澘鍖归厤璇嗗埆椤甸潰鐗瑰緛鍥炬爣
2. OCR 璇嗗埆椤甸潰鏍囬鏂囨湰
3. 棰滆壊鍖归厤璇嗗埆鐗瑰畾鍖哄煙
"""

import cv2
import numpy as np
import subprocess
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
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


def template_match(img, template_path, roi=None, threshold=0.8):
    """
    妯℃澘鍖归厤
    
    Args:
        img: 婧愬浘鍍?        template_path: 妯℃澘璺緞
        roi: [x, y, w, h] 鎼滅储鍖哄煙
        threshold: 鍖归厤闃堝€?        
    Returns:
        (鏄惁鍖归厤锛屼綅缃紝缃俊搴?
    """
    template = cv2.imread(str(template_path))
    if template is None:
        return False, None, 0
    
    if roi:
        x, y, w, h = roi
        search_img = img[y:y+h, x:x+w]
    else:
        search_img = img
        x, y = 0, 0
    
    result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
    max_val = np.max(result)
    max_loc = np.unravel_index(np.argmax(result), result.shape)
    
    if max_val >= threshold:
        location = (x + max_loc[1], y + max_loc[0])
        return True, location, float(max_val)
    
    return False, None, float(max_val)


def detect_region_color(img, roi, lower_hsv, upper_hsv):
    """
    妫€娴嬪尯鍩熼鑹?    
    Args:
        img: 婧愬浘鍍?        roi: [x, y, w, h]
        lower_hsv: HSV 涓嬮檺 [h, s, v]
        upper_hsv: HSV 涓婇檺 [h, s, v]
        
    Returns:
        鍖归厤鍍忕礌鏁?    """
    x, y, w, h = roi
    crop = img[y:y+h, x:x+w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
    return int(np.count_nonzero(mask))


def analyze_page_features(img):
    """
    鍒嗘瀽椤甸潰鐗瑰緛锛堜笉浣跨敤閲戣壊鍏冪礌璁℃暟锛?    
    鐗瑰緛锛?    1. 宸︿笂瑙掑尯鍩熶寒搴︼紙鑿滃崟椤甸潰閫氬父鏈夋殫鑹茶儗鏅級
    2. 鍙充笂瑙掕祫婧愬浘鏍囧尯鍩熼鑹插垎甯?    3. 搴曢儴瀵艰埅鏍忓尯鍩熺壒寰?    4. 涓ぎ鍖哄煙鏂囨湰瀵嗗害
    """
    h, w = img.shape[:2]
    
    features = {}
    
    # 1. 宸︿笂瑙?200x200 鍖哄煙骞冲潎浜害
    top_left = img[0:200, 0:200]
    features['top_left_brightness'] = top_left.mean()
    
    # 2. 鍙充笂瑙掕祫婧愬尯鍩燂紙閫氬父鏈夌豢鑹?榛勮壊璧勬簮鍥炬爣锛?    top_right = img[0:100, w-400:w]
    hsv_tr = cv2.cvtColor(top_right, cv2.COLOR_BGR2HSV)
    
    # 缁胯壊鍍忕礌锛堣祫婧愬浘鏍囷級
    green_mask = cv2.inRange(hsv_tr, np.array([40, 50, 50]), np.array([80, 255, 200]))
    features['green_pixels_top_right'] = int(np.count_nonzero(green_mask))
    
    # 榛勮壊鍍忕礌
    yellow_mask = cv2.inRange(hsv_tr, np.array([20, 100, 100]), np.array([35, 255, 255]))
    features['yellow_pixels_top_right'] = int(np.count_nonzero(yellow_mask))
    
    # 3. 搴曢儴瀵艰埅鏍忓尯鍩燂紙1080 楂樺害鐨?70%-100%锛?    bottom_nav = img[int(h*0.7):h, int(w*0.3):int(w*0.7)]
    features['bottom_nav_brightness'] = bottom_nav.mean()
    
    # 4. 涓ぎ鍖哄煙杈圭紭妫€娴嬶紙UI 鍏冪礌瀵嗗害锛?    center = img[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
    gray = cv2.cvtColor(center, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    features['center_edge_density'] = int(np.count_nonzero(edges)) / edges.size * 100
    
    # 5. 宸︿晶杈规爮鍖哄煙锛堣彍鍗曢〉闈㈤€氬父鏈夊乏渚у鑸級
    left_bar = img[int(h*0.1):int(h*0.9), 0:int(w*0.15)]
    features['left_bar_brightness'] = left_bar.mean()
    
    return features


def classify_page_v2(features):
    """
    V2 椤甸潰鍒嗙被锛堝熀浜庡鐗瑰緛锛?    
    鏍规嵁瀹為檯閲囬泦鏁版嵁鏍″噯鐨勮鍒欙細
    - 浠诲姟闈㈡澘锛歭eft_bar_brightness > 120 AND green_pixels < 30
    - 涓栫晫椤甸潰锛歡reen_pixels > 100 OR left_bar_brightness < 80
    - 閫€鍑哄璇濇锛氬緟杩涗竴姝ュ垎鏋?    """
    f = features
    
    # 瑙勫垯 1: 浠诲姟闈㈡澘锛堝乏渚т寒杈规爮 + 杈冨皯缁胯壊鍍忕礌锛?    if f['left_bar_brightness'] > 120 and f['green_pixels_top_right'] < 30:
        return "quest_panel", 0.9
    
    # 瑙勫垯 2: 涓栫晫椤甸潰锛堣緝澶氱豢鑹茶祫婧愬浘鏍?鎴?宸︿晶杈规爮鏆楋級
    if f['green_pixels_top_right'] > 100 or f['left_bar_brightness'] < 80:
        return "world", 0.8
    
    # 瑙勫垯 3: 閫€鍑哄璇濇锛堥渶瑕佹洿澶氱壒寰侊級
    # 鏆傛椂鐢ㄦ帓闄ゆ硶
    return "unknown", 0.3


def main():
    print("\n" + "="*70)
    print("鏂拌瘑鍒柟娉曟祴璇?)
    print("="*70)
    
    # 閲囬泦涓嶅悓椤甸潰鏍锋湰
    pages = {
        "world": [],
        "quest_panel": [],
        "exit_dialog": [],
    }
    
    # 1. 閲囬泦涓栫晫椤甸潰
    print("\n[1] 閲囬泦涓栫晫椤甸潰鏍锋湰...")
    for i in range(3):
        # 鎸夎繑鍥為敭纭繚鍦ㄤ笘鐣?        for _ in range(5):
            keyevent(4)
            time.sleep(0.3)
        time.sleep(1)
        
        img = screencap()
        if img is None:
            continue
        
        features = analyze_page_features(img)
        page_type, confidence = classify_page_v2(features)
        
        print(f"  鏍锋湰 {i+1}: {page_type} (缃俊搴?{confidence:.2f})")
        print(f"    鐗瑰緛锛歿features}")
        
        pages["world"].append(features)
        
        # 淇濆瓨鏍锋湰
        cv2.imwrite(str(PROJECT / f'cache/test_recognition/world_{i+1}.png'), img)
        time.sleep(0.5)
    
    # 2. 閲囬泦浠诲姟闈㈡澘
    print("\n[2] 閲囬泦浠诲姟闈㈡澘鏍锋湰...")
    tap(860, 80)  # 浠诲姟鍥炬爣
    time.sleep(2)
    
    for i in range(3):
        img = screencap()
        if img is None:
            continue
        
        features = analyze_page_features(img)
        page_type, confidence = classify_page_v2(features)
        
        print(f"  鏍锋湰 {i+1}: {page_type} (缃俊搴?{confidence:.2f})")
        print(f"    鐗瑰緛锛歿features}")
        
        pages["quest_panel"].append(features)
        
        cv2.imwrite(str(PROJECT / f'cache/test_recognition/quest_{i+1}.png'), img)
        time.sleep(0.5)
    
    # 杩斿洖涓栫晫
    for _ in range(3):
        keyevent(4)
        time.sleep(0.3)
    
    # 3. 閲囬泦閫€鍑哄璇濇
    print("\n[3] 閲囬泦閫€鍑哄璇濇鏍锋湰...")
    keyevent(4)  # 瑙﹀彂閫€鍑哄璇濇
    time.sleep(1)
    
    for i in range(3):
        img = screencap()
        if img is None:
            continue
        
        features = analyze_page_features(img)
        page_type, confidence = classify_page_v2(features)
        
        print(f"  鏍锋湰 {i+1}: {page_type} (缃俊搴?{confidence:.2f})")
        print(f"    鐗瑰緛锛歿features}")
        
        pages["exit_dialog"].append(features)
        
        cv2.imwrite(str(PROJECT / f'cache/test_recognition/dialog_{i+1}.png'), img)
        
        # 鍏抽棴瀵硅瘽妗嗭紙鎸夎繑鍥炴垨鐐瑰嚮鍙栨秷锛?        keyevent(4)
        time.sleep(0.5)
    
    # 缁熻鍒嗘瀽
    print("\n" + "="*70)
    print("鐗瑰緛缁熻")
    print("="*70)
    
    for page_name, samples in pages.items():
        if not samples:
            continue
        
        print(f"\n{page_name}:")
        for feature, values in samples[0].items():
            all_values = [s[feature] for s in samples]
            print(f"  {feature}: min={min(all_values):.1f} max={max(all_values):.1f} avg={sum(all_values)/len(all_values):.1f}")
    
    # 淇濆瓨鐗瑰緛鏁版嵁
    import json
    cache_dir = PROJECT / 'cache' / 'test_recognition'
    cache_dir.mkdir(exist_ok=True)
    
    with open(cache_dir / 'features.json', 'w', encoding='utf-8') as f:
        json.dump({
            name: samples 
            for name, samples in pages.items() if samples
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n[淇濆瓨] 鐗瑰緛鏁版嵁锛歿cache_dir / 'features.json'}")
    print(f"[淇濆瓨] 鍥惧儚鏍锋湰锛歿cache_dir}/")
    
    print("\n[缁撹] 璇锋牴鎹笂杩扮壒寰佺粺璁℃暟鎹紝璋冩暣 classify_page_v2 鐨勫垎绫昏鍒?)


if __name__ == "__main__":
    main()

