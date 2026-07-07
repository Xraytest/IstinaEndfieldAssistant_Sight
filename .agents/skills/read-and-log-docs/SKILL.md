---
name: read-and-log-docs
description: "在项目对话开始时必须先读取全部项目文档；完成用户要求后将任务需求写入 docs/TASK_LOG.md，若与现有文档冲突则先提出并询问用户。"
metadata:
  author: user
  version: "1.0.0"
---

# read-and-log-docs

## MANDATORY: Conversation Start Rule

每次与该项目的用户开始对话时，**必须先读取**以下全部文件：

- `CLAUDE.md`
- `docs/CODE_REVIEW_NAMING_AND_BINDING.md`
- `docs/DEAD_CODE_CLEANUP.md`
- `docs/GUI_TASK_QUEUE_ANALYSIS.md`
- `docs/DELEGATION_CHAIN_ANALYSIS.md`
- `docs/IEA_VS_MaaEnd_COMPARISON.md`
- `docs/CHAIN_RECONSTRUCTION_REPORT.md`
- `docs/LLM_PERFORMANCE.md`

读取结果用于指导后续所有工具调用、代码修改与实现规划。

若项目文档范围发生变化，需同步更新本 skill 的文件列表。

---

## MANDATORY: Post-Completion Rule

完成任何用户要求后，必须将任务需求追加到项目文档：

- `docs/TASK_LOG.md`

若该文件不存在，应自动创建。

### Append Format

向 `docs/TASK_LOG.md` 追加记录：

```markdown
## YYYY-MM-DD HH:MM

- **User Request**: <用户原始请求>
- **Outcome**: <实际完成结果>
- **Files Modified**: <修改的文件列表>
```

---

## Conflict Detection

在写入 `docs/TASK_LOG.md` 前，必须先检查新记录是否与现有文档内容冲突：

1. 读取 `docs/TASK_LOG.md` 历史记录
2. 读取 `CLAUDE.md` 及其他 `docs/*.md` 中的约束、规范、架构说明
3. 若发现以下任一情况，视为冲突：
   - 新任务需求与历史记录中的决策或结论相矛盾
   - 新任务需求与 `CLAUDE.md` 或 `docs/*.md` 中的既有规范相冲突
   - 新任务需求可能覆盖或废弃未完成的旧任务

## Conflict Handling

若存在冲突：

1. **停止写入** `docs/TASK_LOG.md`
2. **向用户提出冲突说明**，包括：
   - 冲突点具体内容
   - 新需求与旧文档的差异
   - 可能的解决方向（保留旧规则 / 覆盖旧规则 / 折中方案）
3. **等待用户确认**后再继续
