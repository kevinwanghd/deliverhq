#!/usr/bin/env python3
"""
DeliverHQ selftest — 一键验证框架健康度
用法: python scripts/selftest.py [DeliverHQ根目录]
"""

import sys
sys.dont_write_bytecode = True
import os
import re
import json
import shutil
import subprocess
import tempfile
import yaml
from pathlib import Path

# 残余问题1修复：统一设置子进程环境变量，防止 Windows GBK 编码问题
# 注入到当前进程的环境变量，所有 subprocess.run 调用会继承
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from runtime_support import configure_console

ROOT = Path(__file__).resolve().parents[2]
configure_console()

from selftest_contracts import ALL_CONTRACTS

_subprocess_run = subprocess.run


def _run_subprocess_utf8(*args, **kwargs):
    """Default text subprocess pipes to UTF-8 on every host locale."""
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _subprocess_run(*args, **kwargs)


subprocess.run = _run_subprocess_utf8
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
    """运行 check_skeleton.py 验证骨架完整性"""
    section("1. 骨架完整性")
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
        "suite.py",  # selftest implementation owns the contamination term list
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
    entries = ["SKILL.md", "AGENTS.md", "attention.md", "dir-graph.yaml", "docs/CONTEXT.md", "notes/_index.md", "inbox/README.md", "journal/README.md"]
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


def check_light_entry_contract():
    """Validate the free-flow style light entry and lane routing contract."""
    section("4b. Light Entry / Lane Contract")
    script = ROOT / "scripts" / "deliver.py"
    if not script.exists():
        print(f"  {FAIL} scripts/deliver.py missing")
        return False

    cases = [
        ("fix a typo in README only", "quick", False, "quick_direct"),
        ("add an order export feature", "standard", True, "deliver-standard"),
        ("refactor payment auth callback in production", "strict", True, "deliver-strict"),
        ("scan this legacy codebase and turn code into requirements", "legacy", True, "deliver-legacy"),
    ]
    all_ok = True
    for prompt, lane, required, entry in cases:
        result = subprocess.run(
            [sys.executable, str(script), "route", prompt, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=SUBPROCESS_ENV,
        )
        if result.returncode != 0:
            print(f"  {FAIL} deliver.py failed for {prompt!r}: {result.stderr[:160]}")
            all_ok = False
            continue
        try:
            data = json.loads(result.stdout)
        except Exception as exc:
            print(f"  {FAIL} deliver.py returned non-JSON for {prompt!r}: {exc}")
            all_ok = False
            continue
        actual = (data.get("lane"), bool(data.get("deliverhq_required")), data.get("entry"))
        expected = (lane, required, entry)
        if actual == expected:
            print(f"  {PASS} {prompt!r} -> lane={lane}, entry={entry}")
        else:
            print(f"  {FAIL} {prompt!r}: expected={expected}, actual={actual}")
            all_ok = False

    lane_result = subprocess.run(
        [sys.executable, str(script), "lanes"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env=SUBPROCESS_ENV,
    )
    if lane_result.returncode == 0 and all(name in lane_result.stdout for name in ("quick", "standard", "strict", "legacy")):
        print(f"  {PASS} lanes command lists all governance lanes")
    else:
        print(f"  {FAIL} lanes command missing expected lanes")
        all_ok = False
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
        "specgate.py", "designgate.py", "architecturegate.py", "context_window_check.py",
        "pre_dev_gate.py", "dev_phase.py", "reviewgate.py", "qualitygate.py",
        "deploygate.py", "writeback_gate.py", "permissiongate.py",
        "workflow_router.py", "cr_state.py", "gate_json_output.py", "dir_graph_lint.py", "structuregate.py", "init_project_structure.py", "scan_legacy_structure.py",
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

    package_json = ROOT.parent / "package.json"
    if package_json.exists():
        import json
        try:
            package_version = json.loads(package_json.read_text(encoding="utf-8")).get("version")
            checks["../package.json"] = package_version == expected_version.lstrip("v")
        except Exception:
            checks["../package.json"] = False

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

    orchestrator_file = ROOT / "scripts" / "orchestrator_core.py"
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
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue  # 防御：不足 3 段的行跳过（避免 unpacking ValueError）
        skill_type, script_path, args_value = parts
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
    expected = ["spec", "design", "architecture", "context", "pre_dev", "dev"]
    if pipeline != expected:
        print(f"  {FAIL} 默认 pipeline 应为 {expected}，实际为 {pipeline}")
        return False

    print(f"  {PASS} 默认 pipeline 明确停在 dev handoff: {' → '.join(pipeline)}")
    return True


def check_verb_layer_contract():
    """动词层契约：5 个用户面动词派生自 FROZEN_GATES，无漂移、无丢失门禁。

    动词层是 54 个脚本的「默认入口」收口（降低认知负荷），但绝不能成为第二个事实源。
    本契约真实执行 orchestrator 的 validate_verbs()，并锁死动词集合与 BLOCK 透传纪律：
      1. validate_verbs() 必须 PASS（动词↔冻结门禁一致）。
      2. 动词集合恰为 {spec, design, dev, verify, archive}（防悄悄增删动词）。
      3. execute_skill 在失败分支必须透传脚本 stdout（verbatim 报告，不二次概括）。
      4. 不触碰 get_default_pipeline（由 default_pipeline_contract 单独锁定）。
    """
    section("13b. 动词层契约 (verb layer ↔ FROZEN_GATES)")

    code = """
import sys
sys.path.insert(0, 'scripts')
from skill_orchestrator import SkillOrchestrator, VERBS
orch = SkillOrchestrator()
errors, warnings = orch.validate_verbs()
print('VERBS=' + ','.join(sorted(VERBS)))
print('ERRORS=' + '|'.join(errors))
print('VERIFY=' + ','.join(VERBS.get('verify', [])))
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
        print(f"  {FAIL} 无法加载动词层: {result.stderr.splitlines()[:2]}")
        return False

    verbs_line = ""
    errors_line = ""
    verify_line = ""
    for line in result.stdout.splitlines():
        if line.startswith("VERBS="):
            verbs_line = line[len("VERBS="):]
        elif line.startswith("ERRORS="):
            errors_line = line[len("ERRORS="):]
        elif line.startswith("VERIFY="):
            verify_line = line[len("VERIFY="):]

    ok = True

    # 1. validate_verbs 必须无 error
    if errors_line.strip():
        print(f"  {FAIL} validate_verbs 报错: {errors_line}")
        ok = False
    else:
        print(f"  {PASS} validate_verbs 通过（动词↔FROZEN_GATES 一致）")

    # 2. 动词集合冻结
    expected_verbs = "archive,design,dev,spec,verify"
    if verbs_line != expected_verbs:
        print(f"  {FAIL} 动词集合应为 [{expected_verbs}]，实际 [{verbs_line}]")
        ok = False
    else:
        print(f"  {PASS} 动词集合冻结: {verbs_line}")

    # 2b. verify 链必须串入 loop 治理：goal_contract（双轨/防 Goodhart）+ anti_gaming（diff 取证）
    verify_steps = verify_line.split(",") if verify_line else []
    for must in ("goal_contract", "anti_gaming"):
        if must not in verify_steps:
            print(f"  {FAIL} verify 链缺少 '{must}'（loop 可控性未串入）")
            ok = False
    if "goal_contract" in verify_steps and "anti_gaming" in verify_steps:
        print(f"  {PASS} verify 链含 goal_contract + anti_gaming: {' → '.join(verify_steps)}")

    # 3. 失败分支透传 verbatim 报告（静态检查源码）
    orch_src = (ROOT / "scripts" / "orchestrator_core.py").read_text(encoding="utf-8")
    fail_branch = orch_src.split("Skill failed", 1)
    if len(fail_branch) == 2 and "result.stdout" in fail_branch[1].split("return False", 1)[0]:
        print(f"  {PASS} 失败分支透传脚本 stdout（不丢取证粒度）")
    else:
        print(f"  {FAIL} 失败分支未透传 stdout，BLOCK 报告会被吞掉")
        ok = False

    # 4. verify 失败只跑 retry_guard 只读 status，绝不自动 record（防违背"重试需人给新假设"）
    #    检查 _run_retry_status 方法体：必须调 status 子命令，且体内不得出现 record 子命令调用。
    method_body = ""
    if "def _run_retry_status" in orch_src:
        after = orch_src.split("def _run_retry_status", 1)[1]
        # 方法体到下一个同级 def 为止
        method_body = after.split("\n    def ", 1)[0]
    if not method_body:
        print(f"  {FAIL} 未发现 retry_guard 只读 status 集成")
        ok = False
    elif '"status"' not in method_body and "'status'" not in method_body:
        print(f"  {FAIL} _run_retry_status 未调用 status 子命令")
        ok = False
    elif '"record"' in method_body or "'record'" in method_body or ", record" in method_body:
        print(f"  {FAIL} _run_retry_status 体内出现 record，违背'重试需人给新假设'")
        ok = False
    else:
        print(f"  {PASS} 失败后仅 retry_guard status（只读，不自动 record）")



    return ok


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

        # GSD 写作约束：no-op verify → BLOCK
        noop = GOOD.replace("    verify: v\n    done: d\n", "    verify: 'echo done'\n    done: d\n", 1)
        if run([str(make_cr(noop))]) == 0:
            print(f"  {FAIL} no-op verify(echo) 应 BLOCK"); return False
        print(f"  {PASS} no-op verify(echo done) → BLOCKED")

        # GSD 写作约束：done 含主观语言 → BLOCK
        subj = GOOD.replace("    verify: v\n    done: d\n", "    verify: v\n    done: 'looks correct'\n", 1)
        if run([str(make_cr(subj))]) == 0:
            print(f"  {FAIL} done 含主观语言应 BLOCK"); return False
        print(f"  {PASS} done='looks correct' → BLOCKED")
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


def make_architecture_design_content(confirmation_line):
    return (
        "# 架构设计\n\n"
        "> 第二道人工门禁。编码前必须有架构设计并经人工确认。\n\n"
        "## 1. 模块拆分与目录结构\n模块 A 落在 a.py。\n\n"
        "## 2. 数据流与状态管理\n数据从 API 到页面状态。\n\n"
        "## 3. 接口封装与依赖\n通过 repository 封装。\n\n"
        "## 4. 异常处理与验证策略\n失败时返回清晰错误并跑 selftest。\n\n"
        "## 5. 测试接缝 (Test Seams)\nAPI 层集成测试。\n\n"
        "## 6. 设计分块到实现映射\nblock A -> a.py。\n\n"
        + confirmation_line + "\n"
    )


def check_architecturegate_confirmation_contract():
    """检查 ArchitectureGate 未确认模板不得被误判为已人工确认。"""
    section("23. ArchitectureGate 人工确认契约")
    tmp = Path(tempfile.mkdtemp())
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from architecturegate import check_architecturegate
        from cr_state import load_state

        def make_cr(name, confirmation_line):
            cr = tmp / name
            cr.mkdir()
            (cr / "architecture-design.md").write_text(
                make_architecture_design_content(confirmation_line),
                encoding="utf-8",
            )
            return cr

        unconfirmed = make_cr("unconfirmed", "**人工确认**：未确认 / 已确认（确认人 / 日期）")
        passed, _ = check_architecturegate(unconfirmed)
        evidence = json.loads((unconfirmed / "evidence" / "architecture-result.json").read_text(encoding="utf-8"))
        if not passed or not any("尚未人工确认" in warning for warning in evidence.get("warnings", [])):
            print(f"  {FAIL} 未确认模板未产生人工确认 warning")
            return False
        print(f"  {PASS} 未确认模板 → warning")

        confirmed = make_cr("confirmed", "**人工确认**：已确认（张三 / 2026-06-20）")
        passed, _ = check_architecturegate(confirmed)
        evidence = json.loads((confirmed / "evidence" / "architecture-result.json").read_text(encoding="utf-8"))
        state = load_state(confirmed)
        if not passed or any("尚未人工确认" in warning for warning in evidence.get("warnings", [])):
            print(f"  {FAIL} 真实人工确认仍产生 warning")
            return False
        if not state or state.current_state.value != "design":
            actual = state.current_state.value if state else "missing"
            print(f"  {FAIL} ArchitectureGate PASS 后状态应保持 design，实际为 {actual}")
            return False
        print(f"  {PASS} 真实人工确认 → PASS 无 warning，状态保持 design")
        return True
    except Exception as exc:
        print(f"  {FAIL} ArchitectureGate 人工确认契约异常: {exc}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_designgate_mobile_keyword_contract():
    """检查移动端关键词回退检测不误伤英文子串。"""
    section("24. DesignGate 移动端关键词契约")
    tmp = Path(tempfile.mkdtemp())
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from designgate import detect_ui_type

        def make_cr(name, content):
            cr = tmp / name
            (cr / "design").mkdir(parents=True)
            (cr / "request.md").write_text(content, encoding="utf-8")
            return cr

        negative = make_cr(
            "negative",
            "# Approval workflow\nWARNING: pending Application review. Apply for access.\n管理后台审批流程。\n",
        )
        ui_type, is_mobile = detect_ui_type(negative)
        if is_mobile or ui_type != "B端":
            print(f"  {FAIL} Approval/WARNING/Application 被误判为移动端: {ui_type}, {is_mobile}")
            return False
        print(f"  {PASS} 英文子串不触发移动端")

        ios = make_cr("ios", "# iOS App\n原生客户端登录页面。\n")
        ui_type, is_mobile = detect_ui_type(ios)
        if ui_type != "C端" or not is_mobile:
            print(f"  {FAIL} iOS App 未识别为移动端: {ui_type}, {is_mobile}")
            return False

        rn = make_cr("rn", "# React Native\n客户端首页。\n")
        ui_type, is_mobile = detect_ui_type(rn)
        if ui_type != "C端" or not is_mobile:
            print(f"  {FAIL} React Native 未识别为移动端: {ui_type}, {is_mobile}")
            return False
        print(f"  {PASS} 真实移动端关键词仍识别")
        return True
    except Exception as exc:
        print(f"  {FAIL} DesignGate 移动端关键词契约异常: {exc}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_predev_requires_architecture_contract():
    """检查 PreDevGate 不得绕过 ArchitectureGate。"""
    section("25. PreDevGate 架构门禁契约")
    tmp = Path(tempfile.mkdtemp())
    old_selftest = os.environ.get("DELIVERHQ_SELFTEST")
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from architecturegate import check_architecturegate
        from cr_state import create_state
        from pre_dev_gate import check_cr_readiness

        os.environ["DELIVERHQ_SELFTEST"] = "1"

        def make_cr(name):
            cr = tmp / name
            cr.mkdir()
            create_state(cr, name, "测试 CR", lane="fast")
            (cr / "acceptance-spec.md").write_text("## 验收条件\n### AC-1: ok\n", encoding="utf-8")
            (cr / "traceability.yml").write_text("schema: deliverhq-traceability\n", encoding="utf-8")
            return cr

        missing = make_cr("missing-arch")
        if check_cr_readiness(missing, lane="fast"):
            print(f"  {FAIL} 缺 architecture-design.md 时 PreDevGate 被放行")
            return False
        print(f"  {PASS} 缺架构设计 → BLOCKED")

        no_evidence = make_cr("missing-evidence")
        (no_evidence / "architecture-design.md").write_text(
            make_architecture_design_content("**人工确认**：已确认（张三 / 2026/06/20）"),
            encoding="utf-8",
        )
        if check_cr_readiness(no_evidence, lane="fast"):
            print(f"  {FAIL} 缺 ArchitectureGate 证据时 PreDevGate 被放行")
            return False
        print(f"  {PASS} 缺 ArchitectureGate 证据 → BLOCKED")

        good = make_cr("with-evidence")
        (good / "architecture-design.md").write_text(
            make_architecture_design_content("**人工确认**：已确认（张三 / 2026/06/20）"),
            encoding="utf-8",
        )
        arch_passed, _ = check_architecturegate(good)
        if not arch_passed:
            print(f"  {FAIL} ArchitectureGate 正例未通过")
            return False
        if not check_cr_readiness(good, lane="fast"):
            print(f"  {FAIL} ArchitectureGate 通过后 PreDevGate 仍阻断")
            return False
        print(f"  {PASS} ArchitectureGate 证据齐全 → PASS")
        return True
    except Exception as exc:
        print(f"  {FAIL} PreDevGate 架构门禁契约异常: {exc}")
        return False
    finally:
        if old_selftest is None:
            os.environ.pop("DELIVERHQ_SELFTEST", None)
        else:
            os.environ["DELIVERHQ_SELFTEST"] = old_selftest
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_structure_governance_contract():
    """检查 Project Structure Governance 新/老项目最小契约。"""
    section("26. Project Structure Governance 契约")
    import tempfile
    import shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        project = tmp / "new-project"
        project.mkdir()
        init_script = ROOT / "scripts" / "init_project_structure.py"
        gate_script = ROOT / "scripts" / "structuregate.py"
        scan_script = ROOT / "scripts" / "scan_legacy_structure.py"
        for script in (init_script, gate_script, scan_script):
            if not script.exists():
                print(f"  {FAIL} 缺少脚本: {script.name}")
                return False

        result = subprocess.run(
            [sys.executable, str(init_script), str(project), "--profile", "fullstack-web"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=SUBPROCESS_ENV,
        )
        if result.returncode != 0:
            print(f"  {FAIL} init_project_structure 失败: {result.stderr.splitlines()[:2]}")
            return False
        required = [
            project / "DeliverHQ" / "STRUCTURE-PROFILE.yml",
            project / "DeliverHQ" / "REPO_MAP.md",
            project / "DeliverHQ" / "COMMANDS.yml",
            project / "apps" / "web" / "src" / "features",
            project / "apps" / "api" / "src" / "modules",
            project / "packages" / "shared-types",
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            print(f"  {FAIL} init-project 缺少产物: {missing[:3]}")
            return False

        result = subprocess.run(
            [sys.executable, str(gate_script), str(project)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=SUBPROCESS_ENV,
        )
        if result.returncode != 0:
            print(f"  {FAIL} structuregate 正例失败")
            for line in result.stdout.splitlines()[:8]:
                print(f"    {line}")
            return False

        (project / ".env").write_text("SECRET=1\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(gate_script), str(project)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=SUBPROCESS_ENV,
        )
        if result.returncode == 0:
            print(f"  {FAIL} structuregate 应阻断 .env")
            return False
        (project / ".env").unlink()

        legacy = tmp / "legacy-project"
        (legacy / "src" / "controllers").mkdir(parents=True)
        (legacy / "src" / "controllers" / "user.py").write_text("def get_user(): pass\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(scan_script), str(legacy)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=SUBPROCESS_ENV,
        )
        if result.returncode != 0:
            print(f"  {FAIL} scan_legacy_structure 失败")
            return False
        if not (legacy / "DeliverHQ" / "docs" / "reports" / "structure-assessment-report.md").exists():
            print(f"  {FAIL} legacy scan 未生成结构报告")
            return False
        candidate = legacy / "DeliverHQ" / "STRUCTURE-PROFILE.candidate.yml"
        if not candidate.exists():
            print(f"  {FAIL} legacy scan 未生成候选 profile")
            return False
        (legacy / "DeliverHQ" / "STRUCTURE-PROFILE.yml").write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(gate_script), str(legacy), "--mode", "progressive"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            env=SUBPROCESS_ENV,
        )
        if result.returncode != 0:
            print(f"  {FAIL} progressive StructureGate 应允许 legacy fenced 项目")
            for line in result.stdout.splitlines()[:8]:
                print(f"    {line}")
            return False

        print(f"  {PASS} Project Structure Governance contract PASS")
        return True
    except Exception as exc:
        print(f"  {FAIL} Project Structure Governance contract 异常: {exc}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_packaging_hygiene():
    """检查发布边界，不把本地 Python 运行缓存误判成发布污染。"""
    section("27. Packaging Hygiene")
    temp_state_files = [
        path for pattern in ("loop_state.json", "*.tmp", "*.bak")
        for path in ROOT.rglob(pattern)
        if "__pycache__" not in path.parts
        and not any(part in {"examples", "change-requests"} for part in path.parts)
    ]

    published_cache = []
    package_root = ROOT.parent
    npm = shutil.which("npm")
    if (package_root / "package.json").is_file() and npm:
        result = subprocess.run(
            [npm, "pack", "--dry-run", "--json"],
            cwd=package_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"  {FAIL} npm pack --dry-run 执行失败")
            return False
        try:
            payload = json.loads(result.stdout)
            files = payload[0].get("files", []) if payload else []
            published_cache = [
                item.get("path", "") for item in files
                if "__pycache__" in item.get("path", "").split("/")
                or item.get("path", "").endswith(".pyc")
            ]
        except (json.JSONDecodeError, TypeError, AttributeError):
            print(f"  {FAIL} 无法解析 npm pack 发布清单")
            return False

    if published_cache or temp_state_files:
        print(f"  {FAIL} 发布边界包含缓存/临时状态文件")
        for path in published_cache[:10]:
            print(f"    published cache: {path}")
        for path in temp_state_files[:10]:
            print(f"    temp/state: {path.relative_to(ROOT)}")
        return False

    print(f"  {PASS} 发布清单不含 Python 缓存或临时状态")
    return True


def check_handoff_state_contract():
    """STATE 指针契约（借 Pocock /handoff，替代 SessionStart hook）：从 state.yml 汇总刷新 STATE.md。"""
    section("34. STATE 指针契约 (handoff_state)")
    hs = ROOT / "scripts" / "handoff_state.py"
    if not hs.exists():
        print(f"  {FAIL} handoff_state.py 不存在")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-handoff-"))
    try:
        home = tmp / "DeliverHQ"
        cr = home / "change-requests" / "CR-001"
        cr.mkdir(parents=True)
        # 最小 state.yml（cr_state 可解析的字段）
        (cr / "state.yml").write_text(
            "cr_id: CR-001\nlane: standard\ncurrent_state: blocked\ncurrent_phase: dev\n"
            "next_required_gate: review\nrequires_human: false\nblocking_reason: 测试阻塞\n",
            encoding="utf-8")

        rc = subprocess.run(
            [sys.executable, str(hs), "--home", str(home)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=SUBPROCESS_ENV,
        )
        state_md = home / "STATE.md"
        ok = True
        if rc.returncode == 0 and state_md.exists():
            text = state_md.read_text(encoding="utf-8")
            if "CR-001" in text and "review" in text and "done = 建出来的" in text:
                print(f"  {PASS} STATE.md 含 CR/下一道门/不变式")
            else:
                print(f"  {FAIL} STATE.md 内容不完整"); ok = False
        else:
            print(f"  {FAIL} 刷新 STATE.md 失败 rc={rc.returncode}"); ok = False

        # 无活跃 CR 时也应安全生成
        empty_home = tmp / "EmptyHQ"
        (empty_home / "change-requests").mkdir(parents=True)
        rc2 = subprocess.run(
            [sys.executable, str(hs), "--home", str(empty_home), "--print"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=SUBPROCESS_ENV,
        )
        if rc2.returncode == 0 and "无活跃 CR" in rc2.stdout:
            print(f"  {PASS} 无活跃 CR → 安全输出")
        else:
            print(f"  {FAIL} 空 home 处理异常 rc={rc2.returncode}"); ok = False
        return ok
    except Exception as e:
        print(f"  {FAIL} handoff_state 契约异常: {e}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_prd_linkage_contract():
    """PRD↔CR 链路契约:drift_check + prd_writeback 端到端。

    设计文档(PRD-LAYER-DESIGN)承诺过的事必须有契约守:
      1. CR 正确填 derived_from → drift_check PASS
      2. 改 PRD 锚点正文 → drift_check 警告(confirmed 锚点)
      3. CR 无 derived_from → drift_check 警告
      4. prd_writeback 回填占位符 → 哈希不变(关键不变式,曾因 _anchor_hash
         漏剥 markdown ** 而失效,本契约同时守这个 bug 不复现)
      5. prd_writeback 幂等(同一 CR 反复回填 ≡ 单次)
      6. 多 CR 回填 → 去重排序
    """
    section("36. PRD↔CR 链路契约 (drift_check + prd_writeback)")
    dc = ROOT / "scripts" / "drift_check.py"
    wb = ROOT / "scripts" / "prd_writeback.py"
    if not dc.exists() or not wb.exists():
        print(f"  {FAIL} drift_check.py / prd_writeback.py 不存在")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-prd-"))
    try:
        # 临时骨架:docs/PRD.md + scripts 副本 + 一个 CR
        skill = tmp / "skill"
        (skill / "docs").mkdir(parents=True)
        (skill / "change-requests" / "CR-X").mkdir(parents=True)
        shutil.copytree(str(ROOT / "scripts"), str(skill / "scripts"))

        prd_path = skill / "docs" / "PRD.md"
        prd_path.write_text(
            "# PRD\n\n## [PRD-FOO] 功能\n\n"
            "- **状态**: confirmed\n\n意图:做某事。\n\n"
            "**关联 CR**: {{由 writeback-agent 自动回填}}\n",
            encoding="utf-8")

        # 用 drift_check 算锚点哈希
        sys.path.insert(0, str(skill / "scripts"))
        try:
            import importlib
            import drift_check as _dc
            importlib.reload(_dc)
            h0 = _dc._anchor_hash(prd_path.read_text(encoding="utf-8"), "PRD-FOO")
        finally:
            if str(skill / "scripts") in sys.path:
                sys.path.remove(str(skill / "scripts"))

        spec = skill / "change-requests" / "CR-X" / "acceptance-spec.md"
        spec.write_text(
            "# spec\n\n```yaml\nderived_from:\n  prd_section: PRD-FOO\n  prd_hash: " + h0 + "\n```\n",
            encoding="utf-8")

        def run(script, *args):
            return subprocess.run(
                [sys.executable, str(skill / "scripts" / script)] + list(args),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, env=SUBPROCESS_ENV)

        ok = True

        # 1. drift_check PASS
        r = run("drift_check.py", str(skill / "change-requests" / "CR-X"), "--root", str(skill))
        if r.returncode == 0 and "PASS" in r.stdout:
            print(f"  {PASS} 正确填 derived_from → PASS")
        else:
            print(f"  {FAIL} 应 PASS,得 {r.stdout[:160]}"); ok = False

        # 2. 改 PRD 正文 → 警告
        prd_path.write_text(prd_path.read_text(encoding="utf-8").replace("做某事", "做另一件事"), encoding="utf-8")
        r = run("drift_check.py", str(skill / "change-requests" / "CR-X"), "--root", str(skill))
        if "reconcile" in r.stdout or "confirmed" in r.stdout:
            print(f"  {PASS} 改 PRD 正文 → 警告(对账提示)")
        else:
            print(f"  {FAIL} 改正文应警告,得 {r.stdout[:160]}"); ok = False

        # 3. CR 无 derived_from → 警告
        spec.write_text("# spec\n\n纯净 spec,无 derived_from\n", encoding="utf-8")
        r = run("drift_check.py", str(skill / "change-requests" / "CR-X"), "--root", str(skill))
        if "未链接 PRD" in r.stdout or "无 derived_from" in r.stdout:
            print(f"  {PASS} CR 无 derived_from → 警告")
        else:
            print(f"  {FAIL} 应警告未链接,得 {r.stdout[:160]}"); ok = False

        # 4. prd_writeback 回填占位符,哈希不变(关键不变式)
        spec.write_text(
            "# spec\n\n```yaml\nderived_from:\n  prd_section: PRD-FOO\n  prd_hash: x\n```\n",
            encoding="utf-8")
        # 重读 _anchor_hash 反映最新 PRD
        sys.path.insert(0, str(skill / "scripts"))
        try:
            import importlib
            import drift_check as _dc
            importlib.reload(_dc)
            h_before = _dc._anchor_hash(prd_path.read_text(encoding="utf-8"), "PRD-FOO")
        finally:
            if str(skill / "scripts") in sys.path:
                sys.path.remove(str(skill / "scripts"))

        r = run("prd_writeback.py", str(skill / "change-requests" / "CR-X"))
        if r.returncode == 0 and "hash 不变" in r.stdout:
            print(f"  {PASS} 占位符首次回填 → 哈希不变 ({h_before})")
        else:
            print(f"  {FAIL} 回填应成功且哈希不变,得 {r.stdout[:200]}"); ok = False

        # PRD 现在含真实 CR-X,断言哈希值真的没变
        sys.path.insert(0, str(skill / "scripts"))
        try:
            import importlib
            import drift_check as _dc
            importlib.reload(_dc)
            h_after = _dc._anchor_hash(prd_path.read_text(encoding="utf-8"), "PRD-FOO")
        finally:
            if str(skill / "scripts") in sys.path:
                sys.path.remove(str(skill / "scripts"))
        if h_before == h_after:
            print(f"  {PASS} 回填后再算哈希仍 {h_after}(守 _anchor_hash 粗体 bug)")
        else:
            print(f"  {FAIL} 哈希变了 {h_before} → {h_after}"); ok = False

        # 5. 幂等
        r = run("prd_writeback.py", str(skill / "change-requests" / "CR-X"))
        if "幂等" in r.stdout or "已记录" in r.stdout:
            print(f"  {PASS} 二次回填同 CR → 幂等无操作")
        else:
            print(f"  {FAIL} 应幂等,得 {r.stdout[:160]}"); ok = False

        # 6. 多 CR → 去重排序
        (skill / "change-requests" / "CR-AAA").mkdir()
        (skill / "change-requests" / "CR-AAA" / "acceptance-spec.md").write_text(
            "```yaml\nderived_from: {prd_section: PRD-FOO, prd_hash: x}\n```\n",
            encoding="utf-8")
        run("prd_writeback.py", str(skill / "change-requests" / "CR-AAA"))
        prd_text = prd_path.read_text(encoding="utf-8")
        # 应按字母序:CR-AAA 在 CR-X 之前
        assoc = [l for l in prd_text.splitlines() if "关联 CR" in l]
        if assoc and "CR-AAA, CR-X" in assoc[0]:
            print(f"  {PASS} 多 CR 回填 → 去重+排序: {assoc[0].strip()}")
        else:
            print(f"  {FAIL} 排序异常: {assoc}"); ok = False

        return ok
    except Exception as e:
        import traceback
        print(f"  {FAIL} PRD 链路契约异常: {e}")
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_flatten_reproducible_contract():
    """逆向输入 flatten 可复现契约（借 BMAD flatten）：同一份代码必产同一 input_hash。

    逆向链最隐蔽的不可复现来源——rglob 顺序/--max-files 截断/源码被悄改——
    会让"同一项目"扫出不同候选集。flatten 把输入压成确定性、可哈希的清单：
      1. 同一项目两次扫描 → input_hash 完全相同（确定性）
      2. 改动任一源码文件 → input_hash 必变（敏感性，防伪造"我没动过代码"）
    """
    section("35. 逆向输入 flatten 可复现契约 (BMAD flatten)")
    sl = ROOT / "scripts" / "scan_legacy.py"
    if not sl.exists():
        print(f"  {FAIL} scan_legacy.py 不存在")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-flatten-"))
    try:
        proj = tmp / "legacy"
        (proj / "src" / "auth").mkdir(parents=True)
        (proj / "src" / "auth" / "login.py").write_text(
            "def check_login(u, p):\n    if u and p:\n        return True\n    return False\n",
            encoding="utf-8")
        (proj / "src" / "util.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        def scan(out):
            return subprocess.run(
                [sys.executable, str(sl), str(proj), "--out", str(out)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, env=SUBPROCESS_ENV, cwd=str(ROOT))

        def read_hash(out_dir):
            f = out_dir / "reverse-input-flatten.yml"
            if not f.exists():
                return None
            return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("input_hash")

        ok = True
        d1, d2 = tmp / "o1", tmp / "o2"
        scan(d1 / "c.yml"); scan(d2 / "c.yml")
        h1, h2 = read_hash(d1), read_hash(d2)
        if h1 and h1 == h2:
            print(f"  {PASS} 同一项目两次扫描 → input_hash 一致 ({h1[:12]})")
        else:
            print(f"  {FAIL} 应一致：{h1} vs {h2}"); ok = False

        # 改一个字节 → hash 必变
        (proj / "src" / "util.py").write_text("def add(a, b):\n    return a + b + 0\n", encoding="utf-8")
        d3 = tmp / "o3"
        scan(d3 / "c.yml")
        h3 = read_hash(d3)
        if h3 and h3 != h1:
            print(f"  {PASS} 改动源码 → input_hash 必变（敏感性）")
        else:
            print(f"  {FAIL} 改码后 hash 未变（伪造风险）：{h3}"); ok = False
        return ok
    except Exception as e:
        print(f"  {FAIL} flatten 契约异常: {e}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_must_haves_contract():
    """must_haves 谓词校验契约（借 GSD 判据语法，确定性）：pass / blocked / skip。"""
    section("33. must_haves 谓词契约 (must_haves_check)")
    mh = ROOT / "scripts" / "must_haves_check.py"
    if not mh.exists():
        print(f"  {FAIL} must_haves_check.py 不存在")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-musthaves-"))

    def run(cr, root):
        return subprocess.run(
            [sys.executable, str(mh), str(cr), "--root", str(root), "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=SUBPROCESS_ENV,
        )

    try:
        import json as _json
        repo = tmp / "repo"
        (repo / "src").mkdir(parents=True)
        cr = repo / "DeliverHQ" / "change-requests" / "CR-X"
        cr.mkdir(parents=True)

        (repo / "src" / "todo.py").write_text(
            "\n".join("class Todo:" if i == 0 else "    f%d = %d" % (i, i) for i in range(12)),
            encoding="utf-8")

        manifest = (
            "must_haves:\n"
            "  artifacts:\n"
            "    - name: Todo\n"
            "      path: src/todo.py\n"
            "      min_lines: 8\n"
            "      exports: [\"Todo\"]\n"
            "      anti_stub: true\n"
        )
        (cr / "verification-manifest.yml").write_text(manifest, encoding="utf-8")

        ok = True
        r = run(cr, repo)
        if r.returncode == 0 and _json.loads(r.stdout)["status"] == "pass":
            print(f"  {PASS} 谓词全成立 → PASS")
        else:
            print(f"  {FAIL} 应 PASS，得 {r.stdout[:120]}"); ok = False

        (repo / "src" / "todo.py").write_text("class Todo:\n    pass  # TODO\n", encoding="utf-8")
        r = run(cr, repo)
        if r.returncode == 1 and _json.loads(r.stdout)["status"] == "blocked":
            print(f"  {PASS} stub/缺行 → BLOCKED")
        else:
            print(f"  {FAIL} 应 BLOCKED，得 rc={r.returncode} {r.stdout[:120]}"); ok = False

        (cr / "verification-manifest.yml").write_text("build:\n  enabled: false\n", encoding="utf-8")
        r = run(cr, repo)
        if r.returncode == 0 and _json.loads(r.stdout)["status"] == "skip":
            print(f"  {PASS} 无 must_haves 段 → skip（向后兼容）")
        else:
            print(f"  {FAIL} 应 skip，得 {r.stdout[:120]}"); ok = False

        return ok
    except Exception as e:
        print(f"  {FAIL} must_haves 契约异常: {e}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_token_budget_contract():
    """入口链 token 预算契约（Pocock token 经济一等指标）：常驻链不得无声膨胀。"""
    section("32. 入口链 token 预算契约 (token_budget)")
    tb = ROOT / "scripts" / "token_budget.py"
    if not tb.exists():
        print(f"  {FAIL} token_budget.py 不存在")
        return False
    rc = subprocess.run(
        [sys.executable, str(tb)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        env=SUBPROCESS_ENV,
    )
    out = rc.stdout.decode("utf-8", "replace")
    if rc.returncode == 0 and "在预算内" in out:
        for line in out.splitlines():
            if "总计" in line:
                print(f"  {PASS} {line.strip()}")
                break
        else:
            print(f"  {PASS} 入口链在预算内")
        return True
    print(f"  {FAIL} 入口链超 token 预算（裁剪入口或下沉到 references/）")
    for line in out.splitlines():
        if "总计" in line:
            print(f"    {line.strip()}")
    return False


def check_capability_tiers_contract():
    """能力调用分层契约（Pocock 双轴）：core 由 default_enabled 派生，且有界。"""
    section("30. 能力调用分层契约 (capability_tiers)")
    ct = ROOT / "scripts" / "capability_tiers.py"
    if not ct.exists():
        print(f"  {FAIL} capability_tiers.py 不存在")
        return False

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import capability_tiers as ctmod
    except Exception as e:
        print(f"  {FAIL} 无法导入 capability_tiers: {e}")
        return False

    rows = ctmod.parse_matrix()
    if not rows:
        print(f"  {FAIL} 未从矩阵解析到任何能力行")
        return False
    core, on_demand = ctmod.classify(rows)

    ok = True
    if all(r["default_enabled"] for r in core) and not any(r["default_enabled"] for r in on_demand):
        print(f"  {PASS} 分层与 default_enabled 一致（core={len(core)}, on-demand={len(on_demand)}）")
    else:
        print(f"  {FAIL} 分层与 default_enabled 不一致")
        ok = False

    CORE_MAX = 20
    if len(core) <= CORE_MAX:
        print(f"  {PASS} core 集合有界（{len(core)} ≤ {CORE_MAX}）")
    else:
        print(f"  {FAIL} core 集合超界（{len(core)} > {CORE_MAX}）：新增常驻能力须显式提高上限并说明")
        ok = False

    return ok


def check_knowledge_lifecycle_contract():
    """知识生命周期契约：重复知识可晋升，退场知识必须可审计。"""
    section("31. 知识生命周期契约 (memory_store)")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import memory_store
    except Exception as e:
        print(f"  {FAIL} 无法导入 memory_store: {e}")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-memory-contract-"))
    store = memory_store.MemoryStore(tmp / "memory")
    first = store.add("repeat failure", "mistake", root_cause="same cause", evidence=["missing.md"])
    store.add("repeat again", "mistake", root_cause="same cause")
    store.add("repeat third", "mistake", root_cause="same cause")
    old = store.add("old rule", "rule")
    new = store.add("new rule", "rule")
    store.supersede(old.id, new.id)
    store.obsolete(new.id, "newer guidance exists")
    report = store.audit_lifecycle(root=str(tmp), min_occurrences=3)

    ok = True
    if first.id in report["promotion_candidates"]:
        print(f"  {PASS} 重复知识进入晋升候选")
    else:
        print(f"  {FAIL} 重复知识未进入晋升候选")
        ok = False
    if not report["blockers"] and any("evidence path missing" in item for item in report["warnings"]):
        print(f"  {PASS} 生命周期审计区分 blocker 与 warning")
    else:
        print(f"  {FAIL} 生命周期审计结果异常: {report}")
        ok = False
    if store.get(new.id).status == "obsolete":
        print(f"  {PASS} obsolete 退场状态可记录原因")
    else:
        print(f"  {FAIL} obsolete 状态未记录")
        ok = False
    return ok


def check_capability_stocktake_contract():
    """新增能力前必须先盘点复用/扩展路径。"""
    section("32. 能力盘点契约 (capability_stocktake)")
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT))
    try:
        import capability_stocktake
    except Exception as e:
        print(f"  {FAIL} 无法导入 capability_stocktake: {e}")
        return False

    blocked = capability_stocktake.check_stocktake(
        intent="review checks",
        proposed_name="ReviewGate",
        records=[],
    )
    accepted = capability_stocktake.check_stocktake(
        intent="review checks",
        proposed_name="Review Evidence Helper",
        why_existing_insufficient="needs a separate lifecycle seam",
        records=[],
    )
    if blocked["blockers"] and not accepted["blockers"]:
        print(f"  {PASS} 缺复用决策会阻断，记录理由后通过")
        return True
    print(f"  {FAIL} 能力盘点契约异常: blocked={blocked}, accepted={accepted}")
    return False


def check_wording_drift_contract():
    """入口文档引用能力矩阵，不重复维护能力状态表。"""
    section("33. 文档措辞漂移契约 (wording_drift_check)")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import wording_drift_check
    except Exception as e:
        print(f"  {FAIL} 无法导入 wording_drift_check: {e}")
        return False

    report = wording_drift_check.check_wording_drift(ROOT)
    if not report["blockers"]:
        print(f"  {PASS} 入口文档以 CAPABILITY-MATRIX.md 为能力状态唯一来源")
        return True
    print(f"  {FAIL} 文档漂移检查失败: {report['blockers']}")
    return False


def check_lane_advisor_contract():
    """客观规模分档建议器契约：fast / standard / high-risk / split 四类正例。"""
    section("31. 客观规模分档契约 (lane_advisor)")
    la = ROOT / "scripts" / "lane_advisor.py"
    if not la.exists():
        print(f"  {FAIL} lane_advisor.py 不存在")
        return False

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-lane-"))

    def make(spec, trace):
        cr = tmp / ("cr_%d" % make.n); make.n += 1
        cr.mkdir()
        (cr / "acceptance-spec.md").write_text(spec, encoding="utf-8")
        (cr / "traceability.yml").write_text(trace, encoding="utf-8")
        return cr
    make.n = 0

    def run(cr):
        return subprocess.run(
            [sys.executable, str(la), str(cr), "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=SUBPROCESS_ENV,
        )

    def trace_files(n):
        lines = ["schema: x", "X:", "  implementation:"]
        for i in range(n):
            lines.append("    - file: f%d.py" % i)
        return "\n".join(lines) + "\n"

    try:
        import json as _json
        ok = True

        r = run(make("## 验收条件\n### 场景 1: a\n", trace_files(1)))
        if _json.loads(r.stdout)["lane"] == "fast":
            print(f"  {PASS} 小改动 → fast")
        else:
            print(f"  {FAIL} 小改动应 fast，得 {r.stdout[:80]}"); ok = False

        r = run(make("## 验收条件\n### 场景 1: a\n### 场景 2: b\n### 场景 3: c\n", trace_files(4)))
        if _json.loads(r.stdout)["lane"] == "standard":
            print(f"  {PASS} 中等规模 → standard")
        else:
            print(f"  {FAIL} 中等规模应 standard，得 {r.stdout[:80]}"); ok = False

        r = run(make("## 验收条件\n### 场景 1: 用户登录 auth token\n",
                     "schema: x\nX:\n  implementation:\n    - file: login.py\n"))
        if _json.loads(r.stdout)["lane"] == "high-risk":
            print(f"  {PASS} 敏感域 → high-risk（不降级）")
        else:
            print(f"  {FAIL} 敏感域应 high-risk，得 {r.stdout[:80]}"); ok = False

        r = run(make("## 验收条件\n### 场景 1: a\n", trace_files(9)))
        if r.returncode == 2 and _json.loads(r.stdout)["decision"] == "split":
            print(f"  {PASS} 超硬阈值 → 建议拆分 (exit 2)")
        else:
            print(f"  {FAIL} 超阈值应建议拆分，rc={r.returncode}"); ok = False

        return ok
    except Exception as e:
        print(f"  {FAIL} lane_advisor 契约异常: {e}")
        return False
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def check_gate_composition_contract():
    """Gate 冻结 + 组合规则契约：防止治理债无声扩张.

    正例：当前仓库应 PASS。
    反例：临时引入一个未登记的 *gate*.py → 检查应 BLOCK。
    """
    section("29. Gate 冻结 + 组合规则契约")
    gc = ROOT / "scripts" / "gate_composition_check.py"
    if not gc.exists():
        print(f"  {FAIL} gate_composition_check.py 不存在")
        return False

    rc = subprocess.run(
        [sys.executable, str(gc)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        env=SUBPROCESS_ENV,
    ).returncode
    if rc != 0:
        print(f"  {FAIL} 当前仓库应 PASS 但被 BLOCK")
        return False
    print(f"  {PASS} 当前 Gate 集合与组合规则 PASS")

    intruder = ROOT / "scripts" / "_tmp_intruder_gate.py"
    try:
        intruder.write_text("# temp unregistered gate for contract test\n", encoding="utf-8")
        rc2 = subprocess.run(
            [sys.executable, str(gc)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
            env=SUBPROCESS_ENV,
        ).returncode
        if rc2 == 0:
            print(f"  {FAIL} 未登记的新 Gate 脚本应被 BLOCK 但通过了")
            return False
        print(f"  {PASS} 未登记的新 Gate 脚本 → BLOCKED")
        return True
    finally:
        if intruder.exists():
            intruder.unlink()


def check_needs_clarification_contract():
    """SpecGate 必须阻断含 [NEEDS CLARIFICATION] 的 spec（借 Spec-Kit 约定）。

    正反例：
      - 注入 [NEEDS CLARIFICATION] 的临时 spec → BLOCKED
      - 同一 spec 去掉标记 → 不因该标记阻断
    用临时目录，不污染示例 CR。
    """
    section("28. NEEDS CLARIFICATION 契约 (SpecGate)")
    specgate = ROOT / "scripts" / "specgate.py"
    if not specgate.exists():
        print(f"  {FAIL} specgate.py 不存在")
        return False

    base = (
        "# Acceptance Spec\n\n"
        "## 1. Data Spec\n字段 A：字符串\n\n"
        "## 2. Interface Spec\n`do()`：执行\n\n"
        "## 3. Behavior Spec\n## 验收条件\n"
        "### 场景 1: 正常\n- 响应时间 < 200ms\n"
        "### 场景 2: 异常\n- 报错\n"
        "### 场景 3: 边界\n- 上限\n"
    )
    marker = "\n### 场景 4: 并发\n- 并发上限 [NEEDS CLARIFICATION: 未定]\n"

    tmp = Path(tempfile.mkdtemp(prefix="deliverhq-needs-clar-"))
    try:
        neg = tmp / "neg.md"
        neg.write_text(base + marker, encoding="utf-8")
        pos = tmp / "pos.md"
        pos.write_text(base, encoding="utf-8")

        neg_rc = subprocess.run(
            [sys.executable, str(specgate), str(neg)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
            env=SUBPROCESS_ENV,
        ).returncode
        pos_rc = subprocess.run(
            [sys.executable, str(specgate), str(pos)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
            env=SUBPROCESS_ENV,
        ).returncode

        ok = True
        if neg_rc != 0:
            print(f"  {PASS} 含 [NEEDS CLARIFICATION] 的 spec 被 BLOCKED")
        else:
            print(f"  {FAIL} 含 [NEEDS CLARIFICATION] 的 spec 未被阻断")
            ok = False
        if pos_rc == 0:
            print(f"  {PASS} 去掉标记后不因该标记阻断")
        else:
            print(f"  {FAIL} 去掉标记后仍被阻断（标记检查过宽）")
            ok = False
        return ok
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


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
        results["light_entry_contract"] = check_light_entry_contract()
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
        results["verb_layer_contract"] = check_verb_layer_contract()
        results["capability_status_consistency"] = check_capability_status_consistency()
        results["gate_contract"] = check_gate_contract()
        results["reverse_spec_contract"] = check_reverse_spec_contract()
        results["loop_control_contract"] = check_loop_control_contract()
        results["high_risk_approval_failclosed"] = check_high_risk_approval_failclosed()
        results["plan_checker_contract"] = check_plan_checker_contract()
        results["evidence_loop_contract"] = check_evidence_loop_contract()
        results["architecturegate_confirmation_contract"] = check_architecturegate_confirmation_contract()
        results["designgate_mobile_keyword_contract"] = check_designgate_mobile_keyword_contract()
        results["predev_requires_architecture_contract"] = check_predev_requires_architecture_contract()
        results["structure_governance_contract"] = check_structure_governance_contract()
        results["packaging_hygiene"] = check_packaging_hygiene()
        results["needs_clarification_contract"] = check_needs_clarification_contract()
        results["gate_composition_contract"] = check_gate_composition_contract()
        results["capability_tiers_contract"] = check_capability_tiers_contract()
        results["knowledge_lifecycle_contract"] = check_knowledge_lifecycle_contract()
        results["capability_stocktake_contract"] = check_capability_stocktake_contract()
        results["wording_drift_contract"] = check_wording_drift_contract()
        results["token_budget_contract"] = check_token_budget_contract()
        results["must_haves_contract"] = check_must_haves_contract()
        results["handoff_state_contract"] = check_handoff_state_contract()
        results["lane_advisor_contract"] = check_lane_advisor_contract()
        results["flatten_reproducible_contract"] = check_flatten_reproducible_contract()
        results["prd_linkage_contract"] = check_prd_linkage_contract()
    finally:
        restore_example_crs(snapshot_dir)

    if tuple(results) != ALL_CONTRACTS:
        raise RuntimeError("selftest contract catalog does not match execution order")

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
