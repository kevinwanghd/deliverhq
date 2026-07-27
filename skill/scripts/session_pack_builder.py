"""
Session Pack Builder - 生成每次会话的最小输入。

输出格式: runtime/session-packs/T<id>-r<n>.md (Markdown)

Token 预算: 40K token ≈ 160K 字符
截断优先级: task goal + AC（不截）> decisions > file scope > handoff summary

依赖:
    - plan.yml（task schema）
    - acceptance-spec.md（AC 列表）
    - context-summary.md（上下文摘要）
"""
import hashlib
import yaml
import os
from pathlib import Path
from datetime import datetime, timezone


TOKEN_BUDGET = 160_000  # 字符数（40K token × 4 chars/token）


class TokenBudgetExceeded(Exception):
    """必需内容超预算（任务粒度过大）。"""
    pass


def _now() -> str:
    """
    返回当前 UTC 时间戳（ISO 8601 格式）。

    优先读 SOURCE_DATE_EPOCH 环境变量（支持可复现构建）。
    """
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        dt = datetime.fromtimestamp(int(source_date_epoch), tz=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def build(cr_path: Path, task_id: str, run_id: str) -> Path:
    """
    生成 session pack。

    Args:
        cr_path: CR 目录
        task_id: 任务 ID（如 T1）
        run_id: 运行 ID（如 T1-r1）

    Returns:
        session pack 文件路径

    Raises:
        ValueError: 必需文件缺失或 task 不存在
        TokenBudgetExceeded: 必需内容超预算（说明任务粒度过大）
    """
    # 1. 加载必需文件
    plan = _load_plan(cr_path)
    task = _find_task(plan, task_id)
    acceptance_spec = _load_acceptance_spec(cr_path)
    context_summary = _load_context_summary(cr_path)

    # 2. 组装 sections
    sections = []
    sections.append(_section_header(task_id, run_id))
    sections.append(_section_goal(task))
    sections.append(_section_acceptance_criteria(task, acceptance_spec))
    sections.append(_section_file_scope(task))
    sections.append(_section_verification(task))

    # 可选（超预算时截断）
    optional_sections = []
    optional_sections.append(_section_decisions(context_summary))
    optional_sections.append(_section_handoff(context_summary))
    optional_sections.append(_section_prior_run(cr_path, task_id, run_id))
    optional_sections.append(_section_constraints())

    # 3. 计算预算
    mandatory_content = "\n\n".join(sections)
    mandatory_size = len(mandatory_content)

    if mandatory_size > TOKEN_BUDGET:
        raise TokenBudgetExceeded(
            f"任务 {task_id} 的必需内容超预算: {mandatory_size} > {TOKEN_BUDGET}。"
            f"建议拆分任务（减少 AC 数量或文件范围）。"
        )

    remaining = TOKEN_BUDGET - mandatory_size

    # 4. 填充可选内容（按优先级，超限则截断）
    for section in optional_sections:
        if len(section) <= remaining:
            sections.append(section)
            remaining -= len(section)
        else:
            # 截断并标记
            truncated = section[:remaining] + "\n\n[TRUNCATED]"
            sections.append(truncated)
            break

    # 5. 生成完整内容
    content = "\n\n".join(sections)

    # 6. 计算输入哈希。哈希定义为移除哈希占位后的规范化包内容，避免自引用。
    input_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    content = content.replace("input_hash: <pending>", f"input_hash: sha256:{input_hash}")

    # 7. 写文件
    runtime = cr_path / "runtime"
    context_packs_dir = runtime / "context-packs"
    context_packs_dir.mkdir(parents=True, exist_ok=True)
    pack_path = context_packs_dir / f"{run_id}.md"
    pack_path.write_text(content, encoding="utf-8")

    # 旧版客户端兼容：在传迁期间保留 session-packs 副本，但以 context-packs 为真实来源。
    legacy_dir = runtime / "session-packs"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = legacy_dir / pack_path.name
    legacy_path.write_text(content, encoding="utf-8")

    # 传统调用者仍收到旧路径；调度器和新客户端可使用同内容的 context-packs 规范路径。
    return legacy_path


def _load_plan(cr_path: Path) -> dict:
    """加载 plan.yml。"""
    plan_path = cr_path / "plan.yml"
    if not plan_path.exists():
        raise ValueError(f"plan.yml 不存在: {plan_path}")
    return yaml.safe_load(plan_path.read_text(encoding="utf-8"))


def _find_task(plan: dict, task_id: str) -> dict:
    """从 plan 中查找 task。"""
    tasks = plan.get("tasks", [])
    task = next((t for t in tasks if t.get("task_id") == task_id), None)
    if not task:
        raise ValueError(f"任务 {task_id} 在 plan.yml 中未找到")
    return task


def _load_acceptance_spec(cr_path: Path) -> dict:
    """
    加载 acceptance-spec.md，解析为 {AC-1: "描述", ...}。

    简化版：只取包含 "AC-" 的行。
    """
    spec_path = cr_path / "acceptance-spec.md"
    if not spec_path.exists():
        return {}

    content = spec_path.read_text(encoding="utf-8")
    spec = {}
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("- ") and "AC-" in line:
            # "- AC-1: 描述"
            parts = line[2:].split(":", 1)
            if len(parts) == 2:
                ac_id = parts[0].strip()
                ac_text = parts[1].strip()
                spec[ac_id] = ac_text
    return spec


def _load_context_summary(cr_path: Path) -> dict:
    """
    加载 context-summary.md，提取 decisions 和 handoff。

    简化版：返回整个文件内容。
    """
    summary_path = cr_path / "context-summary.md"
    if not summary_path.exists():
        return {"full_text": ""}

    content = summary_path.read_text(encoding="utf-8")
    return {"full_text": content}


def _section_header(task_id: str, run_id: str) -> str:
    """生成 header（元数据）。"""
    return f"""<!-- arc-session-pack -->
<!-- task_id: {task_id} -->
<!-- run_id: {run_id} -->
<!-- generated_at: {_now()} -->
<!-- input_hash: <pending> -->

# Session Pack — {run_id}
"""


def _section_goal(task: dict) -> str:
    """生成任务目标。"""
    return f"""## Task Goal

{task.get("goal", "（无目标描述）")}
"""


def _section_acceptance_criteria(task: dict, acceptance_spec: dict) -> str:
    """
    生成验收条件（仅 task.covers 指定的 AC）。
    """
    covers = task.get("covers", [])
    if not covers:
        return "## Acceptance Criteria\n\n（无）\n"

    lines = ["## Acceptance Criteria\n"]
    for ac_id in covers:
        ac_text = acceptance_spec.get(ac_id, f"{ac_id} 未找到")
        lines.append(f"- **{ac_id}**: {ac_text}")

    return "\n".join(lines)


def _section_file_scope(task: dict) -> str:
    """生成文件范围。"""
    files = task.get("files", [])
    if not files:
        return "## File Scope\n\n（无限制）\n"

    lines = ["## File Scope\n", "只允许修改以下文件：\n"]
    for f in files:
        lines.append(f"- `{f}`")

    return "\n".join(lines)


def _section_verification(task: dict) -> str:
    """生成验证命令。"""
    verify = task.get("verify", "echo '无验证命令'")
    done = task.get("done", "（无明确完成标准）")

    return f"""## Verification

**命令**:
```bash
{verify}
```

**完成标准**: {done}
"""


def _section_decisions(context_summary: dict) -> str:
    """生成决策摘要（可截断）。"""
    full_text = context_summary.get("full_text", "")
    if not full_text:
        return ""

    # 简化：取整个 context-summary 的前 30%
    max_len = len(full_text) // 3
    truncated = full_text[:max_len]

    return f"""## Context Decisions

{truncated}
"""


def _section_handoff(context_summary: dict) -> str:
    """生成交接摘要（可截断）。"""
    full_text = context_summary.get("full_text", "")
    if not full_text:
        return ""
    lines = full_text.splitlines()
    headings = [i for i, line in enumerate(lines) if line.lstrip().startswith("#")]
    handoff_start = next((i for i in headings if "handoff" in lines[i].lower() or "交接" in lines[i]), None)
    if handoff_start is not None:
        next_heading = next((i for i in headings if i > handoff_start), len(lines))
        handoff = "\n".join(lines[handoff_start:next_heading]).strip()
    else:
        handoff = "\n".join(lines[-min(40, len(lines)):]).strip()
    return f"## Handoff Summary\n\n{handoff}\n" if handoff else ""


def _section_prior_run(cr_path: Path, task_id: str, run_id: str) -> str:
    """生成上次运行摘要（如果是重试）。"""
    # 检查是否是重试（run_id 包含 -r2 或更高）
    if "-r1" in run_id or "-r" not in run_id:
        return ""

    # 简化：标注是重试
    return f"""## Prior Run

这是任务 {task_id} 的重试运行（{run_id}）。
"""


def _section_constraints() -> str:
    """生成禁止事项和输出契约。"""
    return """## Constraints

- 不得修改任何 `*gate*.py` / `selftest.py` / `anti_gaming_check.py`
- 不得降低 `verification-manifest.yml` 中的覆盖率阈值
- 不得删除或跳过测试用例

## Required Output

完成后**必须**在工作目录根写入 `agent-result.yml`，格式如下：

```yaml
task_id: <task_id>
status: done              # done | failed | blocked
changed_files:
  - path/to/file1.py
  - path/to/file2.py
test_command: "<验证命令>"
notes: "<可选：简要说明>"
```

**字段说明**：
- `task_id`: 本任务的 ID
- `status`: 完成状态（done=成功，failed=失败但可重试，blocked=阻塞需人工）
- `changed_files`: 改动的文件列表（相对于工作目录）
- `test_command`: 用于验证的命令（应与 Verification 段一致）
- `notes`: 可选的简要说明
"""
