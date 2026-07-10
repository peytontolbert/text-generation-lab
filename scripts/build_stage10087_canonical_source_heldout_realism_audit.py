#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10087
NAME = "stage10087_canonical_source_heldout_realism_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "canonical_source_heldout_realism_audit.json"
SPEC = OUT_DIR / "canonical_source_heldout_realistic_successor_spec.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_SOURCE_HELDOUT_REALISM_AUDIT_STAGE10087.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10083_canonical_label_aligned_source_heldout_successor_packet/canonical_label_aligned_source_heldout_manifest.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage10086_canonical_label_aligned_source_heldout_same_manifest_comparison_audit/canonical_label_aligned_source_heldout_same_manifest_comparison_audit.json"

SEMANTIC_SURFACES = {
    "symbol_definition_or_implementation_surface",
    "entrypoint_or_invocation_surface",
    "configuration_or_settings_surface",
    "implementation_file_surface",
    "test_surface",
}
CONCRETE_FIELD_GROUPS = {
    "failure_text": ["failure_text", "failure_excerpt", "task_observation"],
    "trace_or_stack": ["stack_trace", "trace_excerpt", "call_trace", "runtime_trace"],
    "code_snippets": ["relevant_snippets", "snippet", "code_excerpt", "definition_excerpt"],
    "file_or_symbol_refs": ["file_paths", "file_path", "symbol_names", "symbol_name", "candidate_paths"],
    "test_assertions": ["test_assertion", "assertion_text", "expected_vs_actual", "expected_output"],
    "config_fragments": ["config_excerpt", "config_fragment"],
}
LEVELS = {
    "L0": "abstract_category_evidence",
    "L1": "realistic_failure_text_plus_candidate_descriptions",
    "L2": "snippets_trace_and_test_assertions",
    "L3": "multi_file_causal_localization",
    "L4": "ambiguous_or_counterfactual_case_requiring_abstain",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _heldout_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("split") or "") in {"eval", "strict_eval"}]


def _input_state(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("input_state") if isinstance(row.get("input_state"), dict) else {}


def _has_any_field(payload: dict[str, Any], names: list[str]) -> bool:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def _candidate_surface_only(row: dict[str, Any]) -> bool:
    choices = (_input_state(row).get("candidate_choices") or [])
    parsed = []
    for choice in choices:
        if not isinstance(choice, str) or ":" not in choice:
            return False
        parsed.append(choice.split(":", 1)[1].strip())
    return bool(parsed) and set(parsed).issubset(SEMANTIC_SURFACES)


def _realism_level(row: dict[str, Any]) -> str:
    state = _input_state(row)
    has_trace = _has_any_field(state, CONCRETE_FIELD_GROUPS["trace_or_stack"])
    has_snippet = _has_any_field(state, CONCRETE_FIELD_GROUPS["code_snippets"])
    has_assert = _has_any_field(state, CONCRETE_FIELD_GROUPS["test_assertions"])
    has_paths = _has_any_field(state, CONCRETE_FIELD_GROUPS["file_or_symbol_refs"])
    if has_trace and has_snippet and has_assert and has_paths:
        return "L2"
    if _has_any_field(state, ["failure_text", "failure_excerpt"]) and has_paths:
        return "L1"
    if _candidate_surface_only(row):
        return "L0"
    return "L0"


def build_audit() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    heldout_rows = _heldout_rows(rows)
    comparison = load_json(COMPARISON)
    failures: list[str] = []
    if comparison.get("passed") is not True:
        failures.append("stage10086_not_passed")
    if len(rows) != 95:
        failures.append("rows_not_95")
    if len(heldout_rows) != 55:
        failures.append("heldout_rows_not_55")

    level_counts = Counter(_realism_level(row) for row in heldout_rows)
    candidate_surface_only = sum(1 for row in heldout_rows if _candidate_surface_only(row))
    missing_source_identity = sum(1 for row in heldout_rows if not row.get("source_id") and not row.get("source_root"))
    present_field_groups = {
        group: sum(1 for row in heldout_rows if _has_any_field(_input_state(row), names))
        for group, names in CONCRETE_FIELD_GROUPS.items()
    }
    language_levels: dict[str, dict[str, int]] = {}
    for language in sorted({str(row.get("language_family") or "") for row in heldout_rows}):
        language_levels[language] = dict(sorted(Counter(_realism_level(row) for row in heldout_rows if str(row.get("language_family") or "") == language).items()))

    claim_boundary = {
        "structured_edit_target_taxonomy_supported": True,
        "source_heldout_taxonomy_comparison_supported": True,
        "serious_software_maintenance_eval_supported": False,
        "expert_maintainer_realism_supported": False,
        "reason": "Prompt-visible evidence remains abstract category routing without concrete failure text, stack traces, snippets, file paths, or test assertions.",
    }
    if level_counts.get("L0") != len(heldout_rows):
        failures.append("heldout_rows_not_all_l0")
    if present_field_groups["trace_or_stack"] != 0:
        failures.append("unexpected_trace_fields_present")
    if present_field_groups["code_snippets"] != 0:
        failures.append("unexpected_code_snippet_fields_present")
    if present_field_groups["test_assertions"] != 0:
        failures.append("unexpected_test_assertion_fields_present")

    successor_spec = {
        "successor_name": "canonical_source_heldout_realistic_maintenance_successor",
        "preserve_from_stage10083": {
            "canonical_label_map": {
                "TARGET_TEST": "A",
                "TARGET_ENTRYPOINT": "B",
                "TARGET_SYMBOL": "C",
                "TARGET_FILE": "D",
                "TARGET_CONFIG": "E",
            },
            "heldout_split_integrity": True,
            "source_overlap_policy": "no_train_source_overlap_in_eval_or_strict_eval",
            "anti_cheat_requirements": [
                "opaque_candidate_tokens",
                "candidate_permutation",
                "no_target_literals_in_prompt_surface",
                "counterfactual_audit",
                "expert_maintainer_review",
            ],
        },
        "required_visible_fields_by_level": {
            "L1": ["failure_text", "candidate_descriptions", "language_family", "file_extension"],
            "L2": ["failure_text", "trace_excerpt", "relevant_snippets", "test_assertion", "candidate_descriptions"],
            "L3": ["failure_text", "trace_excerpt", "multi_file_snippets", "candidate_paths", "causal_distractors"],
            "L4": ["failure_text", "conflicting_evidence", "abstain_label", "request_more_evidence_options"],
        },
        "minimum_expert_maintainer_packet": {
            "failure_text": "Expected 400, got 200 for login request with empty email.",
            "trace_excerpt": ["auth/routes.py: login()", "auth/validators.py: normalize_email()"],
            "relevant_snippets": [
                "def normalize_email(email): return email.strip().lower()",
                "def login(req): email = normalize_email(req.email); create_session(email)",
                "assert response.status_code == 400",
            ],
            "candidate_descriptions": [
                "A. tests/test_login.py",
                "B. app.py entrypoint",
                "C. auth/validators.py::normalize_email",
                "D. auth/routes.py::login",
                "E. config/auth.yaml",
            ],
            "answer_requires": ["connect failure to trace", "reason over code behavior", "distinguish symptom from cause"],
        },
        "next_stage_intent": "reuse stage10083 row shell but replace abstract task_observation and visible_locality_evidence with source-backed failure text, snippets, traces, and candidate paths",
    }
    write_json(SPEC, successor_spec)

    examples = []
    for target in ["TARGET_SYMBOL", "TARGET_FILE", "TARGET_TEST", "TARGET_ENTRYPOINT", "TARGET_CONFIG"]:
        row = next((row for row in heldout_rows if str((row.get("clean_state") or {}).get("edit_localization_target_hidden") or "") == target), None)
        if not row:
            continue
        state = _input_state(row)
        examples.append({
            "target_family": target,
            "task_observation": state.get("task_observation"),
            "visible_locality_evidence": state.get("visible_locality_evidence"),
            "candidate_choices": state.get("candidate_choices"),
            "realism_level": _realism_level(row),
        })

    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "claim_boundary": claim_boundary,
        "metrics": {
            "rows": len(rows),
            "heldout_rows": len(heldout_rows),
            "level_counts": dict(sorted(level_counts.items())),
            "rows_with_explicit_surface_candidate_choices": candidate_surface_only,
            "missing_source_identity_rows": missing_source_identity,
            "present_field_groups": present_field_groups,
            "per_language_levels": language_levels,
            "macro_exact_100m": (comparison.get("metrics") or {}).get("macro_exact_100m"),
            "macro_exact_gemma": (comparison.get("metrics") or {}).get("macro_exact_gemma"),
            "macro_delta_100m_minus_gemma": (comparison.get("metrics") or {}).get("macro_delta_100m_minus_gemma"),
        },
        "examples": examples,
        "findings": [
            "The current canonical source-heldout packet is cleanly source-heldout and anti-cheat aware for taxonomy routing, but its visible evidence remains abstract.",
            "Every heldout row fits L0 abstract category evidence rather than realistic broken-function maintenance evidence, even when some heldout rows omit explicit candidate choice text.",
            "No heldout row exposes stack traces, concrete code snippets, file paths, or test assertions to the model-visible surface.",
            "This supports a narrow claim about edit-target taxonomy, not a broad claim about expert-maintainer software maintenance intelligence.",
        ],
        "artifacts": {
            "manifest": display(MANIFEST),
            "comparison": display(COMPARISON),
            "successor_spec": display(SPEC),
        },
        "failures": failures,
    }
    write_json(AUDIT, audit)
    return audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    next_step = "Build a stage10083-derived heldout successor that preserves canonical labels and anti-cheat controls but replaces abstract evidence with concrete failure text, trace excerpts, snippets, file paths, and abstention-capable ambiguous cases."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "spec": display(SPEC), "doc": display(DOC)},
        "decision": "Audited the canonical source-heldout winner for eval realism and found that it cleanly supports edit-target taxonomy claims but not serious expert-maintainer software-maintenance claims without a richer visible evidence surface.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10087 Canonical Source Heldout Realism Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Heldout rows: `{built['metrics']['heldout_rows']}`",
        f"Realism levels: `{built['metrics']['level_counts']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
