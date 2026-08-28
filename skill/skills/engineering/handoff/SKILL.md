---
name: handoff
description: 把当前会话压缩成交接文档，让另一个 Agent 可以接续工作。适用场景：切换会话、委托子任务、长流程中间节点。用前先读 `handoff_state.py` 了解 DeliverHQ 的 state.yml 状态恢复机制。
disable-model-invocation: true
---

# Handoff

把当前 DeliverHQ 会话压缩成交接文档，供下一个 Agent（或下一个会话）接续。

## 何时用

- 长流程中间切换上下文
- 把 CR 推进工作委托给子 Agent
- 会话结束前写交接记录
- 从一个 Agent 角色切换到另一个（如 Spec → Dev）

## 流程

### 1. 收集关键产物

从当前 CR 的 `state.yml` 读：
- 当前 phase（spec/design/dev/review/quality 等）
- 已通过的 Gate（specgate/qualitygate 等）
- `needs_human` 原因
- 下一道门是什么

### 2. 收集文件路径

按 DeliverHQ `handoff_state.py` 的输出格式，列出：
- 当前 CR 目录
- 关键产物文件（acceptance-spec / implementation-plan / quality-report 等）
- 阻塞原因（如有）

### 3. 写交接文档

格式：

```markdown
# Handoff — CR-XXX

## 当前状态
- Phase: ...
- 已通过 Gate: ...
- 下一道门: ...
- needs_human: ...

## 已完成产物
- `acceptance-spec.md` — ...
- `implementation-plan.md` — ...
- ...

## 阻塞原因（如有）
...

## 上下文摘要
（用 `context-summary.md` 格式，压缩到 200 字以内）

## 下一步动作
1. ...
2. ...
```

保存到 CR 目录下的 `handoff.md`。

### 4. 刷新 STATE.md

运行：
```bash
python DeliverHQ/scripts/handoff_state.py --home <项目根>/DeliverHQ --cr CR-XXX
```

## 与 mattpocock handoff 的差异

DeliverHQ 的 handoff 不依赖外部模板工具，直接用 `handoff_state.py` + CR 产物文件。
交接时必须引用 `state.yml` 中的实际状态，不用口头描述。
