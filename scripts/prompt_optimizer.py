#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鎻愮ず璇嶄紭鍖栧櫒 - 鍩轰簬鎵ц鍒嗘瀽鑷姩浼樺寲鏍囧噯娴佹彁绀鸿瘝

宸ヤ綔娴佺▼:
1. 鎵ц鏍囧噯娴佸苟璁板綍
2. 瑙嗚subagent鍒嗘瀽鎵ц璐ㄩ噺
3. 鎻愬彇浼樺寲寤鸿
4. 鑷姩鏇存柊閰嶇疆鏂囦欢
5. 楠岃瘉浼樺寲鏁堟灉锛堝彲閫夊惊鐜級
"""

import sys
import os
import json
import shutil
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Set

from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

# 鍔ㄦ€佸鍏tandard_flow_engine
spec = importlib.util.spec_from_file_location(
    "standard_flow_engine",
    PROJECT_ROOT / "scripts" / "standard_flow_engine.py"
)
engine_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_module)

FlowConfig = engine_module.FlowConfig
FlowRecorder = engine_module.FlowRecorder
Local2BEngine = engine_module.Local2BEngine
StandardFlowExecutor = engine_module.StandardFlowExecutor
VisualAnalyzer = engine_module.VisualAnalyzer


class PromptOptimizer:
    """鎻愮ず璇嶄紭鍖栧櫒"""

    def __init__(self, config: FlowConfig):
        self.config = config
        self.backup_dir = PROJECT_ROOT / "config" / "standard_flows" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_config(self):
        """澶囦唤褰撳墠閰嶇疆"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"flows_config_{timestamp}.json"
        shutil.copy2(self.config.config_path, backup_path)
        print(f"[backup] 閰嶇疆宸插浠? {backup_path}")
        return backup_path

    def optimize_flow(self, flow_name: str, executor: StandardFlowExecutor,
                      analyzer_model: str = None) -> Dict[str, Any]:
        """鎵ц骞朵紭鍖栧崟涓祦绋?""
        print(f"\n{'='*60}")
        print(f"浼樺寲娴佺▼: {flow_name}")
        print(f"{'='*60}")

        # 1. 鎵ц娴佺▼锛堣褰曟埅鍥撅級
        print("\n[1/3] 鎵ц娴佺▼骞惰褰?..")
        recorder = FlowRecorder(session_name=f"optimize_{flow_name}", record_video=True)
        executor.recorder = recorder
        success = executor.execute_flow(flow_name)

        # 2. 瑙嗚鍒嗘瀽
        print("\n[2/3] 瑙嗚subagent鍒嗘瀽...")
        analyzer = VisualAnalyzer(model=analyzer_model or self.config.execution_config.get("analysis_model"))
        analysis = analyzer.analyze_execution(recorder, flow_name)

        # 淇濆瓨鍒嗘瀽缁撴灉
        analysis_path = os.path.join(recorder.session_dir, "analysis.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"  鍒嗘瀽宸蹭繚瀛? {analysis_path}")

        # 3. 搴旂敤浼樺寲
        print("\n[3/3] 搴旂敤鎻愮ず璇嶄紭鍖?..")
        applied = self._apply_optimizations(flow_name, analysis)

        return {
            "flow": flow_name,
            "execution_success": success,
            "analysis": analysis,
            "optimizations_applied": applied,
            "recorder_dir": recorder.session_dir,
        }

    def _apply_optimizations(self, flow_name: str, analysis: Dict[str, Any]) -> int:
        """搴旂敤鍒嗘瀽涓殑浼樺寲寤鸿鍒伴厤缃?""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            print(f"[WARN] 娴佺▼涓嶅瓨鍦? {flow_name}")
            return 0

        optimizations = analysis.get("prompt_optimizations", {})
        if not optimizations:
            print("  鏃犱紭鍖栧缓璁?)
            return 0

        applied_count = 0
        steps_by_id = {step["id"]: step for step in flow_config.get("steps", [])}

        for step_id, new_prompt in optimizations.items():
            if step_id in steps_by_id:
                old_prompt = steps_by_id[step_id]["prompt_template"]
                # 绠€鍗曠殑鐩镐技搴︽鏌ワ紝閬垮厤鏃犳剰涔夌殑淇敼
                if self._is_significant_change(old_prompt, new_prompt):
                    steps_by_id[step_id]["prompt_template"] = new_prompt
                    applied_count += 1
                    print(f"  鉁?鏇存柊姝ラ: {step_id}")
                    # 鎵撳嵃宸紓棰勮
                    print(f"    鏃? {old_prompt[:80]}...")
                    print(f"    鏂? {new_prompt[:80]}...")
                else:
                    print(f"  鈯?璺宠繃 {step_id}: 鍙樺寲涓嶆樉钁?)

        if applied_count > 0:
            # 淇濆瓨閰嶇疆
            self._save_config()
            print(f"\n  鍏卞簲鐢?{applied_count} 澶勪紭鍖?)
        else:
            print("  鏃犻渶浼樺寲锛堟墍鏈夊缓璁彉鍖栦笉鏄捐憲锛?)

        return applied_count

    def _is_significant_change(self, old: str, new: str) -> bool:
        """妫€鏌ユ槸鍚︽槸鏈夋剰涔夌殑鍙樻洿"""
        # 鍘婚櫎绌虹櫧瀛楃姣旇緝
        old_clean = " ".join(old.split())
        new_clean = " ".join(new.split())

        if old_clean == new_clean:
            return False

        # 闀垮害宸紓瓒呰繃10%鎴栧叧閿瓧绗﹀彉鍖?        len_ratio = abs(len(new_clean) - len(old_clean)) / max(len(old_clean), 1)
        return len_ratio > 0.1 or len(new_clean) > len(old_clean) * 1.2

    def _save_config(self):
        """淇濆瓨閰嶇疆锛堝厛澶囦唤锛?""
        self.backup_config()
        with open(self.config.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config._config, f, ensure_ascii=False, indent=2)
        print(f"[save] 閰嶇疆宸蹭繚瀛? {self.config.config_path}")

    def optimize_all_flows(self, flows: List[str] = None, iterations: int = 1) -> Dict[str, Any]:
        """鎵归噺浼樺寲澶氫釜娴佺▼"""
        if flows is None:
            flows = [f for f in self.config.all_flows if self.config.is_flow_enabled(f)]

        print(f"鎵归噺浼樺寲 {len(flows)} 涓祦绋嬶紝杩唬 {iterations} 娆?)

        results = {}
        engine = Local2BEngine()
        engine.load()

        for iteration in range(iterations):
            print(f"\n{'='*60}")
            print(f"杩唬 {iteration + 1}/{iterations}")
            print(f"{'='*60}")

            for flow_name in flows:
                executor = StandardFlowExecutor(self.config, engine)
                result = self.optimize_flow(flow_name, executor)
                results[f"{flow_name}_iter{iteration+1}"] = result

                # 姝ラ闂存殏鍋?                time.sleep(2)

        # 鐢熸垚鎬荤粨鎶ュ憡
        summary_path = PROJECT_ROOT / "cache" / f"optimization_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary = {
            "timestamp": datetime.now().isoformat(),
            "iterations": iterations,
            "flows_optimized": flows,
            "results": results,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n[summary] 浼樺寲鎬荤粨: {summary_path}")

        return summary


def main():
    """涓诲嚱鏁帮細浼樺寲鎵€鏈夋爣鍑嗘祦"""
    import argparse

    parser = argparse.ArgumentParser(description="鏍囧噯娴佹彁绀鸿瘝鑷姩浼樺寲鍣?)
    parser.add_argument("--flows", nargs="+",
                        choices=["daily_quest", "weekly_quest", "resource_collection",
                                 "base_management", "character_ascension",
                                 "weapon_crafting", "event_rewards", "all"],
                        default=["all"], help="瑕佷紭鍖栫殑娴佺▼")
    parser.add_argument("--iterations", type=int, default=1,
                        help="浼樺寲杩唬娆℃暟")
    parser.add_argument("--analyzer-model", default="Qwen3.6-Max-Preview-thinking",
                        help="鐢ㄤ簬鍒嗘瀽鐨勮瑙夋ā鍨?)
    parser.add_argument("--dry-run", action="store_true",
                        help="浠呭垎鏋愪笉淇敼閰嶇疆")

    args = parser.parse_args()

    config = FlowConfig()
    optimizer = PromptOptimizer(config)

    flows_to_optimize = []
    if "all" in args.flows:
        flows_to_optimize = [f for f in config.all_flows if config.is_flow_enabled(f)]
    else:
        flows_to_optimize = args.flows

    print(f"寮€濮嬩紭鍖?{len(flows_to_optimize)} 涓祦绋?)
    print(f"鍒嗘瀽妯″瀷: {args.analyzer_model}")
    print(f"杩唬娆℃暟: {args.iterations}")
    print(f"骞茶繍琛? {args.dry_run}")

    if args.dry_run:
        print("\n[DRY RUN] 浠呮墽琛屽垎鏋愶紝涓嶄細淇敼閰嶇疆")
        engine = Local2BEngine()
        engine.load()

        for flow_name in flows_to_optimize:
            executor = StandardFlowExecutor(config, engine)
            recorder = FlowRecorder(session_name=f"dry_{flow_name}", record_video=True)
            executor.recorder = recorder

            print(f"\n鎵ц鍒嗘瀽: {flow_name}")
            success = executor.execute_flow(flow_name)

            analyzer = VisualAnalyzer(model=args.analyzer_model)
            analysis = analyzer.analyze_execution(recorder, flow_name)

            if "prompt_optimizations" in analysis:
                print(f"  鍙戠幇 {len(analysis['prompt_optimizations'])} 鏉′紭鍖栧缓璁?)
            else:
                print("  鏃犱紭鍖栧缓璁?)
    else:
        # 瀹為檯浼樺寲
        summary = optimizer.optimize_all_flows(
            flows=flows_to_optimize,
            iterations=args.iterations
        )

        print("\n浼樺寲瀹屾垚锛?)
        print(f"浼樺寲缁熻:")
        for key, result in summary["results"].items():
            flow = result["flow"]
            applied = result["optimizations_applied"]
            print(f"  {flow}: {applied} 澶勪慨鏀?)


if __name__ == "__main__":
    sys.exit(main())

