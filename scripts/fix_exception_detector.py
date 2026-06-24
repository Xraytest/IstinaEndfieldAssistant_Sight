#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""淇 exception_detector.py - 娣诲姞 error_counters 閫掑閫昏緫"""

file_path = r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\src\core\service\cloud\managers\exception_detector.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 鏌ユ壘骞舵浛鎹?
old_code = '''            if matches:
                return {
                    "type": error_type,'''

new_code = '''            if matches:
                # 鏂板锛氶€掑閿欒璁℃暟鍣?
                self.error_counters[error_type] += 1
                return {
                    "type": error_type,'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("鉁?宸叉坊鍔?error_counters 閫掑閫昏緫")
else:
    print("鉁?鏈壘鍒拌鏇挎崲鐨勪唬鐮佸潡")

# 楠岃瘉
with open(file_path, 'r', encoding='utf-8') as f:
    new_content = f.read()

if 'error_counters[error_type] += 1' in new_content:
    print("鉁?楠岃瘉鎴愬姛锛氳鏁板櫒閫掑宸叉坊鍔?)
else:
    print("鉁?楠岃瘉澶辫触")

