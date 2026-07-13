# Test Plan: CR-006

## AC Coverage

| AC | 正例 | 反例 |
|---|---|---|
| AC-1 | 两次 bootstrap JSON 相同 | 无效路径退出 2 |
| AC-2 | candidate 首次创建 | 已有 candidate 保持字节不变并报 conflict |
| AC-3 | quick/standard/strict/legacy 输出 Gate 与成本 | required/skipped 不相交 |
| AC-4 | 完整 Brownfield evidence PASS | 缺 reuse_checks BLOCK |
| AC-5 | approved reference scan PASS | 缺 scan/approval BLOCK |
| AC-6 | 当前 hash PASS | stale hash 与三阶段全文 BLOCK |

## Commands

- `python -m unittest discover -s tests -p 'test_*.py'`
- `python skill/scripts/selftest.py skill`
- `node --check bin/cli.js`
- `npm pack --dry-run --json`
