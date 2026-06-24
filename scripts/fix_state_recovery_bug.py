#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""淇 state_recovery.py _press_back 涓己澶辩殑 res 鍙橀噺瀹氫箟"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\state_recovery\state_recovery.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''def _press_back(self) -> bool:
        """鎸夎繑鍥為敭"""
        try:
            if self.touch_executor:
                return self.touch_executor.execute_tool_call("click", {"x": int(0.05 * res[0]), "y": int(0.5 * res[1])})'''

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
                return self.touch_executor.execute_tool_call("click", {"x": x_px, "y": y_px})'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("鉁?淇瀹屾垚锛氭坊鍔犱簡 res 鍙橀噺瀹氫箟")
else:
    print("鉁?鏈壘鍒拌鏇挎崲鐨勪唬鐮佸潡")
    # 妫€鏌ユ槸鍚﹀凡瀛樺湪姝ｇ‘鐨勪唬鐮?
    if "res = self.touch_executor.get_resolution()" in content and "_press_back" in content:
        print("  浣嗘枃浠朵技涔庡凡鏈夌浉鍏充唬鐮侊紝闇€瑕佹墜鍔ㄦ鏌?)

