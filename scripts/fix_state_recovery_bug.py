#!/usr/bin/env python
"""修复 state_recovery.py _press_back 中缺失的 res 变量定义"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\state_recovery\state_recovery.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''def _press_back(self) -> bool:
        """按返回键"""
        try:
            if self.touch_executor:
                return self.touch_executor.execute_tool_call("click", {"x": int(0.05 * res[0]), "y": int(0.5 * res[1])})'''

new_code = '''def _press_back(self) -> bool:
        """点击屏幕左侧边缘模拟返回（TouchManager 不支持 press_key）"""
        try:
            if self.touch_executor:
                res = self.touch_executor.get_resolution()
                # 点击屏幕左侧 5% 区域模拟返回手势
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
    print("✓ 修复完成：添加了 res 变量定义")
else:
    print("✗ 未找到要替换的代码块")
    # 检查是否已存在正确的代码
    if "res = self.touch_executor.get_resolution()" in content and "_press_back" in content:
        print("  但文件似乎已有相关代码，需要手动检查")
