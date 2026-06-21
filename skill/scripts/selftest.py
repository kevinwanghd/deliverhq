#!/usr/bin/env python3
"""
DeliverHQ selftest — 一键验证框架健康度
用法: python scripts/selftest.py [DeliverHQ根目录]
"""

import sys
sys.dont_write_bytecode = True
import os
import re
import shutil
import subprocess
import tempfile
import yaml
from pathlib import Path

from runtime_support import configure_console

ROOT = Path(__file__).resolve().parent.parent
configure_console()
positional_args = [a for a in sys.argv[1:] if not a.startswith("--")]
if positional_args:
    ROOT = Path(positional_args[0]).resolve()

# Load version from single source of truth
VERSION_FILE = ROOT / "VERSION.yml"
try:
    with open(VERSION_FILE, encoding="utf-8") as f:
        version_data = yaml.safe_load(f)
        VERSION_STRING = version_data.get("version_string", "v4.8")
except Exception:
    VERSION_STRING = "v4.8"  # fallback

CONTAMINATION_TERMS = [
    "SelfAutoAd", "X.SelfAutoAd", "SelfAutomaticAd",
    "Vivo", "vivo", "OPPO", "Oppo", "oppo",
    "巨量引擎", "OceanEngine", "oceanengine",
    "Hangfire", "hangfire",
    "广告投放", "广告平台", "广告计划",
    "MongoDB", "mongodb",
]

TEMPLATE_VAR_RE = re.compile(r"\{\{[^}]+\}\}")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
SUBPROCESS_ENV = {**dict(os.environ), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "DELIVERHQ_SELFTEST": "1", "DELIVERHQ_AUTO_MISTAKE_BOOK": "0"}


def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def snapshot_example_crs():
    temp_dir = Path(tempfile.mkdtemp(prefix="deliverhq-selftest-"))
    for cr_name in ("CR-EXAMPLE", "CR-BLOCKED-EXAMPLE"):
        source = ROOT / "change-requests" / cr_name
        if source.exists():
            shutil.copytree(source, temp_dir / cr_name)
    return temp_dir


def restore_example_crs(snapshot_dir):
    for source in snapshot_dir.iterdir():
        target = ROOT / "change-requests" / source.name
        if target.exists():
            shutil.rmtree(str(target))
        shutil.copytree(source, target)
    shutil.rmtree(str(snapshot_dir), ignore_errors=True)


def check_skeleton():
    """运行 check_skeleton.py 验证 47 文件完整性"""
    section("1. 骨架完整性 (47 files)")
    script = ROOT / "scripts" / "check_skeleton.py"
    if not script.exists():
        print(f"  {FAIL} check_skeleton.py 不存在")
        return False
    result = subprocess.run(
        [sys.executable, str(script), str(ROOT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=SUBPROCESS_ENV,
    )
    if result.returncode == 0:
        print(f"  {PASS} 骨架完整")
        return True
    else:
        print(f"  {FAIL} 骨架不完整")
        for line in result.stdout.decode().splitlines():
            if "✗" in line:
                print(f"    {line.strip()}")
        return False


def check_contamination():
    """检查语义污染（项目特定术语残留）"""
    section("2. 语义污染检查")
    hits = []
    skip_dirs = {
        "_archived",
        "delivery",
        ".git",
        "__pycache__",
        "evals",
        "examples",  # examples 目录存放真实工作示例，不检查污染
        # 运行时产物目录：跑 Gate 时生成，会记录宿主项目的绝对路径，
        # 属于运行产物而非 skill 模板本体。否则连跑两次 selftest 第二次会假报污染。
        "evidence",
        "workspace",
        "outputs",
        "artifacts",
        ".baseline",
    }
    skip_files = {
        "selftest.py",
        "CONTEXT.md",  # CONTEXT.md 是部署后填充的，允许项目特定内容
        "P0-FIX-REPORT.md",  # P0 修复报告，引用污染词作为问题示例
        "FINAL-DELIVERY-REPORT.md",  # 交付报告，引用污染词作为问题示例
        "NEXT-STEPS.md",  # 规划文档，可能引用历史问题
    }

    for path in ROOT.rglob("*"):
        if path.is_dir():
            continue
        if any(sd in path.parts for sd in skip_dirs):
            continue
        if path.name in skip_files:
            continue
        if path.suffix in (".pyc", ".gz", ".tar", ".zip", ".png", ".jpg"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = path.relative_to(ROOT)
        for term in CONTAMINATION_TERMS:
            if term in content:
                hits.append((str(rel), term))

    if not hits:
        print(f"  {PASS} 无污染词残留")
        return True
    else:
        print(f"  {FAIL} 发现 {len(hits)} 处污染:")
        for filepath, term in hits[:20]:
            print(f"    - {filepath}: '{term}'")
        if len(hits) > 20:
            print(f"    ... 还有 {len(hits)-20} 处")
        return False


def check_template_residue():
    """检查 CR-EXAMPLE 中是否有未替换的模板变量（CR-TEMPLATE 中允许存在）"""
    section("3. 模板变量残留检查 (CR-EXAMPLE)")
    example_dir = ROOT / "change-requests" / "CR-EXAMPLE"
    if not example_dir.exists():
        print(f"  {WARN} CR-EXAMPLE 不存在，跳过")
        return True

    hits = []
    for path in example_dir.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix in (".pyc", ".gz"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        matches = TEMPLATE_VAR_RE.findall(content)
        if matches:
            rel = path.relative_to(ROOT)
            hits.append((str(rel), matches))

    if not hits:
        print(f"  {PASS} CR-EXAMPLE 无模板变量残留")
        return True
    else:
        print(f"  {FAIL} CR-EXAMPLE 中有未替换的模板变量:")
        for filepath, vars in hits:
            print(f"    - {filepath}: {vars[:5]}")
        return False


def check_entry_files():
    """验证入口文件存在且非空"""
    section("4. 入口文件验证")
    entries = ["SKILL.md", "AGENTS.md", "dir-graph.yaml", "docs/CONTEXT.md"]
    all_ok = True
    for entry in entries:
        path = ROOT / entry
        if not path.exists():
            print(f"  {FAIL} {entry} 不存在")
            all_ok = False
        elif path.stat().st_size < 100:
            print(f"  {WARN} {entry} 内容过短 ({path.stat().st_size} bytes)")
            all_ok = False
        else:
            print(f"  {PASS} {entry} ({path.stat().st_size} bytes)")
    return all_ok


def check_scripts_runnable():
    """验证所有脚本可被 Python 解析（无语法错误）"""
    section("5. 脚本语法检查")
    scripts_dir = ROOT / "scripts"
    all_ok = True
    for script in sorted(scripts_dir.glob("*.py")):
        try:
            source = script.read_text(encoding="utf-8")
            compile(source, str(script), "exec")
            print(f"  {PASS} {script.name}")
        except Exception as exc:
            print(f"  {FAIL} {script.name}: {exc}")
            all_ok = False
    return all_ok


def check_cr_template_gates():
    """验证 Gate 脚本存在"""
    section("6. Gate 脚本可用性")
    gates = [
        "specgate.py", "designgate.py", "context_window_check.py",
        "pre_dev_gate.py", "dev_phase.py", "reviewgate.py", "qualitygate.py",
        "deploygate.py", "writeback_gate.py", "permissiongate.py",
        "workflow_router.py", "cr_state.py", "gate_json_output.py", "dir_graph_lint.py",
    ]
    all_ok = True
    for gate in gates:
        path = ROOT / "scripts" / gate
        if path.exists():
            print(f"  {PASS} {gate}")
        else:
            print(f"  {FAIL} {gate} 缺失")
            all_ok = False
    return all_ok


def check_cr_state_files():
    """验证示例 CR 都有 state.yml"""
    section("7. CR 状态文件验证")

    examples = [
        ROOT / "change-requests" / "CR-EXAMPLE",
        ROOT / "change-requests" / "CR-BLOCKED-EXAMPLE",
    ]

    all_ok = True
    for cr_dir in examples:
        state_file = cr_dir / "state.yml"
        if not state_file.exists():
            print(f"  {FAIL} {cr_dir.name}/state.yml 缺失")
            all_ok = False
            continue

        try:
            data = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            print(f"  {FAIL} {cr_dir.name}/state.yml 读取失败: {exc}")
            all_ok = False
            continue

        required = ["lane", "last_gate", "next_required_gate"]
        missing = [key for key in required if key not in data]
        if missing:
            print(f"  {FAIL} {cr_dir.name}/state.yml 缺少字段: {', '.join(missing)}")
            all_ok = False
        else:
            print(f"  {PASS} {cr_dir.name}/state.yml")

    return all_ok


def check_routing_eval():
    """运行真实 eval_routing.py，禁止 total=0 时通过。"""
    section("7. Routing Eval 真实执行")
    eval_script = ROOT / "scripts" / "eval_routing.py"
    if not eval_script.exists():
        print(f"  {FAIL} scripts/eval_routing.py 不存在")
        return False

    result = subprocess.run(
        [sys.executable, str(eval_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env=SUBPROCESS_ENV,
    )
    output = result.stdout + result.stderr
    totals = [int(value) for value in re.findall(r"总用例:\s*(\d+)", output)]
    if result.returncode == 0 and totals and all(value > 0 for value in totals):
        print(f"  {PASS} eval_routing.py PASS（case totals={totals}）")
        return True

    print(f"  {FAIL} eval_routing.py FAIL")
    if not totals:
        print("    未读取到总用例统计")
    elif any(value == 0 for value in totals):
        print(f"    读取到 0 case: totals={totals}")
    for line in output.splitlines():
        if "总用例" in line or "准确率" in line or "FAIL" in line or "Misrouted" in line or "False" in line:
            print(f"    {line.strip()}")
    return False


def check_cr_example_pass():
    """验证 CR-EXAMPLE 能通过 SpecGate（正例）"""
    section("8. CR-EXAMPLE SpecGate 正例验证")
    cr_example = ROOT / "change-requests" / "CR-EXAMPLE" / "acceptance-spec.md"

    if not cr_example.exists():
        print(f"  {WARN} CR-EXAMPLE/acceptance-spec.md 不存在，跳过")
        return True

    specgate = ROOT / "scripts" / "specgate.py"
    if not specgate.exists():
        print(f"  {FAIL} specgate.py 不存在")
        return False

    result = subprocess.run(
        [sys.executable, str(specgate), str(cr_example)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        env=SUBPROCESS_ENV,
    )

    if result.returncode == 0:
        print(f"  {PASS} CR-EXAMPLE SpecGate PASS（正例验证成功）")
        return True
    else:
        print(f"  {FAIL} CR-EXAMPLE SpecGate 应该 PASS 但被阻断")
        print(f"    输出: {result.stdout.decode()[:200]}")
        return False


def check_cr_blocked_example():
    """验证 CR-BLOCKED-EXAMPLE 被 SpecGate 阻断（反例）"""
    section("9. CR-BLOCKED-EXAMPLE SpecGate 反例验证")
    cr_blocked = ROOT / "change-requests" / "CR-BLOCKED-EXAMPLE" / "acceptance-spec.md"

    if not cr_blocked.exists():
        print(f"  {WARN} CR-BLOCKED-EXAMPLE/acceptance-spec.md 不存在，跳过")
        return True

    specgate = ROOT / "scripts" / "specgate.py"
    if not specgate.exists():
        print(f"  {FAIL} specgate.py 不存在")
        return False

    result = subprocess.run(
        [sys.executable, str(specgate), str(cr_blocked)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        env=SUBPROCESS_ENV,
    )

    if result.returncode != 0:
        print(f"  {PASS} CR-BLOCKED-EXAMPLE SpecGate BLOCKED（反例验证成功）")
        return True
    else:
        print(f"  {FAIL} CR-BLOCKED-EXAMPLE 应该被阻断但通过了 SpecGate")
        print(f"    这意味着 Gate 检查不够严格")
        return False


def check_version_consistency():
    """检查版本号一致性"""
    section("10. 版本号一致性检查")

    # 读取 VERSION.yml
    version_file = ROOT / "VERSION.yml"
    if not version_file.exists():
        print(f"  {FAIL} VERSION.yml 不存在")
        return False

    try:
        with open(version_file, encoding="utf-8") as f:
            version_data = yaml.safe_load(f)
        expected_version = version_data.get("version_string", "")
    except Exception as e:
        print(f"  {FAIL} VERSION.yml 读取失败: {e}")
        return False

    if not expected_version:
        print(f"  {FAIL} VERSION.yml 缺少 version_string")
        return False

    # 检查各文件
    checks = {}

    readme = ROOT / "README.md"
    if readme.exists():
        checks["README.md"] = expected_version in readme.read_text(encoding="utf-8")

    skill = ROOT / "SKILL.md"
    if skill.exists():
        checks["SKILL.md"] = expected_version in skill.read_text(encoding="utf-8")

    all_ok = True
    for file, ok in checks.items():
        if ok:
            print(f"  {PASS} {file} 版本一致 ({expected_version})")
        else:
            print(f"  {FAIL} {file} 版本号不含 {expected_version}")
            all_ok = False

    return all_ok


def check_orchestrator_references():
    """检查 orchestrator 是否引用不存在的脚本"""
    section("11. Orchestrator 脚本引用检查")

    orchestrator_file = ROOT / "scripts" / "skill_orchestrator.py"
    if not orchestrator_file.exists():
        print(f"  {WARN} skill_orchestrator.py 不存在，跳过")
        return True

    try:
        content = orchestrator_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  {FAIL} 读取 orchestrator 失败: {e}")
        return False

    # 提取所有 script_path 引用
    import re
    script_paths = re.findall(r'script_path="(scripts/[^"]+)"', content)

    if not script_paths:
        print(f"  {WARN} 未找到 script_path 引用")
        return True

    all_exist = True
    for script_path in script_paths:
        full_path = ROOT / script_path
        if full_path.exists():
            print(f"  {PASS} {script_path}")
        else:
            print(f"  {FAIL} {script_path} 不存在")
            all_exist = False

    return all_exist


def check_orchestrator_contracts():
    """验证 Orchestrator 的 script_path + args_template 能被对应脚本接受。"""
    section("12. Orchestrator 参数契约检查")

    script = ROOT / "scripts" / "skill_orchestrator.py"
    if not script.exists():
        print(f"  {FAIL} skill_orchestrator.py 不存在")
        return False

    code = """
import sys
sys.path.insert(0, 'scripts')
from skill_orchestrator import SkillOrchestrator
orch = SkillOrchestrator()
cr_path = 'change-requests/CR-EXAMPLE'
for key, skill in orch.skills.items():
    cr_id = cr_path.split('/')[-1]
    print(f'{key}|{skill.script_path}|{skill.args_template.format(cr_path=cr_path, cr_id=cr_id)}')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
    )
    if result.returncode != 0:
        print(f"  {FAIL} 无法加载 SkillOrchestrator: {result.stderr.splitlines()[:2]}")
        return False

    all_ok = True
    for line in result.stdout.splitlines():
        if not line.strip() or "|" not in line:
            continue
        skill_type, script_path, args_value = line.split("|", 2)
        full_script = ROOT / script_path
        if not full_script.exists():
            print(f"  {FAIL} {skill_type}: {script_path} 缺失")
            all_ok = False
            continue
        if not args_value:
            print(f"  {FAIL} {skill_type}: args_template 为空")
            all_ok = False
            continue
        # 不要求所有老脚本支持 --help；Gate 契约正反例由 gate_contract_check.py 真实执行。
        print(f"  {PASS} {skill_type}: {script_path} args='{args_value}'")

    return all_ok


def check_default_pipeline_contract():
    """默认 pipeline 必须停在 dev handoff，不能假装自动完成 review/quality/deploy。"""
    section("13. 默认 Pipeline 契约检查")

    code = """
import sys
sys.path.insert(0, 'scripts')
from skill_orchestrator import SkillOrchestrator
print(','.join(SkillOrchestrator().get_default_pipeline()))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
    )
    if result.returncode != 0:
        print(f"  {FAIL} 读取默认 pipeline 失败: {result.stderr.splitlines()[:2]}")
        return False

    pipeline = result.stdout.strip().split(',') if result.stdout.strip() else []
    expected = ["spec", "design", "context", "pre_dev", "dev"]
    if pipeline != expected:
        print(f"  {FAIL} 默认 pipeline 应为 {expected}，实际为 {pipeline}")
        return False

    print(f"  {PASS} 默认 pipeline 明确停在 dev handoff: {' → '.join(pipeline)}")
    return True


def check_capability_status_consistency():
    """入口文档必须引用 CAPABILITY-MATRIX，不重复维护完整能力状态。"""
    section("14. 能力状态一致性检查")
    matrix = ROOT / "CAPABILITY-MATRIX.md"
    if not matrix.exists():
        print(f"  {FAIL} CAPABILITY-MATRIX.md 不存在")
        return False

    files = [ROOT / "README.md", ROOT / "SKILL.md", ROOT / "AGENTS.md"]
    all_ok = True
    for path in files:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if "CAPABILITY-MATRIX.md" in content:
            print(f"  {PASS} {path.name} 引用 CAPABILITY-MATRIX.md")
        else:
            print(f"  {FAIL} {path.name} 未引用 CAPABILITY-MATRIX.md")
            all_ok = False

    matrix_text = matrix.read_text(encoding="utf-8", errors="ignore")
    required_phrases = [
        "PermissionGate",
        "experimental",
        "default_enabled",
        "allowed_in_pipeline",
        "Darwin Score",
        "Quality Ratchet",
    ]
    for phrase in required_phrases:
        if phrase not in matrix_text:
            print(f"  {FAIL} CAPABILITY-MATRIX.md 缺少关键状态: {phrase}")
            all_ok = False

    return all_ok


def check_dir_graph_lint():
    """Run dir-graph contract lint."""
    script = ROOT / "scripts" / "dir_graph_lint.py"
    if not script.exists():
        print(f"  {FAIL} dir_graph_lint.py 不存在")
        return False
    result = subprocess.run(
        [sys.executable, str(script), str(ROOT / "dir-graph.yaml")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env=SUBPROCESS_ENV,
    )
    if result.returncode == 0:
        print(f"  {PASS} dir-graph lint PASS")
        return True
    print(f"  {FAIL} dir-graph lint FAIL")
    for line in result.stdout.splitlines():
        if "BLOCKED" in line or line.strip().startswith("-"):
            print(f"    {line.strip()}")
    return False


def check_gate_json_evidence_schema():
    """Validate the canonical Gate JSON evidence schema through the real writer."""
    import tempfile
    import shutil

    tmp = Path(tempfile.mkdtemp())
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from gate_json_output import GATE_SCHEMA_VERSION, load_gate_result_json, validate_gate_result_payload
        from runtime_support import write_gate_evidence

        pass_path = write_gate_evidence(
            tmp,
            "schema_pass",
            "pass",
            blocking_items=[],
            warnings=["warn"],
            commands_run=["true"],
            artifacts=["artifact.txt"],
            next_action="continue",
            metadata={"sample": True},
        )
        blocked_path = write_gate_evidence(
            tmp,
            "schema_blocked",
            "blocked",
            blocking_items=["missing evidence"],
            warnings=[],
            commands_run=["false"],
            artifacts=[],
            next_action="fix blockers",
            metadata={},
        )

        legacy_path = tmp / "legacy-gate-output.json"
        from gate_json_output import BlockingItem, GateOutput, load_gate_output_json, save_gate_output_json
        legacy_output = GateOutput(
            gate_name="LegacyGate",
            result="blocked",
            cr_id="CR-LEGACY",
            timestamp="2026-01-01T00:00:00",
            blocking_items=[BlockingItem("legacy blocker", "p1", file="x.py", line=7, suggestion="fix it")],
            warnings=["legacy warning"],
            next_action="legacy next",
            metadata={"kept": True},
        )
        save_gate_output_json(legacy_output, str(legacy_path))
        loaded_legacy = load_gate_output_json(str(legacy_path))
        if loaded_legacy.cr_id != "CR-LEGACY" or loaded_legacy.blocking_items[0].severity != "p1" \
                or loaded_legacy.blocking_items[0].file != "x.py" or loaded_legacy.metadata != {"kept": True}:
            print(f"  {FAIL} legacy GateOutput JSON round-trip failed")
            return False

        for path in (pass_path, blocked_path):
            payload = load_gate_result_json(path)
            errors = validate_gate_result_payload(payload)
            if errors:
                print(f"  {FAIL} {path.name} schema errors: {errors}")
                return False
            if payload.get("schema_version") != GATE_SCHEMA_VERSION:
                print(f"  {FAIL} {path.name} schema_version 不一致")
                return False
            for field in ["blocking_items", "warnings", "commands_run", "artifacts", "failure_attribution"]:
                if not isinstance(payload.get(field), list):
                    print(f"  {FAIL} {path.name} {field} 不是 list")
                    return False
            if not isinstance(payload.get("metadata"), dict):
                print(f"  {FAIL} {path.name} metadata 不是 dict")
                return False
        print(f"  {PASS} Gate JSON evidence schema PASS")
        return True
    except Exception as exc:
        print(f"  {FAIL} Gate JSON evidence schema FAIL: {exc}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_gate_contract():
    """检查 Gate 契约：直接复用独立的 gate_contract_check.py"""
    section("15. Gate 契约检查")

    gate_contract = ROOT / "scripts" / "gate_contract_check.py"
    if not gate_contract.exists():
        print(f"  {FAIL} gate_contract_check.py 不存在")
        return False

    result = subprocess.run(
        [sys.executable, str(gate_contract)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        env=SUBPROCESS_ENV,
    )

    contract_ok = result.returncode == 0
    if contract_ok:
        print(f"  {PASS} gate_contract_check PASS")
    else:
        print(f"  {FAIL} gate_contract_check FAIL")
        for line in result.stdout.splitlines():
            if "❌" in line or "BLOCKED" in line:
                print(f"    {line.strip()}")

    dir_graph_ok = check_dir_graph_lint()
    schema_ok = check_gate_json_evidence_schema()
    return contract_ok and dir_graph_ok and schema_ok


def check_reverse_spec_contract():
    """检查逆向链路契约（目标2）：scan→gate→convert→specgate 闭环可用。

    防止逆向能力沦为"文档摆设"。在临时目录造一个迷你老项目，跑完整链路：
      1. scan_legacy 生成候选（应识别 auth 敏感域 + 无测试 → review_required）
      2. ReverseSpecGate 对未裁决高风险条目 → BLOCK（反例）
      3. 裁决后 ReverseSpecGate → PASS（正例）
      4. reverse_to_spec 转化出的 acceptance-spec.md → 能过 SpecGate（闭环对接目标1）
    """
    section("17. 逆向链路契约 (Reverse-Spec)")
    import tempfile
    scripts_dir = ROOT / "scripts"
    needed = ["scan_legacy.py", "reverse_spec_gate.py",
              "confirm_reverse_spec.py", "reverse_to_spec.py"]
    for s in needed:
        if not (scripts_dir / s).exists():
            print(f"  {FAIL} 缺少逆向脚本: {s}")
            return False

    tmp = Path(tempfile.mkdtemp())
    try:
        # 造迷你老项目：auth 模块无测试（应触发 review_required）
        proj = tmp / "legacy"
        (proj / "src" / "auth").mkdir(parents=True)
        (proj / "src" / "auth" / "login.py").write_text(
            "def check_login(u, p):\n    if u and p:\n        return True\n    return False\n",
            encoding="utf-8")
        cr = tmp / "CR-RT"
        cr.mkdir()
        cand = cr / "reverse-spec-candidates.yml"

        def run(args):
            return subprocess.run([sys.executable] + args,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=SUBPROCESS_ENV, cwd=str(ROOT)).returncode

        # 1. scan
        rc = run([str(scripts_dir / "scan_legacy.py"), str(proj), "--out", str(cand)])
        if rc != 0 or not cand.exists():
            print(f"  {FAIL} scan_legacy 失败")
            return False
        print(f"  {PASS} scan_legacy 生成候选")

        # 2. 反例：未裁决高风险 → BLOCK
        rc = run([str(scripts_dir / "reverse_spec_gate.py"), str(cand)])
        if rc == 0:
            print(f"  {FAIL} ReverseSpecGate 未阻断未裁决的高风险条目（反例失败）")
            return False
        print(f"  {PASS} ReverseSpecGate 反例 BLOCKED")

        # 3. 裁决全部待确认条目为真需求
        data = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
        for c in data.get("candidates", []):
            cid = c.get("id")
            run([str(scripts_dir / "confirm_reverse_spec.py"), str(cand),
                 "--id", cid, "--action", "confirm",
                 "--criteria", "用户名和密码均非空时登录成功", "--by", "selftest"])
        rc = run([str(scripts_dir / "reverse_spec_gate.py"), str(cand)])
        if rc != 0:
            print(f"  {FAIL} 裁决后 ReverseSpecGate 仍 BLOCK（正例失败）")
            return False
        print(f"  {PASS} ReverseSpecGate 正例 PASS")

        # 4. 转化 + specgate 闭环
        rc = run([str(scripts_dir / "reverse_to_spec.py"), str(cr), "--candidates", str(cand)])
        spec = cr / "acceptance-spec.md"
        if rc != 0 or not spec.exists():
            print(f"  {FAIL} reverse_to_spec 转化失败")
            return False
        rc = run([str(scripts_dir / "specgate.py"), str(spec)])
        if rc != 0:
            print(f"  {FAIL} 转化出的 acceptance-spec 未能通过 SpecGate（闭环断裂）")
            return False
        print(f"  {PASS} 转化产物通过 SpecGate（闭环成功）")
        return True
    except Exception as e:
        print(f"  {FAIL} 逆向契约检查异常: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_loop_control_contract():
    """检查 loop 可控性契约（goal contract / 反钻空子 / 重试上限），防止沦为文档摆设。

    1. Goal Contract 校验器：模板(占位符)→BLOCK，合规契约→PASS，缺 invariants→BLOCK（防 Goodhart）
    2. 反钻空子检查器：能加载、非 git 环境优雅降级
    3. 重试守卫：同类失败达上限→needs_human；拒绝原地重复假设
    """
    section("18. Loop 可控性契约 (Goal/反钻空子/重试)")
    import tempfile
    scripts_dir = ROOT / "scripts"
    needed = ["goal_contract.py", "anti_gaming_check.py", "retry_guard.py"]
    for s in needed:
        if not (scripts_dir / s).exists():
            print(f"  {FAIL} 缺少 loop 控制脚本: {s}")
            return False

    tmp = Path(tempfile.mkdtemp())

    def run(args):
        return subprocess.run([sys.executable] + args,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=SUBPROCESS_ENV).returncode
    try:
        # 1a. 合规契约 → PASS
        good = tmp / "good.yml"
        good.write_text(
            "schema: deliverhq-goal-contract\nversion: 1\ncr_id: T\n"
            "goal: 为接口增加分页能力\n"
            "success_criteria:\n  metrics:\n    - id: t\n      command: pytest\n      expect: exit_zero\n"
            "  invariants:\n    - tests_not_reduced\n"
            "verification_commands:\n  - python scripts/qualitygate.py x\n"
            "boundaries:\n  allowed_paths: [src/**]\n  forbidden_actions:\n    - 删除测试以让测试通过\n"
            "on_failure:\n  max_retries: 3\n"
            "escalate_to_human_when:\n  - 重试耗尽\n", encoding="utf-8")
        if run([str(scripts_dir / "goal_contract.py"), str(good)]) != 0:
            print(f"  {FAIL} 合规 Goal Contract 应 PASS 但被阻断")
            return False
        print(f"  {PASS} Goal Contract 正例 PASS")

        # 1b. 缺 invariants → BLOCK（防 Goodhart 核心）
        bad = tmp / "bad.yml"
        bad.write_text(good.read_text(encoding="utf-8").replace(
            "  invariants:\n    - tests_not_reduced\n", "  invariants: []\n"), encoding="utf-8")
        if run([str(scripts_dir / "goal_contract.py"), str(bad)]) == 0:
            print(f"  {FAIL} 缺 invariants 的契约应 BLOCK（Goodhart 漏洞未堵）")
            return False
        print(f"  {PASS} Goal Contract 缺 invariants → BLOCKED（防 Goodhart）")

        # 2. 反钻空子：非 git 临时目录优雅降级（不崩、不误判）
        crd = tmp / "CR"
        crd.mkdir()
        rc = run([str(scripts_dir / "anti_gaming_check.py"), str(crd)])
        if rc not in (0, 1):
            print(f"  {FAIL} anti_gaming_check 异常退出码: {rc}")
            return False
        print(f"  {PASS} 反钻空子检查器可运行")

        # 3. 重试守卫：达上限 → needs_human（exit!=0），并写回 state
        try:
            sys.path.insert(0, str(scripts_dir))
            import cr_state
            cr_state.save_state(crd, cr_state.ensure_state(crd))
        except Exception:
            pass
        last_rc = 0
        for h in ("h1", "h2", "h3"):
            last_rc = run([str(scripts_dir / "retry_guard.py"), str(crd),
                           "record", "--gate", "Q", "--blocker", "x", "--hypothesis", h])
        if last_rc == 0:
            print(f"  {FAIL} 重试达上限后仍可重试（未进 needs_human）")
            return False
        print(f"  {PASS} 重试上限 → needs_human")
        return True
    except Exception as e:
        print(f"  {FAIL} loop 契约检查异常: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_high_risk_approval_failclosed():
    """回归测试：high-risk 人工审批必须 fail-closed（空审批不得放行）。

    历史 bug：check_high_risk_human_approval 曾只排除负面信号（占位符/pending），
    不正向要求批准证据 → 空的 human-decisions.md 被误判为"已审批"。本检查锁死该行为。
    """
    section("19. high-risk 审批 fail-closed 回归")
    import tempfile
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from pre_dev_gate import check_high_risk_human_approval
    except Exception as e:
        print(f"  {FAIL} 无法导入 check_high_risk_human_approval: {e}")
        return False

    tmp = Path(tempfile.mkdtemp())
    try:
        # 反例：空审批 → 必须 BLOCK
        empty = tmp / "empty"
        empty.mkdir()
        (empty / "human-decisions.md").write_text("# Human Decisions\n（空）\n", encoding="utf-8")
        passed_empty, _ = check_high_risk_human_approval(empty)
        if passed_empty:
            print(f"  {FAIL} 空审批被放行（fail-open 回归！）")
            return False
        print(f"  {PASS} 空审批 → BLOCKED")

        # 反例2：缺文件 → 必须 BLOCK
        missing = tmp / "missing"
        missing.mkdir()
        passed_missing, _ = check_high_risk_human_approval(missing)
        if passed_missing:
            print(f"  {FAIL} 缺 human-decisions.md 被放行")
            return False
        print(f"  {PASS} 缺审批文件 → BLOCKED")

        # 正例：有真实决策行 → PASS
        good = tmp / "good"
        good.mkdir()
        (good / "human-decisions.md").write_text(
            "# Human Decisions\n\n| # | 决策 | 原因 | 决策人 | 日期 |\n|---|---|---|---|---|\n"
            "| 1 | 采用软删除 | 可审计 | 技术负责人 | 2026-06-01 |\n", encoding="utf-8")
        passed_good, _ = check_high_risk_human_approval(good)
        if not passed_good:
            print(f"  {FAIL} 真实审批记录被误拦")
            return False
        print(f"  {PASS} 真实审批记录 → PASS")
        return True
    except Exception as e:
        print(f"  {FAIL} 审批回归检查异常: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_plan_checker_contract():
    """检查 PlanChecker 契约（执行层），防止沦为文档摆设。

    临时 fixture 跑：合规 plan → PASS；缺 verify / AC 未覆盖 / 文件冲突 / 循环依赖 → BLOCK；
    并验证 --emit-waves 能派生 wave。
    """
    section("20. PlanChecker 契约 (plan.yml)")
    import tempfile
    pc = ROOT / "scripts" / "plan_checker.py"
    if not pc.exists():
        print(f"  {FAIL} 缺少 plan_checker.py")
        return False

    tmp = Path(tempfile.mkdtemp())

    def run(args):
        return subprocess.run([sys.executable, str(pc)] + args,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=SUBPROCESS_ENV).returncode

    def make_cr(plan_yaml):
        cr = tmp / ("cr_%d" % make_cr.n); make_cr.n += 1
        cr.mkdir()
        (cr / "acceptance-spec.md").write_text(
            "## 验收条件\n### AC-1: a\n### AC-2: b\n", encoding="utf-8")
        (cr / "plan.yml").write_text(plan_yaml, encoding="utf-8")
        return cr
    make_cr.n = 0

    GOOD = ("schema: deliverhq-plan\ncr_id: C\ntasks:\n"
            "  - task_id: T1\n    goal: a\n    files: [a.py]\n    covers: [AC-1]\n    verify: v\n    done: d\n"
            "  - task_id: T2\n    goal: b\n    files: [b.py]\n    depends_on: [T1]\n    covers: [AC-2]\n    verify: v\n    done: d\n")
    try:
        # 正例 → PASS
        if run([str(make_cr(GOOD))]) != 0:
            print(f"  {FAIL} 合规 plan 应 PASS"); return False
        print(f"  {PASS} 合规 plan → PASS")

        # 缺 verify → BLOCK
        bad = GOOD.replace("    verify: v\n    done: d\n", "    verify: ''\n    done: d\n", 1)
        if run([str(make_cr(bad))]) == 0:
            print(f"  {FAIL} 缺 verify 应 BLOCK"); return False
        print(f"  {PASS} 缺 verify → BLOCKED")

        # AC 未覆盖 → BLOCK（只覆盖 AC-1）
        miss = ("schema: deliverhq-plan\ncr_id: C\ntasks:\n"
                "  - task_id: T1\n    goal: a\n    covers: [AC-1]\n    verify: v\n    done: d\n")
        if run([str(make_cr(miss))]) == 0:
            print(f"  {FAIL} AC 未覆盖应 BLOCK"); return False
        print(f"  {PASS} AC 未覆盖 → BLOCKED")

        # 文件冲突 → BLOCK
        conflict = ("schema: deliverhq-plan\ncr_id: C\ntasks:\n"
                    "  - task_id: T1\n    goal: a\n    files: [x.py]\n    covers: [AC-1]\n    verify: v\n    done: d\n"
                    "  - task_id: T2\n    goal: b\n    files: [x.py]\n    covers: [AC-2]\n    verify: v\n    done: d\n")
        if run([str(make_cr(conflict))]) == 0:
            print(f"  {FAIL} 文件冲突应 BLOCK"); return False
        print(f"  {PASS} 文件冲突 → BLOCKED")

        # 循环依赖 → BLOCK
        cycle = ("schema: deliverhq-plan\ncr_id: C\ntasks:\n"
                 "  - task_id: T1\n    goal: a\n    covers: [AC-1]\n    depends_on: [T2]\n    verify: v\n    done: d\n"
                 "  - task_id: T2\n    goal: b\n    covers: [AC-2]\n    depends_on: [T1]\n    verify: v\n    done: d\n")
        if run([str(make_cr(cycle))]) == 0:
            print(f"  {FAIL} 循环依赖应 BLOCK"); return False
        print(f"  {PASS} 循环依赖 → BLOCKED")

        # wave 派生
        if run([str(make_cr(GOOD)), "--emit-waves"]) != 0:
            print(f"  {FAIL} --emit-waves 应成功"); return False
        print(f"  {PASS} wave 派生可运行")
        return True
    except Exception as e:
        print(f"  {FAIL} PlanChecker 契约异常: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_evidence_loop_contract():
    """检查证据补全 Loop 契约（执行层），防止沦为文档摆设。

    临时 fixture 跑：无 state → fail_closed；缺证据 → needs_human(列 gaps)；齐全 → done。
    验证 loop 可恢复（读 state.yml）、有停止条件、缺口转 needs-human。
    """
    section("22. 证据补全 Loop 契约")
    import tempfile
    el = ROOT / "scripts" / "evidence_loop.py"
    if not el.exists():
        print(f"  {FAIL} 缺少 evidence_loop.py")
        return False

    tmp = Path(tempfile.mkdtemp())

    def run(args):
        return subprocess.run([sys.executable, str(el)] + args,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=SUBPROCESS_ENV).returncode
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import cr_state

        # 1. 无 state → fail_closed（非 0）
        empty = tmp / "empty"; empty.mkdir()
        if run([str(empty)]) == 0:
            print(f"  {FAIL} 无 state.yml 应 fail-closed"); return False
        print(f"  {PASS} 无 state → fail-closed")

        # 2. 有 state 但缺证据 → needs_human（非 0）
        miss = tmp / "miss"; miss.mkdir()
        cr_state.create_state(miss, "CR-T", "t", lane="standard")
        if run([str(miss)]) == 0:
            print(f"  {FAIL} 缺证据应 needs-human"); return False
        # 状态确实被写回 needs_human
        st = cr_state.load_state(miss)
        if not st or st.current_state.value != "needs_human":
            print(f"  {FAIL} 缺证据后状态未置 needs_human"); return False
        print(f"  {PASS} 缺证据 → needs-human（状态已写回）")

        # 3. 证据齐全 → done（0）
        full = tmp / "full"; full.mkdir()
        cr_state.create_state(full, "CR-F", "t", lane="standard")
        (full / "acceptance-spec.md").write_text("## 验收条件\n### AC-1: a\n", encoding="utf-8")
        (full / "traceability.yml").write_text("schema: t\nCR-F:\n  implementation:\n    - file: a.py\n", encoding="utf-8")
        (full / "evidence").mkdir(exist_ok=True)
        (full / "evidence" / "changed-files.json").write_text('{"changed_files":["a.py"]}', encoding="utf-8")
        (full / "verification-manifest.yml").write_text("build:\n  enabled: true\n  command: true\n", encoding="utf-8")
        (full / "test-plan.md").write_text("# 测试计划\n- 用例1\n", encoding="utf-8")
        if run([str(full)]) != 0:
            print(f"  {FAIL} 证据齐全应 done"); return False
        print(f"  {PASS} 证据齐全 → done")
        return True
    except Exception as e:
        print(f"  {FAIL} 证据 Loop 契约异常: {e}")
        return False
    finally:
        import shutil
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_packaging_hygiene():
    """检查发布包中不应包含运行时垃圾文件。"""
    section("23. Packaging Hygiene")
    pycache_dirs = [path for path in ROOT.rglob("__pycache__") if path.is_dir()]
    pyc_files = list(ROOT.rglob("*.pyc"))

    temp_state_files = [
        path for pattern in ("loop_state.json", "*.tmp", "*.bak")
        for path in ROOT.rglob(pattern)
        if not any(part in {"examples", "change-requests"} for part in path.parts)
    ]

    if pycache_dirs or pyc_files or temp_state_files:
        print(f"  {FAIL} 发现不应发布的缓存/临时状态文件")
        for path in pycache_dirs[:10]:
            print(f"    __pycache__: {path.relative_to(ROOT)}")
        for path in pyc_files[:10]:
            print(f"    pyc: {path.relative_to(ROOT)}")
        for path in temp_state_files[:10]:
            print(f"    temp/state: {path.relative_to(ROOT)}")
        return False

    print(f"  {PASS} 未发现 __pycache__ / *.pyc")
    return True


def main():
    routing_only = "--routing-eval" in sys.argv

    if routing_only:
        print("=" * 50)
        print("  DeliverHQ — Routing Eval 检查")
        print("=" * 50)
        print(f"  根目录: {ROOT}")
        ok = check_routing_eval()
        print()
        if ok:
            print(f"  {PASS} routing_eval PASS")
            sys.exit(0)
        else:
            print(f"  {FAIL} routing_eval FAIL")
            sys.exit(1)

    print("=" * 50)
    print(f"  DeliverHQ {VERSION_STRING} — 框架自检")
    print("=" * 50)
    print(f"  根目录: {ROOT}")

    results = {}
    snapshot_dir = snapshot_example_crs()
    try:
        results["skeleton"] = check_skeleton()
        results["contamination"] = check_contamination()
        results["template_residue"] = check_template_residue()
        results["entry_files"] = check_entry_files()
        results["scripts_syntax"] = check_scripts_runnable()
        results["gate_availability"] = check_cr_template_gates()
        results["cr_state"] = check_cr_state_files()
        results["routing_eval"] = check_routing_eval()
        results["cr_example_pass"] = check_cr_example_pass()
        results["cr_blocked_blocked"] = check_cr_blocked_example()
        results["version_consistency"] = check_version_consistency()
        results["orchestrator_refs"] = check_orchestrator_references()
        results["orchestrator_contracts"] = check_orchestrator_contracts()
        results["default_pipeline_contract"] = check_default_pipeline_contract()
        results["capability_status_consistency"] = check_capability_status_consistency()
        results["gate_contract"] = check_gate_contract()
        results["reverse_spec_contract"] = check_reverse_spec_contract()
        results["loop_control_contract"] = check_loop_control_contract()
        results["high_risk_approval_failclosed"] = check_high_risk_approval_failclosed()
        results["plan_checker_contract"] = check_plan_checker_contract()
        results["evidence_loop_contract"] = check_evidence_loop_contract()
        results["packaging_hygiene"] = check_packaging_hygiene()
    finally:
        restore_example_crs(snapshot_dir)

    section("总结")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  通过: {passed}/{total}")
    print()
    for name, ok in results.items():
        icon = PASS if ok else FAIL
        print(f"  {icon} {name}")

    print()
    if passed == total:
        print(f"  {PASS} DeliverHQ 框架健康，可正常使用")
        sys.exit(0)
    else:
        print(f"  {FAIL} 有 {total - passed} 项检查未通过，需修复")
        sys.exit(1)


if __name__ == "__main__":
    main()
