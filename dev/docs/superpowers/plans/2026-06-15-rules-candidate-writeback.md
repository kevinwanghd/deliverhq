# Rules Candidate Writeback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a minimal dual-track rules writeback flow so AI writes `docs/rules-candidates.md` instead of mutating canonical `docs/rules.md`.

**Architecture:** Keep `docs/rules.md` as the human-governed canonical rules source, add `docs/rules-candidates.md` for CR-scoped AI proposals, and teach `WritebackGate` to validate candidate writeback based on explicit signals in `writeback-report.md`. Update agent permissions and example docs so the new boundary is consistent across the repo.

**Tech Stack:** Python 3 scripts, Markdown docs, existing DeliverHQ gate/state framework

---

### Task 1: Add Rules Candidate Documents

**Files:**
- Create: `docs/rules-candidates.md`
- Create: `docs/rules-deprecated.md`
- Test: `python scripts/selftest.py`

- [ ] **Step 1: Create `docs/rules-candidates.md` with a clear candidate template**

```md
# DeliverHQ Rules Candidates

> AI-generated or CR-proposed rule changes land here first. `docs/rules.md` remains the canonical rules source until a human promotes approved entries.

## How To Use
- Add one entry per proposed rule or rule change.
- Keep the source CR and trigger problem explicit.
- Do not edit `docs/rules.md` directly from Writeback Agent output.

## Candidate Rule Template
## Candidate Rule: <short title>
- Source CR: CR-XXX
- Trigger: <review finding, repeated bug, or quality failure>
- Proposed Rule: <rule text>
- Scope: <where this applies>
- Promotion Recommendation: yes/no

---

## Active Candidates

<!-- Add candidate entries below this line -->
```

- [ ] **Step 2: Create `docs/rules-deprecated.md` as a future-safe holding area**

```md
# DeliverHQ Deprecated Rules

> Rules removed from canonical use should be recorded here with the reason they were retired.

## Deprecated Rule Template
## Deprecated Rule: <short title>
- Deprecated On: YYYY-MM-DD
- Replaced By: <new rule or N/A>
- Reason: <why this rule no longer applies>
```

- [ ] **Step 3: Run selftest to confirm the new docs do not break packaging or syntax checks**

Run: `python scripts/selftest.py`
Expected: `DeliverHQ 框架健康，可正常使用`

- [ ] **Step 4: Commit the document additions**

```bash
git add docs/rules-candidates.md docs/rules-deprecated.md
git commit -m "docs: add rules candidate writeback docs"
```

### Task 2: Teach WritebackGate The Candidate-Zone Contract

**Files:**
- Modify: `scripts/writeback_gate.py`
- Test: `scripts/writeback_gate.py`
- Test: `python scripts/selftest.py`

- [ ] **Step 1: Write the failing behavior mentally against the current contract**

Use this target behavior when editing:

```text
PASS:
- writeback-report.md says no new rules were produced
- OR it says new rules were produced and docs/rules-candidates.md exists with non-template content

WARNING:
- writeback-report.md does not clearly say whether rules were produced

BLOCKED:
- report claims new/updated rules but docs/rules-candidates.md is missing
- report claims new/updated rules but docs/rules-candidates.md is still template/placeholder
```

- [ ] **Step 2: Add explicit helper functions to parse the report and inspect the candidate file**

Insert helpers near the top of `scripts/writeback_gate.py`:

```python
def detect_rules_writeback_intent(report_text: str):
    lowered = report_text.lower()
    no_rules_markers = [
        "本次无新规则",
        "无新规则",
        "no new rules",
    ]
    has_rules_markers = [
        "docs/rules-candidates.md",
        "rules-candidates.md",
        "新增规则候选",
        "更新规则候选",
        "proposed rule",
        "candidate rule",
    ]

    if any(marker in lowered for marker in no_rules_markers):
        return "none"
    if any(marker in lowered for marker in has_rules_markers):
        return "candidate"
    return "unknown"


def candidate_rules_ready(candidate_path: Path):
    if not candidate_path.exists():
        return False, "docs/rules-candidates.md 不存在"

    content = candidate_path.read_text(encoding="utf-8")
    invalid_markers = [
        "<short title>",
        "CR-XXX",
        "<review finding, repeated bug, or quality failure>",
        "<rule text>",
        "<where this applies>",
    ]
    if any(marker in content for marker in invalid_markers):
        return False, "docs/rules-candidates.md 仍包含模板占位符"
    if "## Candidate Rule:" not in content:
        return False, "docs/rules-candidates.md 缺少候选规则条目"
    return True, ""
```

- [ ] **Step 3: Replace the old `rules.md` writeback assumption with candidate-zone validation**

Update the document section in `check_writeback_gate()` so it checks:

```python
rules_path = deliverhq_docs / 'rules.md'
candidate_rules_path = deliverhq_docs / 'rules-candidates.md'
deprecated_rules_path = deliverhq_docs / 'rules-deprecated.md'

for doc_name, doc_path in {
    'architecture.md': deliverhq_docs / 'architecture.md',
    'interfaces.md': deliverhq_docs / 'interfaces.md',
    'data-model.md': deliverhq_docs / 'data-model.md',
    'rules.md': rules_path,
    'rules-candidates.md': candidate_rules_path,
    'rules-deprecated.md': deprecated_rules_path,
    'decisions.md': deliverhq_docs / 'decisions.md',
}.items():
    ...

rules_intent = detect_rules_writeback_intent(content)
if rules_intent == "candidate":
    ready, reason = candidate_rules_ready(candidate_rules_path)
    if not ready:
        blockers.append(reason)
elif rules_intent == "unknown":
    warnings.append("writeback-report.md 未明确说明是否产生规则候选")
```

- [ ] **Step 4: Add explicit evidence metadata to the gate writeback result**

Extend the `update_gate_from_result()` calls with artifacts and next actions:

```python
update_gate_from_result(
    Path(cr_path),
    'writeback',
    False,
    blockers=blockers,
    state_after_pass='archived',
    current_phase='writeback',
    current_owner='writeback-agent',
    next_required_gate='writeback',
    artifacts=['writeback-report.md', 'docs/rules-candidates.md'],
    warnings=warnings,
    next_action='补齐候选规则写回或明确声明本次无新规则后重新运行 WritebackGate',
)
```

And for success:

```python
update_gate_from_result(
    Path(cr_path),
    'writeback',
    True,
    blockers=[],
    state_after_pass='archived',
    current_phase='writeback',
    current_owner='writeback-agent',
    next_required_gate=None,
    artifacts=['writeback-report.md', 'docs/rules-candidates.md'],
    warnings=warnings,
    next_action='进入归档流程',
)
```

- [ ] **Step 5: Run WritebackGate on the example CR**

Run: `python scripts/writeback_gate.py change-requests/CR-EXAMPLE`
Expected: `PASS` or `PASS WITH WARNINGS`, but not a crash

- [ ] **Step 6: Run full selftest to catch gate regressions**

Run: `python scripts/selftest.py`
Expected: `14/14`

- [ ] **Step 7: Commit the gate logic**

```bash
git add scripts/writeback_gate.py
git commit -m "feat: validate rules candidate writeback"
```

### Task 3: Update Agent Permissions And Skill Guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: `SKILL.md`
- Modify: `README.md`
- Test: `python scripts/selftest.py`

- [ ] **Step 1: Update Writeback Agent write permissions in `AGENTS.md`**

Change the Writeback Agent block from direct canonical rules writes to candidate-only writes:

```md
**可写**：`writeback-report.md`, `writeback-gate-report.md`, `docs/architecture.md`, `docs/interfaces.md`, `docs/data-model.md`, `docs/rules-candidates.md`, `docs/decisions.md`, `docs/mistake-book.md`, `traceability.yml`
```

And add one explicit standard:

```md
- 新增/修改的规则先写入 `docs/rules-candidates.md`，不得直接改写 `docs/rules.md`
```

- [ ] **Step 2: Update the rules guidance in `SKILL.md`**

Replace the current single-file wording with:

```md
| `docs/rules.md` | 开发/Review | Canonical 编码规则（只读） |
| `docs/rules-candidates.md` | Writeback | 候选规则沉淀（AI 可写） |
```

Also revise any writeback guidance that says "写回 rules.md" to:

```md
先写入 `docs/rules-candidates.md`，由后续治理流程决定是否晋升到 `docs/rules.md`
```

- [ ] **Step 3: Update the repo structure and memory section in `README.md`**

Replace the docs tree snippet with:

```md
│   ├── rules.md                # 正式规则源（canonical）
│   ├── rules-candidates.md     # 候选规则区（Writeback Agent 写入）
│   ├── rules-deprecated.md     # 废弃规则区
```

And update explanatory text from direct rules updates to candidate writeback.

- [ ] **Step 4: Run selftest after doc updates**

Run: `python scripts/selftest.py`
Expected: `DeliverHQ 框架健康，可正常使用`

- [ ] **Step 5: Commit the doc and permission updates**

```bash
git add AGENTS.md SKILL.md README.md
git commit -m "docs: document rules candidate writeback flow"
```

### Task 4: Update Example Writeback Content

**Files:**
- Modify: `change-requests/CR-EXAMPLE/writeback-report.md`
- Modify: `examples/golden-path/CR-001/writeback-report.md`
- Test: `python scripts/writeback_gate.py change-requests/CR-EXAMPLE`

- [ ] **Step 1: Update `change-requests/CR-EXAMPLE/writeback-report.md` to explicitly use candidate wording**

Replace:

```md
- docs/rules.md - 新增规则
```

with:

```md
- docs/rules-candidates.md - 新增规则候选，待治理流程审核后晋升
```

Also add an explicit marker in the knowledge section:

```md
### 规则候选

- 已新增候选规则到 `docs/rules-candidates.md`
```

- [ ] **Step 2: Update the golden-path example with the same candidate-zone language**

Replace direct `docs/rules.md` references in `examples/golden-path/CR-001/writeback-report.md` with:

```md
docs/rules-candidates.md - 新增候选规则，等待人工治理流程确认
```

- [ ] **Step 3: Add one real candidate entry to `docs/rules-candidates.md` so the example path is valid**

Append a concrete example entry:

```md
## Candidate Rule: 规则沉淀必须先写候选区
- Source CR: CR-EXAMPLE
- Trigger: Writeback 阶段需要沉淀新规则，但不能让 AI 直接修改 canonical rules
- Proposed Rule: 所有 AI 生成的新规则或规则修改建议必须先写入 `docs/rules-candidates.md`，不得直接写入 `docs/rules.md`
- Scope: Writeback / Memory 治理流程
- Promotion Recommendation: yes
```

- [ ] **Step 4: Run WritebackGate against the updated example**

Run: `python scripts/writeback_gate.py change-requests/CR-EXAMPLE`
Expected: `PASS`

- [ ] **Step 5: Commit the example updates**

```bash
git add change-requests/CR-EXAMPLE/writeback-report.md examples/golden-path/CR-001/writeback-report.md docs/rules-candidates.md
git commit -m "docs: update writeback examples for candidate rules"
```

### Task 5: Final Verification And Cleanup

**Files:**
- Modify: any touched file if verification reveals a regression
- Test: `python scripts/selftest.py`
- Test: `python scripts/writeback_gate.py change-requests/CR-EXAMPLE`
- Test: `python scripts/gate_contract_check.py`

- [ ] **Step 1: Run the full verification set**

Run:

```bash
python scripts/writeback_gate.py change-requests/CR-EXAMPLE
python scripts/gate_contract_check.py
python scripts/selftest.py
```

Expected:

```text
WritebackGate: PASS
gate_contract_check: PASS
selftest: 14/14
```

- [ ] **Step 2: If verification changes a state/evidence file unintentionally, review and keep only intentional outputs**

Check:

```bash
git status --short
```

Expected: only files touched by this feature remain staged or intentionally modified

- [ ] **Step 3: Commit the verified final state**

```bash
git add docs/rules-candidates.md docs/rules-deprecated.md scripts/writeback_gate.py AGENTS.md SKILL.md README.md change-requests/CR-EXAMPLE/writeback-report.md examples/golden-path/CR-001/writeback-report.md
git commit -m "feat: add rules candidate writeback flow"
```

- [ ] **Step 4: Prepare handoff notes**

Record this summary in the final handoff:

```text
- canonical rules remain in docs/rules.md
- AI writes rule proposals to docs/rules-candidates.md
- WritebackGate enforces candidate-zone semantics
- no automatic promotion or deprecation logic was added in this round
```
