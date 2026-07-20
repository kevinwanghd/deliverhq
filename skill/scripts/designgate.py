#!/usr/bin/env python3
"""
DesignGate - 设计产物完备性检查
检查设计稿是否满足 C 端（高保真）/ B 端（低保真）要求
"""

import sys
import re
from pathlib import Path

from cr_state import update_gate_from_result
from runtime_support import configure_console

configure_console()

class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

ASCII_TOKEN_RE = re.compile(r'(?<![A-Za-z0-9])(?:Android|iOS|iPhone|iPad|Flutter|React Native|RN|ReactNative|Harmony|HarmonyOS|Mini Program)(?![A-Za-z0-9])')


def _contains_mobile_keyword(content, mobile_keywords):
    for keyword in mobile_keywords:
        if keyword.isascii():
            continue
        if keyword in content:
            return True
    return bool(ASCII_TOKEN_RE.search(content))


def detect_ui_type(cr_path):
    """从 design/metadata.yml、acceptance-spec 或 request 推断 UI 类型。

    返回 (ui_type, is_mobile)：
      ui_type ∈ {C端, B端, 无UI}；is_mobile 标记是否移动端/客户端原生场景。
    判定优先级：移动端/客户端 > B端强信号 > C端专属信号 > B端通用信号 > 无UI。

    设计理由：
    - 移动端 App 即使含"后台"也是 C 端高保真（优先级最高，不变）。
    - Admin/管理后台是 B端强信号，不应被 'UI'/'页面' 这类泛用词误判为 C端。
    - '页面'/'UI' 等泛用词既出现在 C 端也出现在 B 端，不能作为 C端判断依据。
    - 只有明确的 C端专属词（'H5'/'Web 端'/'C 端'/'C端'/'用户界面'/'前端'）才判 C端。

    残余问题2修复：'客户端'/'App' 太宽泛（某些业务里指SDK客户端/合作方App，非移动端UI），
    从强移动端判据降级为需要结合上下文（"移动端客户端"/"手机App" 才命中）。
    """
    # 移动端/客户端关键词（命中即视为 C 端 + is_mobile，最高优先级）
    # 注：'客户端'/'App' 已移除（太宽泛，SDK/合作方 App 等场景误判）
    mobile_keywords = [
        '移动端', '原生',
        '安卓', 'Android', 'iOS', 'iPhone', 'iPad',
        'Flutter', 'React Native', 'RN', 'ReactNative',
        '鸿蒙', 'Harmony', 'HarmonyOS', '小程序', 'Mini Program',
        '手机App', '移动端App', '移动端客户端',  # 明确的移动端上下文
    ]
    # B端强信号：命中即优先判 B端（高于泛用 C端词）
    b_end_strong_keywords = [
        '管理后台', '管理系统', '后台管理', '内部工具', '运营平台',
        'Admin', 'admin', 'ADMIN', '运营后台', '管理平台', '控制台',
        'B 端', 'B端', 'Dashboard', 'dashboard',
    ]
    # C端专属词：明确指向 C端，泛用词（'UI'/'页面'）移出，不再作为 C端判据
    c_end_exclusive_keywords = [
        '用户界面', '前端', 'H5', 'Web 端', 'C 端', 'C端',
    ]
    # B端通用信号（不含强信号，用于兜底）
    b_end_generic_keywords = ['后台']

    # 优先读取结构化 metadata.yml
    metadata_path = Path(cr_path) / "design" / "metadata.yml"
    if metadata_path.exists():
        try:
            import yaml
            metadata = yaml.safe_load(metadata_path.read_text(encoding='utf-8')) or {}
            ui_type = str(metadata.get('ui_type', '')).strip()
            platform = str(metadata.get('platform', '')).strip().lower()
            is_mobile = platform in ('android', 'ios', 'flutter', 'rn', 'react-native', 'harmony', 'miniprogram', 'mobile') \
                or any(kw.lower() in platform for kw in ['android', 'ios', 'flutter', 'harmony'])
            if ui_type in ['C端', 'B端', '无UI']:
                # 移动端平台显式声明时，强制 C 端
                if is_mobile and ui_type != '无UI':
                    return 'C端', True
                return ui_type, is_mobile
        except Exception:
            pass  # YAML 解析失败，回退到关键词检测

    # 回退：从文档内容推断
    spec_path = Path(cr_path) / "acceptance-spec.md"
    request_path = Path(cr_path) / "request.md"

    content = ""
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
    elif request_path.exists():
        content = request_path.read_text(encoding='utf-8')

    has_mobile = _contains_mobile_keyword(content, mobile_keywords)
    has_b_strong = any(kw in content for kw in b_end_strong_keywords)
    has_c_exclusive = any(kw in content for kw in c_end_exclusive_keywords)
    has_b_generic = any(kw in content for kw in b_end_generic_keywords)

    # 优先级：移动端 > B端强信号 > C端专属词 > B端通用词 > 无UI
    # 注：'UI'/'页面'等泛用词已从判据中移除，避免把 Admin 后台误判为 C端
    if has_mobile:
        return 'C端', True       # 移动端 App 一律 C 端高保真，即使同时含"后台"
    elif has_b_strong:
        return 'B端', False      # Admin/管理系统等强 B端信号优先于泛用 C端词
    elif has_c_exclusive:
        return 'C端', False
    elif has_b_generic:
        return 'B端', False
    else:
        return '无UI', False

def load_design_waiver(cr_path):
    """读取 CR 的 exceptions.yml，返回一条针对 DesignGate 的已声明豁免（若有）。

    正门机制（软而不焊死）：小需求若确实不需要保真稿，可在 exceptions.yml 显式
    声明一条 gate_override（gate=DesignGate），写明 reason 即可放行——留痕、可审计，
    区别于"没建 design/ 目录就静默绕过"的暗门。

    返回 dict（reason / approved_by / approved_date），或 None（无豁免），
    或 {"_invalid": ...}（写了但缺 reason）。B 档：reason 必填，approved_by 选填。
    """
    exc_path = Path(cr_path) / "exceptions.yml"
    if not exc_path.exists():
        return None
    try:
        import yaml
        data = yaml.safe_load(exc_path.read_text(encoding='utf-8')) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for entry in (data.get("exceptions") or []):
        if not isinstance(entry, dict):
            continue
        override = entry.get("gate_override") or {}
        # 兼容两种写法：{gate_override: {gate: ...}} 或扁平 {gate: ...}
        if not override and str(entry.get("gate", "")).strip():
            override = entry
        if str(override.get("gate", "")).strip().lower() in ("designgate", "design"):
            reason = str(override.get("reason", "")).strip()
            if not reason:
                return {"_invalid": "缺少 reason"}
            return {
                "reason": reason,
                "approved_by": str(override.get("approved_by", "")).strip(),
                "approved_date": str(override.get("approved_date", "")).strip(),
            }
    return None


def _print_waiver(waiver, ui_type):
    """打印豁免记录（留痕）。审批人缺失时明确标记为自我声明。"""
    approver = waiver.get("approved_by") or "（自我声明，无独立审批）"
    date = waiver.get("approved_date") or "-"
    print(f"{Color.YELLOW}⚠ DesignGate 已豁免（{ui_type}）{Color.END}")
    print(f"  理由: {waiver['reason']}")
    print(f"  审批: {approver}  日期: {date}")


def check_designgate(cr_path):
    """检查设计产物完备性"""
    print(f"{Color.BLUE}=== DesignGate 检查 ==={Color.END}\n")

    waiver = load_design_waiver(cr_path)
    valid_waiver = waiver if (waiver and "_invalid" not in waiver) else None
    if waiver and "_invalid" in waiver:
        print(f"{Color.YELLOW}⚠ exceptions.yml 有 DesignGate 豁免但无效：{waiver['_invalid']}（reason 必填，豁免不生效）{Color.END}\n")

    design_dir = Path(cr_path) / "design"
    if not design_dir.exists():
        # 洞1 软堵：无 design/ 时先探测 spec/request 是否明显是 UI 需求。
        ui_probe, _ = detect_ui_type(cr_path)
        if valid_waiver:
            _print_waiver(valid_waiver, ui_probe if ui_probe != '无UI' else '无 design/')
            update_gate_from_result(
                Path(cr_path), 'design', True, blockers=[],
                state_after_pass='design', current_phase='design',
                current_owner='design-agent', next_required_gate='architecture',
                next_action='进入 ArchitectureGate',
                metadata={"ui_type": ui_probe, "design_waived": True, "waiver_reason": valid_waiver["reason"]},
            )
            return True, [], ui_probe
        if ui_probe in ('C端', 'B端'):
            # 该有设计却没 design/ 且未显式豁免 → 指向两条正门（软阻断，不焊死）
            print(f"{Color.RED}✗ 识别到 {ui_probe} UI 需求，但无 design/ 目录且未声明豁免{Color.END}")
            blockers = [
                "识别到 UI 需求（%s）却无设计产物。二选一：" % ui_probe
                + "① 补设计稿（C 端需 design/hi-fi-spec.md）；"
                + "② 若为小需求无需保真稿，在 exceptions.yml 声明 gate_override(gate: DesignGate, reason: ...)"
            ]
            update_gate_from_result(
                Path(cr_path), 'design', False, blockers=blockers,
                state_after_pass='design', current_phase='design',
                current_owner='design-agent', next_required_gate='design',
                metadata={"ui_type": ui_probe},
            )
            return False, blockers, ui_probe
        print(f"{Color.GREEN}✓ 无 design/ 目录，判定为无 UI 需求{Color.END}")
        update_gate_from_result(
            Path(cr_path),
            'design',
            True,
            blockers=[],
            state_after_pass='design',
            current_phase='design',
            current_owner='design-agent',
            next_required_gate='architecture',
            next_action='进入 ArchitectureGate',
            metadata={"ui_type": "N/A"},
        )
        return True, [], "N/A"

    ui_type, is_mobile = detect_ui_type(cr_path)
    metadata_path = Path(cr_path) / "design" / "metadata.yml"
    source = "metadata.yml" if metadata_path.exists() else "关键词推断"
    platform_label = "（移动端/客户端）" if is_mobile else ""
    print(f"{Color.BLUE}UI 类型: {ui_type}{platform_label} (来源: {source}){Color.END}\n")

    blockers = []
    warnings = []

    # 检查设计文件
    lofi = (design_dir / "lo-fi-spec.md").exists()
    hifi = (design_dir / "hi-fi-spec.md").exists()
    prototype = (design_dir / "prototype.html").exists()
    assets_dir = (design_dir / "assets").exists()

    if ui_type == 'C端':
        # C 端必须高保真——除非本 CR 已显式声明 DesignGate 豁免（小需求正门）
        if not hifi and valid_waiver:
            _print_waiver(valid_waiver, ui_type)
            update_gate_from_result(
                Path(cr_path), 'design', True, blockers=[],
                state_after_pass='design', current_phase='design',
                current_owner='design-agent', next_required_gate='architecture',
                next_action='进入 ArchitectureGate',
                metadata={"ui_type": ui_type, "design_waived": True, "waiver_reason": valid_waiver["reason"]},
            )
            return True, [], ui_type
        if not hifi:
            print(f"{Color.RED}✗ C 端 UI 缺少 hi-fi-spec.md{Color.END}")
            blockers.append("C 端必须有高保真设计稿（小需求可在 exceptions.yml 声明 DesignGate 豁免）")
        else:
            print(f"{Color.GREEN}✓ hi-fi-spec.md 存在{Color.END}")
            # 检查内容完整性（避免误报：只检查明显的模板变量）
            hifi_content = (design_dir / "hi-fi-spec.md").read_text(encoding='utf-8')
            if '{{' in hifi_content and '}}' in hifi_content:
                blockers.append("hi-fi-spec.md 包含未替换模板变量 {{}}")
            # 放宽视觉规范检查：只要有色彩/字体/间距任一描述即可
            if not any(kw in hifi_content for kw in ['色彩', '颜色', '字体', '间距', 'color', 'font', 'spacing']):
                warnings.append("hi-fi-spec.md 建议补充视觉规范（色彩/字体/间距）")

            # 移动端专项：高保真必须覆盖平台规范/多机型/状态/深色模式/安全区
            if is_mobile:
                mobile_checks = {
                    "平台设计规范（iOS HIG / Material Design / 鸿蒙）":
                        ['HIG', 'Material', 'Human Interface', '鸿蒙', 'Harmony', '平台规范', '设计规范'],
                    "多机型/尺寸适配（不同分辨率、安全区/刘海）":
                        ['多机型', '尺寸适配', '分辨率', '安全区', '刘海', 'safe area', 'SafeArea', '响应式'],
                    "深色模式（Dark Mode）":
                        ['深色', '暗色', 'Dark Mode', 'dark mode', '夜间'],
                    "交互状态（默认/按下/禁用/加载/空/错误）":
                        ['交互状态', '按下', '禁用', '加载态', '空态', '错误态', 'pressed', 'disabled', 'loading', 'empty'],
                }
                for label, kws in mobile_checks.items():
                    if not any(kw in hifi_content for kw in kws):
                        warnings.append(f"移动端高保真建议覆盖：{label}")

        if not prototype:
            print(f"{Color.YELLOW}⚠ 缺少 prototype.html{Color.END}")
            warnings.append("建议提供可交互原型")
        else:
            print(f"{Color.GREEN}✓ prototype.html 存在{Color.END}")

        if not assets_dir or not list(Path(design_dir / "assets").glob("*")):
            print(f"{Color.YELLOW}⚠ 缺少设计资源 (assets/){Color.END}")
            warnings.append("建议提供切图/设计稿图片")

        # 直读审计（UI 编码前产物）：四元组追溯，杜绝凭截图臆测样式
        dra = design_dir / "direct-read-audit.md"
        if not dra.exists():
            print(f"{Color.YELLOW}⚠ 缺少 direct-read-audit.md{Color.END}")
            warnings.append("UI 编码前建议产出 direct-read-audit.md（视觉常量四元组：节点→属性→原始值→代码映射）")
        else:
            dra_content = dra.read_text(encoding='utf-8')
            if '{{' in dra_content and '}}' in dra_content:
                warnings.append("direct-read-audit.md 仍含未替换模板变量 {{}}（需填入真实设计源原始值）")
            else:
                print(f"{Color.GREEN}✓ direct-read-audit.md 存在{Color.END}")

    elif ui_type == 'B端':
        # B 端可低保真
        if hifi:
            print(f"{Color.GREEN}✓ hi-fi-spec.md 存在 (B 端高保真，最佳){Color.END}")
        elif lofi:
            print(f"{Color.GREEN}✓ lo-fi-spec.md 存在 (B 端可接受){Color.END}")
        else:
            print(f"{Color.RED}✗ 缺少设计稿 (lo-fi 或 hi-fi){Color.END}")
            blockers.append("B 端至少需要低保真设计稿")

    else:  # 无 UI
        print(f"{Color.YELLOW}⚠ 无法判断 UI 类型，但有 design/ 目录{Color.END}")
        warnings.append("存在 design/ 但未识别到 UI 需求")

    # 汇总结果
    print(f"\n{Color.BLUE}=== DesignGate 结果 ==={Color.END}")
    if blockers:
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        for i, b in enumerate(blockers, 1):
            print(f"  {i}. {b}")
        update_gate_from_result(
            Path(cr_path),
            'design',
            False,
            blockers=blockers,
            state_after_pass='design',
            current_phase='design',
            current_owner='design-agent',
            next_required_gate='design',
        )
        return False, blockers, ui_type

    if warnings:
        print(f"{Color.YELLOW}⚠️  PASS WITH WARNINGS{Color.END}")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    print(f"{Color.GREEN}✅ PASS{Color.END}")
    update_gate_from_result(
        Path(cr_path),
        'design',
        True,
        blockers=[],
        state_after_pass='design',
        current_phase='design',
        current_owner='design-agent',
        next_required_gate='architecture',
    )
    return True, [], ui_type

def main():
    if len(sys.argv) < 2:
        print("用法: python designgate.py <path/to/CR-XXX>")
        sys.exit(1)

    cr_path = sys.argv[1]
    passed, blockers, ui_type = check_designgate(cr_path)

    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
