# SpecGate 输出格式 — spec-output.json

> 来源：Nexad Agent Harness 实践。核心原则：Reviewer Agent 必须从独立 Session 启动，只拿 SpecGate 的结构化输出，不拿 Main Agent 的推理 Context。

## 为什么需要独立 Context

Nexad 的核心发现：Self-evaluation 失效的根因不是「同一个模型」，而是「同一个 Context」。Main Agent 在同一 Context 中会「合理化」掉问题——它评估的是自己的推理过程，不是代码本身。

解法：Context 隔离。同模型、同版本 Claude，但 Reviewer Agent 拿到的是：
- SPEC.md / TECH_SPEC.md（业务目标）
- git diff（代码改动）
- governance rules（治理规则）

而不是 Main Agent 的：
- 完整对话历史
- 中间推理过程
- 自我辩护的理由

## 文件位置

```
DeliverHQ/change-requests/{cr_id}/
├── spec-output.json       ← SpecGate 产出，Reviewer Agent 的唯一输入
├── evidence/
│   └── adversarial_review_report.md  ← Reviewer Agent 的产出
```

## spec-output.json Schema

```json
{
  "version": "1.0",
  "cr_id": "CR-001",
  "generated_at": "2026-08-23T12:00:00Z",
  "generated_by": "Claude Code / Hermes Agent",
  
  "background": {
    "title": "xxx",
    "why": "为什么做这个变更（从用户原始需求提取）",
    "derived_from": ["CR-xxx", "REQ-yyy"]
  },

  "requirements": [
    {
      "id": "REQ-1",
      "text": "需求原文",
      "acceptance_criteria": ["可验证的验收标准"],
      "files_affected": ["src/Foo.cs"],
      "risk_level": "HIGH|MEDIUM|LOW"
    }
  ],

  "implementation": {
    "approach": "实现的总体思路",
    "changed_files": [
      {
        "path": "src/Foo.cs",
        "change_type": "add|modify|delete",
        "summary": "一句话描述改动"
      }
    ],
    "self_assessment": {
      "irreversible": true,
      "side_effects": ["可能影响 xxx"],
      "rollout_plan": "如何回滚"
    }
  },

  "governance": {
    "tier": "T0|T1|T2|T3",
    "rules_applied": ["RL-C01", "RL-C07"],
    "untested_rationale": "（如果有豁免的话）"
  },

  "diff_summary": {
    "total_lines_added": 100,
    "total_lines_removed": 20,
    "new_files": ["src/New.cs"],
    "deleted_files": [],
    "modified_files": ["src/Foo.cs"]
  }
}
```

## 生成时机

SpecGate 输出在以下时机生成：
- `CR` 初始化时（`create_cr.py`）
- Main Agent 完成 TECH_SPEC.md 沉淀后

## Reviewer Agent 的输入约束

Reviewer Agent 启动时，其 Context 仅包含：
1. 本文件（spec-output.json）全文
2. git diff（通过 `git diff` 命令获取）
3. governance rules（从 governance.config.yml 读取）
4. adversarial_review.py 的 prompt 模板

Reviewer Agent **禁止**访问：
- Main Agent 的对话历史
- 本次会话的中间文件（除了 spec-output.json）
- 其他 CR 的 context

## 与 adversarial_review.py 的关系

`spec-output.json` 替换 `adversarial_review.py` 中的 `generate_review_prompt()` 部分：
- `reviewer_agent.py` 读取 `spec-output.json`
- 构造 prompt 时，只用 spec-output 的字段
- 输出到 `evidence/adversarial_review_report.md`

