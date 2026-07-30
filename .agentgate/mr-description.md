<!-- agentgate-pr-bind {"base_ref": "origin/main", "changed_paths": [".github/pull_request_template.md", ".github/workflows/agentgate.yml", ".github/workflows/governance.yml", "CLAUDE.md"], "diff_fingerprint": "b82bc9f2861c39659147cc71c8576dc84cbf0cb15284a1ef4bbadc45cb1d7d92", "prepared_from_sha": "c6a77b0949795f6824cf57284e6a6b0ef37d944f", "schema_version": "agentgate.io/pr-description-binding/v1"} -->

## 背景

为 deliverhq 接入 AgentGate GitHub 门禁，让 Pull Request 自动校验治理描述、风险扫描和基础质量信号；workflow 直接引用 AgentGate main，避免继续依赖已删除的临时 rollout 分支。同时修复现有 node-test 在 package.json 没有 test script 时误失败的问题。

## 变更内容

新增 AgentGate PR 描述清单；新增 GitHub Actions workflow 调用 kevinwanghd/AgentGate 的可复用门禁；更新 pull request template 提示治理字段；在 CLAUDE.md 中补充 AgentGate 工作流约束和 PR 提交流程；调整现有 governance.yml 的 node-test，让没有 scripts.test 的 package 跳过。

## 不包含的内容

无

## 自测确认

pass - python E:\ClaudeCode\AgentGate-rollout-kit-clean\scripts\agentgate.py pr verify --target-branch origin/main --config governance.config.yml；pass - git diff --check；GitHub Actions 上 AgentGate 门禁已通过，原 node-test 失败原因为 package.json 缺少 test script，已补跳过逻辑。

## 风险与回滚

低风险。变更只新增 GitHub PR 门禁、协作提示和 CI skip 条件，不改业务运行时代码；如 workflow 配置异常，可回滚本提交恢复原 PR 流程。

## 关联

-

---

<details>
<summary>📊 治理元数据（CI 自动采集）</summary>

- **AI-Usage**: heavy
- **AI-Tools**: codex
- **AI-Models**: GPT-5
- **AI-Lines**: 328/352
- **Tested**: pass - AgentGate installer completed; PR manifest generation and verification will run before push

</details>
