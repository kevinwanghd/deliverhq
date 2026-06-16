#!/usr/bin/env python3
"""
DesignGate - 设计产物完备性检查
检查设计稿是否满足 C 端（高保真）/ B 端（低保真）要求
"""

import sys
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

def detect_ui_type(cr_path):
    """从 design/metadata.yml、acceptance-spec 或 request 推断 UI 类型"""
    # 优先读取结构化 metadata.yml
    metadata_path = Path(cr_path) / "design" / "metadata.yml"
    if metadata_path.exists():
        try:
            import yaml
            metadata = yaml.safe_load(metadata_path.read_text(encoding='utf-8'))
            ui_type = metadata.get('ui_type', '').strip()
            if ui_type in ['C端', 'B端', '无UI']:
                return ui_type
        except:
            pass  # YAML 解析失败，回退到关键词检测

    # 回退：从文档内容推断
    spec_path = Path(cr_path) / "acceptance-spec.md"
    request_path = Path(cr_path) / "request.md"

    content = ""
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
    elif request_path.exists():
        content = request_path.read_text(encoding='utf-8')

    # 关键词判断
    c_end_keywords = ['用户界面', '前端', 'UI', '页面', '移动端', 'App', '客户端']
    b_end_keywords = ['管理后台', '后台', '管理系统', '内部工具']

    has_c = any(kw in content for kw in c_end_keywords)
    has_b = any(kw in content for kw in b_end_keywords)

    if has_b:
        return 'B端'
    elif has_c:
        return 'C端'
    else:
        return '无UI'

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
            next_required_gate='context',
            next_action='进入 ContextWindowGate',
            metadata={"ui_type": "N/A"},
        )
        return True, [], "N/A"

    ui_type = detect_ui_type(cr_path)
    metadata_path = Path(cr_path) / "design" / "metadata.yml"
    source = "metadata.yml" if metadata_path.exists() else "关键词推断"
    print(f"{Color.BLUE}UI 类型: {ui_type} (来源: {source}){Color.END}\n")

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

        if not prototype:
            print(f"{Color.YELLOW}⚠ 缺少 prototype.html{Color.END}")
            warnings.append("建议提供可交互原型")
        else:
            print(f"{Color.GREEN}✓ prototype.html 存在{Color.END}")

        if not assets_dir or not list(Path(design_dir / "assets").glob("*")):
            print(f"{Color.YELLOW}⚠ 缺少设计资源 (assets/){Color.END}")
            warnings.append("建议提供切图/设计稿图片")

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
        next_required_gate='context',
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
