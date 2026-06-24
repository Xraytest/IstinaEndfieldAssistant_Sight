#!/usr/bin/env python3
"""
Agent-标准流集成模块 - 将标准流配置与AgentExecutor集成

特性:
1. 标准流指令转换为Agent可理解的指令
2. 自动记录执行过程
3. 集成视觉分析反馈
4. 支持动态提示词优化
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from scripts.standard_flow_engine import FlowConfig, FlowRecorder, Local2BEngine
from core.service.cloud.agent_executor import AgentExecutor


class AgentStandardFlowRunner:
    """通过AgentExecutor运行标准流"""

    def __init__(self, agent_executor: AgentExecutor, config: FlowConfig = None):
        self.agent_executor = agent_executor
        self.config = config or FlowConfig()
        self.recorder = None
        self._stop_requested = False

    def run_flow(self, flow_name: str, record: bool = True) -> Dict[str, Any]:
        """运行标准流"""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            return {"status": "error", "message": f"Unknown flow: {flow_name}"}

        steps = flow_config.get("steps", [])
        if not steps:
            return {"status": "success", "message": "Flow has no steps"}

        # 初始化记录器
        if record:
            self.recorder = FlowRecorder(
                session_name=f"agent_{flow_name}",
                record_video=True
            )
        else:
            self.recorder = None

        print(f"\n{'='*60}")
        print(f"Agent执行流程: {flow_name}")
        print(f"描述: {flow_config.get('description', '')}")
        print(f"步骤数: {len(steps)}")
        print(f"{'='*60}\n")

        results = []
        context = {"current_page": "unknown"}

        for i, step_cfg in enumerate(steps):
            if self._stop_requested:
                break

            step_id = i + 1
            step_key = step_cfg["id"]
            action_type = step_cfg["action"]
            description = step_cfg["description"]
            prompt_template = step_cfg["prompt_template"]

            print(f"\n[步骤 {step_id}/{len(steps)}] {step_key}: {description}")

            # 准备Agent指令
            prompt = self.config.substitute_variables(prompt_template)
            prompt = prompt.replace("{{current_page}}", context.get("current_page", "unknown"))

            # 构建完整指令
            instruction = f"""Standard flow step: {step_key}
Action type: {action_type}
Description: {description}

{prompt}

Output JSON with action and required fields only.
"""

            # 发送到Agent
            start_time = time.time()
            result = self.agent_executor.send_instruction(instruction)
            elapsed = time.time() - start_time

            # 记录
            if self.recorder:
                self.recorder.record_step(
                    step_id=step_id,
                    step_key=step_key,
                    action=action_type,
                    description=description,
                    prompt=instruction,
                    decision=result.get("reply", ""),
                    success=result.get("status") == "success",
                    error=result.get("message", ""),
                    metadata={
                        "elapsed_seconds": elapsed,
                        "actions_executed": len(result.get("execution_results", [])),
                    }
                )

            # 更新上下文
            if result.get("status") == "success":
                print(f"  [OK] 执行成功 ({elapsed:.1f}s)")
                results.append({"step": step_key, "success": True})
            else:
                print(f"  [FAIL] {result.get('message')}")
                results.append({"step": step_key, "success": False, "error": result.get("message")})

            time.sleep(1)

        # 生成报告
        report = {
            "flow": flow_name,
            "total_steps": len(steps),
            "success_count": sum(1 for r in results if r["success"]),
            "fail_count": sum(1 for r in results if not r["success"]),
            "results": results,
        }

        if self.recorder:
            report_file = os.path.join(self.recorder.session_dir, "agent_flow_report.json")
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n报告已保存: {report_file}")

        return report

    def stop(self):
        """停止执行"""
        self._stop_requested = True
        if self.agent_executor:
            # AgentExecutor没有直接的停止方法，但可以重置
            self.agent_executor.reset_conversation()


def create_standard_flow_commands(agent_executor: AgentExecutor) -> Dict[str, callable]:
    """创建标准流命令字典，便于GUI集成"""
    config = FlowConfig()

    commands = {}
    for flow_name in config.all_flows:
        if config.is_flow_enabled(flow_name):
            runner = AgentStandardFlowRunner(agent_executor, config)
            commands[flow_name] = lambda f=flow_name, r=runner: r.run_flow(f)

    return commands


# 示例：如何与GUI集成
def integrate_with_gui():
    """示例：如何将标准流集成到GUI"""
    print("""
GUI集成示例:

from scripts.agent_standard_flow_integration import AgentStandardFlowRunner, FlowConfig

class EnhancedStandardReasoningPage(StandardReasoningPage):
    def __init__(self, agent_executor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_executor = agent_executor
        self.config = FlowConfig()
        self.runner = AgentStandardFlowRunner(agent_executor, self.config)

    def _execute_selected_flows(self):
        selected = [fid for fid, cb in self._flow_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "No Flow Selected", "Select at least one flow.")
            return

        self._execute_btn.setEnabled(False)
        self._exec_stop_btn.setEnabled(True)

        for flow_id in selected:
            self._log(f"[{flow_id}] Starting via Agent...")
            result = self.runner.run_flow(flow_id)
            if result["status"] == "success":
                success_rate = result["success_count"] / result["total_steps"]
                self._log(f"[{flow_id}] Completed - {success_rate:.0%} success")
            else:
                self._log(f"[{flow_id}] Failed: {result.get('message')}")

        self._execute_btn.setEnabled(True)
        self._exec_stop_btn.setEnabled(False)

这样，标准流将通过AgentExecutor执行，利用云端VLM能力，
同时保留配置化和记录分析功能。
""")


if __name__ == "__main__":
    integrate_with_gui()
