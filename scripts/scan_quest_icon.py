#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""鎵弿瀵艰埅鏍忎换鍔″浘鏍囩簿纭綅缃?(鍍忕礌宸紓娉?"""
import sys, os, time, cv2, numpy as np, subprocess

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE

ADB_PATH = os.path.join(str(PROJECT_ROOT), "3rd-part", "adb", "adb.exe")
DEVICE = "localhost:16512"

def main():
    if not MAAFW_AVAILABLE:
        print("[ERROR] MaaFramework 涓嶅彲鐢?)
        return 1
    
    # 杩炴帴璁惧
    config = MaaFwTouchConfig(
        adb_path=ADB_PATH,
        address=DEVICE,
        screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
        input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
    )
    executor = MaaFwTouchExecutor(config)
    if not executor.connect():
        print("[ERROR] 杩炴帴澶辫触")
        return 1
    print(f"[OK] 宸茶繛鎺ワ紝鍒嗚鲸鐜囷細{executor.get_resolution()}")
    
    # 鍥炲埌涓讳笘鐣?    print("[鍓嶇疆] 鍥炲埌涓讳笘鐣?..")
    for _ in range(6):
        subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(0.3)
    time.sleep(2)
    
    # 鍩哄噯鎴浘
    print("[鍩哄噯] 鑾峰彇鍩哄噯鎴浘...")
    img_base = executor.screencap()
    if img_base is None:
        print("[ERROR] 鍩哄噯鎴浘澶辫触")
        executor.disconnect()
        return 1
    
    # 宸茬煡 quest_icon 澶ц嚧浣嶇疆 (MaaFw 1280x720 绌洪棿)
    # flows_config.json 涓槸 [855, 33] ADB 鍧愭爣 鈫?MaaFw 鍧愭爣绾?[570, 22]
    # 浣嗗疄闄呮父鎴忓鑸爮鍦ㄩ《閮紝y 搴旇鍦?30-70 涔嬮棿
    x_base = 570  # 855 / 1.5
    y_positions = [25, 28, 30, 32, 33, 35, 38, 40, 45, 50, 55, 60]
    
    print(f"\n[鎵弿] 鎵弿浠诲姟鍥炬爣浣嶇疆 (x={x_base}, y={y_positions})")
    print("=" * 60)
    
    results = []
    for y in y_positions:
        # 鐐瑰嚮
        executor.click(x_base, y)
        time.sleep(2.5)
        
        # 鎴浘
        img = executor.screencap()
        if img is None:
            print(f"y={y:3d}: 鎴浘澶辫触")
            continue
        
        # 鍍忕礌宸紓鍒嗘瀽
        diff = cv2.absdiff(img_base, img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        
        # 涓ぎ闈㈡澘鍖哄煙 (y:80-650, x:100-1180)
        center_changed = cv2.countNonZero(thresh[80:650, 100:1180])
        # 瀵艰埅鏍忓尯鍩?(y:35-75, x:640-1000)
        nav_changed = cv2.countNonZero(thresh[35:75, 640:1000])
        # 鍏ㄥ眬鍙樺寲鐜?        total_changed = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        change_rate = total_changed / total_pixels * 100
        
        results.append({
            'y': y,
            'center': center_changed,
            'nav': nav_changed,
            'rate': change_rate
        })
        
        status = "鉁? if center_changed > 100000 else ("鈿狅笍" if center_changed > 10000 else "鉂?)
        print(f"{status} y={y:3d}: center={center_changed:8d} px ({change_rate:5.1f}%)")
        
        # 鍏抽棴闈㈡澘 (鐐瑰嚮杩斿洖閿?
        subprocess.run([ADB_PATH, "-s", DEVICE, "shell", "input", "keyevent", "4"], capture_output=True)
        time.sleep(1.5)
    
    print("\n" + "=" * 60)
    if results:
        best = max(results, key=lambda r: r['center'])
        print(f"[鏈€浣砞 y={best['y']} (center={best['center']} px, rate={best['rate']:.1f}%)")
        
        # 杞崲涓?ADB 鍧愭爣
        adb_y = int(best['y'] * 1.5)
        print(f"[ADB] 鍧愭爣锛歔855, {adb_y}]")
        
        if best['center'] > 100000:
            print("[缁撹] 鉁?浠诲姟鍥炬爣浣嶇疆宸茬‘璁?)
        else:
            print("[缁撹] 鉂?鏈壘鍒版湁鏁堜綅缃紝鍙兘闇€瑕佽皟鏁?x 鍧愭爣")
    
    executor.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())

