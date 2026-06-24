"""分析项目模块导入关系 - 正确处理相对导入"""

import ast
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight")
SRC_DIR = PROJECT_ROOT / "src"

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

def get_package_base(module_name: str) -> str:
    """获取模块所属的一级包名（如 src.core.capability.device.adb_manager -> src.core.capability）"""
    parts = module_name.split('.')
    if len(parts) >= 3:
        return '.'.join(parts[:3])  # src.core.capability
    return module_name

def extract_imports_with_resolution(file_path: Path, current_module: str) -> Set[str]:
    """提取并解析导入语句为绝对模块名
    
    处理相对导入：from .sub import X -> 基于当前模块路径解析
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return set()
    
    imports = set()
    current_parts = current_module.split('.')
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                # 标准库或第三方库过滤
                if is_third_party_or_stdlib(module):
                    continue
                imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            # 处理 from X import Y
            if node.level == 0:
                # 绝对导入: from src.core import X
                if node.module and not is_third_party_or_stdlib(node.module):
                    imports.add(node.module)
            else:
                # 相对导入: from . import X 或 from ..sub import X
                if node.module:
                    # 有具体模块名: from .sub import X
                    relative_parts = node.module.split('.')
                    target_parts = current_parts[:-node.level] + list(relative_parts)
                    imports.add('.'.join(target_parts))
                else:
                    # 仅 from . import X (当前包)
                    target_parts = current_parts[:-node.level]
                    if target_parts:
                        imports.add('.'.join(target_parts))
    
    return imports

def is_third_party_or_stdlib(module_name: str) -> bool:
    """判断是否为第三方库或标准库"""
    third_party = {
        'PyQt6', 'PIL', 'cryptography', 'cv2', 'numpy', 'requests', 'aiohttp',
        'pynvml', 'modelscope', 'llama_cpp', 'maa', 'maafw',
        'logging', 'os', 'sys', 'json', 'time', 'typing', 'dataclasses',
        'enum', 'abc', 'collections', 'itertools', 'functools', 'pathlib',
        'subprocess', 'threading', 'asyncio', 'socket', 'select', 'struct',
        'hashlib', 'base64', 'tempfile', 'shutil', 'glob', 're', 'datetime',
        'math', 'random', 'statistics', 'inspect', 'warnings', 'traceback',
        'importlib', 'pkgutil', 'modulefinder', 'runpy', 'ctypes', 'ctypes.wintypes',
        'win32api', 'win32con', 'win32gui', 'win32process', 'win32security',
        'psutil', 'yaml', 'toml', 'configparser', 'argparse', 'getopt',
    }
    # 检查模块名是否以第三方库开头
    for lib in third_party:
        if module_name == lib or module_name.startswith(lib + '.'):
            return True
    return False

def analyze_all_imports() -> Dict:
    """分析整个项目的导入关系"""
    all_files = list(SRC_DIR.rglob("*.py"))
    
    file_to_module = {}
    import_graph = defaultdict(set)
    reverse_graph = defaultdict(set)
    
    # 第一遍：建立文件到模块的映射
    for file_path in all_files:
        module_name = get_module_name(file_path)
        file_to_module[file_path] = module_name
    
    # 第二遍：提取每个文件的导入
    for file_path in all_files:
        module_name = file_to_module[file_path]
        imports = extract_imports_with_resolution(file_path, module_name)
        
        # 过滤掉非项目内部的导入
        project_imports = set()
        for imp in imports:
            if imp.startswith('src.') or imp.startswith('istina'):
                project_imports.add(imp)
            # 检查是否是项目内部的其他模块（如从 .core 导入）
            elif '.' in imp and not is_third_party_or_stdlib(imp):
                # 尝试转换为 src. 前缀
                if imp.startswith('core.') or imp.startswith('cli.') or imp.startswith('gui.'):
                    project_imports.add(f'src.{imp}')
                elif imp.startswith('.'):
                    # 相对导入已处理，跳过
                    continue
        
        import_graph[module_name] = project_imports
        for imp in project_imports:
            reverse_graph[imp].add(module_name)
    
    return {
        'file_to_module': file_to_module,
        'import_graph': dict(import_graph),
        'reverse_graph': dict(reverse_graph),
    }

def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """使用 DFS 查找循环依赖"""
    cycles = []
    visited = set()
    stack = []
    
    def dfs(node: str):
        if node in stack:
            idx = stack.index(node)
            cycles.append(stack[idx:] + [node])
            return
        if node in visited:
            return
        
        visited.add(node)
        stack.append(node)
        
        for neighbor in graph.get(node, []):
            dfs(neighbor)
        
        stack.pop()
    
    for node in graph:
        dfs(node)
    
    return cycles

# 执行分析
print("正在分析项目导入关系（正确处理相对导入）...\n")
analysis = analyze_all_imports()
file_to_module = analysis['file_to_module']
import_graph = analysis['import_graph']
reverse_graph = analysis['reverse_graph']

print("=" * 80)
print("项目导入关系分析结果")
print("=" * 80)
print(f"总 Python 文件数: {len(analysis['file_to_module'])}")

# 统计各包的导入情况
print("\n" + "=" * 80)
print("1. 各模块出度统计（导入外部模块数）")
print("=" * 80)
coupling = {}
for module, imports in analysis['import_graph'].items():
    coupling[module] = {
        'out_degree': len(imports),
        'imports': list(imports),
    }

# 计算入度
reverse = defaultdict(set)
for module, imports in analysis['import_graph'].items():
    for imp in imports:
        reverse[imp].add(module)

for module in coupling:
    coupling[module]['in_degree'] = len(reverse.get(module, set()))

sorted_by_out = sorted(coupling.items(), key=lambda x: x[1]['out_degree'], reverse=True)
print("\n出度最高的20个模块:")
for module, data in sorted_by_out[:20]:
    print(f"  {module}:")
    print(f"    出度: {data['out_degree']}, 入度: {data['in_degree']}")
    if data['imports']:
        print(f"    导入: {', '.join(sorted(data['imports'])[:8])}")

print("\n" + "=" * 80)
print("2. 入度最高的20个模块（被最多模块导入）")
print("=" * 80)
sorted_by_in = sorted(coupling.items(), key=lambda x: x[1]['in_degree'], reverse=True)
for module, data in sorted_by_in[:20]:
    print(f"  {module}:")
    print(f"    入度: {data['in_degree']}, 出度: {data['out_degree']}")
    if data['in_degree'] > 0:
        importers = list(reverse.get(module, set()))
        print(f"    被导入: {', '.join(sorted(importers)[:8])}")

print("\n" + "=" * 80)
print("3. 循环依赖检测")
print("=" * 80)
cycles = find_cycles(analysis['import_graph'])
if cycles:
    print(f"发现 {len(cycles)} 个循环依赖:")
    for i, cycle in enumerate(cycles[:15], 1):
        print(f"\n  循环 {i}:")
        print(f"    {' -> '.join(cycle)}")
else:
    print("未发现循环依赖")

print("\n" + "=" * 80)
print("4. 关键模块分析")
print("=" * 80)

# 分析 src.core.__init__ 的实际导入情况
core_init = 'src.core.__init__'
if core_init in file_to_module.values():
    core_file = [f for f, m in file_to_module.items() if m == core_init][0]
    print(f"\n检查 {core_init} 的导入语句:")
    with open(core_file, 'r', encoding='utf-8') as f:
        content = f.read()
    print("  文件内容:")
    for line in content.split('\n')[:30]:
        print(f"    {line}")

# 分析 cloud 模块的依赖
print("\n" + "=" * 80)
print("5. Cloud 模块依赖详情")
print("=" * 80)
cloud_modules = [m for m in analysis['file_to_module'].values() if 'cloud' in m]
print(f"Cloud 相关模块总数: {len(cloud_modules)}")
for module in sorted(cloud_modules):
    imports = analysis['import_graph'].get(module, set())
    print(f"\n  {module}:")
    print(f"    出度: {len(imports)}")
    if imports:
        print(f"    导入列表: {', '.join(sorted(imports))}")

# 分析 GUI 模块对 cloud 的依赖
print("\n" + "=" * 80)
print("6. GUI 模块对 Cloud 的依赖")
print("=" * 80)
gui_modules = [m for m in analysis['file_to_module'].values() if m.startswith('src.gui')]
gui_to_cloud = []
for module in gui_modules:
    imports = analysis['import_graph'].get(module, set())
    cloud_imports = [imp for imp in imports if 'cloud' in imp]
    if cloud_imports:
        gui_to_cloud.append((module, cloud_imports))

if gui_to_cloud:
    print(f"发现 {len(gui_to_cloud)} 个 GUI 模块导入了 Cloud 模块:")
    for module, cloud_imps in gui_to_cloud:
        print(f"\n  {module}:")
        for imp in cloud_imps:
            print(f"    -> {imp}")
else:
    print("未发现 GUI 模块导入 Cloud 模块")

# 分析 capability 各子模块的依赖
print("\n" + "=" * 80)
print("7. Capability 子模块依赖分布")
print("=" * 80)
capability_submodules = {
    'device': [],
    'local_inference': [],
    'ocr': [],
    'recognition': [],
    'vlm': [],
    'screenshot': [],
    'screen_analysis': [],
    'adb_utils': [],
    'input': [],
}
for module in analysis['file_to_module'].values():
    if 'capability' in module:
        for submod in capability_submodules.keys():
            if f'capability.{submod}' in module:
                capability_submodules[submod].append(module)

for submod, modules in sorted(capability_submodules.items()):
    if modules:
        total_out = sum(coupling[m]['out_degree'] for m in modules)
        total_in = sum(coupling[m]['in_degree'] for m in modules)
        print(f"\n  capability.{submod}: {len(modules)} 个模块")
        print(f"    总出度: {total_out}, 总入度: {total_in}")
        # 找出该子模块中出度最高的
        sorted_mods = sorted(modules, key=lambda m: coupling[m]['out_degree'], reverse=True)
        top = sorted_mods[0]
        if coupling[top]['out_degree'] > 0:
            print(f"    最活跃: {top} (出度 {coupling[top]['out_degree']})")

# 生成详细报告
from datetime import datetime
report_path = PROJECT_ROOT / "IMPORT_ANALYSIS_REPORT_V2.md"
with open(report_path, 'w', encoding='utf-8') as f:
    f.write("# 模块导入关系分析报告（修正版）\n\n")
    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write("## 分析说明\n\n")
    f.write("- 使用 AST 解析所有 `.py` 文件\n")
    f.write("- 正确处理相对导入（from . import X）\n")
    f.write("- 过滤标准库和第三方库\n")
    f.write("- 仅关注项目内部模块（以 `src.` 或 `istina` 开头）\n\n")
    
    f.write("## 概览\n\n")
    f.write(f"- 总 Python 文件数: {len(analysis['file_to_module'])}\n")
    f.write(f"- 检测到循环依赖: {len(cycles)} 个\n\n")
    
    f.write("## 模块耦合度排名\n\n")
    f.write("### 出度最高的模块（依赖最多外部模块）\n\n")
    for module, data in sorted_by_out[:30]:
        f.write(f"- **{module}**: 出度={data['out_degree']}, 入度={data['in_degree']}\n")
        if data['imports']:
            f.write(f"  - 导入: {', '.join(sorted(data['imports']))}\n")
    
    f.write("\n### 入度最高的模块（被最多模块依赖）\n\n")
    for module, data in sorted_by_in[:30]:
        f.write(f"- **{module}**: 入度={data['in_degree']}, 出度={data['out_degree']}\n")
        if data['in_degree'] > 0:
            importers = list(reverse.get(module, set()))
            f.write(f"  - 被导入: {', '.join(sorted(importers))}\n")
    
    if cycles:
        f.write("\n## 循环依赖\n\n")
        for i, cycle in enumerate(cycles, 1):
            f.write(f"{i}. `{' -> '.join(cycle)}`\n")
    
    f.write("\n## 架构健康度评估\n\n")
    
    # 评估标准：
    # 1. 入度高但出度低 = 稳定基础模块（good）
    # 2. 出度高但入度低 = 高层/胶水代码（ok）
    # 3. 双向高 = 紧耦合（warning）
    # 4. 双向低 = 孤立模块（warning）
    
    f.write("### 潜在问题模块\n\n")
    for module, data in sorted_by_out[:50]:
        if data['out_degree'] > 5 and data['in_degree'] > 5:
            f.write(f"- **{module}**: 双向高耦合（入度={data['in_degree']}, 出度={data['out_degree']}）\n")
    
    f.write("\n### 高入度基础模块（稳定层）\n\n")
    for module, data in sorted_by_in[:20]:
        if data['in_degree'] > 5 and data['out_degree'] < 3:
            f.write(f"- **{module}**: 入度={data['in_degree']}, 出度={data['out_degree']} （基础服务层）\n")
    
    f.write("\n### 高出度胶水模块（协调层）\n\n")
    for module, data in sorted_by_out[:20]:
        if data['out_degree'] > 8 and data['in_degree'] < 3:
            f.write(f"- **{module}**: 出度={data['out_degree']}, 入度={data['in_degree']} （协调/入口模块）\n")

print(f"\n详细报告已保存至: {report_path}")
