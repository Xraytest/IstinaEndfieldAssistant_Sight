#!/usr/bin/env python3
"""
IstinaEndfieldAssistant_Sight — 统一 CLI 入口 v4

薄路由层，将各子命令委托给领域专用的 CLI 模块 (src/cli/) 或核心模块。

用法:
  python -m src.cli.istina <command> [args]

子命令:
  module list                    # 列出所有模块
  module test <name>             # 测试单个模块可用性
  module test all                # 测试所有模块
  module info <name>             # 查看模块详情
"""

import sys
import os
import json
import argparse
import subprocess
import importlib
from pathlib import Path
from typing import Optional, Dict, Any, List

# ── 路径设置 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ── 模块清单（自动发现） ──────────────────────────────────────

def _discover_modules() -> Dict[str, Dict]:
    """扫描 core/*/ 下的子包，返回 {模块名: {layer, path, exports}}"""
    modules = {}
    core_dir = SRC_DIR / "core"
    for layer_dir in ["foundation", "capability", "service"]:
        layer_path = core_dir / layer_dir
        if not layer_path.exists():
            continue
        for sub_dir in sorted(layer_path.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
                continue
            init_file = sub_dir / "__init__.py"
            if not init_file.exists():
                continue
            exports = []
            try:
                with open(init_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if "__all__" in content:
                    import ast
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name) and target.id == "__all__":
                                    if isinstance(node.value, ast.List):
                                        exports = [
                                            elt.value for elt in node.value.elts
                                            if isinstance(elt, ast.Constant)
                                        ]
            except Exception:
                pass
            modules[sub_dir.name] = {
                "layer": layer_dir,
                "path": str(sub_dir),
                "exports": exports,
            }
    return modules


def _check_module_available(module_name: str) -> Dict:
    """检查模块可用性"""
    result = {
        "module": module_name,
        "layer": "unknown",
        "available": False,
        "runtime_ready": False,
        "checks": {"import": False, "dependencies": False, "config": False, "runtime": False},
        "details": {"import_error": None, "missing_deps": [], "config_path": None, "runtime_info": None},
    }
    modules = _discover_modules()
    if module_name not in modules:
        result["details"]["import_error"] = f"模块 '{module_name}' 未找到"
        return result
    mod_info = modules[module_name]
    result["layer"] = mod_info["layer"]
    try:
        import_path = f"core.{mod_info['layer']}.{module_name}"
        mod = importlib.import_module(import_path)
        result["checks"]["import"] = True
    except Exception as e:
        result["details"]["import_error"] = str(e)
        return result
    deps = getattr(mod, "__dependencies__", [])
    if deps:
        missing = []
        for dep in deps:
            try:
                importlib.import_module(f"core.{mod_info['layer']}.{dep}")
            except Exception:
                missing.append(dep)
        result["checks"]["dependencies"] = len(missing) == 0
        result["details"]["missing_deps"] = missing
    else:
        result["checks"]["dependencies"] = True
    result["checks"]["config"] = True
    result["checks"]["runtime"] = False
    if mod_info["layer"] == "foundation":
        result["available"] = result["checks"]["import"]
    elif mod_info["layer"] == "capability":
        result["available"] = result["checks"]["import"] and result["checks"]["dependencies"]
    elif mod_info["layer"] == "service":
        result["available"] = result["checks"]["import"] and result["checks"]["dependencies"]
    return result


# ── 模块子命令 ────────────────────────────────────────────────

def cmd_module_list(args):
    modules = _discover_modules()
    if args.json:
        print(json.dumps(modules, ensure_ascii=False, indent=2))
        return 0
    print(f"\n{'模块名':<20} {'层级':<15} {'导出符号数':<10}")
    print("-" * 50)
    for name, info in sorted(modules.items()):
        print(f"{name:<20} {info['layer']:<15} {len(info['exports']):<10}")
    print(f"\n共 {len(modules)} 个模块")
    return 0


def cmd_module_test(args):
    if args.name == "all":
        modules = _discover_modules()
        all_ok = True
        for name in sorted(modules.keys()):
            result = _check_module_available(name)
            status = "✓" if result["available"] else "✗"
            print(f"{status} {name:<20} [{result['layer']:<12}]")
            if not result["available"]:
                all_ok = False
                for check, ok in result["checks"].items():
                    if not ok:
                        detail = result["details"].get(f"{check}_error") or "unknown"
                        print(f"    └─ {check}: FAIL ({detail})")
        print(f"\n{'='*40}")
        print(f"总体: {'全部通过' if all_ok else '存在不可用模块'}")
        return 0 if all_ok else 1
    else:
        result = _check_module_available(args.name)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            status = "✓" if result["available"] else "✗"
            print(f"{status} {result['module']:<20} [{result['layer']:<12}]")
            if not result["available"]:
                for check, ok in result["checks"].items():
                    if not ok:
                        detail = result["details"].get(f"{check}_error") or "unknown"
                        print(f"    └─ {check}: FAIL ({detail})")
        return 0 if result["available"] else 1


def cmd_module_info(args):
    modules = _discover_modules()
    if args.name not in modules:
        print(f"模块 '{args.name}' 未找到")
        return 1
    info = modules[args.name]
    print(f"\n模块: {args.name}")
    print(f"层级: {info['layer']}")
    print(f"路径: {info['path']}")
    print(f"导出符号 ({len(info['exports'])}):")
    for exp in info["exports"]:
        print(f"  - {exp}")
    return 0


# ── CLI 解析 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="IstinaEndfieldAssistant_Sight — 统一 CLI v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # module 子命令
    p_mod = sub.add_parser("module", help="模块管理 (list/test/info)")
    p_mod_sub = p_mod.add_subparsers(dest="module_action", help="模块操作")
    p_mod_list = p_mod_sub.add_parser("list", help="列出所有模块")
    p_mod_list.add_argument("--json", action="store_true")
    p_mod_test = p_mod_sub.add_parser("test", help="测试模块可用性")
    p_mod_test.add_argument("name", help="模块名 (或 'all')")
    p_mod_test.add_argument("--json", action="store_true")
    p_mod_info = p_mod_sub.add_parser("info", help="查看模块详情")
    p_mod_info.add_argument("name", help="模块名")

    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "module":
        if not args.module_action:
            print("需要子命令: list, test, info")
            return 1
        route = {
            "list": cmd_module_list,
            "test": cmd_module_test,
            "info": cmd_module_info,
        }
        return route[args.module_action](args)

    # 非 module 命令：直接运行 scripts/ 下的对应脚本
    script_map = {
        "daily": "daily_pipeline.py",
        "harvest": "entity_harvest_pipeline.py",
        "analyze": "analyze_current_page.py",
        "explore": "explore_and_dailies.py",
        "config": None,  # 由 scripts/istina.py 处理
        "auth": None,
        "model": None,
        "nav": None,
        "doctor": None,
        "gpu": None,
        "system": None,
        "device": None,
        "scene": None,
    }
    script_name = script_map.get(args.command)
    if script_name:
        script_path = SCRIPTS_DIR / script_name
        if script_path.exists():
            cmd = [sys.executable, str(script_path)] + extra
            result = subprocess.run(cmd)
            return result.returncode

    # 回退：通过 python -m 直接运行 scripts/istina.py 中的函数
    # 但 scripts/istina.py 现在是薄包装，所以直接调用 core 模块
    print(f"[istina] 命令 '{args.command}' 暂未在 CLI v4 中实现")
    print(f"提示: 可直接运行 scripts/ 下的对应脚本")
    return 1


if __name__ == "__main__":
    sys.exit(main())
