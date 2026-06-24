#!/usr/bin/env python3
"""
Loop Mode Execution Engine for DeliverHQ v4.7

Automatically execute tasks in a loop until completion or blocked.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class TaskStatus(Enum):
    """Task status"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


@dataclass
class Task:
    """Task definition"""
    id: str
    title: str
    description: str
    status: TaskStatus
    dependencies: List[str]
    cr_id: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create from dict"""
        data['status'] = TaskStatus(data['status'])
        return cls(**data)


@dataclass
class LoopConfig:
    """Loop configuration"""
    max_iterations: int = 100
    max_blocked_count: int = 3
    gate_check_enabled: bool = True
    auto_cleanup: bool = True


@dataclass
class LoopResult:
    """Loop execution result"""
    total_tasks: int
    completed: int
    blocked: int
    skipped: int
    iterations: int
    success: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return asdict(self)


class LoopMode:
    """Loop Mode execution engine"""

    def __init__(self, config: Optional[LoopConfig] = None):
        """Initialize loop mode"""
        self.config = config or LoopConfig()
        self.tasks: Dict[str, Task] = {}
        self.iteration = 0
        self.blocked_count = 0

    def add_task(self, task: Task):
        """Add task to loop"""
        self.tasks[task.id] = task

    def load_tasks(self, tasks_file: str):
        """Load tasks from JSON file"""
        with open(tasks_file, 'r') as f:
            data = json.load(f)

        for task_data in data.get('tasks', []):
            task = Task.from_dict(task_data)
            self.add_task(task)

    def get_next_task(self) -> Optional[Task]:
        """Get next executable task"""
        for task in self.tasks.values():
            # Skip non-pending tasks
            if task.status != TaskStatus.PENDING:
                continue

            # Check dependencies
            deps_satisfied = all(
                self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
                if dep_id in self.tasks
            )

            if deps_satisfied:
                return task

        return None

    def execute_task(self, task: Task) -> bool:
        """
        Execute a single task

        Returns:
            True if successful, False if blocked
        """
        print(f"\n{'='*60}")
        print(f"Executing Task: {task.id} - {task.title}")
        print(f"{'='*60}")

        # Update status
        task.status = TaskStatus.IN_PROGRESS
        import datetime
        task.started_at = datetime.datetime.now().isoformat()

        try:
            # Execute task logic
            print(f"📝 {task.description}")

            # 真实执行：如果 task 有 check_command，执行它
            if hasattr(task, 'check_command') and task.check_command:
                import subprocess
                result = subprocess.run(
                    task.check_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    timeout=300
                )

                if result.returncode != 0:
                    raise RuntimeError(f"Check command failed: {result.stderr}")

                print(f"✅ Check passed: {result.stdout[:200]}")

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.datetime.now().isoformat()
            print(f"✅ Task completed: {task.id}")
            return True

        except Exception as e:
            # Mark as blocked
            task.status = TaskStatus.BLOCKED
            task.error_message = str(e)
            print(f"❌ Task blocked: {task.id}")
            print(f"   Error: {e}")
            return False

    def run_gates(self, task: Task) -> bool:
        """
        Run quality gates for task

        Returns:
            True if gates pass, False if blocked
        """
        if not self.config.gate_check_enabled:
            return True

        print(f"\n🚪 Running gates for {task.id}...")

        # 真实执行：根据 task 类型运行相应的 gate
        gate_map = {
            "spec": "scripts/specgate.py",
            "design": "scripts/designgate.py",
            "quality": "scripts/qualitygate.py",
            "review": "scripts/reviewgate.py",
        }

        gate_script = gate_map.get(task.type)
        if not gate_script:
            print(f"⚠️  No gate for task type: {task.type}")
            return True

        gate_path = ROOT / gate_script
        if not gate_path.exists():
            print(f"⚠️  Gate script not found: {gate_script}")
            return True

        # 执行 gate
        import subprocess
        try:
            result = subprocess.run(
                [sys.executable, str(gate_path), task.target_path or ""],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=60
            )

            if result.returncode == 0:
                print(f"✅ Gate passed: {gate_script}")
                return True
            else:
                print(f"❌ Gate failed: {gate_script}")
                print(result.stdout)
                return False

        except Exception as e:
            print(f"❌ Gate error: {e}")
            return False

    def run_loop(self) -> LoopResult:
        """
        Run the main loop

        Returns:
            LoopResult with execution summary
        """
        print(f"\n{'#'*60}")
        print(f"# Loop Mode: Starting Execution")
        print(f"# Total tasks: {len(self.tasks)}")
        print(f"# Max iterations: {self.config.max_iterations}")
        print(f"{'#'*60}\n")

        self.iteration = 0
        self.blocked_count = 0

        while self.iteration < self.config.max_iterations:
            self.iteration += 1
            print(f"\n{'='*60}")
            print(f"Iteration {self.iteration}")
            print(f"{'='*60}")

            # Get next task
            task = self.get_next_task()

            if not task:
                # Check if all tasks are completed
                completed = sum(1 for t in self.tasks.values()
                              if t.status == TaskStatus.COMPLETED)
                blocked = sum(1 for t in self.tasks.values()
                            if t.status == TaskStatus.BLOCKED)
                pending = sum(1 for t in self.tasks.values()
                            if t.status == TaskStatus.PENDING)

                if pending == 0:
                    # All tasks processed
                    print(f"\n✅ All tasks processed!")
                    break
                else:
                    # Tasks are blocked by dependencies
                    print(f"\n⚠️  No executable tasks found")
                    print(f"   Pending: {pending}")
                    print(f"   Blocked: {blocked}")
                    self.blocked_count += 1

                    if self.blocked_count >= self.config.max_blocked_count:
                        print(f"\n❌ Max blocked count reached ({self.config.max_blocked_count})")
                        break
                    continue

            # Reset blocked count when we find a task
            self.blocked_count = 0

            # Execute task
            success = self.execute_task(task)

            if success:
                # Run gates
                gates_pass = self.run_gates(task)

                if not gates_pass:
                    task.status = TaskStatus.BLOCKED
                    task.error_message = "Gates failed"
                    print(f"❌ Gates failed for {task.id}")

        # Generate result
        completed = sum(1 for t in self.tasks.values()
                       if t.status == TaskStatus.COMPLETED)
        blocked = sum(1 for t in self.tasks.values()
                     if t.status == TaskStatus.BLOCKED)
        skipped = sum(1 for t in self.tasks.values()
                     if t.status == TaskStatus.SKIPPED)

        all_completed = completed == len(self.tasks)

        result = LoopResult(
            total_tasks=len(self.tasks),
            completed=completed,
            blocked=blocked,
            skipped=skipped,
            iterations=self.iteration,
            success=all_completed,
            message=f"Completed {completed}/{len(self.tasks)} tasks in {self.iteration} iterations"
        )

        # Print summary
        self.print_summary(result)

        return result

    def print_summary(self, result: LoopResult):
        """Print execution summary"""
        print(f"\n{'#'*60}")
        print(f"# Loop Mode: Execution Summary")
        print(f"{'#'*60}")
        print(f"Total tasks:   {result.total_tasks}")
        print(f"Completed:     {result.completed} ✅")
        print(f"Blocked:       {result.blocked} ❌")
        print(f"Skipped:       {result.skipped} ⏭️")
        print(f"Iterations:    {result.iterations}")
        print(f"Success:       {'✅ YES' if result.success else '❌ NO'}")
        print(f"{'#'*60}\n")

        # Print blocked tasks
        if result.blocked > 0:
            print(f"\n⚠️  Blocked tasks:")
            for task in self.tasks.values():
                if task.status == TaskStatus.BLOCKED:
                    print(f"   - {task.id}: {task.title}")
                    print(f"     Error: {task.error_message}")

    def save_state(self, output_file: str):
        """Save execution state"""
        data = {
            'iteration': self.iteration,
            'blocked_count': self.blocked_count,
            'tasks': [task.to_dict() for task in self.tasks.values()]
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n💾 State saved to {output_file}")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="DeliverHQ Loop Mode Execution Engine")
    parser.add_argument('tasks_file', help='Tasks JSON file')
    parser.add_argument('--max-iterations', type=int, default=100,
                       help='Maximum iterations (default: 100)')
    parser.add_argument('--max-blocked', type=int, default=3,
                       help='Maximum consecutive blocked iterations (default: 3)')
    parser.add_argument('--no-gates', action='store_true',
                       help='Disable gate checking')
    parser.add_argument('--output', default='loop_state.json',
                       help='Output state file (default: loop_state.json)')

    args = parser.parse_args()

    # Create config
    config = LoopConfig(
        max_iterations=args.max_iterations,
        max_blocked_count=args.max_blocked,
        gate_check_enabled=not args.no_gates
    )

    # Create loop mode
    loop = LoopMode(config)

    try:
        # Load tasks
        loop.load_tasks(args.tasks_file)

        # Run loop
        result = loop.run_loop()

        # Save state
        loop.save_state(args.output)

        # Exit with appropriate code
        sys.exit(0 if result.success else 1)

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
