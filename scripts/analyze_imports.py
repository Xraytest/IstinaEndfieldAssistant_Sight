"""分析项目模块导入关系"""

import ast
import os
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight")
SRC_DIR = PROJECT_ROOT / "src"

def extract_imports(file_path: Path) -> Tuple[Set[str], Set[str]]:
    """提取文件中的导入语句
    
    Returns:
        (绝对导入集合, 相对导入集合)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return set(), set()
    
    absolute_imports = set()
    relative_imports = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module.startswith('src.') or module.startswith('istina'):
                    absolute_imports.add(module)
                elif not module.startswith(('PyQt6', 'cryptography', 'PIL', 'cv2', 'numpy', 'requests', 'aiohttp', 'logging', 'os', 'sys', 'json', 'time', 'typing', 'dataclasses', 'enum', 'abc', 'collections', 'itertools', 'functools', 'pathlib', 'subprocess', 'threading', 'asyncio')):
                    # 可能是项目内部模块但未使用 src. 前缀
                    if '.' in module:
                        absolute_imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # 处理 from X import Y
                if node.module.startswith('src.') or node.module.startswith('istina'):
                    absolute_imports.add(node.module)
                elif node.level == 0 and node.module and not node.module.startswith(('PyQt6', 'cryptography', 'PIL', 'cv2', 'numpy', 'requests', 'aiohttp', 'logging', 'os', 'sys', 'json', 'time', 'typing', 'dataclasses', 'enum', 'abc', 'collections', 'itertools', 'functools', 'pathlib', 'subprocess', 'threading', 'asyncio')):
                    absolute_imports.add(node.module)
                elif node.level > 0:
                    # 相对导入
                    relative_imports.add(f".{node.module}" if node.module else ".")
    
    return absolute_imports, relative_imports

def get_module_name(file_path: Path) -> str:
    """从文件路径获取模块名（如 src.core.capability.device.adb_manager）"""
    rel_path = file_path.relative_to(PROJECT_ROOT)
    parts = list(rel_path.parts)
    # 去掉 .py 后缀
    if parts[-1].endswith('.__init__.py'):
        parts[-1] = parts[-1].replace('.__init__.py', '')
    elif parts[-1].endswith('.py'):
        parts[-1] = parts[-1][:-3]
    return '.'.join(parts)

def analyze_imports() -> Dict[str, Dict]:
    """分析整个项目的导入关系"""
    all_files = list(SRC_DIR.rglob("*.py"))
    
    # 构建导入图
    import_graph = defaultdict(set)  # module -> set(imported_modules)
    reverse_graph = defaultdict(set)  # imported_module -> set(modules that import it)
    
    file_to_module = {}
    for file_path in all_files:
        module_name = get_module_name(file_path)
        file_to_module[file_path] = module_name
    
    for file_path in all_files:
        module_name = file_to_module[file_path]
        abs_imports, rel_imports = extract_imports(file_path)
        
        for imp in abs_imports:
            import_graph[module_name].add(imp)
            reverse_graph[imp].add(module_name)
        
        # 处理相对导入：转换为绝对模块名
        for rel_imp in rel_imports:
            # 简单处理：基于当前模块路径
            if rel_imp == ".":
                # 导入同包的其他模块（需要从 __init__.py 推断）
                continue
            # 这里简化处理，实际需要更精确的包路径计算
            pass
    
    return {
        'file_to_module': file_to_module,
        'import_graph': dict(import_graph),
        'reverse_graph': dict(reverse_graph),
    }

def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """使用 DFS 查找循环依赖"""
    visited = set()
    stack = []
    cycles = []
    
    def dfs(node: str, path: List[str]):
        if node in stack:
            # 发现循环
            cycle_start = stack.index(node)
            cycle = stack[cycle_start:] + [node]
            cycles.append(cycle)
            return
        
        if node in visited:
            return
        
        visited.add(node)
        stack.append(node)
        
        for neighbor in graph.get(node, []):
            dfs(neighbor, path.copy())
        
        stack.pop()
    
    for node in graph:
        dfs(node, [])
    
    return cycles

def analyze_coupling(graph: Dict[str, Set[str]]) -> Dict[str, Dict]:
    """分析模块耦合度"""
    coupling = {}
    for module, imports in graph.items():
        coupling[module] = {
            'out_degree': len(imports),
            'imports': list(imports),
        }
    
    # 计算入度
    reverse = defaultdict(set)
    for module, imports in graph.items():
        for imp in imports:
            reverse[imp].add(module)
    
    for module in coupling:
        coupling[module]['in_degree'] = len(reverse.get(module, set()))
    
    return coupling

# 执行分析
print("正在分析项目导入关系...\n")
analysis = analyze_imports()

print("=" * 80)
print("项目结构概览")
print("=" * 80)
print(f"总 Python 文件数: {len(analysis['file_to_module'])}")
print(f"根模块数: {len(analysis['file_to_module'])}")

# 按包分组
packages = defaultdict(list)
for file_path, module in analysis['file_to_module'].items():
    parts = module.split('.')
    if len(parts) > 3:
        pkg = '.'.join(parts[:4])  # src.core.capability.device
    else:
        pkg = module
    packages[pkg].append(module)

print("\n主要包结构:")
for pkg in sorted(packages.keys())[:20]:
    print(f"  {pkg}: {len(packages[pkg])} 个模块")

print("\n" + "=" * 80)
print("导入关系分析")
print("=" * 80)

# 找出导入最多的模块（高入度）
coupling = analyze_coupling(analysis['import_graph'])
sorted_by_in = sorted(coupling.items(), key=lambda x: x[1]['in_degree'], reverse=True)
print("\n入度最高的模块（被最多模块导入）:")
for module, data in sorted_by_in[:15]:
    print(f"  {module}: in_degree={data['in_degree']}, out_degree={data['out_degree']}")

# 找出导出最多的模块（高出度）
sorted_by_out = sorted(coupling.items(), key=lambda x: x[1]['out_degree'], reverse=True)
print("\n出度最高的模块（导入最多外部模块）:")
for module, data in sorted_by_out[:15]:
    print(f"  {module}: out_degree={data['out_degree']}, in_degree={data['in_degree']}")
    if data['imports']:
        print(f"    导入: {', '.join(list(data['imports'])[:5])}")

# 检查循环依赖
print("\n" + "=" * 80)
print("循环依赖检测")
print("=" * 80)
cycles = find_cycles(analysis['import_graph'])
if cycles:
    print(f"发现 {len(cycles)} 个循环依赖:")
    for i, cycle in enumerate(cycles[:10], 1):
        print(f"\n循环 {i}: {' -> '.join(cycle)}")
else:
    print("未发现循环依赖")

# 检查 src/core/__init__.py 的导入爆炸问题
print("\n" + "=" * 80)
print("核心问题检查: src/core/__init__.py 导入爆炸")
print("=" * 80)
core_init_module = 'src.core'
if core_init_module in analysis['import_graph']:
    core_imports = analysis['import_graph'][core_init_module]
    print(f"src.core 导入了 {len(core_imports)} 个模块:")
    for imp in sorted(core_imports):
        print(f"  - {imp}")
else:
    print("src.core 未找到导入关系（可能是未分析相对导入）")

# 检查 cloud 模块的依赖情况
print("\n" + "=" * 80)
print("Cloud 模块依赖分析")
print("=" * 80)
cloud_modules = [m for m in analysis['file_to_module'].values() if 'cloud' in m]
print(f"Cloud 相关模块数: {len(cloud_modules)}")
for module in sorted(cloud_modules):
    imports = analysis['import_graph'].get(module, set())
    print(f"\n{module}:")
    print(f"  导入 {len(imports)} 个外部模块")
    if imports:
        print(f"    {', '.join(sorted(list(imports))[:8])}")

# 保存详细报告
report_path = PROJECT_ROOT / "IMPORT_ANALYSIS_REPORT.md"
with open(report_path, 'w', encoding='utf-8') as f:
    f.write("# 模块导入关系分析报告\n\n")
    f.write(f"生成时间: {os.path.datetime.now().isoformat()}\n\n")
    f.write("## 概览\n\n")
    f.write(f"- 总 Python 文件数: {len(analysis['file_to_module'])}\n")
    f.write(f"- 检测到循环依赖: {len(cycles)} 个\n\n")
    
    f.write("## 入度最高的模块（被最多模块导入）\n\n")
    for module, data in sorted_by_in[:20]:
        f.write(f"- **{module}**: in_degree={data['in_degree']}, out_degree={data['out_degree']}\n")
    
    f.write("\n## 出度最高的模块（导入最多外部模块）\n\n")
    for module, data in sorted_by_out[:20]:
        f.write(f"- **{module}**: out_degree={data['out_degree']}, in_degree={data['in_degree']}\n")
        if data['imports']:
            f.write(f"  - 导入: {', '.join(sorted(list(data['imports']))[:10])}\n")
    
    if cycles:
        f.write("\n## 循环依赖列表\n\n")
        for i, cycle in enumerate(cycles, 1):
            f.write(f"{i}. `{' -> '.join(cycle)}`\n")
    
    f.write("\n## 详细导入图（前50个模块）\n\n")
    for module in sorted(coupling.keys())[:50]:
        data = coupling[module]
        f.write(f"### {module}\n")
        f.write(f"- 入度: {data['in_degree']}, 出度: {data['out_degree']}\n")
        if data['imports']:
            f.write(f"- 导入: `{', '.join(sorted(list(data['imports']))) }`\n")
        f.write("\n")

print(f"\n详细报告已保存至: {report_path}")
