# _archived — 已退役能力（保留化石，不进默认流程）

本目录存放被框架演进**主动判定为方向错误或从未真正接入**的脚本。它们从 `scripts/` 移出、
从 `CAPABILITY-MATRIX.md` 移除（"砍"而非"藏"），但用 `git mv` 保留以备考。

| 脚本 | 退役原因 | 退役版本 |
|---|---|---|
| `loop_mode.py` | v4.7「AI 自动循环执行」愿景的核心，但与后来确立的"DevPhase 停在 handoff、人在环、不自动写码"哲学直接冲突。395 行真实逻辑，留作 roadmap Dynamic Workflow 的参考化石。 | v5.9 |
| `darwin_score.py` | "AI 给 DeliverHQ 自己打 9 维质量分"。分数是**硬编码常量**（非真实扫描），且自评违反"信证据不信声明、干活与验收非同一 agent"的核心差异化。从未真正工作。 | v5.9 |
| `quality_ratchet.py` | 配合 darwin_score 的"分数不许退化"棘轮。`__main__` 是写死 `total:69` 的测试桩，从未接真实输入。随 darwin_score 一并退役。 | v5.9 |

退役判据（与 CAPABILITY-MATRIX 设计约束一致）：
- `not_integrated` 且无 selftest 契约、无 pipeline 引用；
- 或与"证据驱动 / 人在环 / 对抗式验证"核心哲学冲突。

如需复活：`git mv _archived/<x>.py scripts/`，补 selftest 契约与矩阵行，并经 CR 论证。
