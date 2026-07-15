# Implementation Plan: CR-006

## 技术方案

- 用 `bootstrap_project.py` 组合现有 Legacy Scan 纯函数，统一来源证据和候选渲染。
- Node CLI 只做参数与 Python adapter，不承载扫描逻辑。
- route 在现有 `build_decision` 返回值上追加 Gate plan 与 heuristic range。
- PlanChecker 和 ContextWindowGate 在既有 Interface 内增加确定性证据检查。

## 实施步骤

1. Bootstrap report-only、candidate apply、CLI 正反例。
2. Lane Gate plan、成本因素与兼容 JSON。
3. Brownfield read/write、reuse、destructive evidence。
4. Context sources SHA-256、两阶段窗口、excluded approaches。
5. 能力矩阵、README、Lane 文档和 package budget。

## 复用证据

- `scan_legacy.detect_tech_stack/find_source_files/find_test_files`
- `scan_legacy_structure.collect_findings/list_top_level`
- `deliver.py build_decision`
- `plan_checker.check_plan`
- `context_window_check.check_context_window`

## 破坏性变更

未修改既有命令语义或删除公开 Interface；route JSON 为 additive change。npm package 移除 CHANGELOG 发布项不影响运行时，仓库仍保留 CHANGELOG。

## 验证

- `python -m unittest discover -s tests -p 'test_*.py'`
- `python skill/scripts/selftest.py skill`
- `node --check bin/cli.js`
- `npm pack --dry-run --json`
