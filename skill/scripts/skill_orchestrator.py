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
        script_path = Path(skill.script_path)

        if not script_path.exists():
            print(f"❌ Skill script not found: {script_path}")
            return False

        # Build args using template
        cr_id = Path(cr_path).name  # e.g., CR-001
        args_value = skill.args_template.format(cr_path=cr_path, cr_id=cr_id)

        # Run skill script
        result = subprocess.run(
            [sys.executable, str(script_path), args_value],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        if result.returncode == 0:
            print(f"✅ Skill completed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ Skill failed")
            if result.stderr:
                print(result.stderr)
            return False

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

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
