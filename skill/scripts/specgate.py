#!/usr/bin/env python3
"""
SpecGate - 验收规格完备性检查
检查 acceptance-spec.md 是否满足开发前置条件（SDD 三段式 + 模糊词检测）
"""

import sys
import os
from pathlib import Path
import re

from cr_state import update_gate_from_result
from runtime_support import configure_console

configure_console()

class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

# 模糊词列表（需要量化的词汇）
FUZZY_WORDS = [
    '尽快', '合理', '优化', '良好体验', '高性能',
    '稳定', '友好', '智能', '自动', '适当',
    '较快', '较好', '足够', '尽量', '尽可能',
    '一定程度', '基本', '大概', '约', '左右'
]

def _check_prd_linkage(spec_path, content, blockers, warnings, strict_mode):
    """检查 9：PRD 链接与 PRD↔CR 对账（warning-first，不破坏现有链路）。

    - 无 derived_from.prd_section：提示未链接 PRD（仅警告，便于老项目/示例渐进接入）
    - prd_hash 与 docs/PRD.md 当前锚点不一致：
        - confirmed 锚点          → 严格模式阻断，默认仅警告（NEED_HUMAN_DECISION）
        - reverse-engineered 锚点 → 仅警告（老项目放宽）
    复用 drift_check 的锚点哈希逻辑，保持单一来源。
    """
    try:
        from drift_check import _anchor_section, _anchor_hash, DERIVED_RE, PRD_HASH_RE
    except Exception as exc:
        print(f"{Color.YELLOW}⚠ 无法加载 drift_check（跳过 PRD 对账）: {exc}{Color.END}")
        return

    dm = DERIVED_RE.search(content)
    if not dm:
        print(f"{Color.YELLOW}⚠ 未声明 derived_from.prd_section（CR 未链接 PRD）{Color.END}")
        warnings.append("CR 未链接 PRD（建议补 derived_from.prd_section）")
        return

    anchor = dm.group(1)
    # 从 acceptance-spec.md 向上定位 skill 根（含 docs/PRD.md）：CR目录/上级/skill根
    root = Path(spec_path).resolve().parent.parent.parent
    prd = root / "docs" / "PRD.md"
    if not prd.exists():
        print(f"{Color.YELLOW}⚠ docs/PRD.md 不存在，跳过对账{Color.END}")
        warnings.append("docs/PRD.md 不存在，无法对账 PRD 链接")
        return

    prd_text = prd.read_text(encoding="utf-8")
    cur = _anchor_hash(prd_text, anchor)
    if cur is None:
        print(f"{Color.YELLOW}⚠ PRD 中找不到锚点 {anchor}{Color.END}")
        warnings.append(f"PRD 中找不到锚点 {anchor}")
        return

    hm = PRD_HASH_RE.search(content)
    recorded = hm.group(1) if hm else ''
    section = _anchor_section(prd_text, anchor) or ''
    is_reverse = bool(re.search(r'(状态|status)[^\n]*reverse-engineered', section))

    if recorded == cur:
        print(f"{Color.GREEN}✓ PRD 链接一致（{anchor}）{Color.END}")
        return

    msg = f"PRD↔CR 不一致 {anchor}（cr_hash {recorded or '∅'} vs current {cur}）→ 需对账：改CR/改PRD/记差异"
    if is_reverse:
        print(f"{Color.YELLOW}⚠ {msg}（reverse-engineered，仅警告）{Color.END}")
        warnings.append(msg + "（reverse-engineered，仅警告）")
    elif strict_mode:
        print(f"{Color.RED}✗ {msg}{Color.END}")
        blockers.append(msg)
    else:
        print(f"{Color.YELLOW}⚠ {msg}（严格模式下会阻断）{Color.END}")
        warnings.append(msg)


def has_quantifiable_metric(content, fuzzy_word):
    """检查模糊词附近是否有量化指标"""
    # 在模糊词前后 100 字符内查找数字+单位
    pattern = rf'.{{0,100}}{re.escape(fuzzy_word)}.{{0,100}}'
    matches = re.finditer(pattern, content, re.DOTALL)

    for match in matches:
        context = match.group(0)
        # 查找量化指标：数字 + 单位/百分比/比较符号
        if re.search(r'\d+\s*(ms|秒|分钟|%|MB|GB|QPS|次|个|元|<|>|≤|≥)', context):
            return True
    return False

def check_specgate(spec_path):
    """检查 acceptance-spec.md 完备性"""
    print(f"{Color.BLUE}=== SpecGate 检查 ==={Color.END}\n")

    if not Path(spec_path).exists():
        print(f"{Color.RED}✗ BLOCKED: {spec_path} 不存在{Color.END}")
        return False, ["acceptance-spec.md 缺失"]

    content = Path(spec_path).read_text(encoding='utf-8')
    blockers = []
    warnings = []

    # 严格模式开关
    strict_mode = os.environ.get('DELIVERHQ_STRICT_MODE', '0') == '1'

    # 检查 1: SDD 三段式结构
    print(f"{Color.BLUE}[SDD 结构]{Color.END}")
    required_sections = [
        ('## 1. Data Spec', 'Data Spec（数据规格）'),
        ('## 2. Interface Spec', 'Interface Spec（接口规格）'),
        ('## 3. Behavior Spec', 'Behavior Spec（行为规格）'),
    ]

    missing_sections = []
    for section_pattern, section_name in required_sections:
        if section_pattern not in content:
            missing_sections.append(section_name)

    if missing_sections:
        msg = f"缺少 SDD 结构: {', '.join(missing_sections)}"
        if strict_mode:
            print(f"{Color.RED}✗ {msg}{Color.END}")
            blockers.append(msg)
        else:
            print(f"{Color.YELLOW}⚠ {msg}（严格模式下会阻断）{Color.END}")
            warnings.append(msg)
    else:
        print(f"{Color.GREEN}✓ SDD 三段式结构完整{Color.END}")

    # 检查 2: 模板变量未替换
    print(f"\n{Color.BLUE}[模板变量]{Color.END}")
    template_vars = re.findall(r'\{\{[^}]+\}\}', content)
    if template_vars:
        print(f"{Color.RED}✗ 检测到未替换模板变量: {set(template_vars)}{Color.END}")
        blockers.append(f"包含模板变量: {', '.join(list(set(template_vars))[:5])}")
    else:
        print(f"{Color.GREEN}✓ 无模板变量{Color.END}")

    # 检查 3: [待确认] / [NEEDS CLARIFICATION] 占位符
    print(f"\n{Color.BLUE}[待确认占位符]{Color.END}")
    # [NEEDS CLARIFICATION]：借 Spec-Kit 约定，spec 起草期可标，SpecGate 放行前必须为零。
    # 大小写不敏感，容忍 [NEEDS CLARIFICATION: ...] 带补充说明的形式。
    needs_clar_count = len(re.findall(r'\[\s*NEEDS[ _]CLARIFICATION', content, re.IGNORECASE))
    pending_count = content.count('[待确认]') + content.count('[TODO]') + needs_clar_count
    if pending_count > 0:
        print(f"{Color.RED}✗ 包含 {pending_count} 处待确认占位符{Color.END}")
        detail = "[待确认]/[TODO]"
        if needs_clar_count:
            detail += f"/[NEEDS CLARIFICATION]×{needs_clar_count}"
        blockers.append(f"{pending_count} 处待确认占位符未解决（{detail}）")
    else:
        print(f"{Color.GREEN}✓ 无待确认占位符{Color.END}")

    # 检查 4: P0 Open Questions 未解决
    print(f"\n{Color.BLUE}[P0 待确认问题]{Color.END}")
    p0_open_pattern = r'\|\s*Q\d+\s*\|.*?\|\s*P0\s*\|.*?\|\s*open\s*\|'
    if re.search(p0_open_pattern, content):
        print(f"{Color.RED}✗ 存在 P0 待确认问题（status=open）{Color.END}")
        blockers.append("P0 Open Questions 未解决")
    else:
        print(f"{Color.GREEN}✓ 无 P0 待确认问题{Color.END}")

    # 检查 5: P0 Assumptions 未验证
    print(f"\n{Color.BLUE}[P0 假设验证]{Color.END}")
    p0_assumption_pattern = r'\|\s*A\d+\s*\|.*?\|\s*P0\s*\|.*?\|\s*pending\s*\|'
    if re.search(p0_assumption_pattern, content):
        print(f"{Color.RED}✗ 存在 P0 假设未验证（status=pending）{Color.END}")
        blockers.append("P0 Assumptions 未验证")
    else:
        print(f"{Color.GREEN}✓ 无 P0 假设待验证{Color.END}")

    # 检查 6: 模糊词检查
    print(f"\n{Color.BLUE}[模糊词检查]{Color.END}")
    fuzzy_found = []
    for word in FUZZY_WORDS:
        if word in content:
            if not has_quantifiable_metric(content, word):
                fuzzy_found.append(word)

    if fuzzy_found:
        msg = f"包含模糊词但无量化指标: {', '.join(fuzzy_found[:5])}"
        if len(fuzzy_found) > 5:
            msg += f" 等 {len(fuzzy_found)} 个"

        if strict_mode:
            print(f"{Color.RED}✗ {msg}{Color.END}")
            blockers.append(msg)
        else:
            print(f"{Color.YELLOW}⚠ {msg}（严格模式下会阻断）{Color.END}")
            warnings.append(msg)
    else:
        print(f"{Color.GREEN}✓ 无未量化的模糊词{Color.END}")

    # 检查 7: 验收场景数量
    print(f"\n{Color.BLUE}[验收场景]{Color.END}")
    scenario_count = content.count('### 场景') + content.count('## 场景')
    if scenario_count == 0:
        given_count = content.count('**Given**')
        scenario_count = given_count if given_count > 0 else content.count('Given')

    if scenario_count < 3:
        print(f"{Color.YELLOW}⚠ 验收场景数偏少 ({scenario_count} 处){Color.END}")
        warnings.append("建议至少 3 个验收场景（正常/异常/边界）")
    else:
        print(f"{Color.GREEN}✓ 验收场景充足 ({scenario_count} 处){Color.END}")

    # 检查 8: 非功能需求
    print(f"\n{Color.BLUE}[非功能需求]{Color.END}")
    has_nfr = any(kw in content for kw in ['性能', '响应时间', 'QPS', 'SLA', '安全', '可用性'])
    if has_nfr:
        print(f"{Color.GREEN}✓ 包含非功能需求{Color.END}")
    else:
        print(f"{Color.YELLOW}⚠ 未明确非功能需求{Color.END}")
        warnings.append("建议明确性能/安全/可用性指标")

    # 检查 9: PRD 链接与对账（warning-first）
    print(f"\n{Color.BLUE}[PRD 链接对账]{Color.END}")
    _check_prd_linkage(spec_path, content, blockers, warnings, strict_mode)

    # 汇总结果
    print(f"\n{Color.BLUE}=== SpecGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
        print(f"\n{Color.YELLOW}提示：设置 DELIVERHQ_STRICT_MODE=1 启用严格模式{Color.END}")
        update_gate_from_result(
            Path(spec_path).parent,
            'spec',
            False,
            blockers=blockers,
            state_after_pass='spec_review',
            current_phase='spec',
            current_owner='spec-agent',
            next_required_gate='spec',
        )
        return False, blockers

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    print(f"{Color.GREEN}✅ PASS{Color.END}")
    update_gate_from_result(
        Path(spec_path).parent,
        'spec',
        True,
        blockers=[],
        state_after_pass='spec_review',
        current_phase='spec',
        current_owner='spec-agent',
        next_required_gate='design',
    )
    return True, []

def main():
    if len(sys.argv) < 2:
        print("用法: python specgate.py <path/to/acceptance-spec.md>")
        sys.exit(1)

    spec_path = sys.argv[1]
    passed, blockers = check_specgate(spec_path)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
