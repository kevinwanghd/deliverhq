#!/usr/bin/env python3
"""
Manual Worktree Manager checks for DeliverHQ v4.7 (not collected by pytest)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from worktree_manager import WorktreeManager, WorktreeStatus


def run_command(cmd):
    """Run shell command"""
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    return result.returncode == 0, result.stdout, result.stderr


def test_create_worktree():
    """Test worktree creation"""
    print("\n📝 Test: Create worktree")

    manager = WorktreeManager()

    # Create test worktree
    try:
        info = manager.create("CR-TEST", "master")

        # Verify
        assert info.cr_id == "CR-TEST"
        assert info.status == WorktreeStatus.ACTIVE
        assert Path(info.path).exists()

        print("✅ PASS: Worktree created successfully")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        # Cleanup
        try:
            manager.cleanup("CR-TEST", force=True)
        except:
            pass


def test_list_worktrees():
    """Test listing worktrees"""
    print("\n📝 Test: List worktrees")

    manager = WorktreeManager()

    try:
        # Create test worktree
        manager.create("CR-TEST1", "master")

        # List
        worktrees = manager.list_worktrees()

        # Verify
        assert len(worktrees) > 0
        assert any(wt.cr_id == "CR-TEST1" for wt in worktrees)

        print(f"✅ PASS: Found {len(worktrees)} worktrees")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        # Cleanup
        try:
            manager.cleanup("CR-TEST1", force=True)
        except:
            pass


def test_max_worktrees_limit():
    """Test max worktrees limit"""
    print("\n📝 Test: Max worktrees limit")

    manager = WorktreeManager()
    created = []

    try:
        # Try to create max+1 worktrees
        for i in range(manager.config.max_worktrees + 1):
            cr_id = f"CR-T{i:02d}"
            try:
                manager.create(cr_id, "master")
                created.append(cr_id)
            except RuntimeError as e:
                if "Maximum worktrees limit" in str(e):
                    print(f"✅ PASS: Max limit enforced at {len(created)} worktrees")
                    return True
                raise

        print(f"❌ FAIL: Should have hit max limit")
        return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        # Cleanup
        for cr_id in created:
            try:
                manager.cleanup(cr_id, force=True)
            except:
                pass


def test_invalid_cr_id():
    """Test invalid CR ID validation"""
    print("\n📝 Test: Invalid CR ID validation")

    manager = WorktreeManager()

    # Test various invalid formats
    invalid_ids = ["CR001", "cr-001", "TEST", "CR-", "CR-ABCD"]

    for cr_id in invalid_ids:
        try:
            manager.create(cr_id, "master")
            print(f"❌ FAIL: Should have rejected {cr_id}")
            return False
        except ValueError:
            pass  # Expected

    print("✅ PASS: Invalid CR IDs rejected")
    return True


def test_duplicate_worktree():
    """Test duplicate worktree detection"""
    print("\n📝 Test: Duplicate worktree detection")

    manager = WorktreeManager()

    try:
        # Create first
        manager.create("CR-TEST", "master")

        # Try to create duplicate
        try:
            manager.create("CR-TEST", "master")
            print("❌ FAIL: Should have detected duplicate")
            return False
        except RuntimeError as e:
            if "already exists" in str(e):
                print("✅ PASS: Duplicate detected")
                return True
            raise
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        # Cleanup
        try:
            manager.cleanup("CR-TEST", force=True)
        except:
            pass


def test_cleanup_without_force():
    """Test cleanup without force flag"""
    print("\n📝 Test: Cleanup without force flag")

    manager = WorktreeManager()

    try:
        # Create worktree
        manager.create("CR-TEST", "master")

        # Try to cleanup without force (should fail)
        try:
            manager.cleanup("CR-TEST", force=False)
            print("❌ FAIL: Should have required force flag")
            return False
        except RuntimeError as e:
            if "not been merged" in str(e):
                print("✅ PASS: Force flag required for unmerged worktree")
                return True
            raise
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        # Cleanup
        try:
            manager.cleanup("CR-TEST", force=True)
        except:
            pass


def test_worktree_isolation():
    """Test worktree isolation"""
    print("\n📝 Test: Worktree isolation")

    manager = WorktreeManager()

    try:
        # Create two worktrees
        info1 = manager.create("CR-TS1", "master")
        info2 = manager.create("CR-TS2", "master")

        # Verify they have different paths
        assert info1.path != info2.path
        assert Path(info1.path).exists()
        assert Path(info2.path).exists()

        # Create a test file in worktree 1
        test_file1 = Path(info1.path) / "test_isolation_1.txt"
        test_file1.write_text("worktree 1")

        # Verify it doesn't exist in worktree 2
        test_file2 = Path(info2.path) / "test_isolation_1.txt"
        assert not test_file2.exists()

        print("✅ PASS: Worktrees are isolated")
        return True
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False
    finally:
        # Cleanup
        for cr_id in ["CR-TS1", "CR-TS2"]:
            try:
                manager.cleanup(cr_id, force=True)
            except:
                pass


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("DeliverHQ v4.7 Worktree Manager Tests")
    print("=" * 60)

    tests = [
        test_create_worktree,
        test_list_worktrees,
        test_max_worktrees_limit,
        test_invalid_cr_id,
        test_duplicate_worktree,
        test_cleanup_without_force,
        test_worktree_isolation,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ FAIL: Unexpected error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
