#!/usr/bin/env python3
"""
Skills Orchestrator for DeliverHQ v4.7

Thin Harness architecture - orchestrates fat skills.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from cr_state import ensure_state, load_state
from runtime_support import configure_console

# 动词→门禁映射从冻结集合派生（单一事实源），不另起平行清单。
# 若 gate_composition_check 不可用（极少数环境），退化为空集合，
# validate_verbs() 会据此跳过派生校验而非误报。
try:
    from gate_composition_check import FROZEN_GATES as _FROZEN_GATES
except Exception:  # pragma: no cover - 防御性退化
    _FROZEN_GATES = {}

import os as _os
# Windows 编码修复：PYTHONUTF8=1 强制子进程使用 UTF-8，PYTHONIOENCODING 作为备用
SUBPROCESS_ENV = {
    **dict(_os.environ),
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONDONTWRITEBYTECODE": "1",
}

ROOT = Path(__file__).resolve().parent.parent

configure_console()

@dataclass
class SkillConfig:
    """Skill configuration"""
    name: str
    type: str  # spec, design, dev, review, test, quality, deploy, writeback
    script_path: str
    description: str
    inputs: List[str]
    outputs: List[str]
    args_template: str = "{cr_path}"  # How to build CLI args: {cr_path}, {cr_path}/file.md, {cr_id}


# ── 用户面动词（收口 54 个脚本，降低认知负荷）────────────────────
#
# 设计纪律（务必保持，否则会反噬 DeliverHQ 的可观测性 / 取证粒度）：
#   1. 动词是「默认入口」不是「唯一入口」：底层每个脚本仍可被 execute / 直接调用。
#   2. 任一步 BLOCK → 立即停止并透传该脚本的 verbatim 报告，不做二次概括
#      （由 execute_skill 透传 stdout 实现；execute_verb 命中失败即 break）。
#   3. 动词链里的「门禁」步骤必须能在 FROZEN_GATES 中找到（派生自单一事实源，
#      不另起平行清单）；非门禁辅助步骤登记在 VERB_NON_GATE_STEPS。
#      validate_verbs() 把这两条做成机器可检约束。
#   4. 不触碰 get_default_pipeline()（受 selftest 契约锁定：自动链停在 dev handoff）。
#   5. 失败不自动 record retry —— 重试需人/Agent 给出「新假设」，由人显式发起。
#      verify 失败后只跑 retry_guard 的**只读 status**（展示收敛状态），绝不 record。
#
# 每个动词是一串 skill type（见 _load_skills 的 self.skills 键）。
VERBS: Dict[str, List[str]] = {
    "spec":    ["grill", "spec", "drift_check"],
    "design":  ["design", "architecture"],
    "dev":     ["pre_dev", "context", "dev"],
    "verify":  ["goal_contract", "review", "quality", "anti_gaming"],
    "archive": ["writeback", "rule_maturity"],
}

VERB_DESCRIPTIONS: Dict[str, str] = {
    "spec":    "需求澄清拷问（条件）+ 验收规格完备性 + PRD↔CR 对账",
    "design":  "UI/设计产物 + 架构设计人工确认",
    "dev":     "开发前综合门禁 + 上下文纪律 + 开发交接（停在写码前）",
    "verify":  "目标契约双轨校验 + 对抗式审查 + 真实构建/测试 + 反钻空子（信证据不信声明）",
    "archive": "知识沉淀完整性 + 规则成熟度更新",
}

# 动词链里属于「门禁」、必须在 FROZEN_GATES 中可追溯的 skill type → gate 模块名。
# 这是「动词 step ↔ 冻结门禁」的映射，供 validate_verbs 做派生校验。
VERB_GATE_STEPS: Dict[str, str] = {
    "spec":          "specgate",
    "design":        "designgate",
    "architecture":  "architecturegate",
    "pre_dev":       "pre_dev_gate",
    "review":        "reviewgate",
    "quality":       "qualitygate",
    "writeback":     "writeback_gate",
}

# 动词链里的非门禁辅助步骤（不计入 FROZEN_GATES，但允许出现在链中）。
VERB_NON_GATE_STEPS = {"context", "dev", "drift_check", "anti_gaming",
                       "rule_maturity", "goal_contract", "grill"}

# 「条件步」：所需输入文件缺失时 **跳过而非失败**（这是 opt-in 能力，非每个 CR 必备）。
# 形如 step -> 它依赖的 CR 内文件。例如 goal-contract.yml 只有显式启用 loop 治理的 CR 才有；
# 缺失时 verify 不应硬 BLOCK（否则等于强制每个 CR 都写目标契约，违背 fast-lane）。
# grill 同理：request.md 缺失（如某些 CR 直接写 spec）或用户选择跳过，则不强制拷问。
# anti_gaming 本身在脚本层已对缺文件/非 git 做降级，故不列为条件步（让它自己降级并打印）。
VERB_CONDITIONAL_STEPS: Dict[str, str] = {
    "goal_contract": "goal-contract.yml",
    "grill": "request.md",
}

# 不进日常动词链、按需单独调用的门禁（文档化，不丢失）：
#   permissiongate —— high-risk 时由 pre_dev_gate 内部复用（ALLOWED_GATE_EDGES）
#   deploygate     —— 部署就绪检查
#   structuregate  —— 项目结构契约（模式 1 初始化）
#   reverse_spec_gate —— 逆向需求未裁决高风险阻断（模式 2 扫描老项目）
VERB_STANDALONE_GATES = {"permissiongate", "deploygate", "structuregate", "reverse_spec_gate"}

# 不接受位置参数（CR 路径）的尾步脚本：以无参方式调用。
VERB_NO_ARG_STEPS = {"rule_maturity"}


# ── P0 优化：轻量模式 + Token 成本预估 ────────────────────────────
#
# 轻量模式（fast lane）：小改动跳过完整 Gate 链，降低过度工程和 token 消耗。
# Token 成本预估：动词执行前显示预估消耗和费用，用户知情决策。

TOKEN_ESTIMATES = {
    "spec": {
        "no_cache": (30000, 50000),  # (min, max) input tokens
        "with_cache": (5000, 10000),
        "description": "grill + specgate + drift_check"
    },
    "design": {
        "no_cache": (40000, 70000),
        "with_cache": (8000, 15000),
        "description": "designgate + architecturegate"
    },
    "dev": {
        "no_cache": (50000, 100000),
        "with_cache": (10000, 25000),
        "description": "pre_dev_gate + dev_phase"
    },
    "verify": {
        "no_cache": (80000, 150000),
        "with_cache": (15000, 35000),
        "description": "reviewgate + qualitygate + writeback"
    },
    "archive": {
        "no_cache": (20000, 40000),
        "with_cache": (5000, 10000),
        "description": "writeback + rule_maturity"
    },
}

SONNET_PRICING = {
    "input": 3.0 / 1_000_000,   # $3/M input tokens
    "output": 15.0 / 1_000_000,  # $15/M output tokens
}


def estimate_cost(verb: str, has_cache: bool = False) -> Optional[dict]:
    """预估 token 消耗和费用"""
    if verb not in TOKEN_ESTIMATES:
        return None

    est = TOKEN_ESTIMATES[verb]
    key = "with_cache" if has_cache else "no_cache"
    min_tokens, max_tokens = est[key]

    # 假设 output = input * 0.2（经验值）
    min_cost = min_tokens * SONNET_PRICING["input"] + min_tokens * 0.2 * SONNET_PRICING["output"]
    max_cost = max_tokens * SONNET_PRICING["input"] + max_tokens * 0.2 * SONNET_PRICING["output"]

    return {
        "min_tokens": min_tokens,
        "max_tokens": max_tokens,
        "min_cost": min_cost,
        "max_cost": max_cost,
        "description": est["description"],
    }


def print_cost_estimate(verb: str, cr_path: Path):
    """打印成本预估（P0-3）"""
    # 检测是否有 Gate 缓存
    has_cache = (cr_path / "evidence" / ".gate-cache").exists()

    est = estimate_cost(verb, has_cache)
    if not est:
        return

    print(f"\n📊 预估 token 消耗（{est['description']}）：")
    print(f"  - 范围：{est['min_tokens']/1000:.1f}k - {est['max_tokens']/1000:.1f}k tokens")
    print(f"  - 费用：${est['min_cost']:.2f} - ${est['max_cost']:.2f} (Sonnet 定价)")

    if has_cache:
        no_cache_est = estimate_cost(verb, False)
        saved = (no_cache_est["min_cost"] + no_cache_est["max_cost"]) / 2 - (est["min_cost"] + est["max_cost"]) / 2
        print(f"  - ✅ Gate 缓存已启用，预计节省 ${saved:.2f}")

    print("")


def should_use_fast_lane(cr_path: Path) -> bool:
    """判断是否走快速通道（跳过完整 Gate 链）（P0-2）"""

    # 规则 1：用户显式指定 --fast
    if "--fast" in sys.argv:
        return True

    # 规则 2：state.yml 里 lane=fast
    state = load_state(cr_path)
    if state and state.lane == "fast":
        return True

    # 规则 3：request.md 里有 [fast-lane] 标记
    request_file = cr_path / "request.md"
    if request_file.exists():
        content = request_file.read_text(encoding="utf-8")
        if "[fast-lane]" in content or "<!-- fast-lane -->" in content:
            return True

    # 规则 4：智能检测（实验性）
    # 如果 request.md < 200 字 + 没提到"架构/数据库/API"等高风险关键词
    if request_file.exists():
        content = request_file.read_text(encoding="utf-8")
        if len(content) < 200:
            risky_keywords = ["架构", "数据库", "schema", "API", "接口", "migration", "重构", "database", "architecture"]
            if not any(kw in content.lower() for kw in risky_keywords):
                print("🚀 检测到小改动（<200字 + 无高风险关键词）")
                print("   建议走快速通道（跳过 design/architecture gate）")
                print("   保留：specgate（防需求模糊）+ pre_dev_gate（防依赖缺失）")
                choice = input("   使用快速通道？[Y/n]: ").strip().lower()
                return choice in ("", "y", "yes")

    return False


class SkillOrchestrator:
    """Orchestrate skills execution"""

    def __init__(self, skills_dir: str = "skills"):
        """Initialize orchestrator"""
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, SkillConfig] = {}
        self._load_skills()

    def _load_skills(self):
        """Load available skills"""
        # Define built-in skills with correct arg templates
        self.skills = {
            "spec": SkillConfig(
                name="Spec Agent",
                type="spec",
                script_path="scripts/specgate.py",
                description="Generate and validate acceptance specifications",
                inputs=["request.md"],
                outputs=["acceptance-spec.md"],
                args_template="{cr_path}/acceptance-spec.md"  # specgate expects FILE
            ),
            "design": SkillConfig(
                name="Design Agent",
                type="design",
                script_path="scripts/designgate.py",
                description="Create and validate design artifacts",
                inputs=["acceptance-spec.md"],
                outputs=["design/hi-fi-spec.md", "design/lo-fi-spec.md"],
                args_template="{cr_path}"  # designgate expects CR dir
            ),
            "architecture": SkillConfig(
                name="Architecture Gate",
                type="architecture",
                script_path="scripts/architecturegate.py",
                description="Validate architecture design before context/dev handoff",
                inputs=["architecture-design.md"],
                outputs=["evidence/architecture-result.json"],
                args_template="{cr_path}"
            ),
            "context": SkillConfig(
                name="Context Agent",
                type="context",
                script_path="scripts/context_window_check.py",
                description="Validate context summary and sliding-window discipline",
                inputs=["context-summary.md", "implementation-plan.md"],
                outputs=["context-window-report.md"],
                args_template="{cr_path}"
            ),
            "permission": SkillConfig(
                name="Permission Gate",
                type="permission",
                script_path="scripts/permissiongate.py",
                description="Validate protected path access before development",
                inputs=["dir-graph.yaml", "exceptions.yml"],
                outputs=["evidence/permission-result.json"],
                args_template="{cr_path}"
            ),
            "pre_dev": SkillConfig(
                name="Pre Dev Gate",
                type="pre_dev",
                script_path="scripts/pre_dev_gate.py",
                description="Validate CR readiness before development",
                inputs=["acceptance-spec.md", "traceability.yml"],
                outputs=["evidence/pre_dev-result.json"],
                args_template="{cr_id}"
            ),
            "dev": SkillConfig(
                name="Dev Phase Handoff",
                type="dev",
                script_path="scripts/dev_phase.py",
                description="Prepare development context and stop before code-writing",
                inputs=["acceptance-spec.md", "implementation-plan.md", "context-summary.md"],
                outputs=["evidence/dev-phase-result.json"],
                args_template="{cr_path}"
            ),
            "review": SkillConfig(
                name="Review Agent",
                type="review",
                script_path="scripts/reviewgate.py",
                description="Code review and quality check",
                inputs=["implementation/"],
                outputs=["review-report.md"],
                args_template="{cr_path}"  # reviewgate expects CR dir
            ),
            # "test" skill removed: testgate.py does not exist
            "quality": SkillConfig(
                name="Quality Agent",
                type="quality",
                script_path="scripts/qualitygate.py",
                description="Quality gate validation",
                inputs=["test-results/", "review-report.md"],
                outputs=["quality-report.md"],
                args_template="{cr_path}"  # qualitygate expects CR dir
            ),
            "deploy": SkillConfig(
                name="Deploy Agent",
                type="deploy",
                script_path="scripts/deploygate.py",
                description="Deployment readiness check",
                inputs=["quality-report.md"],
                outputs=["deployment-checklist.md"],
                args_template="{cr_path}"  # deploygate expects CR dir
            ),
            "writeback": SkillConfig(
                name="Writeback Agent",
                type="writeback",
                script_path="scripts/writeback_gate.py",  # Correct filename
                description="Knowledge capture and documentation",
                inputs=["*"],
                outputs=["docs/decisions.md", "docs/mistake-book.md"],
                args_template="{cr_path}"  # writeback_gate expects CR dir
            ),
            # ── 以下为动词链路复用的非 Gate 辅助步骤（不属于 FROZEN_GATES）──
            "drift_check": SkillConfig(
                name="PRD↔CR Drift Check",
                type="drift_check",
                script_path="scripts/drift_check.py",
                description="PRD 锚点与 CR 验收规格哈希对账",
                inputs=["acceptance-spec.md"],
                outputs=["evidence/drift-result.json"],
                args_template="{cr_path}"  # drift_check expects CR dir
            ),
            "anti_gaming": SkillConfig(
                name="Anti-Gaming Check",
                type="anti_gaming",
                script_path="scripts/anti_gaming_check.py",
                description="从 git diff 客观检测 reward hacking（信证据不信声明）",
                inputs=["goal-contract.yml"],
                outputs=["evidence/anti-gaming-result.json"],
                args_template="{cr_path}"  # anti_gaming_check expects CR dir
            ),
            "goal_contract": SkillConfig(
                name="Goal Contract Check",
                type="goal_contract",
                script_path="scripts/goal_contract.py",
                description="目标契约双轨校验（metrics 必要条件 + invariants 防 Goodhart）",
                inputs=[],  # 条件步：文件存在性由 execute_verb 在调用前判断（缺失则跳过）
                outputs=["evidence/goal-contract-result.json"],
                args_template="{cr_path}"  # goal_contract 接受 CR 目录或 yml 路径
            ),
            "grill": SkillConfig(
                name="Grill (需求澄清拷问)",
                type="grill",
                script_path="scripts/grill.py",
                description="需求澄清拷问（借 Matt Pocock grilling，填输入端对齐空洞）",
                inputs=[],  # 条件步：request.md 缺失则跳过（不强制每个 CR 都 grill）
                outputs=["request-clarifications.md"],
                args_template="{cr_path}"  # grill.py 接受 CR 目录或 request.md 路径
            ),
            "rule_maturity": SkillConfig(
                name="Rule Maturity Update",
                type="rule_maturity",
                script_path="scripts/update_rule_maturity.py",
                description="按引用次数自动提升规则成熟度（draft→verified→proven）",
                inputs=["*"],
                outputs=["docs/rules.md"],
                # 占位 args_template 满足 orchestrator 参数契约；该脚本不读位置参数，
                # execute_skill 对 VERB_NO_ARG_STEPS 以无参方式实际调用。
                args_template="{cr_path}"
            )
        }

    def get_skill(self, skill_type: str) -> Optional[SkillConfig]:
        """Get skill by type"""
        return self.skills.get(skill_type)

    def list_skills(self) -> List[SkillConfig]:
        """List all available skills"""
        return list(self.skills.values())

    def execute_skill(self, skill_type: str, cr_path: str, **kwargs) -> bool:
        """
        Execute a skill

        Args:
            skill_type: Type of skill to execute
            cr_path: Path to CR directory
            **kwargs: Additional arguments for skill

        Returns:
            True if successful
        """
        skill = self.get_skill(skill_type)
        if not skill:
            raise ValueError(f"Unknown skill type: {skill_type}")

        print(f"\n{'='*60}")
        print(f"Executing Skill: {skill.name}")
        print(f"Description: {skill.description}")
        print(f"{'='*60}\n")

        # Check inputs exist
        cr_dir = Path(cr_path)
        for input_file in skill.inputs:
            if '*' in input_file:
                continue  # Wildcard
            if input_file == 'implementation/':
                if skill_type == 'review':
                    evidence_path = cr_dir / 'evidence' / 'changed-files.json'
                    trace_path = cr_dir / 'traceability.yml'
                    manifest_path = cr_dir / 'verification-manifest.yml'
                    missing = [str(path) for path in (evidence_path, trace_path, manifest_path) if not path.exists()]
                    if missing:
                        print(f"❌ Missing review evidence: {', '.join(missing)}")
                        return False
                continue
            input_path = cr_dir / input_file
            if not input_path.exists():
                print(f"❌ Required input not found: {input_path}")
                return False

        # Execute skill script
        import subprocess
        script_path = ROOT / skill.script_path

        if not script_path.exists():
            print(f"❌ Skill script not found: {script_path}")
            return False

        # Build args using template
        cr_id = Path(cr_path).name  # e.g., CR-001
        args_value = skill.args_template.format(cr_path=cr_path, cr_id=cr_id)

        # 尾步脚本（如 rule_maturity / update_rule_maturity）不接受位置参数：无参调用。
        if skill_type in VERB_NO_ARG_STEPS:
            cmd = [sys.executable, str(script_path)]
        else:
            cmd = [sys.executable, str(script_path), args_value]

        # Run skill script
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace',
            env=SUBPROCESS_ENV,
        )

        if result.returncode == 0:
            print(f"✅ Skill completed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ Skill failed")
            # 透传脚本自身的 verbatim 报告：门禁的 BLOCK 细节多写在 stdout，
            # 必须原样转出，不做二次概括，否则丢失"哪一环、为什么"的取证粒度。
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return False

    def list_verbs(self) -> Dict[str, List[str]]:
        """返回用户面动词 → skill 链映射。"""
        return dict(VERBS)

    def validate_verbs(self):
        """机器可检约束：动词层不漂移、与 FROZEN_GATES 单一事实源一致。

        返回 (errors, warnings)。errors 非空表示动词定义破坏了纪律，应 BLOCK。
        校验项：
          1. 每个动词的每个 step 都在 self.skills 中存在（链不引用幽灵 skill）。
          2. 动词链里被标记为「门禁」的 step（VERB_GATE_STEPS）必须映射到一个
             存在于 FROZEN_GATES 的门禁模块 —— 派生自单一事实源，不另起平行清单。
          3. 每个 FROZEN_GATES 的门禁要么被某动词覆盖（经 VERB_GATE_STEPS），
             要么登记在 VERB_STANDALONE_GATES（按需单独调用），否则就是「丢了门禁」。
          4. 动词链里的每个 step 要么是门禁 step，要么登记在 VERB_NON_GATE_STEPS。
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. step 存在性
        for verb, steps in VERBS.items():
            for step in steps:
                if step not in self.skills:
                    errors.append(f"动词 {verb} 引用了未注册的 skill: {step}")
                if step not in VERB_GATE_STEPS and step not in VERB_NON_GATE_STEPS:
                    errors.append(
                        f"动词 {verb} 的 step '{step}' 既非门禁(VERB_GATE_STEPS)亦未登记为辅助(VERB_NON_GATE_STEPS)"
                    )

        # FROZEN_GATES 不可用时（防御性退化），跳过派生校验，仅给警告。
        if not _FROZEN_GATES:
            warnings.append("FROZEN_GATES 不可用，跳过动词↔冻结门禁派生校验")
            return errors, warnings

        frozen = set(_FROZEN_GATES.keys())

        # 2. 门禁 step 映射的模块必须在 FROZEN_GATES 中
        for step, gate_module in VERB_GATE_STEPS.items():
            if gate_module not in frozen:
                errors.append(
                    f"门禁 step '{step}' 映射到 '{gate_module}'，但它不在 FROZEN_GATES（事实源漂移）"
                )

        # 3. 每个冻结门禁要么被动词覆盖，要么是登记的 standalone
        covered = set(VERB_GATE_STEPS.values())
        for gate_module in frozen:
            if gate_module not in covered and gate_module not in VERB_STANDALONE_GATES:
                errors.append(
                    f"冻结门禁 '{gate_module}' 既未进任何动词链，也未登记为 standalone —— 动词层丢了门禁"
                )

        # standalone 集合里的名字也应是真实冻结门禁（防笔误）
        for g in VERB_STANDALONE_GATES:
            if g not in frozen:
                warnings.append(f"VERB_STANDALONE_GATES 中 '{g}' 不在 FROZEN_GATES，建议核对")

        return errors, warnings

    def execute_verb(self, verb: str, cr_path: str) -> Dict[str, bool]:
        """执行一个用户面动词（顺序跑其 skill 链）。

        任一步失败立即停止；execute_skill 已透传该步的 verbatim 报告。
        这是「默认入口」——底层每个 skill 仍可经 execute 单独调用。
        """
        if verb not in VERBS:
            raise ValueError(f"未知动词: {verb}（可用: {', '.join(VERBS)}）")

        cr_path_obj = Path(cr_path)

        # P0-3: Token 成本预估（动词执行前显示预估）
        print_cost_estimate(verb, cr_path_obj)

        # P0-2: 轻量模式检测（dev 动词才触发，其他动词走完整链）
        use_fast_lane = False
        if verb == "dev" and should_use_fast_lane(cr_path_obj):
            use_fast_lane = True
            print("⚡ 快速通道已激活")
            print("  - 跳过：design/architecture gate")
            print("  - 保留：spec + pre_dev（最低安全网）")
            print("  - 预估 token 节省：30-40%\n")

            # 快速通道：只走 spec + pre_dev，跳过 design/architecture
            # 注意：这里假设 spec 已经跑过了（快速通道通常用于已有 spec 的小改动）
            # 如果 spec 没跑过，还是会在 pre_dev 时被 BLOCK
            chain = ["pre_dev", "context", "dev"]  # 跳过 design/architecture
        else:
            chain = VERBS[verb]

        print(f"\n{'#'*60}")
        print(f"# 动词 {verb}: {VERB_DESCRIPTIONS.get(verb, '')}")
        print(f"# 链路: {' → '.join(chain)}")
        print(f"# CR: {cr_path}")
        print(f"{'#'*60}\n")

        results: Dict[str, bool] = {}
        for step in chain:
            # 条件步：所需输入文件缺失则跳过（opt-in 能力，不强制每个 CR 都有）
            need = VERB_CONDITIONAL_STEPS.get(step)
            if need and not (Path(cr_path) / need).exists():
                print(f"\n⏭  跳过 '{step}'：未发现 {need}（该 CR 未启用此项，非失败）")
                continue
            success = self.execute_skill(step, cr_path)
            results[step] = success
            if not success:
                print(f"\n❌ 动词 {verb} 在 '{step}' 处中止（上方为该步原始报告，未做概括）")
                break

        print(f"\n{'#'*60}")
        print(f"# 动词 {verb} 小结")
        print(f"{'#'*60}")
        for step, success in results.items():
            print(f"{'✅' if success else '❌'} {step}")

        # verify 失败：只跑 retry_guard 的**只读 status**展示收敛状态，绝不 record。
        # record 需人/Agent 给出新假设（达上限转 needs_human），由人显式发起。
        if verb == "verify" and not all(results.values()):
            print("\n── 重试收敛状态（只读，不记录）──")
            self._run_retry_status(cr_path)
            print("提示: 修复后若需记录重试，请显式带新假设调用 "
                  "`retry_guard.py <CR> record --gate <G> --blocker <..> --hypothesis <新假设>`")
        print()

        return results

    def _run_retry_status(self, cr_path: str):
        """只读展示 retry_guard 的当前重试账本状态（绝不 record，不改 state）。"""
        import subprocess
        script = Path("scripts/retry_guard.py")
        if not script.exists():
            return
        try:
            r = subprocess.run(
                [sys.executable, str(script), cr_path, "status"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=20,
            )
            if r.stdout:
                print(r.stdout.rstrip())
        except Exception as e:  # 只读辅助，失败不影响 verify 结论
            print(f"(retry_guard status 不可用: {e})")

    def execute_next_gate(self, cr_path: str) -> bool:
        """Execute the gate required by state.yml."""
        state = ensure_state(Path(cr_path))
        next_gate = state.next_required_gate

        if not next_gate:
            print("✅ No next gate required")
            return True

        skill_type = next_gate.replace("-", "_")
        print(f"▶ Next required gate from state.yml: {next_gate}")
        return self.execute_skill(skill_type, cr_path)

    def execute_state_machine(self, cr_path: str, max_steps: int = 10) -> Dict[str, bool]:
        """Run the CR by repeatedly executing next_required_gate until stop."""
        results: Dict[str, bool] = {}
        steps = 0
        cr_dir = Path(cr_path)

        while steps < max_steps:
            state = ensure_state(cr_dir)
            next_gate = state.next_required_gate
            if not next_gate:
                print("✅ CR has no pending gate")
                break

            skill_type = next_gate.replace("-", "_")
            success = self.execute_skill(skill_type, cr_path)
            results[skill_type] = success
            steps += 1

            refreshed = load_state(cr_dir)
            if not success:
                print(f"❌ State machine stopped at {next_gate}")
                break
            if refreshed and refreshed.next_required_gate == next_gate:
                print(f"⚠ next_required_gate still points to {next_gate}, stopping to avoid loop")
                break

        return results

    def execute_pipeline(self, cr_path: str, pipeline: List[str]) -> Dict[str, bool]:
        """
        Execute a pipeline of skills

        Args:
            cr_path: Path to CR directory
            pipeline: List of skill types to execute in order

        Returns:
            Dict of skill_type -> success
        """
        results = {}

        print(f"\n{'#'*60}")
        print(f"# Executing Pipeline: {' → '.join(pipeline)}")
        print(f"# CR: {cr_path}")
        print(f"{'#'*60}\n")

        for skill_type in pipeline:
            success = self.execute_skill(skill_type, cr_path)
            results[skill_type] = success

            if not success:
                print(f"\n❌ Pipeline stopped at {skill_type}")
                break

        # Summary
        print(f"\n{'#'*60}")
        print(f"# Pipeline Summary")
        print(f"{'#'*60}")
        for skill_type, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {skill_type}")
        print()

        return results

    def get_default_pipeline(self) -> List[str]:
        """Get default CR pipeline"""
        return [
            "spec",
            "design",
            "architecture",
            "context",
            "pre_dev",
            "dev",
        ]


def analyze_cr_size(cr_path: str) -> dict:
    """
    分析 CR 规模，判断是否需要拆解（Epic → Story）。

    判断标准（保守阈值，避免误触发）：
    - acceptance criteria 数量 > 10 → 建议拆
    - CR 总 token 估算 > 5000 → 建议拆

    Returns:
        {
            'total_tokens': int,
            'criteria_count': int,
            'file_count': int,
            'should_decompose': bool,
            'reasons': [str]
        }
    """
    cr_dir = Path(cr_path)
    if not cr_dir.exists():
        return {'error': f'CR 目录不存在: {cr_path}'}

    # 统计 token（简单估算：字符数 / 4）
    total_tokens = 0
    file_count = 0
    for file_path in cr_dir.rglob('*'):
        if file_path.is_file() and file_path.suffix in {'.md', '.yml', '.yaml', '.json'}:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                total_tokens += len(content) // 4
                file_count += 1
            except Exception:
                pass

    # 统计验收标准数量（从 acceptance-spec.md）
    criteria_count = 0
    spec_file = cr_dir / 'acceptance-spec.md'
    if spec_file.exists():
        content = spec_file.read_text(encoding='utf-8', errors='ignore')
        # 计算验收条件条数（- [ ] 或 1. 这类格式）
        import re
        criteria_count = len(re.findall(r'^\s*[-\*] \[[ x]\]|^\s*\d+\.\s', content, re.MULTILINE))

    # 判断是否需要拆解
    reasons = []
    if criteria_count > 10:
        reasons.append(f"验收条件 {criteria_count} 条（建议上限 10 条）")
    if total_tokens > 5000:
        reasons.append(f"CR 总量约 {total_tokens:,} tokens（建议上限 5,000）")

    return {
        'total_tokens': total_tokens,
        'criteria_count': criteria_count,
        'file_count': file_count,
        'should_decompose': len(reasons) > 0,
        'reasons': reasons
    }


def decompose_cr(cr_path: str):
    """
    分析 CR 并给出拆解建议（Epic → Story）。

    不自动创建子 CR——输出建议，由人审阅后用 create_sub_cr.py 执行。
    """
    print("\n🔍 CR 规模分析\n")

    result = analyze_cr_size(cr_path)
    if 'error' in result:
        print(f"❌ {result['error']}")
        return

    cr_name = Path(cr_path).name

    print(f"CR: {cr_name}")
    print(f"  文件数:        {result['file_count']}")
    print(f"  Token 估算:    {result['total_tokens']:,}")
    print(f"  验收条件数:    {result['criteria_count']}")
    print()

    if result['should_decompose']:
        print("⚠️  建议拆解（触发以下阈值）：")
        for reason in result['reasons']:
            print(f"  - {reason}")

        print("""
📋 拆解建议（Epic → Story 模式）：

  1. 把当前 CR 改为 Epic（保留高层验收标准，删除实现细节）
  2. 为每个独立功能点创建子 CR：

     python3 scripts/create_sub_cr.py {cr_name} --title "功能点 1"
     python3 scripts/create_sub_cr.py {cr_name} --title "功能点 2" --depends-on {cr_name}-01
     python3 scripts/create_sub_cr.py {cr_name} --title "功能点 3" --depends-on {cr_name}-02

  3. 每个子 CR 独立走完整 Gate 链（上下文天然隔离）
  4. 所有子 CR 完成后，Epic 进入 archive

  子 CR 查看：
     python3 scripts/create_sub_cr.py {cr_name} --list
     python3 scripts/create_sub_cr.py {cr_name} --status
""".format(cr_name=cr_name))
    else:
        print("✅ CR 规模合理，无需拆解")
        print(f"  （验收条件 ≤ 10 且 tokens ≤ 5,000）")


def route_situation(situation: str = None):
    """动词路由器（借 Pocock ask-matt，治 54→5 收口后剩余认知负荷）。

    根据用户场景（新需求/bug/重构/遗留代码）推荐动词流。
    """
    print("\n🧭 DeliverHQ 动词路由器\n")

    # 路由决策树（仿 Pocock ask-matt 的流程分支逻辑）
    routes = {
        "new_feature": {
            "name": "新需求/功能",
            "flow": ["grill (如有 request.md)", "spec", "design", "dev", "verify", "archive"],
            "entry": "spec",
            "description": "从想法到交付的主流程。有代码库从 grill→spec 开始；无 request.md 直接写 spec。",
            "mode": "standard",
            "keywords": ["新功能", "需求", "feature", "idea", "想法", "加个"]
        },
        "bug_fix": {
            "name": "Bug 修复",
            "flow": ["spec (简化)", "dev", "verify"],
            "entry": "spec",
            "description": "小改动可简化 spec（只写验收条件），跳过 design，直奔 dev→verify。",
            "mode": "fast-lane",
            "keywords": ["bug", "修复", "fix", "错误", "问题"]
        },
        "refactor": {
            "name": "重构/优化",
            "flow": ["spec (重构目标)", "design (架构)", "dev", "verify"],
            "entry": "spec",
            "description": "重构需要明确目标（spec）和架构约束（design），然后 dev→verify。",
            "mode": "standard",
            "keywords": ["重构", "refactor", "优化", "optimize", "改进"]
        },
        "legacy": {
            "name": "遗留代码/逆向工程",
            "flow": ["reverse-spec (模式2)", "design", "verify"],
            "entry": "reverse-spec",
            "description": "已有代码无文档：先逆向生成 spec（模式2：analyze→spec），再补 design 和测试。",
            "mode": "reverse",
            "keywords": ["遗留", "legacy", "无文档", "逆向", "已有代码"]
        },
        "cr_exists": {
            "name": "已有 spec/设计，继续开发",
            "flow": ["design (如未完成)", "dev", "verify", "archive"],
            "entry": "design",
            "description": "CR 已有 acceptance-spec，从 design 或 dev 继续（用 resume 自动判断）。",
            "mode": "standard",
            "keywords": ["继续", "resume", "已有spec", "接着做"]
        },
        "unknown": {
            "name": "不确定/需要引导",
            "flow": ["参考下方决策树"],
            "entry": None,
            "description": "回答几个问题帮你定位场景。",
            "mode": None,
            "keywords": []
        }
    }

    # 如果没给 situation 或给了 "interactive"，走交互式问答
    if not situation or situation.lower() in ("interactive", "?", "help"):
        print("回答几个问题，帮你找到合适的动词流:\n")
        print("1. 你的场景是?")
        print("   a) 我有一个新想法/需求要实现")
        print("   b) 我要修一个 bug")
        print("   c) 我要重构/优化现有代码")
        print("   d) 我有遗留代码，没文档，想补齐")
        print("   e) 我已经有 CR 和 spec，想继续开发")
        print()
        choice = input("选择 (a/b/c/d/e): ").strip().lower()

        route_map = {
            'a': 'new_feature',
            'b': 'bug_fix',
            'c': 'refactor',
            'd': 'legacy',
            'e': 'cr_exists'
        }

        route_key = route_map.get(choice, 'unknown')
        if route_key == 'unknown':
            print("\n⚠ 未识别的选择，显示所有路径供参考。\n")
            for key, route in routes.items():
                if key != 'unknown':
                    print(f"** {route['name']} **")
                    print(f"   流程: {' → '.join(route['flow'])}")
                    print(f"   入口: {route['entry']}")
                    print(f"   说明: {route['description']}\n")
            return
    else:
        # 根据关键词匹配场景
        situation_lower = situation.lower()
        route_key = 'unknown'

        for key, route in routes.items():
            if any(kw in situation_lower for kw in route['keywords']):
                route_key = key
                break

    route = routes[route_key]

    print(f"📍 识别场景: {route['name']}\n")
    print(f"   推荐流程: {' → '.join(route['flow'])}")
    print(f"   入口动词: {route['entry'] or '(见下方)'}")
    if route['mode']:
        print(f"   模式: {route['mode']}")
    print(f"\n   {route['description']}\n")

    # 给出具体命令示例
    if route['entry']:
        print("💡 下一步命令:")
        if route['entry'] == 'spec':
            print(f"   python scripts/skill_orchestrator.py verb spec <CR目录>")
        elif route['entry'] == 'design':
            print(f"   python scripts/skill_orchestrator.py verb design <CR目录>")
        elif route['entry'] == 'reverse-spec':
            print(f"   python scripts/reverse_spec_gate.py mode2 <目标目录>")
        print()

    # 额外提示
    if route_key == 'new_feature':
        print("💬 提示: 如果需求还不清楚，先跑 grill 拷问（需要 request.md）；")
        print("   如果需求已明确，直接写 acceptance-spec.md 后跑 spec 动词。\n")
    elif route_key == 'bug_fix':
        print("💬 提示: Bug 修复可走 fast-lane（简化 spec，跳 design），但要保证测试覆盖。\n")
    elif route_key == 'legacy':
        print("💬 提示: 逆向模式2会先 analyze 代码生成 spec，再转正向流程。\n")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="DeliverHQ Skills Orchestrator")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # list command
    subparsers.add_parser('list', help='List available skills')

    # execute command
    execute_parser = subparsers.add_parser('execute', help='Execute a skill')
    execute_parser.add_argument('skill_type', help='Skill type')
    execute_parser.add_argument('cr_path', help='CR directory path')

    # pipeline command
    pipeline_parser = subparsers.add_parser('pipeline', help='Execute skill pipeline')
    pipeline_parser.add_argument('cr_path', help='CR directory path')
    pipeline_parser.add_argument('--skills', help='Comma-separated skill types (default: full pipeline)')

    next_parser = subparsers.add_parser('next', help='Execute next_required_gate from state.yml')
    next_parser.add_argument('cr_path', help='CR directory path')

    resume_parser = subparsers.add_parser('resume', help='Run state machine from state.yml until blocked/completed')
    resume_parser.add_argument('cr_path', help='CR directory path')
    resume_parser.add_argument('--max-steps', type=int, default=10, help='Safety cap for loop iterations')

    # ── 用户面动词（收口脚本，默认入口）──
    verb_parser = subparsers.add_parser('verb', help='Execute a user-facing verb (spec/design/dev/verify/archive)')
    verb_parser.add_argument('verb', choices=sorted(VERBS), help='Verb name')
    verb_parser.add_argument('cr_path', help='CR directory path')

    subparsers.add_parser('verbs', help='List user-facing verbs and their script chains')
    subparsers.add_parser('validate-verbs', help='Check verb layer derives from FROZEN_GATES (no drift / no dropped gate)')

    # route command (借鉴 Pocock ask-matt 路由器，治认知负荷)
    route_parser = subparsers.add_parser('route', help='Recommend verb flow for your situation (idea/bug/refactor/legacy)')
    route_parser.add_argument('situation', nargs='?', help='Your situation or use "interactive" for guided questions')

    # decompose command (Epic → Story 拆解分析)
    decompose_parser = subparsers.add_parser('decompose', help='Analyse CR size and suggest sub-CR split when it exceeds thresholds')
    decompose_parser.add_argument('cr_path', help='CR directory path')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        orchestrator = SkillOrchestrator()

        if args.command == 'list':
            print("\n📋 Available Skills:\n")
            for skill in orchestrator.list_skills():
                print(f"{skill.type:12} - {skill.name}")
                print(f"{'':12}   {skill.description}")
                print(f"{'':12}   Inputs:  {', '.join(skill.inputs)}")
                print(f"{'':12}   Outputs: {', '.join(skill.outputs)}")
                print()

        elif args.command == 'execute':
            success = orchestrator.execute_skill(args.skill_type, args.cr_path)
            sys.exit(0 if success else 1)

        elif args.command == 'pipeline':
            if args.skills:
                pipeline = args.skills.split(',')
            else:
                pipeline = orchestrator.get_default_pipeline()

            results = orchestrator.execute_pipeline(args.cr_path, pipeline)
            all_success = all(results.values())
            sys.exit(0 if all_success else 1)

        elif args.command == 'next':
            success = orchestrator.execute_next_gate(args.cr_path)
            sys.exit(0 if success else 1)

        elif args.command == 'resume':
            results = orchestrator.execute_state_machine(args.cr_path, max_steps=args.max_steps)
            all_success = all(results.values()) if results else True
            sys.exit(0 if all_success else 1)

        elif args.command == 'verb':
            results = orchestrator.execute_verb(args.verb, args.cr_path)
            all_success = all(results.values()) if results else True
            sys.exit(0 if all_success else 1)

        elif args.command == 'verbs':
            print("\n📋 用户面动词（默认入口；底层脚本仍可经 execute 单独调用）:\n")
            for verb, chain in orchestrator.list_verbs().items():
                print(f"{verb:9} - {VERB_DESCRIPTIONS.get(verb, '')}")
                print(f"{'':9}   链路: {' → '.join(chain)}")
                print()
            print("按需单独调用（不进日常动词链）: " + ", ".join(sorted(VERB_STANDALONE_GATES)))
            print()

        elif args.command == 'validate-verbs':
            errors, warnings = orchestrator.validate_verbs()
            for w in warnings:
                print(f"⚠ {w}")
            if errors:
                print("❌ BLOCKED — 动词层定义破坏纪律:")
                for e in errors:
                    print(f"  - {e}")
                sys.exit(1)
            print("✅ PASS — 动词层派生自 FROZEN_GATES，无漂移、无丢失门禁")
            sys.exit(0)

        elif args.command == 'route':
            route_situation(args.situation)
            sys.exit(0)

        elif args.command == 'decompose':
            decompose_cr(args.cr_path)
            sys.exit(0)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
