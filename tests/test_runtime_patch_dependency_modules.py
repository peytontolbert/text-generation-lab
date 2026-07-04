import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dependency_capability_card_builder import build_dependency_capability_card
from patch_history_modality_builder import build_patch_history_packet
from runtime_trace_normalizer import normalize_runtime_trace


def test_runtime_trace_normalizer_extracts_frames_and_failure_type():
    trace = """Traceback (most recent call last):
  File \"src/app.py\", line 10, in run
    missing()
NameError: name 'missing' is not defined
"""
    packet = normalize_runtime_trace(trace, row_id="r1")
    assert packet["exception_type"] == "NameError"
    assert packet["failure_type"] == "symbol_binding_failure"
    assert packet["frames"][0]["path"] == "src/app.py"
    assert packet["evidence_spans"][0]["line"] == 10


def test_patch_history_builder_extracts_files_hunks_and_symbols():
    diff = """diff --git a/src/app.py b/src/app.py
@@ -1,2 +1,5 @@
-def old():
-    pass
+def new_func():
+    return 1
"""
    packet = build_patch_history_packet(diff, row_id="p1")
    assert packet["stats"]["files_changed"] == 1
    assert packet["stats"]["hunks"] == 1
    assert packet["stats"]["additions"] == 2
    assert packet["stats"]["deletions"] == 2
    assert "new_func" in packet["changed_symbols"]


def test_dependency_capability_card_builder_preserves_import_policy():
    card = build_dependency_capability_card({
        "name": "numpy",
        "version": "2.x",
        "language_family": "python",
        "allowed_import": True,
        "exports": ["array", "dot", "array"],
        "usage_patterns": "vector math,linear algebra",
        "verifier_requirements": ["import_resolves", "tests_pass"],
    })
    assert card["name"] == "numpy"
    assert card["allowed_import"] is True
    assert card["blocked_import"] is False
    assert card["exports"] == ["array", "dot"]
    assert "linear algebra" in card["usage_patterns"]
    assert card["failures"] == []


def test_dependency_capability_card_flags_conflicting_policy():
    card = build_dependency_capability_card({"name": "x", "allowed_import": True, "blocked_import": True})
    assert "allowed_and_blocked_conflict" in card["failures"]
