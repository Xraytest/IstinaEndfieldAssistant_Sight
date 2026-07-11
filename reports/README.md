# reports/ — 分析报告索引

> 本目录存放一次性分析 / 审计 / 事故报告（区别于 `docs/` 的长期参考文档）。
> 按主题分子目录管理；状态用于标识是否仍具参考效力，阅读前先查本表。

## 目录结构

| 子目录 | 用途 |
|--------|------|
| `audits/` | 全代码库 / 专项审计（漏洞、质量基线、命名、文档差异、commit 审计） |
| `incidents/` | 单次故障根因分析（任务/预设列表、标准页清空、队列持久化、DailyFull 执行） |
| `implementation/` | 修复 / 测试实施记录（含从 `docs/` 迁入的清理记录） |
| `analysis/` | 深度算法 / 专题分析 |
| `reference/` | 生成物（非叙述，如函数表） |
| `auto/` | 自动周期审查（由工具生成，不手工维护） |
| `archive/` | 已被取代、仅作历史留存 |

## 报告状态表

### audits/
| 报告 | 状态 | 说明 |
|------|------|------|
| comprehensive_vulnerability_ux_report_2026-07-09.md | Active | IEA 全量静态审计（127 问题） |
| comprehensive_audit_agent_swarm_176.md | Active | IEA + MaaEnd 全代码库 176 代理审计 |
| code_quality_baseline_and_antipattern_audit.md | Active | 代码规范基线 + 反模式审计 |
| commit_audit_120_report.md | Active | 最近 120 commit 审计 |
| function_naming_anomalies_report.md | Active | 函数命名与实现匹配度（已处理 16 处） |
| docs_vs_code_discrepancy_report.md | Active | 文档 vs 代码差异（最新，2026-07-10） |

### incidents/
| 报告 | 状态 | 说明 |
|------|------|------|
| preset_list_regression_deep_analysis_2026-07-10.md | Active（最终根因） | 任务/预设列表复发：`system connect` 致 CLI 子进程崩溃 |
| standard_reasoning_page_clear_analysis.md | Active | 标准推理页内容被清空根因 |
| queue_persistence_analysis.md | Active | 队列未持久化分析 |
| daily_full_preset_execution_analysis_2026-07-10.md | Active | DailyFull 执行与正确性分析 |
| task_preset_list_display_fix_report.md | Superseded | 首次修复记录，后被复发推翻 |
| task_preset_list_not_displaying_analysis.md | Superseded | 早期根因假设（错误） |
| preset_list_regression_analysis_2026-07-10.md | Superseded | os.write 短写假设（错误） |

### implementation/
| 报告 | 状态 | 说明 |
|------|------|------|
| modification_implementation_report.md | Active | IEA 执行算法 21 项建议实施 |
| test_report_2026-07-07.md | Active | 测试执行报告 |
| gui_test_module_split_strategy.md | Active | GUI 测试拆分策略（零 Mock） |
| gui_test_module_split_breakpoint_diagnosis.md | Active | GUI 测试拆分断点诊断 |
| CODE_QUALITY_AND_CLEANUP.md | Active | 死代码 / 孤立代码清理记录（自 `docs/` 迁入） |

### analysis/
| 报告 | 状态 | 说明 |
|------|------|------|
| iea_execution_algorithm_analysis.md | Active | IEA 执行算法全链路分析 |

### reference/
| 报告 | 状态 | 说明 |
|------|------|------|
| function_table.md | Active | 函数清单（生成物） |

### auto/
| 报告 | 状态 | 说明 |
|------|------|------|
| （已清空） | Cleared | ~101 份自动报告已消化，总结见 `AUTO_ANALYSIS_SUMMARY_2026-07-12.md` + `CODE_REVIEW_WARNS.md` |

### archive/
| 报告 | 状态 | 说明 |
|------|------|------|
| code_doc_diff_report_2026-07-08.md | Archived | 已被 `audits/docs_vs_code_discrepancy_report.md` 取代 |

## 阅读建议

- 想了解文档与代码现状：先读 `audits/docs_vs_code_discrepancy_report.md`。
- 故障排查：优先看 `incidents/` 中标记 **Active（最终根因）** 的报告，避免被 Superseded 的早期错误假设误导。
- 历史追溯：`archive/` 仅供复盘，不作为当前结论依据。
