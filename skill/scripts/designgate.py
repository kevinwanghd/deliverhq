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

def check_designgate(cr_path):
    """检查设计产物完备性"""
    print(f"{Color.BLUE}=== DesignGate 检查 ==={Color.END}\n")

    design_dir = Path(cr_path) / "design"
    if not design_dir.exists():
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
        # C 端必须高保真
        if not hifi:
            print(f"{Color.RED}✗ C 端 UI 缺少 hi-fi-spec.md{Color.END}")
            blockers.append("C 端必须有高保真设计稿")
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
