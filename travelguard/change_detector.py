"""Change detection service supporting working tree, git commit ranges, and fixture sources."""

from abc import ABC, abstractmethod
import os
from pathlib import Path
import re
import subprocess
from typing import List, Optional, Tuple

from travelguard.models import ChangeSet, ChangeSourceType, ChangeStatus, FileChange


def parse_unified_diff(diff_text: str) -> List[FileChange]:
    """Parse raw git unified diff output into structured FileChange objects."""
    if not diff_text or not diff_text.strip():
        return []

    file_changes: List[FileChange] = []
    # Split by diff --git
    diff_blocks = re.split(r"(?=diff --git )", diff_text)

    for block in diff_blocks:
        if not block.strip() or not block.startswith("diff --git"):
            continue

        lines = block.splitlines()
        first_line = lines[0]
        # Match 'diff --git a/path b/path'
        match = re.search(r"diff --git a/(.*?) b/(.*)", first_line)
        if not match:
            continue

        old_path_raw = match.group(1).strip()
        new_path_raw = match.group(2).strip()

        # Determine status
        status = ChangeStatus.MODIFIED
        if "new file mode" in block:
            status = ChangeStatus.ADDED
        elif "deleted file mode" in block:
            status = ChangeStatus.DELETED
        elif "similarity index" in block or "rename from" in block:
            status = ChangeStatus.RENAMED

        # Count additions and deletions
        additions = 0
        deletions = 0
        for line in lines:
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                additions += 1
            elif line.startswith("-"):
                deletions += 1

        file_changes.append(
            FileChange(
                path=new_path_raw if status != ChangeStatus.DELETED else old_path_raw,
                status=status,
                old_path=old_path_raw if status == ChangeStatus.RENAMED else None,
                diff=block,
                additions=additions,
                deletions=deletions,
            )
        )

    return file_changes


class BaseChangeSource(ABC):
    """Abstract change source interface."""

    @abstractmethod
    def get_change_set(self) -> ChangeSet:
        """Return the normalized change set."""
        pass

    @abstractmethod
    def get_changed_files(self) -> List[str]:
        """Return list of changed relative file paths."""
        pass

    @abstractmethod
    def get_diff(self, file_path: Optional[str] = None) -> str:
        """Return raw unified diff text, optionally filtered to a single file."""
        pass


class GitWorkingTreeSource(BaseChangeSource):
    """Detects changes in the current Git working tree (staged, unstaged, untracked)."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()

    def _run_git(self, args: List[str]) -> Tuple[int, str, str]:
        """Execute a git command in the repository root."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return res.returncode, res.stdout, res.stderr
        except FileNotFoundError:
            return 127, "", "git executable not found"

    def get_changed_files(self) -> List[str]:
        """Get list of modified, added, deleted, and untracked files via git status."""
        code, out, _ = self._run_git(["status", "--porcelain=v1", "-uall"])
        if code != 0 or not out:
            return []

        changed = []
        for line in out.splitlines():
            if not line or not line.strip():
                continue
            # Format: XY PATH or XY "PATH" or R  OLD -> NEW
            # Two status characters, space, then path (do not strip line before slice)
            parts = line[3:].strip()
            if " -> " in parts:
                parts = parts.split(" -> ")[-1].strip()
            changed.append(parts.replace('"', ""))
        return changed

    def get_diff(self, file_path: Optional[str] = None) -> str:
        """Get unified diff for unstaged and staged changes."""
        diff_parts = []
        # Staged diff
        staged_args = ["diff", "--cached"]
        if file_path:
            staged_args.extend(["--", file_path])
        _, staged_out, _ = self._run_git(staged_args)
        if staged_out.strip():
            diff_parts.append(staged_out.strip())

        # Unstaged diff
        unstaged_args = ["diff"]
        if file_path:
            unstaged_args.extend(["--", file_path])
        _, unstaged_out, _ = self._run_git(unstaged_args)
        if unstaged_out.strip():
            diff_parts.append(unstaged_out.strip())

        # Check untracked files if no staged/unstaged diff exists for it
        if file_path and not diff_parts:
            # Check if file is untracked
            full_path = self.repo_root / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    diff_parts.append(
                        f"diff --git a/{file_path} b/{file_path}\n"
                        f"new file mode 100644\n"
                        f"--- /dev/null\n"
                        f"+++ b/{file_path}\n"
                        + "\n".join(f"+{l}" for l in content.splitlines())
                    )
                except Exception:
                    pass

        return "\n\n".join(diff_parts)

    def get_change_set(self) -> ChangeSet:
        """Extract and normalize all working tree changes."""
        raw_diff = self.get_diff()
        parsed_files = parse_unified_diff(raw_diff)

        # Catch untracked files not captured in diff
        changed_paths = self.get_changed_files()
        existing_diff_paths = {f.path for f in parsed_files}

        for path in changed_paths:
            if path not in existing_diff_paths:
                file_diff = self.get_diff(path)
                if file_diff:
                    extra_parsed = parse_unified_diff(file_diff)
                    if extra_parsed:
                        parsed_files.extend(extra_parsed)
                        continue

                # Add fallback untracked entry if diff couldn't be generated
                parsed_files.append(
                    FileChange(
                        path=path,
                        status=ChangeStatus.UNTRACKED,
                        diff="",
                        additions=0,
                        deletions=0,
                    )
                )

        summary = f"{len(parsed_files)} file(s) changed in working tree"
        return ChangeSet(
            source=ChangeSourceType.WORKING_TREE,
            files=parsed_files,
            summary=summary,
        )


class GitCommitDiffSource(BaseChangeSource):
    """Detects changes between git commits or branch references (e.g., HEAD~1..HEAD or PR base)."""

    def __init__(self, base_ref: str, target_ref: Optional[str] = None, repo_root: Optional[Path] = None):
        self.base_ref = base_ref
        self.target_ref = target_ref or "HEAD"
        self.repo_root = repo_root or Path.cwd()

    def _run_git(self, args: List[str]) -> Tuple[int, str, str]:
        """Execute a git command in the repository root."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return res.returncode, res.stdout, res.stderr
        except FileNotFoundError:
            return 127, "", "git executable not found"

    def get_changed_files(self) -> List[str]:
        """Get changed files between base and target refs."""
        code, out, _ = self._run_git(["diff", "--name-only", f"{self.base_ref}..{self.target_ref}"])
        if code != 0 or not out:
            # Try single ref comparison
            code, out, _ = self._run_git(["diff", "--name-only", self.base_ref])
            if code != 0 or not out:
                return []
        return [line.strip() for line in out.splitlines() if line.strip()]

    def get_diff(self, file_path: Optional[str] = None) -> str:
        """Get unified diff between base and target refs."""
        args = ["diff", f"{self.base_ref}..{self.target_ref}"]
        if file_path:
            args.extend(["--", file_path])
        code, out, _ = self._run_git(args)
        if code != 0 or not out.strip():
            fallback_args = ["diff", self.base_ref]
            if file_path:
                fallback_args.extend(["--", file_path])
            _, out, _ = self._run_git(fallback_args)
        return out.strip()

    def get_change_set(self) -> ChangeSet:
        """Extract and normalize commit diff changes."""
        raw_diff = self.get_diff()
        parsed_files = parse_unified_diff(raw_diff)
        summary = f"{len(parsed_files)} file(s) changed between {self.base_ref} and {self.target_ref}"
        return ChangeSet(
            source=ChangeSourceType.GIT_DIFF,
            base_ref=self.base_ref,
            target_ref=self.target_ref,
            files=parsed_files,
            summary=summary,
        )


class FixtureChangeSource(BaseChangeSource):
    """Provides controlled, deterministic changes from predefined diff fixtures."""

    def __init__(self, raw_diff: str, fixture_name: str = "fixture"):
        self.raw_diff = raw_diff
        self.fixture_name = fixture_name

    def get_changed_files(self) -> List[str]:
        parsed = parse_unified_diff(self.raw_diff)
        return [f.path for f in parsed]

    def get_diff(self, file_path: Optional[str] = None) -> str:
        if not file_path:
            return self.raw_diff
        parsed = parse_unified_diff(self.raw_diff)
        for f in parsed:
            if f.path == file_path:
                return f.diff
        return ""

    def get_change_set(self) -> ChangeSet:
        parsed_files = parse_unified_diff(self.raw_diff)
        return ChangeSet(
            source=ChangeSourceType.FIXTURE,
            summary=f"Fixture: {self.fixture_name} ({len(parsed_files)} files)",
            files=parsed_files,
        )


class ChangeDetector:
    """Service responsible for detecting application changes."""

    def __init__(self, source: Optional[BaseChangeSource] = None):
        self.source = source or GitWorkingTreeSource()

    def get_changed_files(self) -> List[str]:
        """Return list of changed file names."""
        return self.source.get_changed_files()

    def get_diff(self, file_path: Optional[str] = None) -> str:
        """Return unified diff."""
        return self.source.get_diff(file_path=file_path)

    def get_change_summary(self) -> str:
        """Return human-readable summary of detected changes."""
        cs = self.get_change_set()
        return f"{cs.summary} (+{cs.total_additions}, -{cs.total_deletions})"

    def get_change_set(self) -> ChangeSet:
        """Return normalized ChangeSet object."""
        return self.source.get_change_set()
