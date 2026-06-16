#!/usr/bin/env python3
"""
Worktree Manager for DeliverHQ v4.7

Provides worktree isolation for parallel CR development.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum


class WorktreeStatus(Enum):
    """Worktree status"""
    ACTIVE = "ACTIVE"
    MERGED = "MERGED"
    DELETED = "DELETED"


@dataclass
class WorktreeInfo:
    """Worktree information"""
    path: str
    branch: str
    cr_id: str
    status: WorktreeStatus
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorktreeInfo':
        """Create from dict"""
        data['status'] = WorktreeStatus(data['status'])
        return cls(**data)


@dataclass
class MergeResult:
    """Merge operation result"""
    success: bool
    conflicts: List[str]
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return asdict(self)


class WorktreeConfig:
    """Worktree configuration"""
    def __init__(self):
        self.base_path = ".claude/worktrees"
        self.max_worktrees = 10
        self.cleanup_policy = "manual"

    def get_worktree_path(self, cr_id: str) -> Path:
        """Get worktree path for CR"""
        return Path(self.base_path) / cr_id

    def get_branch_name(self, cr_id: str) -> str:
        """Get branch name for CR"""
        return f"feature/{cr_id}"


class WorktreeManager:
    """Worktree manager for parallel CR development"""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize worktree manager"""
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Find git root
            self.project_root = self._find_git_root()

        self.config = WorktreeConfig()
        self.registry_file = self.project_root / ".claude" / "worktree_registry.json"
        self._ensure_directories()

    def _find_git_root(self) -> Path:
        """Find git repository root"""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        raise RuntimeError("Not in a git repository")

    def _ensure_directories(self):
        """Ensure required directories exist"""
        base_dir = self.project_root / self.config.base_path
        base_dir.mkdir(parents=True, exist_ok=True)

        registry_dir = self.registry_file.parent
        registry_dir.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> Dict[str, WorktreeInfo]:
        """Load worktree registry"""
        if not self.registry_file.exists():
            return {}

        with open(self.registry_file, 'r') as f:
            data = json.load(f)

        return {cr_id: WorktreeInfo.from_dict(info)
                for cr_id, info in data.items()}

    def _save_registry(self, registry: Dict[str, WorktreeInfo]):
        """Save worktree registry"""
        data = {cr_id: info.to_dict()
                for cr_id, info in registry.items()}

        with open(self.registry_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _run_git(self, args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run git command"""
        cmd = ["git"] + args
        return subprocess.run(
            cmd,
            cwd=cwd or self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

    def create(self, cr_id: str, base_branch: str = "master") -> WorktreeInfo:
        """
        Create worktree for CR

        Args:
            cr_id: CR identifier (e.g., CR-003)
            base_branch: Base branch to branch from (default: master)

        Returns:
            WorktreeInfo object

        Raises:
            RuntimeError: If worktree creation fails
        """
        # Validate CR ID format
        if not cr_id.startswith("CR-"):
            raise ValueError(f"Invalid CR ID format: {cr_id}. Expected CR-XXX")

        # Extract number part
        try:
            number_part = cr_id[3:]
            if not number_part or not all(c.isdigit() or c.isalpha() for c in number_part):
                raise ValueError(f"Invalid CR ID format: {cr_id}. Expected CR-XXX")
        except:
            raise ValueError(f"Invalid CR ID format: {cr_id}. Expected CR-XXX")

        # Check if worktree already exists
        registry = self._load_registry()
        if cr_id in registry and registry[cr_id].status == WorktreeStatus.ACTIVE:
            raise RuntimeError(f"Worktree for {cr_id} already exists at {registry[cr_id].path}")

        # Check max worktrees limit
        active_count = sum(1 for info in registry.values()
                          if info.status == WorktreeStatus.ACTIVE)
        if active_count >= self.config.max_worktrees:
            raise RuntimeError(
                f"Maximum worktrees limit reached ({self.config.max_worktrees}). "
                f"Please cleanup old worktrees first."
            )

        # Get worktree path and branch name
        worktree_path = self.config.get_worktree_path(cr_id)
        branch_name = self.config.get_branch_name(cr_id)

        # Create worktree
        result = self._run_git([
            "worktree", "add",
            str(worktree_path),
            "-b", branch_name,
            base_branch
        ])

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

        # Create worktree info
        import datetime
        info = WorktreeInfo(
            path=str(worktree_path.absolute()),
            branch=branch_name,
            cr_id=cr_id,
            status=WorktreeStatus.ACTIVE,
            created_at=datetime.datetime.now().isoformat()
        )

        # Save to registry
        registry[cr_id] = info
        self._save_registry(registry)

        print(f"✅ Worktree created: {worktree_path}")
        print(f"   Branch: {branch_name}")
        print(f"   Base: {base_branch}")

        return info

    def switch(self, cr_id: str) -> bool:
        """
        Switch to worktree directory

        Args:
            cr_id: CR identifier

        Returns:
            True if switched successfully

        Note:
            This returns the path for shell to cd into.
            Actual directory change must be done by shell.
        """
        registry = self._load_registry()

        if cr_id not in registry:
            raise RuntimeError(f"Worktree for {cr_id} not found")

        info = registry[cr_id]
        if info.status != WorktreeStatus.ACTIVE:
            raise RuntimeError(f"Worktree for {cr_id} is not active (status: {info.status.value})")

        worktree_path = Path(info.path)
        if not worktree_path.exists():
            raise RuntimeError(f"Worktree path does not exist: {worktree_path}")

        print(f"📂 Switch to: {worktree_path}")
        print(f"   Branch: {info.branch}")
        print(f"   Run: cd {worktree_path}")

        return True

    def list_worktrees(self) -> List[WorktreeInfo]:
        """
        List all worktrees

        Returns:
            List of WorktreeInfo objects
        """
        registry = self._load_registry()
        return list(registry.values())

    def detect_conflicts(self, cr_id: str) -> List[str]:
        """
        Detect merge conflicts before merging

        Args:
            cr_id: CR identifier

        Returns:
            List of conflicting files (empty if no conflicts)
        """
        registry = self._load_registry()

        if cr_id not in registry:
            raise RuntimeError(f"Worktree for {cr_id} not found")

        info = registry[cr_id]

        # Dry-run merge to detect conflicts
        result = self._run_git([
            "merge-tree",
            "master",
            info.branch
        ])

        if result.returncode != 0:
            # Parse conflicts from output
            conflicts = []
            for line in result.stdout.split('\n'):
                if line.startswith('changed in both'):
                    # Extract filename
                    parts = line.split()
                    if len(parts) > 3:
                        conflicts.append(parts[3])
            return conflicts

        return []

    def merge(self, cr_id: str) -> MergeResult:
        """
        Merge worktree branch and cleanup

        Args:
            cr_id: CR identifier

        Returns:
            MergeResult object
        """
        registry = self._load_registry()

        if cr_id not in registry:
            raise RuntimeError(f"Worktree for {cr_id} not found")

        info = registry[cr_id]

        # Detect conflicts first
        conflicts = self.detect_conflicts(cr_id)
        if conflicts:
            return MergeResult(
                success=False,
                conflicts=conflicts,
                message=f"Merge conflicts detected in {len(conflicts)} files. Please resolve manually."
            )

        # Switch to master
        result = self._run_git(["checkout", "master"])
        if result.returncode != 0:
            return MergeResult(
                success=False,
                conflicts=[],
                message=f"Failed to checkout master: {result.stderr}"
            )

        # Merge branch
        result = self._run_git(["merge", info.branch, "--no-ff"])
        if result.returncode != 0:
            return MergeResult(
                success=False,
                conflicts=[],
                message=f"Merge failed: {result.stderr}"
            )

        # Update status
        info.status = WorktreeStatus.MERGED
        registry[cr_id] = info
        self._save_registry(registry)

        print(f"✅ Merged {info.branch} into master")
        print(f"   Run cleanup to remove worktree: python scripts/worktree_manager.py cleanup {cr_id}")

        return MergeResult(
            success=True,
            conflicts=[],
            message=f"Successfully merged {info.branch} into master"
        )

    def cleanup(self, cr_id: str, force: bool = False) -> bool:
        """
        Cleanup worktree and delete branch

        Args:
            cr_id: CR identifier
            force: Force cleanup even if not merged

        Returns:
            True if cleaned up successfully
        """
        registry = self._load_registry()

        if cr_id not in registry:
            raise RuntimeError(f"Worktree for {cr_id} not found")

        info = registry[cr_id]

        # Check if merged
        if info.status == WorktreeStatus.ACTIVE and not force:
            raise RuntimeError(
                f"Worktree {cr_id} has not been merged. "
                f"Use --force to cleanup anyway."
            )

        worktree_path = Path(info.path)

        # Remove worktree first (this will allow branch deletion)
        if worktree_path.exists():
            result = self._run_git(["worktree", "remove", str(worktree_path), "--force"])
            if result.returncode != 0:
                print(f"⚠️  Warning: Failed to remove worktree: {result.stderr}")

        # Delete branch (now that worktree is removed)
        result = self._run_git(["branch", "-D", info.branch])
        if result.returncode != 0:
            # Branch might already be deleted, just warn
            if "not found" not in result.stderr:
                print(f"⚠️  Warning: Failed to delete branch: {result.stderr}")

        # Update registry
        info.status = WorktreeStatus.DELETED
        registry[cr_id] = info
        self._save_registry(registry)

        print(f"✅ Cleaned up worktree for {cr_id}")

        return True


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="DeliverHQ Worktree Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # create command
    create_parser = subparsers.add_parser('create', help='Create worktree')
    create_parser.add_argument('cr_id', help='CR identifier (e.g., CR-003)')
    create_parser.add_argument('--base', default='master', help='Base branch (default: master)')

    # switch command
    switch_parser = subparsers.add_parser('switch', help='Switch to worktree')
    switch_parser.add_argument('cr_id', help='CR identifier')

    # list command
    subparsers.add_parser('list', help='List all worktrees')

    # merge command
    merge_parser = subparsers.add_parser('merge', help='Merge and cleanup worktree')
    merge_parser.add_argument('cr_id', help='CR identifier')

    # cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup worktree')
    cleanup_parser.add_argument('cr_id', help='CR identifier')
    cleanup_parser.add_argument('--force', action='store_true', help='Force cleanup')

    # detect-conflicts command
    conflicts_parser = subparsers.add_parser('detect-conflicts', help='Detect merge conflicts')
    conflicts_parser.add_argument('cr_id', help='CR identifier')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        manager = WorktreeManager()

        if args.command == 'create':
            info = manager.create(args.cr_id, args.base)
            print(json.dumps(info.to_dict(), indent=2))

        elif args.command == 'switch':
            manager.switch(args.cr_id)

        elif args.command == 'list':
            worktrees = manager.list_worktrees()
            for wt in worktrees:
                print(f"{wt.cr_id}: {wt.path} ({wt.status.value})")

        elif args.command == 'merge':
            result = manager.merge(args.cr_id)
            print(json.dumps(result.to_dict(), indent=2))
            if not result.success:
                sys.exit(1)

        elif args.command == 'cleanup':
            manager.cleanup(args.cr_id, args.force)

        elif args.command == 'detect-conflicts':
            conflicts = manager.detect_conflicts(args.cr_id)
            if conflicts:
                print(f"⚠️  Conflicts detected in {len(conflicts)} files:")
                for file in conflicts:
                    print(f"   - {file}")
                sys.exit(1)
            else:
                print("✅ No conflicts detected")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
