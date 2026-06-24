# IEA 服务端依赖完整清单

> 生成时间：2026-06-14  
> 目标：完全移除 IstinaPlatform 服务端依赖

---

## 一、核心依赖文件

### 1.1 通信层

| 文件 | 依赖类型 | 说明 |
|------|---------|------|
| `src/core/communication/communicator.py` | **核心** | TCP/Fernet通信实现 |
| `src/core/communication/__init__.py` | 导出 | 导出 ClientCommunicator |

### 1.2 认证层

| 文件 | 依赖类型 | 说明 |
|------|---------|------|
| `src/core/cloud/managers/auth_manager.py` | **核心** | 云端认证管理 |
| `src/core/cloud/managers/__init__.py` | 导出 | 导出 AuthManager |
| `src/core/cloud/__init__.py` | 导出 | 导出 AuthManager |

---

## 二、使用 ClientCommunicator 的文件（83 处）

### 2.1 GUI 入口

| 文件 | 行数 | 用途 | 改造方式 |
|------|------|------|---------|
| `src/gui/pyqt6/main.py` | 28, 144, 164 | 初始化通信器、认证管理器 | 使用 LocalVLMClient + LocalAuthManager |
| `src/gui/pyqt6/main_window.py` | - | 认证页面、自动登录 | 移除认证页面，直接显示主界面 |
| `src/gui/pyqt6/app_main.py` | 214, 217 | 文档中提到通信器和认证 | 更新文档 |

### 2.2 GUI 页面

| 文件 | 行数 | 用途 | 改造方式 |
|------|------|------|---------|
| `src/gui/pyqt6/pages/prts_full_intelligence_page.py` | 443 | VLM 分析 | 使用 LocalVLMClient |
| `src/gui/pyqt6/pages/iea_page.py` | 66 | 发送请求 | 使用 LocalVLMClient |
| `src/gui/pyqt6/pages/auth_page.py` | - | 认证页面 | **删除或禁用** |
| `src/gui/pyqt6/pages/cloud_page.py` | - | 云端推理页面 | **删除或禁用** |

### 2.3 核心模块

| 文件 | 行数 | 用途 | 改造方式 |
|------|------|------|---------|
| `src/core/element_analysis/element_analyzer.py` | 219 | VLM 元素分析 | 使用 LocalVLMClient |
| `src/core/local_inference/inference_manager.py` | 737 | 云端推理降级 | **移除云端降级** |
| `src/core/device_state_manager.py` | 63, 175 | 设备状态分析 | 使用 LocalVLMClient |

### 2.4 云端模块

| 文件 | 行数 | 用途 | 改造方式 |
|------|------|------|---------|
| `src/core/cloud/agent_executor.py` | 184 | Agent 执行 | 使用 LocalVLMClient |
| `src/core/cloud/exploration_engine.py` | 237 | 探索引擎 | 使用 LocalVLMClient |
| `src/core/cloud/realtime_combat_controller.py` | 63 | 战斗控制 | 使用 LocalVLMClient |

### 2.5 CLI 工具

| 文件 | 行数 | 用途 | 改造方式 |
|------|------|------|---------|
| `scripts/istina.py` | 107-108, 347-348, 485-486 | 认证、GPU 检测 | 移除认证命令，GPU 检测用本地 |
| `src/cli/system_cli.py` | 46-47, 262-263 | 系统诊断 | 移除服务端相关 |
| `src/cli/scenario_cli.py` | 56-57 | 场景采集 | 使用 LocalVLMClient |

### 2.6 ADB 工具

| 文件 | 行数 | 用途 | 改造方式 |
|------|------|------|---------|
| `src/core/adb_utils.py` | 161-164 | 远程截图 | **移除远程截图** |

### 2.7 脚本文件

| 文件 | 用途 | 改造方式 |
|------|------|---------|
| `scripts/daily_pipeline.py` | 每日流水线 | 使用 LocalVLMClient |
| `scripts/explore_game.py` | 游戏探索 | 使用 LocalVLMClient |
| `scripts/explore_tasks.py` | 任务探索 | 使用 LocalVLMClient |
| `scripts/analyze_tasks.py` | 任务分析 | 使用 LocalVLMClient |
| `scripts/find_tasks.py` | 查找任务 | 使用 LocalVLMClient |
| `scripts/navigate_to_game.py` | 导航到游戏 | 使用 LocalVLMClient |
| `scripts/explore_and_dailies.py` | 探索和每日 | 使用 LocalVLMClient |
| `scripts/run_daily_adaptive.py` | 自适应每日 | 使用 LocalVLMClient |
| `scripts/debug_vlm.py` | VLM 调试 | 使用 LocalVLMClient |
| `scripts/debug_vlm2.py` | VLM 调试 2 | 使用 LocalVLMClient |
| `scripts/debug_models.py` | 模型调试 | **删除或禁用** |
| `scripts/discover_models.py` | 发现模型 | **删除或禁用** |
| `scripts/tools/check_models.py` | 检查模型 | **删除或禁用** |
| `scripts/pipelines/recovery.py` | 恢复流程 | 使用 LocalVLMClient |
| `scripts/pipelines/navigate_dailies.py` | 导航每日 | 使用 LocalVLMClient |
| `._vlm_helper.py` | VLM 辅助 | **删除** |

---

## 三、改造优先级

### P0 - 核心路径（必须修改）

1. `src/gui/pyqt6/main.py` - GUI 入口
2. `src/gui/pyqt6/main_window.py` - 主窗口
3. `src/core/communication/communicator.py` - 通信器（替换为 LocalVLMClient）
4. `src/core/cloud/managers/auth_manager.py` - 认证管理器（替换为 LocalAuthManager）
5. `src/core/local_inference/inference_manager.py` - 推理管理器（移除云端降级）
6. `src/core/element_analysis/element_analyzer.py` - 元素分析器

### P1 - 主要功能（建议修改）

7. `src/core/device_state_manager.py` - 设备状态管理
8. `src/core/cloud/agent_executor.py` - Agent 执行器
9. `src/core/cloud/exploration_engine.py` - 探索引擎
10. `scripts/istina.py` - CLI 入口
11. `scripts/daily_pipeline.py` - 每日流水线

### P2 - 辅助功能（可选修改）

12. `src/cli/system_cli.py` - 系统 CLI
13. `src/cli/scenario_cli.py` - 场景 CLI
14. `src/core/adb_utils.py` - ADB 工具（移除远程截图）
15. GUI 页面：`auth_page.py`, `cloud_page.py`（禁用）

### P3 - 调试脚本（可删除）

- 所有 `scripts/debug_*.py`
- 所有 `scripts/tools/check_models.py`
- `._vlm_helper.py`

---

## 四、改造策略

### 策略 A：完全移除（推荐用于分支）

```bash
# 删除文件
rm src/core/communication/communicator.py
rm src/core/cloud/managers/auth_manager.py
rm src/gui/pyqt6/pages/auth_page.py
rm src/gui/pyqt6/pages/cloud_page.py

# 修改导入
# 将所有 from ...communicator import ClientCommunicator
# 改为 from ...local_vlm_client import LocalVLMClient
```

### 策略 B：条件化保留（推荐用于主分支）

```python
# 在 communicator.py 中添加
class ClientCommunicator:
    def __init__(self, config: dict):
        self.mode = config.get("mode", "local_only")
        
        if self.mode == "local_only":
            # 使用本地实现
            self._client = LocalVLMClient(...)
        else:
            # 使用云端实现
            self._socket = socket.socket(...)
    
    def send_request(self, endpoint, data):
        if self.mode == "local_only":
            return self._client.send_request(endpoint, data)
        else:
            # 原有 TCP 逻辑
```

### 策略 C：配置驱动（最灵活）

```python
# 创建工厂函数
def create_communicator(config: dict):
    """根据配置创建通信器"""
    mode = config.get("mode", "local_only")
    
    if mode == "local_only":
        return LocalVLMClient(config)
    elif mode == "hybrid":
        return HybridCommunicator(config)
    else:
        return ClientCommunicator(config)
```

---

## 五、详细改造步骤

### 步骤 1：创建本地组件

```bash
# 创建本地 VLM 客户端
touch src/core/communication/local_vlm_client.py

# 创建本地认证管理器
touch src/core/cloud/managers/local_auth_manager.py
```

### 步骤 2：修改核心模块

```python
# src/core/local_inference/inference_manager.py
# 移除 _process_image_cloud 方法
# 修改 process_image 方法，仅使用本地推理
```

### 步骤 3：修改 GUI

```python
# src/gui/pyqt6/main.py
# 替换导入
from core.communication.local_vlm_client import LocalVLMClient
from core.cloud.managers.local_auth_manager import LocalAuthManager

# 替换初始化
llama_client = LocalVLMClient(config)
auth_manager = LocalAuthManager()
```

### 步骤 4：修改脚本

```python
# scripts/*.py
# 批量替换
# ClientCommunicator(...) → LocalVLMClient(config)
# communicator.send_request(...) → llama_client.send_request(...)
```

### 步骤 5：清理调试脚本

```bash
# 删除或移动调试脚本
mv scripts/debug_*.py scripts/debug_archived/
mv scripts/tools/check_models.py scripts/tools/archived/
```

---

## 六、验证清单

### 6.1 启动测试

- [ ] GUI 正常启动，无认证页面
- [ ] llama-server 检测正常
- [ ] 所有页面可访问

### 6.2 功能测试

- [ ] 元素分析功能正常
- [ ] 标准流执行正常
- [ ] ADB 设备控制正常
- [ ] 截图功能正常

### 6.3 集成测试

- [ ] `standard_flow_engine.py --flow daily_quest` 正常
- [ ] `istina.py device status` 正常
- [ ] `istina.py analyze` 正常

---

## 七、文件修改统计

| 类别 | 文件数 | 修改量 |
|------|-------|--------|
| **新建** | 3 | ~500 行 |
| **修改** | 20+ | ~2000 行 |
| **删除** | 5+ | ~1000 行 |
| **总计** | 28+ | ~3500 行 |

---

## 八、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 遗漏依赖 | 中 | 高 | 使用 grep 全面搜索 |
| 导入错误 | 高 | 中 | 全面测试所有入口 |
| 配置错误 | 中 | 中 | 提供默认配置文件 |
| 功能缺失 | 低 | 高 | 保留云端降级选项 |

---

## 九、回退方案

```bash
# Git 分支管理
git checkout -b local-only
# 进行改造...

# 如果出现问题，切换回主分支
git checkout main
```

---

## 十、总结

本清单列出了所有 83 处服务端依赖，按优先级分类，提供三种改造策略。

**推荐方案**：
1. 核心路径使用策略 A（完全移除）
2. 辅助功能使用策略 B（条件化保留）
3. 调试脚本直接删除

**预计工作量**：4-8 小时（含测试）
