#!/usr/bin/env python3
"""
提示词优化器 - 基于执行分析自动优化标准流提示词

工作流程:
1. 执行标准流并记录
2. 视觉subagent分析执行质量
3. 提取优化建议
4. 自动更新配置文件
5. 验证优化效果（可选循环）
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

# 动态导入standard_flow_engine
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
    """提示词优化器"""

    def __init__(self, config: FlowConfig):
        self.config = config
        self.backup_dir = PROJECT_ROOT / "config" / "standard_flows" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_config(self):
        """备份当前配置"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"flows_config_{timestamp}.json"
        shutil.copy2(self.config.config_path, backup_path)
        print(f"[backup] 配置已备份: {backup_path}")
        return backup_path

    def optimize_flow(self, flow_name: str, executor: StandardFlowExecutor,
                      analyzer_model: str = None) -> Dict[str, Any]:
        """执行并优化单个流程"""
        print(f"\n{'='*60}")
        print(f"优化流程: {flow_name}")
        print(f"{'='*60}")

        # 1. 执行流程（记录截图）
        print("\n[1/3] 执行流程并记录...")
        recorder = FlowRecorder(session_name=f"optimize_{flow_name}", record_video=True)
        executor.recorder = recorder
        success = executor.execute_flow(flow_name)

        # 2. 视觉分析
        print("\n[2/3] 视觉subagent分析...")
        analyzer = VisualAnalyzer(model=analyzer_model or self.config.execution_config.get("analysis_model"))
        analysis = analyzer.analyze_execution(recorder, flow_name)

        # 保存分析结果
        analysis_path = os.path.join(recorder.session_dir, "analysis.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"  分析已保存: {analysis_path}")

        # 3. 应用优化
        print("\n[3/3] 应用提示词优化...")
        applied = self._apply_optimizations(flow_name, analysis)

        return {
            "flow": flow_name,
            "execution_success": success,
            "analysis": analysis,
            "optimizations_applied": applied,
            "recorder_dir": recorder.session_dir,
        }

    def _apply_optimizations(self, flow_name: str, analysis: Dict[str, Any]) -> int:
        """应用分析中的优化建议到配置"""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            print(f"[WARN] 流程不存在: {flow_name}")
            return 0

        optimizations = analysis.get("prompt_optimizations", {})
        if not optimizations:
            print("  无优化建议")
            return 0

        applied_count = 0
        steps_by_id = {step["id"]: step for step in flow_config.get("steps", [])}

        for step_id, new_prompt in optimizations.items():
            if step_id in steps_by_id:
                old_prompt = steps_by_id[step_id]["prompt_template"]
                # 简单的相似度检查，避免无意义的修改
                if self._is_significant_change(old_prompt, new_prompt):
                    steps_by_id[step_id]["prompt_template"] = new_prompt
                    applied_count += 1
                    print(f"  ✓ 更新步骤: {step_id}")
                    # 打印差异预览
                    print(f"    旧: {old_prompt[:80]}...")
                    print(f"    新: {new_prompt[:80]}...")
                else:
                    print(f"  ⊘ 跳过 {step_id}: 变化不显著")

        if applied_count > 0:
            # 保存配置
            self._save_config()
            print(f"\n  共应用 {applied_count} 处优化")
        else:
            print("  无需优化（所有建议变化不显著）")

        return applied_count

    def _is_significant_change(self, old: str, new: str) -> bool:
        """检查是否是有意义的变更"""
        # 去除空白字符比较
        old_clean = " ".join(old.split())
        new_clean = " ".join(new.split())

        if old_clean == new_clean:
            return False

        # 长度差异超过10%或关键字符变化
        len_ratio = abs(len(new_clean) - len(old_clean)) / max(len(old_clean), 1)
        return len_ratio > 0.1 or len(new_clean) > len(old_clean) * 1.2

    def _save_config(self):
        """保存配置（先备份）"""
        self.backup_config()
        with open(self.config.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config._config, f, ensure_ascii=False, indent=2)
        print(f"[save] 配置已保存: {self.config.config_path}")

    def optimize_all_flows(self, flows: List[str] = None, iterations: int = 1) -> Dict[str, Any]:
        """批量优化多个流程"""
        if flows is None:
            flows = [f for f in self.config.all_flows if self.config.is_flow_enabled(f)]

        print(f"批量优化 {len(flows)} 个流程，迭代 {iterations} 次")

        results = {}
        engine = Local2BEngine()
        engine.load()

        for iteration in range(iterations):
            print(f"\n{'='*60}")
            print(f"迭代 {iteration + 1}/{iterations}")
            print(f"{'='*60}")

            for flow_name in flows:
                executor = StandardFlowExecutor(self.config, engine)
                result = self.optimize_flow(flow_name, executor)
                results[f"{flow_name}_iter{iteration+1}"] = result

                # 步骤间暂停
                time.sleep(2)

        # 生成总结报告
        summary_path = PROJECT_ROOT / "cache" / f"optimization_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary = {
            "timestamp": datetime.now().isoformat(),
            "iterations": iterations,
            "flows_optimized": flows,
            "results": results,
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n[summary] 优化总结: {summary_path}")

        return summary


def main():
    """主函数：优化所有标准流"""
    import argparse

    parser = argparse.ArgumentParser(description="标准流提示词自动优化器")
    parser.add_argument("--flows", nargs="+",
                        choices=["daily_quest", "weekly_quest", "resource_collection",
                                 "base_management", "character_ascension",
                                 "weapon_crafting", "event_rewards", "all"],
                        default=["all"], help="要优化的流程")
    parser.add_argument("--iterations", type=int, default=1,
                        help="优化迭代次数")
    parser.add_argument("--analyzer-model", default="Qwen3.6-Max-Preview-thinking",
                        help="用于分析的视觉模型")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅分析不修改配置")

    args = parser.parse_args()

    config = FlowConfig()
    optimizer = PromptOptimizer(config)

    flows_to_optimize = []
    if "all" in args.flows:
        flows_to_optimize = [f for f in config.all_flows if config.is_flow_enabled(f)]
    else:
        flows_to_optimize = args.flows

    print(f"开始优化 {len(flows_to_optimize)} 个流程")
    print(f"分析模型: {args.analyzer_model}")
    print(f"迭代次数: {args.iterations}")
    print(f"干运行: {args.dry_run}")

    if args.dry_run:
        print("\n[DRY RUN] 仅执行分析，不会修改配置")
        engine = Local2BEngine()
        engine.load()

        for flow_name in flows_to_optimize:
            executor = StandardFlowExecutor(config, engine)
            recorder = FlowRecorder(session_name=f"dry_{flow_name}", record_video=True)
            executor.recorder = recorder

            print(f"\n执行分析: {flow_name}")
            success = executor.execute_flow(flow_name)

            analyzer = VisualAnalyzer(model=args.analyzer_model)
            analysis = analyzer.analyze_execution(recorder, flow_name)

            if "prompt_optimizations" in analysis:
                print(f"  发现 {len(analysis['prompt_optimizations'])} 条优化建议")
            else:
                print("  无优化建议")
    else:
        # 实际优化
        summary = optimizer.optimize_all_flows(
            flows=flows_to_optimize,
            iterations=args.iterations
        )

        print("\n优化完成！")
        print(f"优化统计:")
        for key, result in summary["results"].items():
            flow = result["flow"]
            applied = result["optimizations_applied"]
            print(f"  {flow}: {applied} 处修改")


if __name__ == "__main__":
    sys.exit(main())
