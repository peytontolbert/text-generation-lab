from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from patch_minimality_complexity_meter import score_patch, score_rows


def test_passes_small_local_patch() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
-x = 1
+x = 2
"""
    record = score_patch({"row_id": "small", "patch": diff})
    assert record["patch_minimality_route"] == "PASS_PATCH_MINIMALITY"
    assert record["changed_lines"] == 2


def test_blocks_overlarge_patch() -> None:
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n" + "\n".join(f"+x{i}=1" for i in range(12))
    record = score_patch({"row_id": "large", "patch": diff}, max_changed_lines=10)
    assert record["patch_minimality_route"] == "BLOCK_OVERBROAD_PATCH"
    assert "changed_lines_over_budget" in record["reasons"]


def test_holds_public_api_touches() -> None:
    diff = """diff --git a/api.py b/api.py
--- a/api.py
+++ b/api.py
@@ -1 +1 @@
+def public_api():
+    return 1
"""
    record = score_patch({"row_id": "api", "patch": diff})
    assert record["patch_minimality_route"] == "HOLD_PUBLIC_API_REVIEW"
    assert "def:public_api" in record["public_api_touches"]


def test_blocks_new_dependency_or_import() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1,2 @@
+import requests
 x = 1
"""
    record = score_patch({"row_id": "dep", "patch": diff})
    assert record["patch_minimality_route"] == "BLOCK_OVERBROAD_PATCH"
    assert "new_dependency_or_import" in record["reasons"]


def test_blocks_too_many_files() -> None:
    diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
+x=1
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
+y=1
"""
    record = score_patch({"row_id": "files", "patch": diff}, max_files_changed=1)
    assert record["patch_minimality_route"] == "BLOCK_OVERBROAD_PATCH"
    assert "files_changed_over_budget" in record["reasons"]


def test_holds_missing_patch_text() -> None:
    record = score_patch({"row_id": "missing"})
    assert record["patch_minimality_route"] == "HOLD_PATCH_REVIEW"


def test_manifest_counts_routes() -> None:
    card = score_rows([
        {"row_id": "ok", "patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a=1\n+a=2"},
        {"row_id": "missing"},
        {"row_id": "dep", "patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n+import requests"},
    ])
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["review_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
