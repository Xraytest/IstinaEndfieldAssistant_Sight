#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
IstinaEndfieldAssistant_Sight 鈥?缁熶竴 CLI 鍏ュ彛 v4

钖勮矾鐢卞眰锛屽皢鍚勫瓙鍛戒护濮旀墭缁欓鍩熶笓鐢ㄧ殑 CLI 妯″潡 (src/cli/) 鎴栨牳蹇冩ā鍧椼€?
鐢ㄦ硶:
  python -m src.cli.istina <command> [args]

瀛愬懡浠?
  module list                    # 鍒楀嚭鎵€鏈夋ā鍧?  module test <name>             # 娴嬭瘯鍗曚釜妯″潡鍙敤鎬?  module test all                # 娴嬭瘯鎵€鏈夋ā鍧?  module info <name>             # 鏌ョ湅妯″潡璇︽儏
"""

import sys
import os
import json
import argparse
import subprocess
import importlib
from pathlib import Path
from typing import Optional, Dict, Any, List

# 鈹€鈹€ 璺緞璁剧疆 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# 鈹€鈹€ 妯″潡娓呭崟锛堣嚜鍔ㄥ彂鐜帮級 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _discover_modules() -> Dict[str, Dict]:
    """鎵弿 core/*/ 涓嬬殑瀛愬寘锛岃繑鍥?{妯″潡鍚? {layer, path, exports}}"""
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
    """妫€鏌ユā鍧楀彲鐢ㄦ€?""
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
        result["details"]["import_error"] = f"妯″潡 '{module_name}' 鏈壘鍒?
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


# 鈹€鈹€ 妯″潡瀛愬懡浠?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def cmd_module_list(args):
    modules = _discover_modules()
    if args.json:
        print(json.dumps(modules, ensure_ascii=False, indent=2))
        return 0
    print(f"\n{'妯″潡鍚?:<20} {'灞傜骇':<15} {'瀵煎嚭绗﹀彿鏁?:<10}")
    print("-" * 50)
    for name, info in sorted(modules.items()):
        print(f"{name:<20} {info['layer']:<15} {len(info['exports']):<10}")
    print(f"\n鍏?{len(modules)} 涓ā鍧?)
    return 0


def cmd_module_test(args):
    if args.name == "all":
        modules = _discover_modules()
        all_ok = True
        for name in sorted(modules.keys()):
            result = _check_module_available(name)
            status = "鉁? if result["available"] else "鉁?
            print(f"{status} {name:<20} [{result['layer']:<12}]")
            if not result["available"]:
                all_ok = False
                for check, ok in result["checks"].items():
                    if not ok:
                        detail = result["details"].get(f"{check}_error") or "unknown"
                        print(f"    鈹斺攢 {check}: FAIL ({detail})")
        print(f"\n{'='*40}")
        print(f"鎬讳綋: {'鍏ㄩ儴閫氳繃' if all_ok else '瀛樺湪涓嶅彲鐢ㄦā鍧?}")
        return 0 if all_ok else 1
    else:
        result = _check_module_available(args.name)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            status = "鉁? if result["available"] else "鉁?
            print(f"{status} {result['module']:<20} [{result['layer']:<12}]")
            if not result["available"]:
                for check, ok in result["checks"].items():
                    if not ok:
                        detail = result["details"].get(f"{check}_error") or "unknown"
                        print(f"    鈹斺攢 {check}: FAIL ({detail})")
        return 0 if result["available"] else 1


def cmd_module_info(args):
    modules = _discover_modules()
    if args.name not in modules:
        print(f"妯″潡 '{args.name}' 鏈壘鍒?)
        return 1
    info = modules[args.name]
    print(f"\n妯″潡: {args.name}")
    print(f"灞傜骇: {info['layer']}")
    print(f"璺緞: {info['path']}")
    print(f"瀵煎嚭绗﹀彿 ({len(info['exports'])}):")
    for exp in info["exports"]:
        print(f"  - {exp}")
    return 0


# 鈹€鈹€ CLI 瑙ｆ瀽 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    parser = argparse.ArgumentParser(
        description="IstinaEndfieldAssistant_Sight 鈥?缁熶竴 CLI v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="瀛愬懡浠?)

    # module 瀛愬懡浠?    p_mod = sub.add_parser("module", help="妯″潡绠＄悊 (list/test/info)")
    p_mod_sub = p_mod.add_subparsers(dest="module_action", help="妯″潡鎿嶄綔")
    p_mod_list = p_mod_sub.add_parser("list", help="鍒楀嚭鎵€鏈夋ā鍧?)
    p_mod_list.add_argument("--json", action="store_true")
    p_mod_test = p_mod_sub.add_parser("test", help="娴嬭瘯妯″潡鍙敤鎬?)
    p_mod_test.add_argument("name", help="妯″潡鍚?(鎴?'all')")
    p_mod_test.add_argument("--json", action="store_true")
    p_mod_info = p_mod_sub.add_parser("info", help="鏌ョ湅妯″潡璇︽儏")
    p_mod_info.add_argument("name", help="妯″潡鍚?)

    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "module":
        if not args.module_action:
            print("闇€瑕佸瓙鍛戒护: list, test, info")
            return 1
        route = {
            "list": cmd_module_list,
            "test": cmd_module_test,
            "info": cmd_module_info,
        }
        return route[args.module_action](args)

    # 闈?module 鍛戒护锛氱洿鎺ヨ繍琛?scripts/ 涓嬬殑瀵瑰簲鑴氭湰
    script_map = {
        "daily": "daily_pipeline.py",
        "harvest": "entity_harvest_pipeline.py",
        "analyze": "analyze_current_page.py",
        "explore": "explore_and_dailies.py",
        "config": None,  # 鐢?scripts/istina.py 澶勭悊
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
            result = subprocess.run(cmd, timeout=300)
            return result.returncode

    # 鍥為€€锛氶€氳繃 python -m 鐩存帴杩愯 scripts/istina.py 涓殑鍑芥暟
    # 浣?scripts/istina.py 鐜板湪鏄杽鍖呰锛屾墍浠ョ洿鎺ヨ皟鐢?core 妯″潡
    print(f"[istina] 鍛戒护 '{args.command}' 鏆傛湭鍦?CLI v4 涓疄鐜?)
    print(f"鎻愮ず: 鍙洿鎺ヨ繍琛?scripts/ 涓嬬殑瀵瑰簲鑴氭湰")
    return 1


if __name__ == "__main__":
    sys.exit(main())

