<!-- agentgate-pr-bind {"base_ref": "origin/main", "changed_paths": [".github/workflows/agentgate.yml"], "diff_fingerprint": "52c78eabf2738463707fe2dc19899ce351cdb8abf74f30c887db250961a7ac79", "prepared_from_sha": "1a7ce39bfe8fbc81e4cd207cd239b773e78ac7b9", "schema_version": "agentgate.io/pr-description-binding/v1"} -->

## 背景

deliverhq 已接入 AgentGate GitHub 门禁；为了避免业务仓库直接追 AgentGate main，将门禁 workflow 和脚本 checkout 切换到 github-stable 稳定通道。后续 AgentGate 更新时，只要推进 github-stable，所有接入仓库会自动使用稳定版门禁。

## 变更内容

将 .github/workflows/agentgate.yml 中的 reusable workflow ref 从 main 改为 github-stable；将 agentgate-ref 输入从 main 改为 github-stable。

## 不包含的内容

无

## 自测确认

pass - python E:\ClaudeCode\AgentGate-rollout-kit-clean\scripts\agentgate.py pr verify --target-branch origin/main --config governance.config.yml；pass - git diff --check

## 风险与回滚

低风险。只修改 GitHub Actions 中 AgentGate 的引用通道，不改变业务代码；如 stable 分支异常，可回滚本提交或临时改回 main。

## 关联

-

---

<details>
<summary>📊 治理元数据（CI 自动采集）</summary>

- **AI-Usage**: used
- **Tested**: pass - pending AgentGate pr verify after manifest generation

</details>
