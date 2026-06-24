#!/usr/bin/env python3
"""
Qwen3.6 工具调用适配层 — 由于 Qwen3.6 不支持原生 tool_calling，
需要通过自定义格式解析实现。

工作机制：
1. 在 system prompt 中定义可用工具及其参数格式
2. Qwen3.6 以特定 XML/JSON 格式返回工具调用
3. 此适配层解析返回内容，提取工具调用并执行
4. 执行结果重新注入对话上下文

工具列表：
- tap(x, y) - 点击坐标
- swipe(x1,y1,x2,y2,duration) - 滑动
- screenshot() -> base64 - 截图
- ocr() -> list - OCR 识别
- wait(seconds) - 等待
- navigate(target) - 导航到目标页面
- collect_entity(name) - 采集实体图像
"""

import json, re, time, base64, os, subprocess
from typing import Dict, List, Any, Optional, Callable

# ── 工具定义 ───────────────────────────────────────────────────

TOOL_DEFINITIONS = {
    "tap": {
        "description": "点击屏幕指定位置",
        "params": {"x": "int (0-1280)", "y": "int (0-720)"},
        "examples": '{"action":"tap","x":640,"y":360}',
    },
    "swipe": {
        "description": "滑动",
        "params": {"x1": "int", "y1": "int", "x2": "int", "y2": "int", "duration_ms": "int"},
        'examples': '{"action":"swipe","x1":500,"y1":300,"x2":500,"y2":600,"duration_ms":500}',
    },
    "screenshot": {
        "description": "截图并返回base64编码",
        "params": {},
        "examples": '{"action":"screenshot"}',
    },
    "ocr": {
        "description": "OCR识别当前屏幕文字",
        "params": {},
        "examples": '{"action":"ocr"}',
    },
    "wait": {
        "description": "等待指定秒数",
        "params": {"seconds": "float"},
        "examples": '{"action":"wait","seconds":3.0}',
    },
    "navigate": {
        "description": "导航到指定游戏页面",
        "params": {"target": "str: exploration/industry/event_center/signin/dungeon/combat/encyclopedia"},
        "examples": '{"action":"navigate","target":"event_center"}',
    },
    "collect": {
        "description": "采集当前画面中的实体图像",
        "params": {
            "entity_name": "str: 实体名称",
            "variation": "str: normal/combat/skill/damaged/idle",
            "angle": "str: front/side/back/top",
        },
        "examples": '{"action":"collect","entity_name":"surge_tower","variation":"idle","angle":"front"}',
    },
    "move": {
        "description": "移动角色到指定方向",
        "params": {"direction": "str: forward/left/right/back/forward_left/forward_right/back_left/back_right"},
        "examples": '{"action":"move","direction":"forward"}',
    },
    "analyze_screen": {
        "description": "用视觉模型分析当前画面内容",
        "params": {"question": "str: 分析问题"},
        "examples": '{"action":"analyze_screen","question":"画面中有哪些敌人？"}',
    },
}

TOOL_SYSTEM_PROMPT = f"""你是 IEA 游戏实体采集助手。你可以使用以下工具与环境交互：

可用工具（以 JSON 格式返回，每行一个动作，支持多个动作顺序执行）：

{json.dumps(TOOL_DEFINITIONS, ensure_ascii=False, indent=2)}

返回格式要求：
1. 每个动作单独一行 JSON
2. 多个动作按执行顺序排列
3. 先思考后输出动作
4. 动作行以 >>> 开头

示例：
我想知道当前画面有什么
>>> {{"action":"screenshot"}}
>>> {{"action":"analyze_screen","question":"描述画面内容"}}

我要移动到敌人面前攻击
>>> {{"action":"move","direction":"forward"}}
>>> {{"action":"move","direction":"forward"}}
>>> {{"action":"wait","seconds":2}}
>>> {{"action":"screenshot"}}
>>> {{"action":"analyze_screen","question":"敌人位置在哪里？"}}
"""


# ── 动作解析器 ───────────────────────────────────────────────

class QwenToolExecutor:
    """解析 Qwen3.6 输出中的工具调用并执行"""

    def __init__(self, tool_impls: Dict[str, Callable] = None):
        self.tool_impls = tool_impls or {}
        self.execution_log = []

    def register_tool(self, name: str, impl: Callable):
        self.tool_impls[name] = impl

    def parse_actions(self, qwen_response: str) -> List[Dict]:
        """从 Qwen 回复中解析动作列表"""
        actions = []

        # 模式1: >>> {"action":"..."} 格式（推荐）
        for line in qwen_response.split('\n'):
            line = line.strip()
            if line.startswith('>>>'):
                line = line[3:].strip()
                try:
                    action = json.loads(line)
                    if isinstance(action, dict) and 'action' in action:
                        actions.append(action)
                except json.JSONDecodeError:
                    continue

        # 模式2: 独立 JSON 行
        if not actions:
            for line in qwen_response.split('\n'):
                line = line.strip()
                try:
                    action = json.loads(line)
                    if isinstance(action, dict) and 'action' in action:
                        actions.append(action)
                except json.JSONDecodeError:
                    continue

        return actions

    def execute_action(self, action: Dict) -> Dict:
        """执行单个动作"""
        action_type = action.get('action', '')
        params = {k: v for k, v in action.items() if k != 'action'}

        impl = self.tool_impls.get(action_type)
        if impl:
            try:
                result = impl(**params)
                self.execution_log.append({
                    'action': action_type,
                    'params': params,
                    'success': True,
                    'result': str(result)[:500],
                })
                return {'success': True, 'result': result}
            except Exception as e:
                self.execution_log.append({
                    'action': action_type,
                    'params': params,
                    'success': False,
                    'error': str(e),
                })
                return {'success': False, 'error': str(e)}
        else:
            return {'success': False, 'error': f'Unknown tool: {action_type}'}

    def execute_actions(self, actions: List[Dict]) -> List[Dict]:
        """顺序执行多个动作"""
        results = []
        for action in actions:
            result = self.execute_action(action)
            results.append(result)
            if not result['success']:
                break
        return results

    def build_feedback(self, results: List[Dict]) -> str:
        """构建执行反馈回 Qwen"""
        feedback_parts = []
        for i, (action, result) in enumerate(zip(
            [a for r in results for a in [r]], results
        )):
            status = "SUCCESS" if result['success'] else "FAILED"
            feedback_parts.append(
                f"Step {i+1}: {json.dumps(action)} → {status}"
            )
        return '\n'.join(feedback_parts)


# ── 实体采集管线 ─────────────────────────────────────────────

ENTITY_COLLECTOR_PROMPT = """你是 IEA 游戏实体图像采集专家。

任务：在《明日方舟：终末地》中，为指定实体收集多角度、多形态的训练图像。

当前目标实体：{entity_name}
已有此实体图像：{existing_count} 张
目标：1000 张

采集策略：
1. 先确认当前所在位置
2. 前往该实体可能出现的地点（副本、野外、据点）
3. 从不同角度（正面、侧面、背面、俯视）拍摄
4. 在不同状态（待机、移动、攻击、技能、受击）下拍摄
5. 在不同光照（白天、夜晚、技能特效）下拍摄

注意：
- 每张截图后立即保存并分析
- 确保角度差异足够大（相似度 > 30% 才保留）
- 避免重复采集相同角度
- 如果当前区域没有目标实体，尝试导航到其他区域

请一步步执行，每次返回 1-5 个动作。
"""


# ── 主循环 ─────────────────────────────────────────────────────

class EntityCollectionPipeline:
    """自主实体采集管线"""

    def __init__(self, executor: QwenToolExecutor, qwen_api_func: Callable):
        self.executor = executor
        self.qwen = qwen_api_func
        self.collected = {}  # entity_name -> [file_paths]
        self.session_log = []

    def collect_entity(self, entity_name: str, target_count: int = 1000):
        """为指定实体采集图像直到目标数量"""
        existing = self.collected.get(entity_name, [])
        print(f"\n=== 开始采集 [{entity_name}] {len(existing)}/{target_count} ===")

        while len(existing) < target_count:
            # 让 Qwen 决定下一步动作
            prompt = ENTITY_COLLECTOR_PROMPT.format(
                entity_name=entity_name,
                existing_count=len(existing),
            )

            # 添加上次执行反馈
            if self.session_log:
                recent = self.session_log[-5:]
                prompt += "\n\n最近执行记录：\n" + '\n'.join(recent)

            response = self.qwen(prompt)
            actions = self.executor.parse_actions(response)

            if not actions:
                print(f"  Qwen 未返回有效动作，等待后重试")
                time.sleep(3)
                continue

            results = self.executor.execute_actions(actions)
            feedback = self.executor.build_feedback(
                list(zip(actions, results))
            )
            self.session_log.append(feedback)

            # 检查是否有截图被保存
            for action, result in zip(actions, results):
                if action.get('action') == 'collect' and result.get('success'):
                    existing = self.collected.get(entity_name, [])
                    print(f"  Progress: {len(existing)}/{target_count}")

        print(f"=== [{entity_name}] 采集完成: {len(existing)} 张 ===")
