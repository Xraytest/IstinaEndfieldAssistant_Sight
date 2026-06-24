#!/usr/bin/env python
"""修复 state_recovery.py - 替换不存在的 press_key 调用"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\state_recovery\state_recovery.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 检查是否已修复
if '左侧边缘' in content or '0.05 * res' in content:
    print("✓ _press_back 方法已修复")
else:
    print("正在修复 _press_back 方法...")
    
    old_code = '''def _press_back(self) -> bool:
        """按返回键"""
        try:
            if self.touch_executor:
                return self.touch_executor.execute_tool_call("press_key", {"key": "back"})
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"返回键操作异常：{e}")
            return False'''

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
                return self.touch_executor.execute_tool_call("click", {"x": x_px, "y": y_px})
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"点击模拟返回操作异常：{e}")
            return False'''

    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✓ 修复完成")
    else:
        print("✗ 未找到要替换的代码块，可能格式不一致")
        # 尝试查找旧代码
        if 'press_key' in content:
            print("  但文件中仍包含 press_key 引用")
            idx = content.find('press_key')
            print(f"  位置：{idx}")
            print(f"  上下文：{content[max(0,idx-50):idx+100]}")

print("\n检查修复结果...")
with open(file_path, 'r', encoding='utf-8') as f:
    new_content = f.read()
    
if '左侧边缘' in new_content:
    print("✓ 确认修复成功")
elif 'press_key' not in new_content:
    print("✓ press_key 已移除")
else:
    print("✗ 修复可能未完成")
