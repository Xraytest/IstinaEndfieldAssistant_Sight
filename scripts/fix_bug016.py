#!/usr/bin/env python
"""修复 state_recovery.py - BUG-016: detect() 传 None 问题"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\state_recovery\state_recovery.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换传 None 的逻辑
old_code = '''if state_detector:
                # 使用 state_detector 的默认检测方式
                new_state = state_detector.detect(None, device_serial)'''

new_code = '''if state_detector:
                # 修复 BUG-016: 通过 touch_executor 获取截图，而不是传 None
                if hasattr(self.touch_executor, 'screencap'):
                    screenshot = self.touch_executor.screencap()
                    if screenshot is not None:
                        # 使用 lambda 包装截图数据以匹配 detect() 签名
                        new_state = state_detector.detect(lambda ds: screenshot, device_serial)
                    else:
                        new_state = current_state  # 截图失败，假设状态未改变
                else:
                    new_state = "unknown"  # 不支持 screencap'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ 已修复 BUG-016: detect() 传 None 问题")
else:
    print("✗ 未找到要替换的代码块")

# 验证
with open(file_path, 'r', encoding='utf-8') as f:
    new_content = f.read()

if 'lambda ds: screenshot' in new_content:
    print("✓ 验证成功：detect() 现在接收有效的 screen_capture")
else:
    print("✗ 验证失败")
