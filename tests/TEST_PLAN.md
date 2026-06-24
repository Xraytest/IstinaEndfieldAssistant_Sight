# IEA 本地版测试方案

## 测试范围

### 1. 核心模块测试
- [ ] LocalElementAnalyzer - 本地元素分析器
- [ ] LocalAgentExecutor - 本地 Agent 执行器
- [ ] LocalLogManager - 本地日志管理器
- [ ] adb_utils.vlm_analyze() - VLM 分析接口

### 2. CLI 命令测试
- [ ] system doctor - 系统诊断
- [ ] system env - 环境变量检查
- [ ] system disk - 磁盘使用情况
- [ ] system perf - 性能测试
- [ ] scene capture - 场景采集
- [ ] scene nav - 导航到页面
- [ ] scene analyze - VLM 分析画面
- [ ] scene ocr - OCR 检测

### 3. 配置测试
- [ ] client_config.json 加载
- [ ] 推理模式配置
- [ ] 设备配置

### 4. 依赖检查
- [ ] 无云端依赖导入错误
- [ ] InferenceManager 正常初始化
- [ ] 本地推理引擎可用

## 测试环境要求

- Python 3.10+
- Windows 10/11
- ADB 模拟器（localhost:16512）
- 配置文件已创建

## 测试顺序

1. 依赖检查 → 2. 配置测试 → 3. 核心模块 → 4. CLI 命令 → 5. 集成测试
