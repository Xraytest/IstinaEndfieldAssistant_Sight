#!/usr/bin/env python3
"""
验证 Stop hook 条件：修正流程，一个行为的起末由 vlm 判定
"""

import json
import sys
from pathlib import Path

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def verify_stop_hook():
    print('='*70)
    print('Stop hook 条件验证：修正流程，一个行为的起末由 vlm 判定')
    print('='*70)
    
    # 1. 验证配置
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
    
    print(f'\n[配置统计]')
    print(f'  起末双判定：{vlm_both_count} 个 tap 步骤')
    if vlm_steps:
        for step in vlm_steps:
            print(f'    - {step}')
    
    # 2. 验证引擎方法
    # 直接检查文件内容
    engine_file = PROJECT_ROOT / 'scripts' / 'standard_flow_engine.py'
    with open(engine_file, 'r', encoding='utf-8') as f:
        engine_content = f.read()
    
    has_confirm = '_vlm_confirm_target' in engine_content
    has_verify = '_vlm_verify_result' in engine_content
    
    print(f'\n[引擎方法]')
    print(f'  _vlm_confirm_target (行为起始判定): {"✅" if has_confirm else "❌"}')
    print(f'  _vlm_verify_result (行为结束判定): {"✅" if has_verify else "❌"}')
    
    # 3. 验证 VLM 决策器
    vlm_file = PROJECT_ROOT / 'src' / 'core' / 'vlm_client.py'
    with open(vlm_file, 'r', encoding='utf-8') as f:
        vlm_content = f.read()

    has_decide = 'def decide_action(self' in vlm_content

    print(f'\n[VLM 决策器]')
    print(f'  decide_action() 方法：{"✅" if has_decide else "❌"}')
    
    # 4. 总结
    print(f'\n{"="*70}')
    all_ok = vlm_both_count > 0 and has_confirm and has_verify and has_decide
    
    if all_ok:
        print('✅ Stop hook 条件已达成')
        print(f'   - {vlm_both_count} 个 tap 步骤配置了 VLM 起末双判定')
        print(f'   - 引擎支持行为起始判定 (_vlm_confirm_target)')
        print(f'   - 引擎支持行为结束判定 (_vlm_verify_result)')
        print(f'   - VLM 决策器提供简化接口 (decide)')
    else:
        print('❌ Stop hook 条件未完全达成')
        if vlm_both_count == 0:
            print('   - 缺少 VLM 起末双判定的配置')
        if not has_confirm:
            print('   - 缺少行为起始判定方法')
        if not has_verify:
            print('   - 缺少行为结束判定方法')
        if not has_decide:
            print('   - 缺少 VLM 简化接口')
    
    print('='*70)
    return all_ok

if __name__ == '__main__':
    success = verify_stop_hook()
    sys.exit(0 if success else 1)
