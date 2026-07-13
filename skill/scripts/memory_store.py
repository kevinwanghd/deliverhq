#!/usr/bin/env python3
"""
External Memory Integration for DeliverHQ v4.7

Provides persistent memory storage and retrieval across CRs.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, fields
from datetime import datetime


VALID_STATUSES = {"active", "superseded", "deprecated"}


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _fingerprint(entry_type: str, content: str, root_cause: str = "", applies_to: str = "") -> str:
    semantic_cause = root_cause or content
    material = "|".join((_normalize(entry_type), _normalize(semantic_cause), _normalize(applies_to)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class MemoryEntry:
    """Memory entry"""
    id: str
    type: str  # decision, mistake, rule, pattern
    content: str
    context: str
    cr_id: Optional[str]
    tags: List[str]
    created_at: str
    updated_at: str
    references: List[str]
    fingerprint: str = ""
    root_cause: str = ""
    status: str = "active"
    applies_to: str = ""
    keywords: List[str] = None
    occurrences: int = 1
    first_seen: str = ""
    last_seen: str = ""
    superseded_by: Optional[str] = None
    revalidate_when: str = ""
    evidence: List[str] = None

    def __post_init__(self):
        self.keywords = list(self.keywords or [])
        self.evidence = list(self.evidence or [])
        self.fingerprint = self.fingerprint or _fingerprint(
            self.type, self.content, self.root_cause, self.applies_to
        )
        self.first_seen = self.first_seen or self.created_at
        self.last_seen = self.last_seen or self.updated_at
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid memory status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dict"""
        allowed = {field.name for field in fields(cls)}
        payload = {key: value for key, value in data.items() if key in allowed}
        return cls(**payload)


class MemoryStore:
    """External memory store for cross-CR knowledge"""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize memory store"""
        if storage_path is None:
            home = Path(os.environ.get("DELIVERHQ_HOME", "DeliverHQ"))
            storage_path = home / "memory"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.index_file = self.storage_path / "index.json"
        self.entries: Dict[str, MemoryEntry] = {}
        self._load_index()

    def _load_index(self):
        """Load memory index"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                # Corrupted or unreadable index: degrade to empty store.
                self.entries = {}
                return

            self.entries = {
                entry_id: MemoryEntry.from_dict(entry_data)
                for entry_id, entry_data in data.items()
            }

    def _save_index(self):
        """Save memory index"""
        data = {
            entry_id: entry.to_dict()
            for entry_id, entry in self.entries.items()
        }

        with open(self.index_file, 'w', encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _generate_id(self, fingerprint: str) -> str:
        """Generate a stable ID from a semantic SHA-256 fingerprint."""
        return fingerprint[:16]

    def add(self,
            content: str,
            type: str,
            context: str = "",
            cr_id: Optional[str] = None,
            tags: List[str] = None,
            references: List[str] = None,
            root_cause: str = "",
            status: str = "active",
            applies_to: str = "",
            keywords: List[str] = None,
            evidence: List[str] = None,
            fingerprint: Optional[str] = None) -> MemoryEntry:
        """
        Add memory entry

        Args:
            content: Memory content
            type: Type (decision/mistake/rule/pattern)
            context: Context description
            cr_id: Related CR ID
            tags: Tags for categorization
            references: Related entry IDs

        Returns:
            Created MemoryEntry
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid memory status: {status}")
        fingerprint = fingerprint or _fingerprint(type, content, root_cause, applies_to)
        existing = next(
            (entry for entry in self.entries.values() if entry.fingerprint == fingerprint),
            None,
        )
        entry_id = existing.id if existing else self._generate_id(fingerprint)
        now = datetime.now().isoformat()

        # Check if exists
        if existing:
            # Update existing
            entry = existing
            entry.updated_at = now
            entry.last_seen = now
            entry.occurrences += 1
            if tags:
                entry.tags = list(dict.fromkeys(entry.tags + tags))
            if references:
                entry.references = list(dict.fromkeys(entry.references + references))
            if keywords:
                entry.keywords = list(dict.fromkeys(entry.keywords + keywords))
            if evidence:
                entry.evidence = list(dict.fromkeys(entry.evidence + evidence))
        else:
            # Create new
            entry = MemoryEntry(
                id=entry_id,
                type=type,
                content=content,
                context=context,
                cr_id=cr_id,
                tags=tags or [],
                created_at=now,
                updated_at=now,
                references=references or [],
                fingerprint=fingerprint,
                root_cause=root_cause,
                status=status,
                applies_to=applies_to,
                keywords=keywords or [],
                occurrences=1,
                first_seen=now,
                last_seen=now,
                evidence=evidence or [],
            )
            self.entries[entry_id] = entry

        self._save_index()
        print(f"✅ Memory added: {entry_id} ({type})")
        return entry

    def supersede(self, entry_id: str, replacement_id: str) -> MemoryEntry:
        """Mark an entry as superseded while preserving its audit history."""
        if entry_id not in self.entries or replacement_id not in self.entries:
            raise KeyError("Both the old and replacement memory entries must exist")
        entry = self.entries[entry_id]
        entry.status = "superseded"
        entry.superseded_by = replacement_id
        entry.updated_at = datetime.now().isoformat()
        self._save_index()
        return entry

    def deprecate(self, entry_id: str, revalidate_when: str) -> MemoryEntry:
        """Deprecate an entry and record when it may become relevant again."""
        if entry_id not in self.entries:
            raise KeyError(entry_id)
        entry = self.entries[entry_id]
        entry.status = "deprecated"
        entry.revalidate_when = revalidate_when
        entry.updated_at = datetime.now().isoformat()
        self._save_index()
        return entry

    def search(self,
               query: Optional[str] = None,
               type: Optional[str] = None,
               tags: Optional[List[str]] = None,
               cr_id: Optional[str] = None) -> List[MemoryEntry]:
        """
        Search memories

        Args:
            query: Text search query
            type: Filter by type
            tags: Filter by tags
            cr_id: Filter by CR ID

        Returns:
            List of matching MemoryEntry
        """
        results = list(self.entries.values())

        # Filter by type
        if type:
            results = [e for e in results if e.type == type]

        # Filter by tags
        if tags:
            results = [e for e in results
                      if any(tag in e.tags for tag in tags)]

        # Filter by CR
        if cr_id:
            results = [e for e in results if e.cr_id == cr_id]

        # Text search
        if query:
            query_lower = query.lower()
            results = [e for e in results
                      if query_lower in e.content.lower() or
                         query_lower in e.context.lower()]

        # Sort by updated_at (newest first)
        results.sort(key=lambda e: e.updated_at, reverse=True)

        return results

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get memory by ID"""
        return self.entries.get(entry_id)

    def delete(self, entry_id: str) -> bool:
        """Delete memory"""
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save_index()
            print(f"✅ Memory deleted: {entry_id}")
            return True
        return False

    @staticmethod
    def _generated_doc_path(docs_dir: Path, canonical_name: str) -> Path:
        """Preserve human-owned canonical docs and emit a reviewable generated view."""
        canonical = docs_dir / canonical_name
        if not canonical.exists():
            return canonical
        return docs_dir / canonical_name.replace(".md", ".generated.md")

    def export_to_docs(self, docs_path: str = "docs"):
        """
        Export memories to documentation files

        Creates/updates:
        - docs/decisions.md
        - docs/mistake-book.md
        - docs/rules.md
        """
        docs_dir = Path(docs_path)
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Export decisions
        decisions = self.search(type="decision")
        if decisions:
            decisions_file = self._generated_doc_path(docs_dir, "decisions.md")
            with open(decisions_file, 'w', encoding="utf-8") as f:
                f.write("# Architecture Decisions\n\n")
                f.write("> Generated from external memory store\n\n")
                for entry in decisions:
                    f.write(f"## {entry.id}\n\n")
                    f.write(f"**Date**: {entry.created_at[:10]}\n\n")
                    if entry.cr_id:
                        f.write(f"**CR**: {entry.cr_id}\n\n")
                    f.write(f"{entry.content}\n\n")
                    if entry.context:
                        f.write(f"**Context**: {entry.context}\n\n")
                    if entry.tags:
                        f.write(f"**Tags**: {', '.join(entry.tags)}\n\n")
                    f.write("---\n\n")
            print(f"✅ Exported {len(decisions)} decisions to {decisions_file}")

        # Export mistakes
        mistakes = self.search(type="mistake")
        if mistakes:
            mistakes_file = self._generated_doc_path(docs_dir, "mistake-book.md")
            with open(mistakes_file, 'w', encoding="utf-8") as f:
                f.write("# Mistake Book\n\n")
                f.write("> Generated from external memory store\n\n")
                for entry in mistakes:
                    f.write(f"## {entry.id}\n\n")
                    f.write(f"**Date**: {entry.created_at[:10]}\n\n")
                    if entry.cr_id:
                        f.write(f"**CR**: {entry.cr_id}\n\n")
                    f.write(f"**Problem**: {entry.content}\n\n")
                    if entry.context:
                        f.write(f"**Solution**: {entry.context}\n\n")
                    if entry.tags:
                        f.write(f"**Tags**: {', '.join(entry.tags)}\n\n")
                    f.write("---\n\n")
            print(f"✅ Exported {len(mistakes)} mistakes to {mistakes_file}")

        # Export rules
        rules = self.search(type="rule")
        if rules:
            rules_file = self._generated_doc_path(docs_dir, "rules.md")
            with open(rules_file, 'w', encoding="utf-8") as f:
                f.write("# Coding Rules\n\n")
                f.write("> Generated from external memory store\n\n")
                for entry in rules:
                    f.write(f"## {entry.content}\n\n")
                    if entry.context:
                        f.write(f"{entry.context}\n\n")
                    if entry.tags:
                        f.write(f"**Tags**: {', '.join(entry.tags)}\n\n")
                    f.write("---\n\n")
            print(f"✅ Exported {len(rules)} rules to {rules_file}")

    def import_from_docs(self, docs_path: str = "docs"):
        """
        Import existing documentation into memory store

        Parses:
        - docs/MEMORY.md
        - docs/decisions.md (if exists)
        - docs/mistake-book.md (if exists)
        """
        docs_dir = Path(docs_path)

        # Import from MEMORY.md
        memory_file = docs_dir / "MEMORY.md"
        if memory_file.exists():
            print(f"📥 Importing from {memory_file}...")
            # Parse MEMORY.md and extract decisions
            content = memory_file.read_text()

            # Simple parsing - look for decision entries in table
            import re
            decision_pattern = r'\| (\d{4}-\d{2}-\d{2}) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|'
            matches = re.findall(decision_pattern, content)

            for match in matches:
                date, decision, reason, cr_id, author = match
                self.add(
                    content=decision.strip(),
                    type="decision",
                    context=f"Reason: {reason.strip()}",
                    cr_id=cr_id.strip() if cr_id.strip() != '-' else None,
                    tags=["imported", "decision"]
                )

            print(f"✅ Imported {len(matches)} decisions")

    def stats(self) -> Dict[str, int]:
        """Get memory statistics"""
        stats = {
            "total": len(self.entries),
            "decisions": len(self.search(type="decision")),
            "mistakes": len(self.search(type="mistake")),
            "rules": len(self.search(type="rule")),
            "patterns": len(self.search(type="pattern"))
        }
        return stats


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="DeliverHQ External Memory Store")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # add command
    add_parser = subparsers.add_parser('add', help='Add memory entry')
    add_parser.add_argument('type', choices=['decision', 'mistake', 'rule', 'pattern'])
    add_parser.add_argument('content', help='Memory content')
    add_parser.add_argument('--context', default='', help='Context description')
    add_parser.add_argument('--cr', help='Related CR ID')
    add_parser.add_argument('--tags', help='Comma-separated tags')
    add_parser.add_argument('--root-cause', default='', help='Normalized root cause for semantic dedup')
    add_parser.add_argument('--applies-to', default='', help='Runtime/stack/profile scope')
    add_parser.add_argument('--keywords', help='Comma-separated retrieval keywords')
    add_parser.add_argument('--evidence', action='append', help='Evidence path; repeatable')

    # search command
    search_parser = subparsers.add_parser('search', help='Search memories')
    search_parser.add_argument('--query', help='Search query')
    search_parser.add_argument('--type', choices=['decision', 'mistake', 'rule', 'pattern'])
    search_parser.add_argument('--tags', help='Comma-separated tags')
    search_parser.add_argument('--cr', help='CR ID')

    # export command
    export_parser = subparsers.add_parser('export', help='Export to docs/')
    export_parser.add_argument('--path', default='docs', help='Docs path')

    # import command
    import_parser = subparsers.add_parser('import', help='Import from docs/')
    import_parser.add_argument('--path', default='docs', help='Docs path')

    # stats command
    subparsers.add_parser('stats', help='Show statistics')

    # delete command
    delete_parser = subparsers.add_parser('delete', help='Delete memory')
    delete_parser.add_argument('entry_id', help='Entry ID to delete')

    supersede_parser = subparsers.add_parser('supersede', help='Supersede a memory entry')
    supersede_parser.add_argument('entry_id')
    supersede_parser.add_argument('replacement_id')

    deprecate_parser = subparsers.add_parser('deprecate', help='Deprecate a memory entry')
    deprecate_parser.add_argument('entry_id')
    deprecate_parser.add_argument('--revalidate-when', required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        store = MemoryStore()

        if args.command == 'add':
            tags = args.tags.split(',') if args.tags else []
            entry = store.add(
                content=args.content,
                type=args.type,
                context=args.context,
                cr_id=args.cr,
                tags=tags,
                root_cause=args.root_cause,
                applies_to=args.applies_to,
                keywords=args.keywords.split(',') if args.keywords else [],
                evidence=args.evidence or [],
            )
            print(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))

        elif args.command == 'search':
            tags = args.tags.split(',') if args.tags else None
            results = store.search(
                query=args.query,
                type=args.type,
                tags=tags,
                cr_id=args.cr
            )
            print(f"\n🔍 Found {len(results)} memories:\n")
            for entry in results:
                print(f"[{entry.id}] ({entry.type}) {entry.content[:60]}...")
                if entry.cr_id:
                    print(f"  CR: {entry.cr_id}")
                if entry.tags:
                    print(f"  Tags: {', '.join(entry.tags)}")
                print()

        elif args.command == 'export':
            store.export_to_docs(args.path)

        elif args.command == 'import':
            store.import_from_docs(args.path)

        elif args.command == 'stats':
            stats = store.stats()
            print("\n📊 Memory Statistics:\n")
            for key, value in stats.items():
                print(f"  {key.capitalize()}: {value}")
            print()

        elif args.command == 'delete':
            if store.delete(args.entry_id):
                print(f"✅ Deleted {args.entry_id}")
            else:
                print(f"❌ Entry not found: {args.entry_id}")
                sys.exit(1)

        elif args.command == 'supersede':
            entry = store.supersede(args.entry_id, args.replacement_id)
            print(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))

        elif args.command == 'deprecate':
            entry = store.deprecate(args.entry_id, args.revalidate_when)
            print(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
