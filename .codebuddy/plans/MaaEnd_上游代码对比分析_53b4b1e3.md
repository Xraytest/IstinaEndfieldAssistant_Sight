---
name: MaaEnd 上游代码对比分析
overview: 联网拉取 MaaEnd 上游最新版（GitHub MaaEnd/MaaEnd 的 v2 分支），与当前 IstinaEndfieldAssistant_Sight（基于 MaaEnd 的 Python 二次开发版）在架构、功能、模块三个层面做全面对比，并在对话中给出总结（不写报告文件）。
todos:
  - id: fetch-upstream
    content: 确认上游 MaaEnd 仓库地址并浅克隆最新 v2 到工作区外临时目录
    status: completed
  - id: map-current
    content: 使用 [subagent:code-explorer] 梳理当前 Python/PyQt6 项目架构与模块边界
    status: completed
  - id: map-upstream
    content: 使用 [subagent:code-explorer] 梳理上游 MaaEnd(Go+TS) 架构、模块边界与功能清单
    status: completed
    dependencies:
      - fetch-upstream
  - id: compare-features
    content: 构建功能矩阵，对比已实现/缺失/新增能力
    status: completed
    dependencies:
      - map-current
      - map-upstream
  - id: compare-modules
    content: 逐模块深度对比（设备/识别/导航/任务管线/GUI/CLI）
    status: completed
    dependencies:
      - map-current
      - map-upstream
  - id: summarize
    content: 在对话中给出架构+功能+模块全面对比总结
    status: completed
    dependencies:
      - compare-features
      - compare-modules
---

## 用户需求

阅读 MaaEnd 样例代码（上游 GitHub 仓库 `https://github.com/MaaEnd/MaaEnd`，默认分支 `v2`），与当前项目 `IstinaEndfieldAssistant_Sight`（基于 MaaEnd 二次开发的 Python/PyQt6 助手）做全面对比，涵盖架构、功能、模块三个层面，并在对话中给出总结（不生成报告文件）。

## 产品概述

一次面向「二次开发项目 vs 上游样例」的代码调研与差异分析。当前项目为 Python/PyQt6 技术栈，上游 MaaEnd 为 Go + TypeScript + MaaFramework JSON 任务管线的技术栈，二者语言不同，因此对比为架构/功能/概念层面，而非逐文件文本 diff。上游代码应拉取到工作区外临时目录，避免污染当前仓库、不覆盖既有 `MaaEnd/` 快照。

## 核心内容

- 确认上游最新仓库地址与默认分支，拉取最新版到临时目录。
- 梳理双方架构与模块边界。
- 功能清单对比：当前已实现、缺失、相对上游新增。
- 逐模块深度对比（设备控制/识别/导航/任务管线/GUI/CLI）。
- 在对话中输出综合对比总结。

## 技术栈与对比方法

- 当前项目：Python 3.12 + PyQt6 + MaaFramework 运行时封装（`src/core/service/maa_end/runtime.py`），分层架构 `core`（foundation/capability/service）/ `gui` / `cli`，强调 VLM/LLM 视觉推理、大世界路径指引与异常纠错。
- 上游 MaaEnd：Go（`agent/go-service` 核心引擎）、TypeScript（`tools/` 工具链 maa-tools/pipeline-generate）、MaaFramework JSON 任务管线（`assets/resource/pipeline/`）、MXU，覆盖面极广的自动化功能集。

## 实现方法

1. **获取上游**：使用 `git clone --depth 1 --branch v2 --filter=blob:none https://github.com/MaaEnd/MaaEnd.git <工作区外临时目录>` 做部分克隆，限制下载体积；仅读取分析所需文件（README、docs、agent 结构、pipeline 结构、tools、config），不引入本仓库。
2. **架构映射**：以 CLAUDE.md / docs 为基准梳理当前项目分层与模块边界；以 README、docs、目录结构为基准梳理上游分层与模块边界，产出「能力域 → 模块」映射表。
3. **功能矩阵**：基于上游 README 功能一览 + 当前 CLI subcommands + docs，构建「功能点 → 上游是否具备 / 当前是否具备 / 当前新增」三态矩阵。
4. **模块级 diff**：对设备控制、识别、导航、任务管线、GUI、CLI 六个域分别对比实现方式与能力差异。
5. **差异归因**：区分「语言/架构导致的形态差异」与「实际功能缺口/新增增强」。

## 执行注意事项

- 克隆目标必须位于工作区之外（如 `c:/Users/cheng/Documents/ArkStudio/IstinaAI/maaend_upstream_temp`），禁止写入当前仓库、禁止覆盖 `MaaEnd/` 快照，保持 git 工作树干净。
- 对比为概念性，不执行任何代码改动、不提交、不推送。
- 上游体量较大，优先用部分克隆与目录浏览，避免全量下载二进制资源（assets/*.png）。
- 结论聚焦可验证事实：以双方实际文件/文档为依据，不臆测未读代码。

## 架构设计

```
上游 MaaEnd (Go/TS/MaaFW)         当前 Istina (Python/PyQt6)
┌─────────────────────┐          ┌─────────────────────┐
│ agent/go-service    │          │ src/core/service    │
│ tools/ (TS maa-tools)│  <──参照──│ src/core/capability │
│ assets/resource/pipe│          │ src/gui/pyqt6       │
│ config/ + docs/     │          │ src/cli + config/   │
└─────────────────────┘          └─────────────────────┘
        ↑ 接口/任务定义/资源样例的二次开发来源
```

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 克隆并浏览上游 MaaEnd 仓库、梳理当前项目源码结构，跨多目录完成大范围代码探索。
- Expected outcome: 产出上游与当前的架构/模块边界、功能清单与逐模块差异的可验证事实，支撑对话总结。