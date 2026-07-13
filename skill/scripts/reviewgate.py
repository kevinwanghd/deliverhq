#!/usr/bin/env python3
"""
ReviewGate - 代码审查门禁检查
验证 review-report.md、真实变更证据、traceability 与测试计划，确保不是只看审查报告文本。
"""


import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from cr_state import update_gate_from_result
from runtime_support import configure_console

# 定位 DeliverHQ 根目录（脚本在 DeliverHQ/scripts/ 下）
DELIVERHQ_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = DELIVERHQ_ROOT.parent
configure_console()


class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def _read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def parse_review_report(report_path):
    """解析 review-report.md 提取审查结果"""

    if not Path(report_path).exists():
        return None, "review-report.md 不存在"

    content = _read_text(Path(report_path))

    verdict = "UNKNOWN"
    if re.search(r'结论\*\*[:：].*?(✅\s*PASS)', content, re.DOTALL):
        verdict = "PASS"
    elif re.search(r'结论\*\*[:：].*?(⚠️\s*PASS WITH CONDITIONS)', content, re.DOTALL):
        verdict = "PASS_WITH_CONDITIONS"
    elif re.search(r'结论\*\*[:：].*?(❌\s*BLOCKED)', content, re.DOTALL):
        verdict = "BLOCKED"
    elif 'APPROVED' in content:
        verdict = "PASS"

    p0_section = re.search(r'### P0 阻断问题.*?(?=### P1|### P2|## 审查结论|$)', content, re.DOTALL)
    p0_count = 0
    if p0_section:
        p0_text = p0_section.group(0)
        p0_items = []
        for line in p0_text.splitlines():
            stripped = line.strip()
            if re.match(r'^(\d+\.|-|\*)\s+', stripped):
                if '{{' not in stripped and 'P0 阻断问题' not in stripped:
                    if any(keyword in stripped for keyword in ['❌', 'BLOCKED', 'P0', '阻断', 'NEED_FIX', '必须', '严重']):
                        p0_items.append(stripped)
                    elif len(stripped) > 20:
                        p0_items.append(stripped)
        p0_count = len(p0_items)

    scenario_sections = re.findall(r'### 场景\s*\d+:.*?\*\*审查结果\*\*.*?(✅ PASS|⚠️ NEED_FIX|❌ BLOCKED)', content, re.DOTALL)
    scenarios_passed = sum(1 for s in scenario_sections if '✅ PASS' in s)
    scenarios_total = len(scenario_sections)

    trace_complete = 'Traceability 完整性' in content and 'P0 阻断问题' in content

    return {
        'verdict': verdict,
        'p0_count': p0_count,
        'scenarios_passed': scenarios_passed,
        'scenarios_total': scenarios_total,
        'trace_complete': trace_complete,
        'content': content,
    }, None


def _load_traceability(cr_path: Path):
    trace_path = cr_path / 'traceability.yml'
    if not trace_path.exists():
        return None, 'traceability.yml 不存在'

    try:
        return yaml.safe_load(_read_text(trace_path)) or {}, None
    except Exception as exc:
        return None, f'解析 traceability.yml 失败: {exc}'


def _collect_traceability_files(traceability: Dict) -> List[str]:
    files: List[str] = []
    for cr_data in traceability.values():
        if not isinstance(cr_data, dict):
            continue
        for entry in cr_data.get('implementation', []) or []:
            if isinstance(entry, dict) and entry.get('file'):
                files.append(entry['file'].replace('\\', '/'))
        for entry in cr_data.get('tests', []) or []:
            if isinstance(entry, dict) and entry.get('file'):
                files.append(entry['file'].replace('\\', '/'))
        for entry in cr_data.get('data_changes', []) or []:
            if isinstance(entry, dict) and entry.get('migration'):
                files.append(entry['migration'].replace('\\', '/'))
    return files


def _traceability_closure_blockers(traceability: Dict) -> List[str]:
    blockers: List[str] = []
    for cr_id, cr_data in traceability.items():
        if cr_id in {'schema', 'version'} or not isinstance(cr_data, dict):
            continue
        acceptance_criteria = cr_data.get('acceptance_criteria') or []
        implementation = cr_data.get('implementation') or []
        tests = cr_data.get('tests') or []
        if acceptance_criteria and not implementation:
            blockers.append('%s: acceptance_criteria 有记录但 implementation 为空' % cr_id)
        if acceptance_criteria and not tests:
            blockers.append('%s: acceptance_criteria 有记录但 tests 为空' % cr_id)

        covered_numbers = set()
        for test_entry in tests:
            if not isinstance(test_entry, dict):
                continue
            for case in test_entry.get('cases', []) or []:
                covers = str(case.get('covers', '')) if isinstance(case, dict) else ''
                for match in re.findall(r'#(\d+)', covers):
                    covered_numbers.add(int(match))

        if acceptance_criteria and not covered_numbers:
            blockers.append('%s: tests 存在但未声明覆盖任何验收条件编号' % cr_id)
        elif acceptance_criteria and covered_numbers:
            missing = [idx for idx in range(1, len(acceptance_criteria) + 1) if idx not in covered_numbers]
            if missing:
                blockers.append('%s: tests 未覆盖验收条件编号 %s' % (cr_id, ', '.join(str(item) for item in missing)))
    return blockers


def _collect_changed_files_from_evidence(cr_path: Path) -> List[str]:
    candidates = [
        cr_path / 'evidence' / 'changed-files.json',
        cr_path / 'changed-files.json',
        cr_path / 'evidence' / 'dev-phase-result.json',
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(payload, list):
            return [str(item).replace('\\', '/') for item in payload]
        if isinstance(payload, dict):
            values = payload.get('changed_files') or payload.get('files') or []
            if values:
                return [str(item).replace('\\', '/') for item in values]
    return []


def _collect_changed_files() -> Optional[List[str]]:
    try:
        result = subprocess.run(
            ['git', '-C', str(PROJECT_ROOT), 'status', '--porcelain'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    changed_files: List[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if ' -> ' in path:
            path = path.split(' -> ')[-1].strip()
        changed_files.append(path.replace('\\', '/'))
    return changed_files


def _relevant_changed_files(changed_files: Optional[List[str]]) -> List[str]:
    if not changed_files:
        return []

    ignored_prefixes = (
        'DeliverHQ/', 'change-requests/', 'skill/change-requests/',
        '_archived/', 'delivery/',
    )
    relevant = [path for path in changed_files if not path.startswith(ignored_prefixes)]
    return relevant or list(changed_files)


def _load_spec_and_tests(cr_path: Path) -> Tuple[Optional[str], Optional[str], List[str]]:
    spec_path = cr_path / 'acceptance-spec.md'
    test_plan_path = cr_path / 'test-plan.md'
    blockers: List[str] = []

    spec_content = _read_text(spec_path) if spec_path.exists() else None
    test_plan_content = _read_text(test_plan_path) if test_plan_path.exists() else None

    if not spec_path.exists():
        blockers.append('缺少 acceptance-spec.md')
    elif spec_content is not None and ('{{' in spec_content or '[待确认]' in spec_content or '[TODO]' in spec_content):
        blockers.append('acceptance-spec.md 仍有占位符')

    if not test_plan_path.exists():
        blockers.append('缺少 test-plan.md')
    elif test_plan_content is not None and ('{{' in test_plan_content or '[待确认]' in test_plan_content or '[TODO]' in test_plan_content):
        blockers.append('test-plan.md 仍有占位符')

    return spec_content, test_plan_content, blockers


def check_reviewgate(cr_path):
    """ReviewGate 检查"""

    cr_path = Path(cr_path)
    print(f"{Color.BLUE}=== ReviewGate 检查 ==={Color.END}\n")

    report_path = cr_path / 'review-report.md'
    blockers: List[str] = []
    warnings: List[str] = []
    commands_run: List[str] = ['review-report.md parse', 'traceability.yml check', 'git status --porcelain']
    artifacts = ['review-report.md', 'traceability.yml', 'test-plan.md', 'acceptance-spec.md', 'evidence/changed-files.json', 'verification-manifest.yml']

    if not report_path.exists():
        print(f"{Color.RED}✗ review-report.md 不存在{Color.END}")
        blockers.append('缺少 review-report.md，Review Agent 未执行')
        update_gate_from_result(
            cr_path,
            'review',
            False,
            blockers=blockers,
            state_after_pass='code_review',
            current_phase='review',
            current_owner='review-agent',
            next_required_gate='review',
            commands_run=commands_run,
            artifacts=['review-report.md'],
            next_action='生成 review-report.md 后重新运行 ReviewGate',
        )
        return False, blockers

    # 解析 review-report
    result, error = parse_review_report(report_path)
    if error:
        print(f"{Color.RED}✗ 解析失败: {error}{Color.END}")
        blockers.append(error)
        update_gate_from_result(
            cr_path,
            'review',
            False,
            blockers=blockers,
            state_after_pass='code_review',
            current_phase='review',
            current_owner='review-agent',
            next_required_gate='review',
            commands_run=commands_run,
            artifacts=artifacts,
            next_action='修复 ReviewGate 阻断项并重新运行',
            warnings=warnings,
        )
        return False, blockers

    assert result is not None
    print(f"{Color.BLUE}[审查报告]{Color.END}")
    print(f"  审查结论: {result['verdict']}")

    if result['verdict'] == 'BLOCKED':
        print(f"{Color.RED}  ✗ review-report.md 判定为 BLOCKED{Color.END}")
        blockers.append('review-report.md 状态为 BLOCKED')
    elif result['verdict'] == 'PASS':
        print(f"{Color.GREEN}  ✓ review-report.md 判定为 PASS{Color.END}")
    elif result['verdict'] == 'PASS_WITH_CONDITIONS':
        print(f"{Color.YELLOW}  ⚠ review-report.md 判定为 PASS WITH CONDITIONS{Color.END}")
        warnings.append('有条件放行，P1 问题需后续修复')
    else:
        print(f"{Color.RED}  ✗ 无法识别审查结论{Color.END}")
        blockers.append('review-report.md 结论不明确')

    # 检查 2: P0 问题数
    print(f"\n{Color.BLUE}[P0 阻断问题]{Color.END}")
    print(f"  P0 问题数: {result['p0_count']}")

    if result['p0_count'] > 0:
        print(f"{Color.RED}  ✗ 存在 {result['p0_count']} 个 P0 问题{Color.END}")
        blockers.append(f'存在 {result["p0_count"]} 个 P0 阻断问题')
    else:
        print(f"{Color.GREEN}  ✓ 无 P0 问题{Color.END}")

    # 检查 3: 验收场景覆盖
    print(f"\n{Color.BLUE}[验收场景审查]{Color.END}")
    if result['scenarios_total'] > 0:
        scenario_rate = (result['scenarios_passed'] / result['scenarios_total']) * 100
        print(f"  通过率: {result['scenarios_passed']}/{result['scenarios_total']} ({scenario_rate:.0f}%)")

        if scenario_rate < 100:
            print(f"{Color.YELLOW}  ⚠ 部分验收场景需修复{Color.END}")
            warnings.append(f'验收场景通过率 {scenario_rate:.0f}%')
        else:
            print(f"{Color.GREEN}  ✓ 所有验收场景通过{Color.END}")
    else:
        print(f"{Color.RED}  ✗ 未检测到验收场景审查{Color.END}")
        blockers.append('review-report.md 缺少逐场景审查，不能只给总体结论')

    # 检查 4: Traceability 与真实变更
    print(f"\n{Color.BLUE}[Traceability / 变更证据]{Color.END}")
    traceability, trace_error = _load_traceability(cr_path)
    if trace_error:
        print(f"{Color.RED}  ✗ {trace_error}{Color.END}")
        blockers.append(trace_error)
        trace_files: List[str] = []
    elif traceability is None:
        trace_files = []
    else:
        trace_files = _collect_traceability_files(traceability)
        if not trace_files:
            blockers.append('traceability.yml 未记录 implementation/tests 文件')
            print(f"{Color.RED}  ✗ traceability.yml 未记录 implementation/tests 文件{Color.END}")
        else:
            print(f"{Color.GREEN}  ✓ traceability.yml 已记录 {len(trace_files)} 个实现/测试文件{Color.END}")
        closure_blockers = _traceability_closure_blockers(traceability)
        if closure_blockers:
            for item in closure_blockers:
                print(f"{Color.RED}  ✗ {item}{Color.END}")
            blockers.extend(closure_blockers)
        else:
            print(f"{Color.GREEN}  ✓ AC → implementation/tests 闭环完整{Color.END}")

    changed_files = _collect_changed_files()
    evidence_changed_files = _collect_changed_files_from_evidence(cr_path)
    if evidence_changed_files:
        print(f"{Color.GREEN}  ✓ evidence changed-files 记录 {len(evidence_changed_files)} 个文件{Color.END}")
    relevant_changed_files = _relevant_changed_files(evidence_changed_files or changed_files)
    if changed_files is None and not evidence_changed_files:
        blockers.append('缺少 git diff / changed-files 证据，ReviewGate 不能只依赖 review-report.md')
        print(f"{Color.RED}  ✗ 缺少 git diff / changed-files 证据{Color.END}")
    elif relevant_changed_files:
        print(f"{Color.GREEN}  ✓ 发现 {len(relevant_changed_files)} 个可核对变更文件{Color.END}")
        uncovered = [path for path in relevant_changed_files if path not in trace_files]
        if uncovered:
            print(f"{Color.RED}  ✗ 变更未映射到 traceability: {uncovered[:5]}{Color.END}")
            blockers.append('changed files 与 traceability 不一致')
    else:
        blockers.append('未发现可核对的 git diff / changed-files 证据')
        print(f"{Color.RED}  ✗ 未发现可核对的变更证据{Color.END}")

    # 检查 5: 必需章节完整性
    print(f"\n{Color.BLUE}[报告完整性]{Color.END}")
    content = result['content']
    required_sections = [
        '## 验收条件实现审查',
        '## 代码质量审查',
        '## Traceability 完整性',
        '## Adversarial Checks',
        '## 发现的问题汇总',
        '## 审查结论',
    ]
    missing_sections = [section for section in required_sections if section not in content]

    if missing_sections:
        print(f"{Color.RED}  ✗ 缺少必需章节: {missing_sections}{Color.END}")
        blockers.append(f"缺少章节: {', '.join(missing_sections)}")
    else:
        print(f"{Color.GREEN}  ✓ 报告结构完整{Color.END}")

    if '{{' in content:
        print(f"{Color.RED}  ✗ 包含未替换模板变量{Color.END}")
        blockers.append('包含模板变量，未填充实际内容')
    else:
        print(f"{Color.GREEN}  ✓ 无模板变量{Color.END}")

    # 检查 6: Spec / Test / Verification 证据
    print(f"\n{Color.BLUE}[Spec / Test / Verification 证据]{Color.END}")
    _, _, spec_test_blockers = _load_spec_and_tests(cr_path)
    for message in spec_test_blockers:
        print(f"{Color.RED}  ✗ {message}{Color.END}")
    blockers.extend(spec_test_blockers)
    verification_manifest = cr_path / 'verification-manifest.yml'
    if not verification_manifest.exists():
        print(f"{Color.RED}  ✗ 缺少 verification-manifest.yml，ReviewGate 无法确认后续真实测试命令{Color.END}")
        blockers.append('缺少 verification-manifest.yml')
    else:
        print(f"{Color.GREEN}  ✓ verification-manifest.yml 存在{Color.END}")
    if not spec_test_blockers and verification_manifest.exists():
        print(f"{Color.GREEN}  ✓ acceptance-spec.md / test-plan.md / verification-manifest.yml 完整{Color.END}")

    # 汇总结果
    print(f"\n{Color.BLUE}=== ReviewGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
        print(f"\n{Color.RED}⛔ 反馈 Dev Agent 修复问题，重新运行 Review Agent{Color.END}")
        update_gate_from_result(
            cr_path,
            'review',
            False,
            blockers=blockers,
            state_after_pass='code_review',
            current_phase='review',
            current_owner='review-agent',
            next_required_gate='review',
            warnings=warnings,
            commands_run=commands_run,
            artifacts=artifacts,
            next_action='修复 ReviewGate 阻断项并重新运行',
        )
        return False, blockers

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")

    print(f"{Color.GREEN}✅ PASS - 代码审查通过，进入 Test 阶段{Color.END}")
    update_gate_from_result(
        cr_path,
        'review',
        True,
        blockers=[],
        state_after_pass='code_review',
        current_phase='review',
        current_owner='review-agent',
        next_required_gate='quality',
        warnings=warnings,
        commands_run=commands_run,
        artifacts=artifacts,
        next_action='进入 QualityGate',
    )
    return True, []


def main():
    if len(sys.argv) < 2:
        print("用法: python reviewgate.py <path/to/CR-XXX>")
        sys.exit(1)

    cr_path = sys.argv[1]
    passed, _ = check_reviewgate(cr_path)

    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
