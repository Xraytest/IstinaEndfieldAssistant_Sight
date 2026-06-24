#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""淇 state_recovery.py - BUG-016: detect() 浼?None 闂"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\state_recovery\state_recovery.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 鏇挎崲浼?None 鐨勯€昏緫
old_code = '''if state_detector:
                # 浣跨敤 state_detector 鐨勯粯璁ゆ娴嬫柟寮?
                new_state = state_detector.detect(None, device_serial)'''

new_code = '''if state_detector:
                # 淇 BUG-016: 閫氳繃 touch_executor 鑾峰彇鎴浘锛岃€屼笉鏄紶 None
                if hasattr(self.touch_executor, 'screencap'):
                    screenshot = self.touch_executor.screencap()
                    if screenshot is not None:
                        # 浣跨敤 lambda 鍖呰鎴浘鏁版嵁浠ュ尮閰?detect() 绛惧悕
                        new_state = state_detector.detect(lambda ds: screenshot, device_serial)
                    else:
                        new_state = current_state  # 鎴浘澶辫触锛屽亣璁剧姸鎬佹湭鏀瑰彉
                else:
                    new_state = "unknown"  # 涓嶆敮鎸?screencap'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("鉁?宸蹭慨澶?BUG-016: detect() 浼?None 闂")
else:
    print("鉁?鏈壘鍒拌鏇挎崲鐨勪唬鐮佸潡")

# 楠岃瘉
with open(file_path, 'r', encoding='utf-8') as f:
    new_content = f.read()

if 'lambda ds: screenshot' in new_content:
    print("鉁?楠岃瘉鎴愬姛锛歞etect() 鐜板湪鎺ユ敹鏈夋晥鐨?screen_capture")
else:
    print("鉁?楠岃瘉澶辫触")

