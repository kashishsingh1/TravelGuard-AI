"""Unit tests for change detection and diff parsing."""

import pytest
from travelguard.change_detector import (
    ChangeDetector,
    FixtureChangeSource,
    parse_unified_diff,
)
from travelguard.models import ChangeSourceType, ChangeStatus


SAMPLE_DIFF = """diff --git a/frontend/src/components/SearchForm.tsx b/frontend/src/components/SearchForm.tsx
index 1111111..2222222 100644
--- a/frontend/src/components/SearchForm.tsx
+++ b/frontend/src/components/SearchForm.tsx
@@ -10,3 +10,4 @@
-const oldCode = true;
+const newCode = false;
+const extraCode = true;
diff --git a/backend/app/api/new_endpoint.py b/backend/app/api/new_endpoint.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/backend/app/api/new_endpoint.py
@@ -0,0 +1,5 @@
+from fastapi import APIRouter
+router = APIRouter()
+@router.get("/new")
+def new_route():
+    return {"ok": True}
diff --git a/docs/old_guide.md b/docs/old_guide.md
deleted file mode 100644
index 4444444..0000000
--- a/docs/old_guide.md
+++ /dev/null
@@ -1,2 +0,0 @@
-# Old Guide
-Deprecate this.
"""


def test_parse_unified_diff_modified_file():
    """Verify parsing modified files and calculating additions/deletions."""
    changes = parse_unified_diff(SAMPLE_DIFF)
    assert len(changes) == 3

    search_file = next(f for f in changes if "SearchForm.tsx" in f.path)
    assert search_file.status == ChangeStatus.MODIFIED
    assert search_file.additions == 2
    assert search_file.deletions == 1
    assert "SearchForm.tsx" in search_file.path


def test_parse_unified_diff_added_file():
    """Verify parsing newly added files."""
    changes = parse_unified_diff(SAMPLE_DIFF)
    new_file = next(f for f in changes if "new_endpoint.py" in f.path)
    assert new_file.status == ChangeStatus.ADDED
    assert new_file.additions == 5
    assert new_file.deletions == 0


def test_parse_unified_diff_deleted_file():
    """Verify parsing deleted files."""
    changes = parse_unified_diff(SAMPLE_DIFF)
    deleted_file = next(f for f in changes if "old_guide.md" in f.path)
    assert deleted_file.status == ChangeStatus.DELETED
    assert deleted_file.additions == 0
    assert deleted_file.deletions == 2


def test_parse_empty_diff():
    """Verify parsing empty diff returns empty list."""
    assert parse_unified_diff("") == []
    assert parse_unified_diff("   \n\n  ") == []


def test_fixture_change_source():
    """Verify FixtureChangeSource encapsulates diff without altering files."""
    source = FixtureChangeSource(raw_diff=SAMPLE_DIFF, fixture_name="test_fixture")
    detector = ChangeDetector(source=source)

    changed_files = detector.get_changed_files()
    assert len(changed_files) == 3
    assert "frontend/src/components/SearchForm.tsx" in changed_files

    change_set = detector.get_change_set()
    assert change_set.source == ChangeSourceType.FIXTURE
    assert change_set.total_additions == 7
    assert change_set.total_deletions == 3
    assert "3 files" in detector.get_change_summary()
