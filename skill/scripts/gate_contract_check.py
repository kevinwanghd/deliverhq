#!/usr/bin/env python3
"""
Gate Contract Check — 验证所有 Gate 脚本的参数契约

验证内容:
1. 所有 Gate 脚本存在
2. 能对 CR-EXAMPLE 运行并 PASS
3. 能对 CR-BLOCKED-EXAMPLE 运行并 BLOCKED
4. selftest 调用本脚本作为同一 Gate contract 真相源
5. ReviewGate PASS 样例必须包含 changed-files / traceability / verification-manifest 证据
"""

import sys
sys.dont_write_bytecode = True
import os
import subprocess
from pathlib import Path

from runtime_support import configure_console

ROOT = Path(__file__).resolve().parent.parent
configure_console()
SUBPROCESS_ENV = {**dict(os.environ), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "DELIVERHQ_SELFTEST": "1", "DELIVERHQ_AUTO_MISTAKE_BOOK": "0"}

GATES = {
    "specgate": {
        "script": "scripts/specgate.py",
        "args_pass": "change-requests/CR-EXAMPLE/acceptance-spec.md",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE/acceptance-spec.md"
    },
    "designgate": {
        "script": "scripts/designgate.py",
        "args_pass": "change-requests/CR-EXAMPLE",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE"
    },
    "dev_phase": {
        "script": "scripts/dev_phase.py",
        "args_pass": "change-requests/CR-EXAMPLE",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE",
        "expect_blocked": True
    },
    "reviewgate": {
        "script": "scripts/reviewgate.py",
        "args_pass": "change-requests/CR-EXAMPLE",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE",
        "required_evidence_pass": [
            "change-requests/CR-EXAMPLE/evidence/changed-files.json",
            "change-requests/CR-EXAMPLE/traceability.yml",
            "change-requests/CR-EXAMPLE/verification-manifest.yml",
            "change-requests/CR-EXAMPLE/test-plan.md"
        ]
    },
    "qualitygate": {
        "script": "scripts/qualitygate.py",
        "args_pass": "change-requests/CR-EXAMPLE",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE"
    },
    "deploygate": {
        "script": "scripts/deploygate.py",
        "args_pass": "change-requests/CR-EXAMPLE",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE"
    },
    "writeback_gate": {
        "script": "scripts/writeback_gate.py",
        "args_pass": "change-requests/CR-EXAMPLE",
        "args_blocked": "change-requests/CR-BLOCKED-EXAMPLE"
    }
}

def check_gate_exists():
    """检查所有 gate 脚本是否存在"""
    print("=" * 60)
    print("  1. Gate 脚本存在性检查")
    print("=" * 60)

    all_exist = True
    for gate_name, config in GATES.items():
        script_path = ROOT / config["script"]
        if script_path.exists():
            print(f"  ✅ {gate_name:20s} -> {config['script']}")
        else:
            print(f"  ❌ {gate_name:20s} -> {config['script']} (NOT FOUND)")
            all_exist = False

    return all_exist

def run_gate(script, args):
    """运行 gate 并返回 (returncode, stdout, stderr)"""
    script_path = ROOT / script
    args_path = ROOT / args

    if not script_path.exists():
        return None, "", "script not found"

    result = subprocess.run(
        [sys.executable, str(script_path), str(args_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',
        cwd=ROOT,
        env=SUBPROCESS_ENV,
    )

    return result.returncode, result.stdout, result.stderr

def check_gate_pass_blocked():
    """检查 gate 对正反例的响应"""
    print("\n" + "=" * 60)
    print("  2. Gate 正反例验证")
    print("=" * 60)

    all_correct = True

    for gate_name, config in GATES.items():
        script_path = ROOT / config["script"]
        if not script_path.exists():
            print(f"  ⚠️  {gate_name:20s} SKIP (script not found)")
            continue

        evidence_missing = [item for item in config.get("required_evidence_pass", []) if not (ROOT / item).exists()]
        if evidence_missing:
            print(f"  ❌ {gate_name:20s} 缺少 PASS 证据: {evidence_missing}")
            all_correct = False
            continue

        # Test PASS case
        rc_pass, _, _ = run_gate(config["script"], config["args_pass"])

        # Test BLOCKED case
        rc_blocked, _, _ = run_gate(config["script"], config["args_blocked"])

        expect_blocked = config.get("expect_blocked", True)
        if rc_pass == 0 and ((rc_blocked != 0) if expect_blocked else (rc_blocked == 0)):
            blocked_label = "✓" if expect_blocked else "SKIP"
            print(f"  ✅ {gate_name:20s} PASS=✓ BLOCKED={blocked_label}")
        else:
            print(f"  ❌ {gate_name:20s} PASS={rc_pass} BLOCKED={rc_blocked}")
            if rc_pass != 0:
                _, stdout_pass, stderr_pass = run_gate(config["script"], config["args_pass"])
                print(f"     PASS stdout: {stdout_pass.splitlines()[:2]}")
                print(f"     PASS stderr: {stderr_pass.splitlines()[:2]}")
            if expect_blocked and rc_blocked == 0:
                _, stdout_blocked, stderr_blocked = run_gate(config["script"], config["args_blocked"])
                print(f"     BLOCKED stdout: {stdout_blocked.splitlines()[:2]}")
                print(f"     BLOCKED stderr: {stderr_blocked.splitlines()[:2]}")
            all_correct = False

    return all_correct

def main():
    print("=" * 60)
    print("  DeliverHQ Gate Contract Check")
    print("=" * 60)
    print(f"  Root: {ROOT}\n")

    exists_ok = check_gate_exists()
    contract_ok = check_gate_pass_blocked()

    print("\n" + "=" * 60)
    print("  总结")
    print("=" * 60)

    if exists_ok and contract_ok:
        print("  ✅ 所有 Gate 契约验证通过")
        sys.exit(0)
    else:
        if not exists_ok:
            print("  ❌ 部分 Gate 脚本缺失")
        if not contract_ok:
            print("  ❌ 部分 Gate 正反例验证失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
