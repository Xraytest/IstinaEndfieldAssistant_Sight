#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""淇 state_recovery.py - 鏇挎崲涓嶅瓨鍦ㄧ殑 press_key 璋冪敤"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\state_recovery\state_recovery.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 妫€鏌ユ槸鍚﹀凡淇
if '宸︿晶杈圭紭' in content or '0.05 * res' in content:
    print("鉁?_press_back 鏂规硶宸蹭慨澶?)
else:
    print("姝ｅ湪淇 _press_back 鏂规硶...")
    
    old_code = '''def _press_back(self) -> bool:
        """鎸夎繑鍥為敭"""
        try:
            if self.touch_executor:
                return self.touch_executor.execute_tool_call("press_key", {"key": "back"})
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"杩斿洖閿搷浣滃紓甯革細{e}")
            return False'''

    new_code = '''def _press_back(self) -> bool:
        """鐐瑰嚮灞忓箷宸︿晶杈圭紭妯℃嫙杩斿洖锛圱ouchManager 涓嶆敮鎸?press_key锛?""
        try:
            if self.touch_executor:
                res = self.touch_executor.get_resolution()
                # 鐐瑰嚮灞忓箷宸︿晶 5% 鍖哄煙妯℃嫙杩斿洖鎵嬪娍
                if res != (0, 0):
                    x_px = int(0.05 * res[0])
                    y_px = int(0.5 * res[1])
                else:
                    x_px = 96  # 1920 * 0.05
                    y_px = 540  # 1080 * 0.5
                return self.touch_executor.execute_tool_call("click", {"x": x_px, "y": y_px})
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"鐐瑰嚮妯℃嫙杩斿洖鎿嶄綔寮傚父锛歿e}")
            return False'''

    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("鉁?淇瀹屾垚")
    else:
        print("鉁?鏈壘鍒拌鏇挎崲鐨勪唬鐮佸潡锛屽彲鑳芥牸寮忎笉涓€鑷?)
        # 灏濊瘯鏌ユ壘鏃т唬鐮?        if 'press_key' in content:
            print("  浣嗘枃浠朵腑浠嶅寘鍚?press_key 寮曠敤")
            idx = content.find('press_key')
            print(f"  浣嶇疆锛歿idx}")
            print(f"  涓婁笅鏂囷細{content[max(0,idx-50):idx+100]}")

print("\n妫€鏌ヤ慨澶嶇粨鏋?..")
with open(file_path, 'r', encoding='utf-8') as f:
    new_content = f.read()
    
if '宸︿晶杈圭紭' in new_content:
    print("鉁?纭淇鎴愬姛")
elif 'press_key' not in new_content:
    print("鉁?press_key 宸茬Щ闄?)
else:
    print("鉁?淇鍙兘鏈畬鎴?)

