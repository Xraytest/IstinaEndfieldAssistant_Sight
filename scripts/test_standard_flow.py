#!/usr/bin/env python3
"""
标准流测试 — 使用本地 2B 模型逐步骤执行游戏流程，记录过程并提交 Qwen3.5-Max 分析

流程:
  1. detect_state → 2. navigate → 3. interact → 4. verify → 5. record
  每步截图保存，最终打包发送视觉智能体评估

用法:
  python scripts/test_standard_flow.py                    # 完整测试
  python scripts/test_standard_flow.py --steps daily      # 仅测试每日签到
  python scripts/test_standard_flow.py --steps explore    # 仅测试场景探索
  python scripts/test_standard_flow.py --analyze-only     # 仅分析已有记录
"""

import sys, os, json, time, base64, hashlib, re, io, argparse
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from _path_setup import ensure_path; ensure_path()
sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))  # 本地安装的包

# ── 导入本地模块 ──
from core.capability.adb_utils import ADB, vlm_analyze, VLMOptions, adb_screencap
from core.foundation.game_data import Coords, NAVIGATION_MAP


# ══════════════════════════════════════════════════════════════════
# 记录器 - 逐帧记录执行过程
# ══════════════════════════════════════════════════════════════════

@dataclass
class FlowStep:
    """流程单步记录"""
    step_id: int
    action: str            # 动作名
    description: str       # 描述
    prompt: str            # 发给模型的提示词
    decision: str          # 模型返回的决策
    screenshot_path: str   # 截图路径
    timestamp: float       # 时间戳
    success: bool = True   # 是否成功
    error: str = ""        # 错误信息


class FlowRecorder:
    """流程记录器 - 截图 + 元数据"""

    def __init__(self, session_name: str = "standard_flow"):
        self.session_name = session_name
        self.steps: List[FlowStep] = []
        self.session_dir = str(PROJECT_ROOT / "cache" / f"flow_{session_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(self.session_dir, exist_ok=True)
        print(f"[recorder] 会话目录: {self.session_dir}")

    def record_step(self, step_id: int, action: str, description: str,
                    prompt: str, decision: str, success: bool = True,
                    error: str = "") -> str:
        """记录单步: 截图 + 保存元数据"""
        img = adb_screencap()
        ts = time.time()
        h = hashlib.md5(img).hexdigest()[:8] if img else "none"
        fname = f"step_{step_id:03d}_{action}_{ts:.0f}_{h}.png"
        fpath = os.path.join(self.session_dir, fname)

        if img and len(img) > 100:
            with open(fpath, "wb") as f:
                f.write(img)
        else:
            fpath = ""

        step = FlowStep(
            step_id=step_id,
            action=action,
            description=description,
            prompt=prompt,
            decision=decision,
            screenshot_path=fpath,
            timestamp=ts,
            success=success,
            error=error,
        )
        self.steps.append(step)

        status = "OK" if success else "FAIL"
        print(f"  [{status}] step {step_id}: {action} - {description[:50]}")
        return fpath

    def export_report(self) -> Dict[str, Any]:
        """导出完整报告"""
        return {
            "session": self.session_name,
            "total_steps": len(self.steps),
            "success_count": sum(1 for s in self.steps if s.success),
            "fail_count": sum(1 for s in self.steps if not s.success),
            "duration_seconds": self.steps[-1].timestamp - self.steps[0].timestamp if len(self.steps) >= 2 else 0,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "description": s.description,
                    "prompt_preview": s.prompt[:200],
                    "decision_preview": s.decision[:200],
                    "screenshot": s.screenshot_path,
                    "success": s.success,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }

    def get_analysis_payload(self) -> List[Dict[str, Any]]:
        """生成发给视觉智能体的分析载荷 (截图b64 + 步骤描述)"""
        payload = []
        for s in self.steps:
            img_data = None
            if s.screenshot_path and os.path.exists(s.screenshot_path):
                with open(s.screenshot_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
            step_info = {
                "step": s.step_id,
                "action": s.action,
                "description": s.description,
                "prompt": s.prompt,
                "decision": s.decision,
                "success": s.success,
                "error": s.error,
                "screenshot_base64": img_data,
            }
            payload.append(step_info)
        return payload


# ══════════════════════════════════════════════════════════════════
# 标准流程定义
# ══════════════════════════════════════════════════════════════════

# 流步骤模板 - 每一步 = (action_name, description, prompt_template)
STANDARD_FLOWS = {
    "daily_signin": [
        ("detect_screen", "检测当前画面状态",
         "分析当前游戏画面。判断页面类型和关键UI元素位置。\n"
         "\n"
         "页面类型定义:\n"
         "- world_map: 主世界（有探索按钮、小地图、角色、任务指引）\n"
         "- main_menu: 主菜单（顶部有签到/活动/邮件等图标，无角色移动）\n"
         "- signin: 签到页面（有「签到」「寻奇探幽」「限时签到」等标题）\n"
         "- loading_screen: 加载界面（有NOW LOADING/进度条/TIPS）\n"
         "- exit_dialog: 退出确认弹窗（「是否退出游戏？」+「取消」「确认」按钮）\n"
         "- other: 其他\n"
         "\n"
         "特殊检测（优先级最高）:\n"
         "- 如果画面中央有「是否退出游戏？」弹窗，page_type 必须返回 \"exit_dialog\"\n"
         "- 如果画面有NOW LOADING/进度条，page_type 必须返回 \"loading_screen\"\n"
         "\n"
         "弹窗状态验证:\n"
         "- 检测到弹窗后，记录「取消」和「确认」按钮的精确坐标\n"
         "\n"
         "输出JSON（必须包含action字段，即使不执行任何操作也要返回action: \"none\"）:\n"
         '{"action": "none",\n'
         ' "page_type": "world_map|main_menu|signin|loading_screen|exit_dialog|other",\n'
         ' "exit_dialog_buttons": {"cancel": [x, y], "confirm": [x, y]},  // 仅exit_dialog时提供\n'
         ' "description": "一句话画面描述"}'),

        ("navigate_signin", "导航到签到页面",
         "智能导航到签到页面。\n"
         "\n"
         "【全局状态理解】\n"
         "这是5步流程的第2步。上一步(detect_screen)已经检测到页面状态。\n"
         "如果上一步检测到 exit_dialog，本步必须优先处理弹窗，然后继续导航。\n"
         "处理弹窗后，应基于新的页面状态决定下一步操作，而不是重复检测弹窗。\n"
         "\n"
         "页面类型定义:\n"
         "- world_map: 主世界（有探索按钮、小地图、角色）\n"
         "- main_menu: 主菜单（顶部有签到/活动/邮件等图标）\n"
         "- signin: 签到页面\n"
         "- loading_screen: 加载界面\n"
         "- exit_dialog: 退出确认弹窗\n"
         "\n"
         "导航策略（必须严格遵守顺序）:\n"
         "\n"
         "【步骤0】处理退出弹窗（仅当检测到exit_dialog时）\n"
         "如果当前页面是 exit_dialog：\n"
         "  1. 点击「取消」按钮（使用上一步提供的精确坐标）\n"
         "  2. 等待1秒后重新截图\n"
         "  3. 验证弹窗是否消失，如未消失则重试最多3次\n"
         "  4. 弹窗关闭后，更新 current_page 为实际页面（world_map/main_menu）\n"
         "\n"
         "【步骤1】从当前页面导航到签到页面\n"
         "- 如果已在 signin 页面：返回 {\"action\": \"none\", \"current_page\": \"signin\"}\n"
         "- 如果当前在 main_menu：扫描顶部栏寻找签到按钮，点击后验证是否进入signin\n"
         "- 如果当前在 world_map：必须先返回主菜单（点击左上角「探索」按钮约82,45或按ESC），\n"
         "  等待出现main_menu顶部栏后再寻找签到按钮\n"
         "- 如果当前是 loading_screen：等待加载完成\n"
         "\n"
         "输出JSON（纯JSON，必须包含所有字段）:\n"
         '{"action": "tap/back/none/dialog_close",\n'
         ' "target": "操作目标描述",\n'
         ' "coords": [x, y],\n'
         ' "current_page": "world_map|main_menu|signin|loading_screen|exit_dialog",\n'
         ' "need_return": false,  // 是否需要先返回主菜单（world_map时为true）\n'
         ' "found": false,\n'
         ' "retry_count": 0,  // 弹窗处理重试次数\n'
         ' "status": "success/failed/retrying",  // 操作状态\n'
         ' "error": "错误说明"}'),


        ("check_signin", "检查签到状态",
         "分析当前画面是否是签到页面。\n"
         "\n"
         "【前置条件验证 - 必须按顺序执行】\n"
         "\n"
         "1. 【弹窗检测 - 绝对优先】\n"
         "如果检测到「是否退出游戏？」弹窗（page_type=exit_dialog）：\n"
         "   - 这是前序步骤处理失败的标志\n"
         "   - 必须立即返回错误，禁止继续执行\n"
         "   - 返回格式: {\"is_signin_page\": false, \"error\": \"exit_dialog_unresolved\", \"status\": \"error\"}\n"
         "\n"
         "2. 【页面类型验证】\n"
         "仅当 current_page == \"main_menu\" 或 \"signin\" 时才执行此检查\n"
         "   - 如果 current_page == \"world_map\"：返回错误 {\"is_signin_page\": false, \"error\": \"need_return_to_main_menu\", \"status\": \"error\"}\n"
         "   - 如果 current_page == \"loading_screen\"：返回 {\"is_signin_page\": false, \"error\": \"loading_in_progress\", \"status\": \"waiting\"}\n"
         "\n"
         "【签到页面识别】\n"
         "签到页面特征（必须同时满足至少2项）:\n"
         "- 标题文字：「签到」「寻奇探幽」「限时签到」\n"
         "- 有一键领取按钮或日期列表\n"
         "- 背景是签到面板而非游戏3D场景\n"
         "\n"
         "输出JSON（纯JSON，必须包含所有字段）:\n"
         '{"is_signin_page": false,\n'
         ' "has_claim_all": false,\n'
         ' "elements_visible": [],\n'
         ' "next_action": "none/tap/back",\n'
         ' "next_coords": [x, y] if next_action=="tap" else null,\n'
         ' "error": "错误说明（如exit_dialog_unresolved/need_return_to_main_menu/loading_in_progress等）",\n'
         ' "status": "success/error/waiting"}'),

        ("claim_rewards", "领取签到奖励",
         "确认当前在签到页面后，执行奖励领取。\n"
         "\n"
         "【前置条件验证 - 必须按顺序执行】\n"
         "\n"
         "1. 【弹窗检测 - 绝对优先】\n"
         "如果检测到「是否退出游戏？」弹窗（page_type=exit_dialog）：\n"
         "   - 这是严重错误，前序步骤失败\n"
         "   - 必须立即返回错误，禁止任何领取操作\n"
         "   - 返回: {\"action\": \"none\", \"result\": \"prerequisite_failed\", \"error\": \"exit_dialog_unresolved\", \"status\": \"error\"}\n"
         "\n"
         "2. 【签到页面验证】\n"
         "必须 is_signin_page == true 且 has_claim_all == true\n"
         "   - 否则返回: {\"action\": \"none\", \"result\": \"prerequisite_failed\", \"error\": \"条件不满足\", \"status\": \"error\"}\n"
         "\n"
         "【执行步骤】\n"
         "1. 检测「一键领取」按钮\n"
         "2. 如果存在，点击并等待1秒\n"
         "3. 如果有确认弹窗，点击确认\n"
         "4. 验证领取成功（按钮消失或提示完成）\n"
         "5. 如果已领取完毕，返回成功\n"
         "\n"
         "输出JSON（纯JSON，必须包含所有字段）:\n"
         '{"action": "claim/close/back/none",\n'
         ' "coords": [x, y] if action in ["claim","close"] else null,\n'
         ' "result": "success/already_claimed/prerequisite_failed",\n'
         ' "retry_count": 0,\n'
         ' "status": "success/error",\n'
         ' "error": "错误说明（如exit_dialog_unresolved/条件不满足等）"}'),

        ("navigate_back", "返回主世界",
         "任务完成，返回游戏主世界。\n"
         "\n"
         "【流程位置】这是第5步，最后一步。上一步已领取奖励。\n"
         "必须确保没有阻塞性弹窗才能执行返回操作。\n"
         "\n"
         "重要: 如果当前是加载界面(loading_screen)，必须等待加载完成。\n"
         "\n"
         "执行步骤（严格按顺序）:\n"
         "\n"
         "【步骤0】弹窗状态验证（关键！）\n"
         "如果检测到「是否退出游戏？」弹窗（page_type=exit_dialog）：\n"
         "  1. 点击「取消」按钮（使用精确坐标）\n"
         "  2. 等待1秒后重新截图检测\n"
         "  3. 验证弹窗是否消失：\n"
         "     - 如果弹窗消失，继续步骤1\n"
         "     - 如果弹窗仍存在，最多重试3次（包括首次）\n"
         "  4. 若3次后弹窗仍未关闭，返回 {\"action\": \"none\", \"result\": \"dialog_blocked\", \"retry_count\": 3, \"error\": \"exit_dialog_persists_after_retries\"}\n"
         "\n"
         "【步骤1】返回操作\n"
         "- 如果有左上角返回箭头 (约 450,22)，点击它\n"
         "- 或者按返回键 (BACK)\n"
         "- 或者点击空白区域\n"
         "- 等待界面切换完成\n"
         "\n"
         "输出JSON（纯JSON，必须包含所有字段）:\n"
         '{"action": "tap/back/none/dialog_close",\n'
         ' "coords": [x, y] if action=="tap" else null,\n'
         ' "target": "world_map",\n'
         ' "result": "success/dialog_closed/dialog_blocked",\n'
         ' "retry_count": 0,  // 弹窗处理重试次数（0表示未遇到弹窗）\n'
         ' "status": "success/failed/retrying",  // 操作状态\n'
         ' "error": "错误说明（如弹窗未解决等）"}'),
    ],
    "scene_explore": [
        ("detect_screen", "检测当前画面",
         "分析当前游戏画面。输出画面类型和主要元素列表。"
         "JSON: {\"page_type\": \"...\", \"elements\": [...]}"),

        ("random_navigate", "随机探索移动",
         "当前在探索模式。执行一次随机探索动作（点击/滑动）。"
         "选择未探索的方向移动。JSON: {\"action\": \"swipe/tap\", \"direction\": \"...\"}"),

        ("scan_entities", "扫描可见实体",
         "扫描当前画面中的可见实体（建筑/物品/角色/UI元素）。"
         "JSON: {\"entities\": [{\"label\": \"...\", \"type\": \"...\", \"bbox\": [x1,y1,x2,y2]}]}"),

        ("verify_change", "验证场景变化",
         "与上一步对比，画面是否有明显变化？"
         "JSON: {\"changed\": bool, \"new_elements\": []}"),
    ],
    "full_flow": [],  # 在下方构建
}

# 完整流程 = 每日签到 + 场景探索
STANDARD_FLOWS["full_flow"] = (
    STANDARD_FLOWS["daily_signin"] + STANDARD_FLOWS["scene_explore"]
)


# ══════════════════════════════════════════════════════════════════
# 2B 模型接口
# ══════════════════════════════════════════════════════════════════

class Local2BEngine:
    """本地 2B 模型推理接口

    尝试加载 llama-cpp-python，失败则回退到 API 调用。
    """

    def __init__(self):
        self._engine = None
        self._model_path = str(PROJECT_ROOT / "models" / "qwen3.5-2b-qwen3.6-plus-distilled-f16" / "Qwen3.5-2B-UD-Q8_K_XL.gguf")
        self._loaded = False
        self._using_api = False

    def load(self) -> bool:
        """加载 2B 模型"""
        if self._loaded:
            return True

        # 尝试 llama-cpp-python
        try:
            from llama_cpp import Llama
            print(f"[2b] 正在加载模型: {self._model_path}")
            t0 = time.time()
            self._engine = Llama(
                model_path=self._model_path,
                n_ctx=2048,
                n_gpu_layers=0,
                verbose=False,
            )
            t1 = time.time()
            self._loaded = True
            self._using_api = False
            print(f"[2b] 本地模型加载成功 ({t1-t0:.1f}s)")
            return True
        except ImportError:
            print("[2b] llama-cpp-python 未安装, 回退到 API 调用")
        except Exception as e:
            print(f"[2b] 本地加载失败: {e}, 回退到 API")

        # 回退: 使用 IstinaPlatform API
        self._using_api = True
        self._loaded = True
        print("[2b] 使用 API 模式 (exploration_deep tag)")
        return True

    def generate(self, prompt: str, system_prompt: str = "",
                 max_tokens: int = 512, temperature: float = 0.3) -> str:
        """生成文本"""
        if not self._loaded:
            self.load()

        if not self._using_api and self._engine:
            # 本地推理
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            try:
                resp = self._engine.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return resp["choices"][0]["message"]["content"]
            except Exception as e:
                return f'{{"error": "本地推理失败: {e}"}}'
        else:
            # API 回退
            return self._api_generate(prompt, system_prompt, max_tokens, temperature)

    def _api_generate(self, prompt: str, system_prompt: str = "",
                      max_tokens: int = 512, temperature: float = 0.3) -> str:
        """通过 API 生成"""
        try:
            opts = VLMOptions(
                model_tag="exploration_deep",
                timeout=60,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt or "你是游戏操作决策助手。输出JSON格式。",
            )
            img = adb_screencap()
            if not img:
                return '{"error": "截图失败"}'
            resp = vlm_analyze(img, instruction=prompt, opts=opts)
            if resp:
                return resp.get("reply", "")
            return '{"error": "API 无响应"}'
        except Exception as e:
            return f'{{"error": "API 调用失败: {e}"}}'

    def is_local(self) -> bool:
        return not self._using_api


# ══════════════════════════════════════════════════════════════════
# 视觉智能体分析 - Qwen3.5-Max
# ══════════════════════════════════════════════════════════════════

def analyze_with_qwen_max(recorder: FlowRecorder, steps_config: List) -> Dict[str, Any]:
    """将执行记录发送给 Qwen3.5-Max 做完整性分析

    发送所有截图 + 每步的提示词和决策，让视觉智能体评估:
    1. 是否每一步都正确执行了
    2. 卡点在哪里
    3. 提示词需要如何优化
    """
    print("\n" + "=" * 60)
    print("[分析] 发送到 Qwen3.5-Max 进行视觉分析...")
    print("=" * 60)

    payload = recorder.get_analysis_payload()
    total_steps = len(payload)
    if total_steps == 0:
        return {"error": "无步骤可分析"}

    # 构建分析提示词
    analysis_prompt = f"""你是游戏自动化质量分析专家。检查以下 {total_steps} 步标准流执行记录。

对每一步，分析:
1. 截图中的画面是否与描述相符
2. 模型决策是否正确
3. 执行是否成功
4. 如果失败，原因是什么

返回JSON:
{{
  "overall_assessment": "整体评价",
  "step_analyses": [
    {{
      "step": 序号,
      "action": "动作名",
      "screen_correct": true/false,
      "decision_correct": true/false,
      "execution_success": true/false,
      "issues": ["问题描述"],
      "suggestion": "优化建议"
    }}
  ],
  "bottlenecks": ["主要卡点列表"],
  "prompt_optimizations": {{
    "step_X": "优化后的提示词"
  }}
}}
"""

    # 构建包含截图的消息
    messages = [{"role": "system", "content": "你是游戏自动化质量分析专家。仔细分析每帧截图与执行记录。"}]

    user_content = [{"type": "text", "text": analysis_prompt}]

    # 添加所有截图（采样关键步骤，避免超出 token 限制）
    max_images = min(total_steps, 15)
    step_indices = list(range(0, total_steps, max(1, total_steps // max_images)))[:max_images]

    for idx in step_indices:
        step = payload[idx]
        if step.get("screenshot_base64"):
            user_content.append({
                "type": "text",
                "text": f"\n--- Step {step['step']}: {step['action']} ---\n"
                        f"描述: {step['description']}\n"
                        f"提示词: {step['prompt'][:200]}\n"
                        f"决策: {step['decision'][:200]}\n"
                        f"成功: {step['success']}\n"
            })
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{step['screenshot_base64']}"}
            })

    messages.append({"role": "user", "content": user_content})

    # 调用 Qwen3.5-Max 视觉模型
    try:
        import requests
        r = requests.post(
            "http://192.168.1.19:3000/v1/chat/completions",
            headers={
                "Authorization": "Bearer sk-IDYeDxp4uuC5doDT2mX6iPEkkTYwfAY1lwUzm5rQQw8Yzcv3",
                "Content-Type": "application/json",
            },
            json={
                "model": "Qwen3.6-Max-Preview-thinking",
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.1,
            },
            timeout=120,
        )
        if r.status_code == 200:
            result = r.json()
            analysis_text = result["choices"][0]["message"]["content"]

            # 尝试解析 JSON
            json_match = re.search(r'\{[\s\S]*\}', analysis_text)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    print(f"[分析] 收到结构化分析结果")
                    return parsed
                except json.JSONDecodeError:
                    pass

            return {"raw_analysis": analysis_text}
        else:
            return {"error": f"API 返回 {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": f"分析请求失败: {e}"}


# ══════════════════════════════════════════════════════════════════
# 主测试执行器
# ══════════════════════════════════════════════════════════════════

def execute_flow(flow_name: str, steps_config: List, model_engine: Local2BEngine,
                 recorder: FlowRecorder) -> bool:
    """执行标准流，逐步骤测试"""
    adb = ADB()
    total = len(steps_config)
    all_success = True

    adb.wait(2)  # 稳定等待

    for i, (action, desc, prompt_template) in enumerate(steps_config):
        step_id = i + 1
        print(f"\n{'='*50}")
        print(f"[步骤 {step_id}/{total}] {action}: {desc}")
        print(f"{'='*50}")

        # 1. 截图（步骤前状态）
        img_before = adb_screencap()
        before_hash = hashlib.md5(img_before).hexdigest()[:8] if img_before else "none"

        # 2. 调用 2B 模型决策
        full_prompt = prompt_template + "\n当前截图哈希: " + before_hash
        system = "你是《明日方舟：终末地》游戏操作助手。根据当前画面做出正确决策。只输出JSON。"
        decision_text = model_engine.generate(full_prompt, system_prompt=system,
                                               max_tokens=512, temperature=0.3)
        print(f"  决策: {decision_text[:150]}")

        # 3. 解析决策并执行动作 (修复: 先清除 think 标签, 再用平衡花括号提取 JSON)
        success = True
        error_msg = ""

        try:
            # 清理: 去掉 <think> 标签
            clean_decision = re.sub(r'<think>[\s\S]*?</think>', '', decision_text)
            clean_decision = re.sub(r'```(?:json)?\s*', '', clean_decision).strip()

            # 平衡花括号提取最外层 JSON
            parsed_json = None
            depth = 0
            start = -1
            for i, c in enumerate(clean_decision):
                if c == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        try:
                            parsed_json = json.loads(clean_decision[start:i+1])
                            break
                        except json.JSONDecodeError:
                            continue

            if not parsed_json:
                # 回退: 直接搜索简单 JSON
                m = re.search(r'\{[^{}]*\}', clean_decision)
                if m:
                    try:
                        parsed_json = json.loads(m.group())
                    except:
                        pass

            if not parsed_json:
                success = False
                error_msg = "无法解析模型返回的JSON"
            else:
                # 检查是否有明确的错误字段
                if "error" in parsed_json and parsed_json["error"]:
                    success = False
                    error_msg = str(parsed_json["error"])
                # 检查 action 是否为空或无效
                elif "action" not in parsed_json or not parsed_json["action"]:
                    success = False
                    error_msg = "模型未返回有效action"
                # 检查 result/status 字段是否表示失败
                elif "result" in parsed_json and parsed_json["result"] in ("prerequisite_failed", "failed", "dialog_blocked", "unexpected_dialog"):
                    success = False
                    error_msg = f"结果状态: {parsed_json['result']}"
                elif "status" in parsed_json and parsed_json["status"] in ("failed", "failed_after_retries"):
                    success = False
                    error_msg = f"状态: {parsed_json['status']}"
                elif "is_signin_page" in parsed_json and parsed_json.get("is_signin_page") is False and "error" in parsed_json:
                    success = False
                    error_msg = parsed_json.get("error", "检查失败")

            # 根据 action_type 执行对应操作（只在成功解析时执行）
            if parsed_json:
                action_type = parsed_json.get("action", "")
                if action_type == "tap":
                    coords = parsed_json.get("coords", None)
                    if coords and len(coords) == 2:
                        adb.tap(coords[0], coords[1])
                    elif "活动" in str(parsed_json.get("target", "")):
                        adb.tap(*Coords.event_button)
                    elif "签到" in str(parsed_json.get("target", "")):
                        adb.tap(*Coords.signin_entry)
                    else:
                        adb.tap(640, 360)
                    adb.wait(2)
                elif action_type == "swipe":
                    direction = parsed_json.get("direction", "left")
                    if "left" in direction:
                        adb.swipe(900, 360, 300, 360, 600)
                    elif "right" in direction:
                        adb.swipe(300, 360, 900, 360, 600)
                    adb.wait(1.5)
                elif action_type == "back":
                    adb.keyevent(4)
                    adb.wait(2)
                elif action_type in ("claim", "领取"):
                    adb.tap(*Coords.claim_all)
                    adb.wait(1)
                elif action_type == "close":
                    adb.tap(*Coords.close_overlay_x)
                    adb.wait(1)
                elif action_type == "dialog_close":
                    # 处理退出确认弹窗：点击"取消"按钮
                    # 优先使用模型提供的坐标，否则使用默认值
                    if parsed_json.get("coords") and len(parsed_json["coords"]) == 2:
                        adb.tap(parsed_json["coords"][0], parsed_json["coords"][1])
                    else:
                        adb.tap(400, 660)  # 默认取消按钮坐标
                    adb.wait(1)
                elif action_type == "wait":
                    duration = parsed_json.get("duration", 3)
                    adb.wait(duration)
                else:
                    adb.wait(2)
        except Exception as e:
            success = False
            error_msg = f"执行异常: {e}"
            print(f"  动作执行异常: {e}")
            adb.wait(2)

        # 4. 记录步骤
        recorder.record_step(
            step_id=step_id,
            action=action,
            description=desc,
            prompt=full_prompt,
            decision=decision_text,
            success=success,
            error=error_msg,
        )

        if not success:
            all_success = False

    return all_success


def main():
    parser = argparse.ArgumentParser(description="标准流测试 v1")
    parser.add_argument("--steps", choices=["daily", "explore", "full"], default="daily",
                        help="执行的流程")
    parser.add_argument("--analyze-only", action="store_true",
                        help="仅分析已有记录 (不执行游戏流程)")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="执行流程但不发送分析")
    parser.add_argument("--local-only", action="store_true",
                        help="强制使用本地 2B 模型 (失败则退出)")

    args = parser.parse_args()

    # 选择流程
    if args.steps == "daily":
        flow_name = "daily_signin"
        steps = STANDARD_FLOWS["daily_signin"]
    elif args.steps == "explore":
        flow_name = "scene_explore"
        steps = STANDARD_FLOWS["scene_explore"]
    else:
        flow_name = "full_flow"
        steps = STANDARD_FLOWS["full_flow"]

    print("=" * 60)
    print(f"标准流测试 v1")
    print(f"流程: {flow_name} ({len(steps)} 步)")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 初始化
    recorder = FlowRecorder(session_name=flow_name)

    if not args.analyze_only:
        # 初始化 2B 模型引擎
        engine = Local2BEngine()
        ok = engine.load()
        if not ok:
            print("[错误] 模型加载失败")
            return 1
        if args.local_only and not engine.is_local():
            print("[错误] --local-only 但本地模型不可用")
            return 1
        model_type = "本地 2B" if engine.is_local() else "API (exploration_deep)"
        print(f"模型模式: {model_type}")

        # 前置: 确保游戏在运行
        print(f"\n[前置] 确保游戏正在运行...")
        import subprocess
        adb_path = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")
        # 检查游戏进程
        r = subprocess.run([adb_path, "-s", "localhost:16512", "shell", "ps", "-A"],
                          capture_output=True, timeout=10)
        game_running = b'com.hypergryph.endfield' in r.stdout and b'U8UnityContext' in r.stdout

        if not game_running:
            print("[前置] 游戏未运行, 正在启动...")
            # 先回桌面
            subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "keyevent", "3"],
                          capture_output=True, timeout=5)
            time.sleep(2)
            # 启动游戏
            r = subprocess.run([adb_path, "-s", "localhost:16512", "shell",
                              "am", "start", "-n",
                              "com.hypergryph.endfield/com.u8.sdk.U8UnityContext"],
                             capture_output=True, timeout=15)
            print(f"  启动结果: {r.stdout.decode()[:200]}")
            # 等待游戏加载
            print("  等待游戏加载 (30s)...")
            time.sleep(30)
        else:
            print("[前置] 游戏已在运行")

        # 前置: 回到游戏世界（处理标题画面/公告等）
        print("[前置] 导航到游戏主界面...")
        for _ in range(3):
            subprocess.run([adb_path, "-s", "localhost:16512", "shell", "input", "tap", "540", "960"],
                          capture_output=True, timeout=5)
            time.sleep(2)
        print("[前置] 完成")

        # 执行流程
        print(f"\n开始执行 {len(steps)} 步流程...")
        all_ok = execute_flow(flow_name, steps, engine, recorder)
        print(f"\n流程完成: {'全部成功' if all_ok else '有失败步骤'}")

    # 导出报告
    report = recorder.export_report()
    report_path = os.path.join(recorder.session_dir, "flow_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")

    # 发送 Qwen3.5-Max 分析
    if not args.skip_analysis:
        analysis = analyze_with_qwen_max(recorder, steps)
        analysis_path = os.path.join(recorder.session_dir, "qwen_analysis.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"分析结果已保存: {analysis_path}")

        # 输出优化建议
        if "prompt_optimizations" in analysis:
            print(f"\n{'='*60}")
            print("提示词优化建议:")
            print(f"{'='*60}")
            for step_key, optimized in analysis["prompt_optimizations"].items():
                print(f"\n[{step_key}]")
                print(f"  {optimized[:300]}")

        if "bottlenecks" in analysis:
            print(f"\n卡点分析:")
            for b in analysis["bottlenecks"]:
                print(f"  - {b}")
    else:
        print("\n跳过 Qwen3.5-Max 分析")

    return 0


if __name__ == "__main__":
    sys.exit(main())
