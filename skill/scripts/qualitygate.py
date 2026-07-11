#!/usr/bin/env python3
"""
QualityGate - 质量门禁检查
汇总 quality-report.md 结果，并在标准/高风险 lane 里绑定真实验证命令。
"""


import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from baseline_comparison import compare_after_baseline
from cr_state import ensure_state, update_gate_from_result
from runtime_support import configure_console

# 定位 DeliverHQ 根目录（脚本在 DeliverHQ/scripts/ 下）
DELIVERHQ_ROOT = Path(__file__).parent.parent
configure_console()


class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


def parse_quality_report(report_path):
    """解析 quality-report.md 提取检查结果"""

    if not Path(report_path).exists():
        return None, "quality-report.md 不存在"

    content = Path(report_path).read_text(encoding='utf-8')

    verdict_match = re.search(r'质量等级.*?(🟢|🟡|🔴|PASS|BLOCKED)', content, re.IGNORECASE)
    if verdict_match:
        verdict = verdict_match.group(1)
        if '🟢' in verdict or 'PASS' in verdict:
            verdict_status = 'PASS'
        elif '🔴' in verdict or 'BLOCKED' in verdict:
            verdict_status = 'BLOCKED'
        else:
            verdict_status = 'PASS_WITH_WARNING'
    else:
        verdict_status = 'UNKNOWN'

    p0_section = re.search(r'## P0 检查项.*?(?=## P1|## 发现的问题|$)', content, re.DOTALL)
    p0_passed = 0
    p0_total = 0
    p0_blockers: List[str] = []

    if p0_section:
        p0_text = p0_section.group(0)
        p0_passed = p0_text.count('✅')
        p0_failed = p0_text.count('❌')
        p0_total = p0_passed + p0_failed

        blocker_matches = re.findall(r'[|]\s*\d+\s*[|]\s*([^|]+?)\s*[|].*?阻断', p0_text)
        p0_blockers = [match.strip() for match in blocker_matches]

    coverage_match = re.search(r'覆盖率.*?(\d+)%', content)
    coverage = int(coverage_match.group(1)) if coverage_match else None

    return {
        'verdict': verdict_status,
        'p0_passed': p0_passed,
        'p0_total': p0_total,
        'p0_blockers': p0_blockers,
        'coverage': coverage,
    }, None


def check_gate_reports(cr_path):
    """检查其他 Gate 报告状态"""

    gate_statuses = {}
    gates = ['specgate', 'designgate', 'context-window']

    for gate in gates:
        report_path = Path(cr_path) / f"{gate}-report.md"
        if report_path.exists():
            content = report_path.read_text(encoding='utf-8')
            if 'PASS' in content:
                gate_statuses[gate] = 'PASS'
            elif 'BLOCKED' in content:
                gate_statuses[gate] = 'BLOCKED'
            else:
                gate_statuses[gate] = 'UNKNOWN'
        else:
            gate_statuses[gate] = 'MISSING'

    return gate_statuses


def load_verification_manifest(cr_path):
    """加载 verification-manifest.yml 配置"""

    manifest_path = Path(cr_path) / 'verification-manifest.yml'
    if not manifest_path.exists():
        return None, 'verification-manifest.yml 不存在'

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = yaml.safe_load(f)
        return manifest, None
    except Exception as exc:
        return None, f'解析 verification-manifest.yml 失败: {exc}'


def _has_enabled_verification(manifest):
    build_enabled = manifest.get('build', {}).get('enabled', False)
    unit_enabled = manifest.get('test', {}).get('unit', {}).get('enabled', False)
    lint_enabled = any(tool.get('enabled', True) for tool in manifest.get('lint', {}).get('tools', []))
    return build_enabled or unit_enabled or lint_enabled


def _resolve_lane(cr_path, lane_override=None):
    if lane_override:
        return lane_override
    return ensure_state(Path(cr_path)).lane


def normalize_verification_command(command: str) -> str:
    """Make manifest commands portable across Windows/macOS/Linux."""
    stripped = (command or "").strip()
    for launcher in ("python3", "python"):
        if stripped == launcher:
            return f'"{sys.executable}"'
        if stripped.startswith(launcher + " "):
            return f'"{sys.executable}" {stripped[len(launcher) + 1:]}'
    return command


def execute_verification_command(command, working_dir='.', timeout=300):
    """执行验证命令"""

    try:
        command = normalize_verification_command(command)
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': '命令超时',
        }
    except Exception as exc:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': str(exc),
        }


def run_real_verification(cr_path, manifest):
    """执行真实验证命令"""

    print(f"\n{Color.BLUE}=== 真实验证执行 ==={Color.END}\n")

    verification_results = {}
    blockers = []

    # 1. 构建验证
    if manifest.get('build', {}).get('enabled', False):
        print(f"{Color.BLUE}[构建验证]{Color.END}")
        build_config = manifest['build']
        result = execute_verification_command(
            build_config['command'],
            build_config.get('working_dir', '.'),
            build_config.get('timeout', 300),
        )
        verification_results['build'] = result

        if result['success']:
            print(f"{Color.GREEN}  ✓ 构建成功{Color.END}")
        else:
            print(f"{Color.RED}  ✗ 构建失败 (exit {result['returncode']}){Color.END}")
            if result['stderr']:
                print(f"    {result['stderr'][:200]}")
            blockers.append('构建验证失败')

    # 2. 单元测试
    if manifest.get('test', {}).get('unit', {}).get('enabled', False):
        print(f"\n{Color.BLUE}[单元测试]{Color.END}")
        test_config = manifest['test']['unit']
        result = execute_verification_command(
            test_config['command'],
            test_config.get('working_dir', '.'),
            test_config.get('timeout', 600),
        )
        verification_results['test_unit'] = result

        if result['success']:
            print(f"{Color.GREEN}  ✓ 单元测试通过{Color.END}")

            if test_config.get('coverage_enabled', False):
                threshold = test_config.get('coverage_threshold', 80)
                coverage_match = re.search(r'(\d+)%', result['stdout'])
                if coverage_match:
                    coverage = int(coverage_match.group(1))
                    if coverage < threshold:
                        print(f"{Color.RED}  ✗ 覆盖率 {coverage}% < 目标 {threshold}%{Color.END}")
                        blockers.append(f'测试覆盖率 {coverage}% 低于目标 {threshold}%')
                    else:
                        print(f"{Color.GREEN}  ✓ 覆盖率 {coverage}% ≥ 目标 {threshold}%{Color.END}")
        else:
            print(f"{Color.RED}  ✗ 单元测试失败{Color.END}")
            if result['stderr']:
                print(f"    {result['stderr'][:200]}")
            blockers.append('单元测试失败')

    # 3. 静态分析
    if manifest.get('lint', {}).get('enabled', False):
        print(f"\n{Color.BLUE}[静态分析]{Color.END}")
        lint_tools = manifest['lint'].get('tools', [])
        for tool in lint_tools:
            if tool.get('enabled', True):
                result = execute_verification_command(
                    tool['command'],
                    tool.get('working_dir', '.'),
                    tool.get('timeout', 300),
                )
                verification_results[f"lint_{tool['name']}"] = result

                severity = tool.get('severity', 'warning')
                if result['success']:
                    print(f"{Color.GREEN}  ✓ {tool['name']} 通过{Color.END}")
                else:
                    if severity == 'error':
                        print(f"{Color.RED}  ✗ {tool['name']} 失败{Color.END}")
                        blockers.append(f"{tool['name']} 检查失败")
                    else:
                        print(f"{Color.YELLOW}  ⚠ {tool['name']} 有告警{Color.END}")

    return verification_results, blockers


def check_qualitygate(cr_path, mode='hybrid', lane=None):
    """QualityGate 检查"""

    cr_path = Path(cr_path)
    lane = _resolve_lane(cr_path, lane)

    print(f"{Color.BLUE}=== QualityGate 检查 ==={Color.END}")
    print(f"lane: {lane}")
    print(f"模式: {mode}\n")

    report_path = cr_path / 'quality-report.md'
    if not report_path.exists():
        print(f"{Color.RED}✗ quality-report.md 不存在{Color.END}")
        update_gate_from_result(
            cr_path,
            'quality',
            False,
            blockers=['缺少 quality-report.md，Quality Agent 未执行'],
            state_after_pass='testing',
            current_phase='quality',
            current_owner='quality-agent',
            next_required_gate='quality',
        )
        return False, ['缺少 quality-report.md，Quality Agent 未执行']

    result, error = parse_quality_report(report_path)
    if error:
        print(f"{Color.RED}✗ 解析失败: {error}{Color.END}")
        update_gate_from_result(
            cr_path,
            'quality',
            False,
            blockers=[error],
            state_after_pass='testing',
            current_phase='quality',
            current_owner='quality-agent',
            next_required_gate='quality',
        )
        return False, [error]

    assert result is not None

    blockers: List[str] = []

    print(f"{Color.BLUE}[质量报告]{Color.END}")
    print(f"  质量等级: {result['verdict']}")

    if result['verdict'] == 'BLOCKED':
        print(f"{Color.RED}  ✗ quality-report.md 判定为 BLOCKED{Color.END}")
        blockers.append('quality-report.md 状态为 BLOCKED')
    elif result['verdict'] == 'PASS':
        print(f"{Color.GREEN}  ✓ quality-report.md 判定为 PASS{Color.END}")
    else:
        print(f"{Color.YELLOW}  ⚠ quality-report.md 判定为 PASS WITH WARNING{Color.END}")

    print(f"\n{Color.BLUE}[P0 检查项]{Color.END}")
    if result['p0_total'] > 0:
        p0_rate = (result['p0_passed'] / result['p0_total']) * 100
        print(f"  通过率: {result['p0_passed']}/{result['p0_total']} ({p0_rate:.0f}%)")

        if p0_rate < 100:
            print(f"{Color.RED}  ✗ P0 通过率必须 100%{Color.END}")
            blockers.append(f'P0 通过率 {p0_rate:.0f}%，未达标')
            if result['p0_blockers']:
                print(f"  阻断项: {', '.join(result['p0_blockers'][:3])}")
        else:
            print(f"{Color.GREEN}  ✓ P0 通过率 100%{Color.END}")
    else:
        print(f"{Color.YELLOW}  ⚠ 未检测到 P0 检查项{Color.END}")

    if result['coverage'] is not None:
        print(f"\n{Color.BLUE}[测试覆盖率]{Color.END}")
        print(f"  覆盖率: {result['coverage']}%")
        if result['coverage'] < 80:
            print(f"{Color.RED}  ✗ 覆盖率低于 80%{Color.END}")
            blockers.append(f'测试覆盖率 {result["coverage"]}% ，目标 ≥ 80%')
        else:
            print(f"{Color.GREEN}  ✓ 覆盖率达标{Color.END}")

    gate_statuses = check_gate_reports(cr_path)
    print(f"\n{Color.BLUE}[前置 Gate 状态]{Color.END}")
    for gate, status in gate_statuses.items():
        if status == 'PASS':
            print(f"  {Color.GREEN}✓{Color.END} {gate}: PASS")
        elif status == 'BLOCKED':
            print(f"  {Color.RED}✗{Color.END} {gate}: BLOCKED")
            blockers.append(f'{gate} 未通过')
        elif status == 'MISSING':
            print(f"  {Color.YELLOW}⚠{Color.END} {gate}: 报告缺失")
        else:
            print(f"  {Color.YELLOW}?{Color.END} {gate}: {status}")

    manifest, _ = load_verification_manifest(cr_path)
    # parse_only 允许解析 AI 报告，但不能在没有真实 manifest/命令时直接 PASS。
    manifest_required = True
    execute_real_verification = False
    commands_run: List[str] = []
    artifacts = ['quality-report.md']

    if manifest:
        if not _has_enabled_verification(manifest):
            blockers.append('verification-manifest.yml 未启用任何真实验证命令')
            print(f"\n{Color.RED}✗ verification-manifest.yml 未启用任何真实验证命令{Color.END}")
        execute_real_verification = lane in {'standard', 'high-risk'} or mode in {'hybrid', 'execute_only'}
        if mode == 'parse_only' and lane in {'standard', 'high-risk'}:
            print(f"\n{Color.YELLOW}⚠ standard/high-risk 不允许仅 parse_only，已强制执行真实验证命令{Color.END}")
        elif mode == 'parse_only':
            print(f"\n{Color.YELLOW}⚠ parse_only 仅用于 fast/demo/兼容模式，不执行真实验证命令{Color.END}")
    else:
        blockers.append('缺少 verification-manifest.yml，QualityGate 不能仅凭 AI 报告 PASS')
        print(f"\n{Color.RED}✗ 缺少 verification-manifest.yml，QualityGate 默认 fail-closed{Color.END}")

    if manifest and execute_real_verification:
        if manifest.get('build', {}).get('enabled', False):
            commands_run.append(manifest['build']['command'])
        if manifest.get('test', {}).get('unit', {}).get('enabled', False):
            commands_run.append(manifest['test']['unit']['command'])
        for tool in manifest.get('lint', {}).get('tools', []):
            if tool.get('enabled', True):
                commands_run.append(tool['command'])
        verification_results, verification_blockers = run_real_verification(cr_path, manifest)
        blockers.extend(verification_blockers)

    # must_haves 谓词校验（借 GSD 判据语法，确定性）：断言"建出来的=计划的"。
    # manifest 无 must_haves 段则跳过（向后兼容）。
    if manifest and manifest.get('must_haves'):
        print(f"\n{Color.BLUE}[must_haves 谓词]{Color.END}")
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from must_haves_check import check_must_haves, _resolve_root
            mh_status, mh_blockers = check_must_haves(Path(cr_path), _resolve_root(Path(cr_path), None))
            if mh_status == 'pass':
                print(f"{Color.GREEN}  ✓ must_haves 全部成立{Color.END}")
            elif mh_status == 'blocked':
                for b in mh_blockers:
                    print(f"{Color.RED}  ✗ {b}{Color.END}")
                blockers.extend(mh_blockers)
            else:
                print(f"{Color.YELLOW}  ⚠ must_haves 无法校验: {mh_blockers}{Color.END}")
        except Exception as exc:
            print(f"{Color.YELLOW}  ⚠ must_haves 校验跳过: {exc}{Color.END}")

    baseline_artifacts: List[str] = []
    if lane in {'standard', 'high-risk'} and manifest and not blockers:
        print(f"\n{Color.BLUE}[Baseline Comparison]{Color.END}")
        baseline_passed, baseline_blockers, baseline_commands = compare_after_baseline(cr_path)
        commands_run.extend(baseline_commands)
        baseline_artifacts.extend(['evidence/baseline-before.json', 'evidence/baseline-after.json', 'evidence/baseline-comparison.json'])
        if baseline_passed:
            print(f"{Color.GREEN}  ✓ baseline-before / after 对比通过{Color.END}")
        else:
            for item in baseline_blockers:
                print(f"{Color.RED}  ✗ {item}{Color.END}")
            blockers.extend(baseline_blockers)

    print(f"\n{Color.BLUE}=== QualityGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, blocker in enumerate(blockers, 1):
            print(f"  {i}. {blocker}")
        print(f"\n{Color.RED}⛔ 反馈开发者修复，重新运行 Quality Agent{Color.END}")
        if os.environ.get('DELIVERHQ_AUTO_MISTAKE_BOOK', '0') == '1' and os.environ.get('DELIVERHQ_SELFTEST', '0') != '1':
            cr_id = cr_path.name
            failure_summary = '; '.join(blockers[:3])
            update_script = DELIVERHQ_ROOT / 'scripts' / 'update_mistake_book.py'

            if update_script.exists():
                try:
                    subprocess.run([
                        sys.executable,
                        str(update_script),
                        cr_id,
                        'QualityGate',
                        failure_summary,
                        '质量检查未通过',
                        '加强单元测试和代码审查',
                    ], check=False)
                    print(f"\n{Color.BLUE}ℹ️  已自动记录到 docs/mistake-book.md{Color.END}")
                    print(f"{Color.BLUE}   （设置 DELIVERHQ_AUTO_MISTAKE_BOOK=0 可禁用自动记录）{Color.END}")
                except Exception as exc:
                    print(f"\n{Color.YELLOW}⚠️  记录错误案例失败: {exc}{Color.END}")
        else:
            print(f"\n{Color.BLUE}ℹ️  mistake-book 自动写入未启用（设置 DELIVERHQ_AUTO_MISTAKE_BOOK=1 可启用；selftest 永不写入）{Color.END}")

        update_gate_from_result(
            cr_path,
            'quality',
            False,
            blockers=blockers,
            state_after_pass='testing',
            current_phase='quality',
            current_owner='quality-agent',
            next_required_gate='quality',
            commands_run=commands_run,
            artifacts=artifacts + baseline_artifacts,
            next_action='修复质量问题并重新运行 QualityGate',
        )
        return False, blockers

    print(f"{Color.GREEN}✅ PASS - 放行进入 Writeback 阶段{Color.END}")
    update_gate_from_result(
        cr_path,
        'quality',
        True,
        blockers=[],
        state_after_pass='testing',
        current_phase='quality',
        current_owner='quality-agent',
        next_required_gate='writeback',
        commands_run=commands_run,
        artifacts=artifacts + baseline_artifacts + (['verification-manifest.yml'] if manifest else []),
        next_action='进入 WritebackGate',
    )
    return True, []


def main():
    parser = argparse.ArgumentParser(description='QualityGate 检查')
    parser.add_argument('cr_path', help='CR 目录路径')
    parser.add_argument('--mode', choices=['parse_only', 'hybrid', 'execute_only'], default='hybrid', help='验证模式；默认 hybrid，parse_only 仅用于 demo/兼容')
    parser.add_argument('--lane', choices=['fast', 'standard', 'high-risk'], help='覆盖 state.yml 的 lane')

    args = parser.parse_args()

    mode = os.environ.get('QUALITYGATE_MODE') or args.mode
    passed, _ = check_qualitygate(args.cr_path, mode=mode, lane=args.lane)

    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
