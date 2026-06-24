#!/usr/bin/env python
"""修复 exception_detector.py - 添加 error_counters 递增逻辑"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\cloud\managers\exception_detector.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找并替换
old_code = '''            if matches:
                return {
                    "type": error_type,'''

new_code = '''            if matches:
                # 新增：递增错误计数器
                self.error_counters[error_type] += 1
                return {
                    "type": error_type,'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ 已添加 error_counters 递增逻辑")
else:
    print("✗ 未找到要替换的代码块")

# 验证
with open(file_path, 'r', encoding='utf-8') as f:
    new_content = f.read()

if 'error_counters[error_type] += 1' in new_content:
    print("✓ 验证成功：计数器递增已添加")
else:
    print("✗ 验证失败")
