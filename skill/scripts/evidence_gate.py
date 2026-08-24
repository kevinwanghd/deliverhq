#!/usr/bin/env python
"""
Evidence Gate — sentinel 文件 = 唯一判据

来源：企业微信团队"AI代码生成率94%"经验。

核心原则：
  - 长跑命令不靠 stdout 报告成功，全靠落盘文件
  - git commit 用 `git log -1` hash 更新验证
  - 全部由文件证明，不靠 AI 自报

用法：
  python evidence_gate.py check --cr-id CR-001
  python evidence_gate.py record --cr-id CR-001 --type build --file build_report.txt
  python evidence_gate.py verify --cr-id CR-001 --type build
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# 配置
# =============================================================================

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "governance.config.yml"
EVIDENCE_DIR = "evidence"

EVIDENCE_TYPES = {
    "build": {
        "description": "编译产物",
        "sentinel_files": ["build_report.txt", "dist/bundle.js"],
        "command": None,  # 由调用者提供
        "success_indicator": "exit_code_0"
    },
    "test": {
        "description": "测试结果",
        "sentinel_files": ["test_report.json", "coverage/lcov.info"],
        "command": None,
        "success_indicator": "all_passed"
    },
    "git_commit": {
        "description": "Git commit",
        "sentinel_files": None,
        "command": "git log -1 --format=%H",
        "success_indicator": "hash_changed"
    },
    "runtime": {
        "description": "运行时验证",
        "sentinel_files": ["runtime.log", "screenshot.png"],
        "command": None,
        "success_indicator": "log_keyword_matched"
    },
    "adversarial_review": {
        "description": "对抗式审查",
        "sentinel_files": ["adversarial_review_report.md"],
        "command": None,
        "success_indicator": "verdict_pass"
    }
}


# =============================================================================
# 工具函数
# =============================================================================

def get_evidence_dir(cr_id: str) -> Path:
    """获取 evidence 目录"""
    candidates = [
        Path("DeliverHQ") / "change-requests" / cr_id / EVIDENCE_DIR,
        Path("change-requests") / cr_id / EVIDENCE_DIR,
    ]
    for d in candidates:
        if d.exists():
            return d
    # 默认创建
    d = candidates[0]
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_evidence_file(evidence_dir: Path, evidence_type: str) -> Path:
    """获取 evidence JSON 路径"""
    return evidence_dir / f"{evidence_type}.json"


def compute_file_hash(file_path: Path) -> str:
    """计算文件的 SHA256 前8位"""
    if not file_path.exists():
        return ""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:8]


def run_git_command(cmd: list[str], cwd: Path = None) -> tuple[int, str, str]:
    """运行 git 命令，返回 (exit_code, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


# =============================================================================
# 核心操作
# =============================================================================

def record_evidence(
    cr_id: str,
    evidence_type: str,
    sentinel_file: str = None,
    commit_hash: str = None,
    command: str = None,
    note: str = None
) -> dict:
    """记录 evidence"""
    evidence_dir = get_evidence_dir(cr_id)
    evidence_file = get_evidence_file(evidence_dir, evidence_type)

    now = datetime.now().isoformat()

    # 构建 evidence 记录
    evidence = {
        "type": evidence_type,
        "recorded_at": now,
        "sentinel_file": sentinel_file,
        "commit_hash": commit_hash,
        "command": command,
        "note": note,
        "verified": False
    }

    # 计算文件 hash
    if sentinel_file:
        file_path = Path(sentinel_file)
        if file_path.exists():
            evidence["file_hash"] = compute_file_hash(file_path)
            evidence["file_size"] = file_path.stat().st_size
        else:
            evidence["file_missing"] = True

    # git commit 特殊处理
    if evidence_type == "git_commit" and commit_hash:
        evidence["commit_hash"] = commit_hash
        evidence["verified"] = True

    # adversarial_review 不校验文件 hash（报告在审查过程中会多次修改）
    if evidence_type == "adversarial_review":
        evidence["skip_hash_check"] = True

    # 保存
    evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {"success": True, "evidence": evidence}


def verify_evidence(
    cr_id: str,
    evidence_type: str,
    expected_hash: str = None,
    expected_commit: str = None
) -> dict:
    """验证 evidence"""
    evidence_dir = get_evidence_dir(cr_id)
    evidence_file = get_evidence_file(evidence_dir, evidence_type)

    if not evidence_file.exists():
        return {
            "success": False,
            "error": f"未找到 evidence 记录：{evidence_type}",
            "verified": False
        }

    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))

    now = datetime.now().isoformat()
    result = {
        "success": True,
        "type": evidence_type,
        "recorded_at": evidence.get("recorded_at"),
        "verified_at": now,
        "verified": False,
        "checks": []
    }

    # adversarial_review verdict 验证（Gate 核心判据，跳过文件 hash）
    if evidence_type == "adversarial_review" and evidence.get("sentinel_file"):
        report_path = Path(evidence["sentinel_file"])
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")
            import re
            m = re.search(r"verdict[*_]*\s*:\s*(PASS|FAIL)", content, re.IGNORECASE)
            verdict = m.group(1) if m else None
            result["checks"].append({
                "check": "adversarial_review_verdict",
                "verdict": verdict,
                "passed": verdict == "PASS"
            })
            result["verified"] = verdict == "PASS"
            if verdict == "FAIL":
                blockings = re.findall(r"\[(CRITICAL|HIGH)\]\s+([^\n]+)", content)
                if blockings:
                    result["checks"].append({
                        "check": "blocking_findings",
                        "findings": [f"{sev}: {name.strip()}" for sev, name in blockings],
                        "passed": False
                    })
        return result

    # git commit 验证
    if evidence_type == "git_commit":
        _, current_hash, _ = run_git_command(
            ["git", "log", "-1", "--format=%H"]
        )
        recorded_hash = evidence.get("commit_hash", "")

        if expected_commit and current_hash != expected_commit:
            result["checks"].append({
                "check": "commit_hash",
                "expected": expected_commit,
                "actual": current_hash,
                "passed": False
            })
        elif current_hash == recorded_hash:
            result["checks"].append({
                "check": "commit_hash_matches",
                "expected": recorded_hash,
                "actual": current_hash,
                "passed": True
            })
            result["verified"] = True
        else:
            result["checks"].append({
                "check": "commit_hash_matches",
                "expected": recorded_hash,
                "actual": current_hash,
                "passed": False
            })

    # git commit / adversarial_review 已在上面单独处理，通用 sentinel 仅处理 build/test/runtime
    elif evidence.get("sentinel_file") and evidence_type != "adversarial_review":
        file_path = Path(evidence["sentinel_file"])
        if not file_path.exists():
            result["checks"].append({
                "check": "file_exists",
                "file": str(file_path),
                "passed": False,
                "error": "文件不存在"
            })
        else:
            current_hash = compute_file_hash(file_path)
            recorded_hash = evidence.get("file_hash", "")

            if expected_hash and current_hash != expected_hash:
                result["checks"].append({
                    "check": "file_hash",
                    "expected": expected_hash,
                    "actual": current_hash,
                    "passed": False
                })
            elif current_hash == recorded_hash:
                result["checks"].append({
                    "check": "file_hash_matches",
                    "expected": recorded_hash,
                    "actual": current_hash,
                    "passed": True
                })
                result["verified"] = True
            else:
                result["checks"].append({
                    "check": "file_hash_matches",
                    "expected": recorded_hash,
                    "actual": current_hash,
                    "passed": False
                })

    # adversarial_review verdict 验证（Gate 核心判据，跳过文件 hash）
    if evidence_type == "adversarial_review" and evidence.get("sentinel_file"):
        report_path = Path(evidence["sentinel_file"])
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")
            import re
            m = re.search(r"verdict[*_]*\s*:\s*(PASS|FAIL)", content, re.IGNORECASE)
            verdict = m.group(1) if m else None
            result["checks"].append({
                "check": "adversarial_review_verdict",
                "verdict": verdict,
                "passed": verdict == "PASS"
            })
            result["verified"] = verdict == "PASS"
            if verdict == "FAIL":
                blockings = re.findall(r"\[(CRITICAL|HIGH)\]\s+([^\n]+)", content)
                if blockings:
                    result["checks"].append({
                        "check": "blocking_findings",
                        "findings": [f"{sev}: {name.strip()}" for sev, name in blockings],
                        "passed": False
                    })
        return result

    # adversarial_review 特殊分支已 return，以下是通用 sentinel 验证
    if evidence.get("skip_hash_check"):
        result["checks"].append({"check": "sentinel_exists", "passed": True})
        result["verified"] = True
        return result

    # 更新 evidence 记录
    evidence["verified"] = result["verified"]
    evidence["verified_at"] = now
    evidence_file.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return result


def check_all_evidence(cr_id: str) -> dict:
    """检查所有 evidence"""
    evidence_dir = get_evidence_dir(cr_id)

    results = {
        "cr_id": cr_id,
        "evidence_dir": str(evidence_dir),
        "evidences": [],
        "summary": {
            "total": 0,
            "verified": 0,
            "unverified": 0,
            "missing": 0
        }
    }

    for evidence_type in EVIDENCE_TYPES:
        evidence_file = get_evidence_file(evidence_dir, evidence_type)
        if evidence_file.exists():
            evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
            results["evidences"].append({
                "type": evidence_type,
                "exists": True,
                "verified": evidence.get("verified", False),
                "recorded_at": evidence.get("recorded_at")
            })
            results["summary"]["total"] += 1
            if evidence.get("verified"):
                results["summary"]["verified"] += 1
            else:
                results["summary"]["unverified"] += 1
        else:
            results["evidences"].append({
                "type": evidence_type,
                "exists": False
            })
            results["summary"]["missing"] += 1

    return results


# =============================================================================
# CLI
# =============================================================================

def main():
    # argparse subparsers break when sys.argv[0] contains path separators on Windows
    sys.argv[0] = Path(sys.argv[0]).name

    # Manual command dispatch (subparsers unreliable on some Python/Windows combos)
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_usage()
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    command = sys.argv[1]
    if command not in ("check", "record", "verify"):
        _print_usage()
        sys.exit(1)

    # Build parser for each subcommand's options only
    parser = _build_parser(command)
    args = parser.parse_args(sys.argv[2:])

    result = None
    if command == "check":
        result = check_all_evidence(args.cr_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "record":
        result = record_evidence(
            args.cr_id,
            args.type,
            sentinel_file=args.file,
            commit_hash=args.commit_hash,
            command=None,
            note=args.note
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "verify":
        result = verify_evidence(
            args.cr_id,
            args.type,
            expected_hash=args.expected_hash,
            expected_commit=args.expected_commit
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("verified", False) else 1)

    if result and "error" in result and not result["success"]:
        print(f"❌ {result['error']}")
        sys.exit(1)


def _print_usage():
    print("Evidence Gate — sentinel 文件 = 唯一判据")
    print()
    print("用法：")
    print("  python evidence_gate.py check --cr-id CR-001")
    print("  python evidence_gate.py record --cr-id CR-001 --type build --file build.txt")
    print("  python evidence_gate.py verify --cr-id CR-001 --type build")
    print()
    print("命令：check / record / verify")


def _build_parser(command):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cr-id", required=True)
    if command == "record":
        parser.add_argument("--type", required=True,
            choices=["build", "test", "git_commit", "runtime", "adversarial_review"])
        parser.add_argument("--file")
        parser.add_argument("--commit-hash")
        parser.add_argument("--note")
    elif command == "verify":
        parser.add_argument("--type", required=True,
            choices=["build", "test", "git_commit", "runtime", "adversarial_review"])
        parser.add_argument("--expected-hash")
        parser.add_argument("--expected-commit")
    return parser


if __name__ == "__main__":
    main()
