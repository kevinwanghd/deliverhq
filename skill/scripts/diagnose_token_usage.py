#!/usr/bin/env python3
"""
Token Usage Diagnostic — 诊断 DeliverHQ 的 token 消耗模式

分析：
1. 典型 CR 各文件的 token 占用
2. Gate 执行时读取的文件
3. 增量更新 vs 全量读取的对比
"""

import sys
sys.dont_write_bytecode = True
from pathlib import Path
import yaml
import json

ROOT = Path(__file__).resolve().parent.parent

def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（1 token ≈ 4 chars）"""
    return len(text) // 4

def analyze_cr_files(cr_path: Path):
    """分析单个 CR 的文件 token 占用"""
    print(f"\n=== CR: {cr_path.name} ===")

    files_by_size = []
    total_tokens = 0

    for file_path in cr_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in {".md", ".yml", ".yaml", ".json"}:
            try:
                content = file_path.read_text(encoding='utf-8')
                tokens = estimate_tokens(content)
                total_tokens += tokens
                rel_path = file_path.relative_to(cr_path)
                files_by_size.append((tokens, rel_path))
            except Exception:
                pass

    files_by_size.sort(reverse=True)

    print(f"总 token: {total_tokens:,}")
    print("\n最占 token 的文件（前 10）：")
    for tokens, path in files_by_size[:10]:
        print(f"  {tokens:>6,} tokens  {path}")

    # 按阶段分组
    phases = {
        "request": [],
        "spec": [],
        "design": [],
        "dev": [],
        "evidence": [],
        "reports": [],
        "meta": []
    }

    for tokens, path in files_by_size:
        path_str = str(path)
        if "evidence/" in path_str:
            phases["evidence"].append(tokens)
        elif "design/" in path_str:
            phases["design"].append(tokens)
        elif "request" in path_str or "clarification" in path_str:
            phases["request"].append(tokens)
        elif "spec" in path_str or "test-plan" in path_str:
            phases["spec"].append(tokens)
        elif "implementation" in path_str or "dev-" in path_str:
            phases["dev"].append(tokens)
        elif "report" in path_str or "traceability" in path_str:
            phases["reports"].append(tokens)
        else:
            phases["meta"].append(tokens)

    print("\n按阶段分组：")
    for phase, tokens_list in phases.items():
        if tokens_list:
            total = sum(tokens_list)
            print(f"  {phase:12s}: {total:>6,} tokens ({len(tokens_list)} 文件)")

    return total_tokens

def simulate_gate_reads():
    """模拟 Gate 执行时读取的文件"""
    print("\n" + "=" * 60)
    print("  Gate 读取模式分析")
    print("=" * 60)

    # 模拟各阶段 Gate 需要读取的文件
    gate_reads = {
        "SpecGate": ["request.md", "acceptance-spec.md", "request-clarifications.md*", "state.yml"],
        "DesignGate": ["acceptance-spec.md", "design/*.md", "design/metadata.yml", "state.yml"],
        "ArchitectureGate": ["architecture-design.md", "design/*.md", "state.yml"],
        "PreDevGate": ["acceptance-spec.md", "design/*.md", "architecture-design.md", "implementation-plan.md", "state.yml"],
        "ReviewGate": ["traceability.yml", "changed-files (from git)", "state.yml"],
        "QualityGate": ["verification-manifest.yml", "evidence/*.json", "state.yml"],
        "WritebackGate": ["all reports", "traceability.yml", "state.yml"]
    }

    for gate, files in gate_reads.items():
        print(f"\n{gate}:")
        for f in files:
            print(f"  - {f}")

def recommend_optimizations():
    """推荐优化方案"""
    print("\n" + "=" * 60)
    print("  优化建议")
    print("=" * 60)

    print("""
## 问题 1: 改一个字段消耗很多 token

**根因**:
- 每次 Gate 都全量读取上游产物
- evidence/ 目录累积大量 JSON（baseline 90+ 行/文件）
- 没有增量更新机制

**优化方案**:
1. **延迟加载 evidence/**
   - Gate 不自动读 evidence/，只在失败时才深入分析
   - 用摘要代替全文（如只记录 "baseline OK" 而非完整 JSON）

2. **指针化大文件**
   - traceability.yml 126 行太大，改成 "见 traceability.yml" 的指针
   - report 文件只在 writeback 时读取，中间阶段只验证存在性

3. **分层加载**
   - SpecGate: 只读 request + spec
   - DesignGate: 只读 spec + design/
   - QualityGate: 只读 manifest + state（不读 evidence/ 全文）

## 问题 2: CR 拆解太大，上下文爆掉

**根因**:
- 单个 CR 包含从需求到部署的全生命周期（1400+ 行）
- 没有子任务拆解机制
- 大需求被强制塞进单个 CR

**优化方案**:
1. **子 CR 机制（Epic → Story 模式）**
   - CR-PARENT/ 定义总体目标
   - CR-PARENT-001/, CR-PARENT-002/ 是子任务
   - 每个子 CR 独立走完流程，最后在父 CR 汇总

2. **懒归档**
   - 完成的阶段产物移到 _archive/ 子目录
   - 只保留当前阶段需要的文件在顶层

3. **摘要前置**
   - 每个大文件（如 architecture-design.md）加 TLDR 段落
   - Gate 优先读 TLDR，只在 BLOCKED 时才读全文
""")

def main():
    print("=" * 60)
    print("  DeliverHQ Token Usage Diagnostic")
    print("=" * 60)

    # 分析示例 CR
    cr_example = ROOT / "change-requests" / "CR-EXAMPLE"
    if cr_example.exists():
        analyze_cr_files(cr_example)

    # 模拟 Gate 读取
    simulate_gate_reads()

    # 推荐优化
    recommend_optimizations()

if __name__ == "__main__":
    main()
