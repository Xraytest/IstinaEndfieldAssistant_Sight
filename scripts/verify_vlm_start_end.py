#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
楠岃瘉 Stop hook 鏉′欢锛氫慨姝ｆ祦绋嬶紝涓€涓涓虹殑璧锋湯鐢?vlm 鍒ゅ畾
"""

import json
import sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def verify_stop_hook():
    print('='*70)
    print('Stop hook 鏉′欢楠岃瘉锛氫慨姝ｆ祦绋嬶紝涓€涓涓虹殑璧锋湯鐢?vlm 鍒ゅ畾')
    print('='*70)
    
    # 1. 楠岃瘉閰嶇疆
    config_path = PROJECT_ROOT / 'config' / 'standard_flows' / 'flows_config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    vlm_both_count = 0
    vlm_steps = []
    
    for flow_name, flow_cfg in config['flows'].items():
        if not flow_cfg.get('enabled', True):
            continue
        for step in flow_cfg['steps']:
            if step.get('action') == 'tap':
                has_start = step.get('vlm_confirm', False)
                has_end = step.get('vlm_verify', False)
                if has_start and has_end:
                    vlm_both_count += 1
                    vlm_steps.append(f"{flow_name}.{step.get('id')}")
    
    print(f'\n[閰嶇疆缁熻]')
    print(f'  璧锋湯鍙屽垽瀹氾細{vlm_both_count} 涓?tap 姝ラ')
    if vlm_steps:
        for step in vlm_steps:
            print(f'    - {step}')
    
    # 2. 楠岃瘉寮曟搸鏂规硶
    # 鐩存帴妫€鏌ユ枃浠跺唴瀹?    engine_file = PROJECT_ROOT / 'scripts' / 'standard_flow_engine.py'
    with open(engine_file, 'r', encoding='utf-8') as f:
        engine_content = f.read()
    
    has_confirm = '_vlm_confirm_target' in engine_content
    has_verify = '_vlm_verify_result' in engine_content
    
    print(f'\n[寮曟搸鏂规硶]')
    print(f'  _vlm_confirm_target (琛屼负璧峰鍒ゅ畾): {"鉁? if has_confirm else "鉂?}')
    print(f'  _vlm_verify_result (琛屼负缁撴潫鍒ゅ畾): {"鉁? if has_verify else "鉂?}')
    
    # 3. 楠岃瘉 VLM 鍐崇瓥鍣?    vlm_file = PROJECT_ROOT / 'src' / 'core' / 'gui_client.py'
    with open(vlm_file, 'r', encoding='utf-8') as f:
        vlm_content = f.read()

    has_decide = 'def decide_action(self' in vlm_content

    print(f'\n[VLM 鍐崇瓥鍣╙')
    print(f'  decide_action() 鏂规硶锛歿"鉁? if has_decide else "鉂?}')
    
    # 4. 鎬荤粨
    print(f'\n{"="*70}')
    all_ok = vlm_both_count > 0 and has_confirm and has_verify and has_decide
    
    if all_ok:
        print('鉁?Stop hook 鏉′欢宸茶揪鎴?)
        print(f'   - {vlm_both_count} 涓?tap 姝ラ閰嶇疆浜?VLM 璧锋湯鍙屽垽瀹?)
        print(f'   - 寮曟搸鏀寔琛屼负璧峰鍒ゅ畾 (_vlm_confirm_target)')
        print(f'   - 寮曟搸鏀寔琛屼负缁撴潫鍒ゅ畾 (_vlm_verify_result)')
        print(f'   - VLM 鍐崇瓥鍣ㄦ彁渚涚畝鍖栨帴鍙?(decide)')
    else:
        print('鉂?Stop hook 鏉′欢鏈畬鍏ㄨ揪鎴?)
        if vlm_both_count == 0:
            print('   - 缂哄皯 VLM 璧锋湯鍙屽垽瀹氱殑閰嶇疆')
        if not has_confirm:
            print('   - 缂哄皯琛屼负璧峰鍒ゅ畾鏂规硶')
        if not has_verify:
            print('   - 缂哄皯琛屼负缁撴潫鍒ゅ畾鏂规硶')
        if not has_decide:
            print('   - 缂哄皯 VLM 绠€鍖栨帴鍙?)
    
    print('='*70)
    return all_ok

if __name__ == '__main__':
    success = verify_stop_hook()
    sys.exit(0 if success else 1)

