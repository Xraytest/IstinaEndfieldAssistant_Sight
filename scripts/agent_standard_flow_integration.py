#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
Agent-鏍囧噯娴侀泦鎴愭ā鍧?- 灏嗘爣鍑嗘祦閰嶇疆涓嶢gentExecutor闆嗘垚

鐗规€?
1. 鏍囧噯娴佹寚浠よ浆鎹负Agent鍙悊瑙ｇ殑鎸囦护
2. 鑷姩璁板綍鎵ц杩囩▼
3. 闆嗘垚瑙嗚鍒嗘瀽鍙嶉
4. 鏀寔鍔ㄦ€佹彁绀鸿瘝浼樺寲
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
    """閫氳繃AgentExecutor杩愯鏍囧噯娴?""

    def __init__(self, agent_executor: AgentExecutor, config: FlowConfig = None):
        self.agent_executor = agent_executor
        self.config = config or FlowConfig()
        self.recorder = None
        self._stop_requested = False

    def run_flow(self, flow_name: str, record: bool = True) -> Dict[str, Any]:
        """杩愯鏍囧噯娴?""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            return {"status": "error", "message": f"Unknown flow: {flow_name}"}

        steps = flow_config.get("steps", [])
        if not steps:
            return {"status": "success", "message": "Flow has no steps"}

        # 鍒濆鍖栬褰曞櫒
        if record:
            self.recorder = FlowRecorder(
                session_name=f"agent_{flow_name}",
                record_video=True
            )
        else:
            self.recorder = None

        print(f"\n{'='*60}")
        print(f"Agent鎵ц娴佺▼: {flow_name}")
        print(f"鎻忚堪: {flow_config.get('description', '')}")
        print(f"姝ラ鏁? {len(steps)}")
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

            print(f"\n[姝ラ {step_id}/{len(steps)}] {step_key}: {description}")

            # 鍑嗗Agent鎸囦护
            prompt = self.config.substitute_variables(prompt_template)
            prompt = prompt.replace("{{current_page}}", context.get("current_page", "unknown"))

            # 鏋勫缓瀹屾暣鎸囦护
            instruction = f"""Standard flow step: {step_key}
Action type: {action_type}
Description: {description}

{prompt}

Output JSON with action and required fields only.
"""

            # 鍙戦€佸埌Agent
            start_time = time.time()
            result = self.agent_executor.send_instruction(instruction)
            elapsed = time.time() - start_time

            # 璁板綍
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

            # 鏇存柊涓婁笅鏂?            if result.get("status") == "success":
                print(f"  [OK] 鎵ц鎴愬姛 ({elapsed:.1f}s)")
                results.append({"step": step_key, "success": True})
            else:
                print(f"  [FAIL] {result.get('message')}")
                results.append({"step": step_key, "success": False, "error": result.get("message")})

            time.sleep(1)

        # 鐢熸垚鎶ュ憡
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
            print(f"\n鎶ュ憡宸蹭繚瀛? {report_file}")

        return report

    def stop(self):
        """鍋滄鎵ц"""
        self._stop_requested = True
        if self.agent_executor:
            # AgentExecutor娌℃湁鐩存帴鐨勫仠姝㈡柟娉曪紝浣嗗彲浠ラ噸缃?            self.agent_executor.reset_conversation()


def create_standard_flow_commands(agent_executor: AgentExecutor) -> Dict[str, callable]:
    """鍒涘缓鏍囧噯娴佸懡浠ゅ瓧鍏革紝渚夸簬GUI闆嗘垚"""
    config = FlowConfig()

    commands = {}
    for flow_name in config.all_flows:
        if config.is_flow_enabled(flow_name):
            runner = AgentStandardFlowRunner(agent_executor, config)
            commands[flow_name] = lambda f=flow_name, r=runner: r.run_flow(f)

    return commands


# 绀轰緥锛氬浣曚笌GUI闆嗘垚
def integrate_with_gui():
    """绀轰緥锛氬浣曞皢鏍囧噯娴侀泦鎴愬埌GUI"""
    print("""
GUI闆嗘垚绀轰緥:

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

杩欐牱锛屾爣鍑嗘祦灏嗛€氳繃AgentExecutor鎵ц锛屽埄鐢ㄤ簯绔疺LM鑳藉姏锛?鍚屾椂淇濈暀閰嶇疆鍖栧拰璁板綍鍒嗘瀽鍔熻兘銆?""")


if __name__ == "__main__":
    integrate_with_gui()

