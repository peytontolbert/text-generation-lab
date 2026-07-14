#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11474
NAME = "stage11474_residual50_python_cpp_counterfamily_topup"
OUT = ART / NAME
SUMMARY = OUT / "residual50_python_cpp_counterfamily_topup.json"
ROWS = OUT / "residual50_python_cpp_counterfamily_rows.jsonl"
ADMITTED = OUT / "admitted_residual50_python_cpp_counterfamily_rows.jsonl"
BLOCKED = OUT / "blocked_residual50_python_cpp_counterfamily_rows.jsonl"

RETRIEVAL_ROWS = ART / "strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
STAGE11205_ADMITTED = ART / "stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"
RESIDUAL_BANK = ART / "stage11445_targeted_residual_role_support_postrun_audit/bounded_choice_eval_audit_residual_bank_encoder_option_retrieval.json"
INVENTORY = ART / "stage11473_residual50_inventory_and_build_request/residual50_inventory_and_build_request.json"

ROLE_OPTIONS = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
]
LABELS = list("ABCD")
TARGET_ROLE = "candidate_change_surface"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def language_family(files: list[str], repo: str) -> str:
    blob = " ".join(files + [repo]).lower()
    if any(token in blob for token in [".cpp", ".cc", ".cxx", ".cu", ".h", ".hpp", "cmakelists"]):
        return "c_cpp"
    if any(token in blob for token in [".py", "pyproject.toml", "setup.py"]):
        return "python"
    if any(token in blob for token in [".rs", "cargo.toml"]):
        return "rust"
    if any(token in blob for token in [".js", ".ts", ".tsx", ".jsx", ".html", ".css", "package.json"]):
        return "web_js_ts_html"
    return "unknown"


def path_preview(paths: list[str], limit: int = 3) -> str:
    clean = [p for p in paths if p]
    if not clean:
        return "none"
    suffix = f" (+{len(clean) - limit} more)" if len(clean) > limit else ""
    return ", ".join(clean[:limit]) + suffix


def stable_options(seed: str) -> list[dict[str, str]]:
    values = list(ROLE_OPTIONS)
    values.sort(key=lambda value: hashlib.sha256(f"{seed}::{value}".encode()).hexdigest())
    return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]


def parse_retrieval(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        parsed = json.loads(row.get("target_text") or "{}")
    except Exception:
        return None
    final_state = parsed.get("final_state") or {}
    if not isinstance(final_state, dict):
        return None
    changed = final_state.get("expected_changed_files") or []
    tests = final_state.get("verification_targets") or []
    if not changed or not tests:
        return None
    return parsed


def make_row(source: dict[str, Any], parsed: dict[str, Any], variant: str) -> dict[str, Any]:
    final_state = parsed["final_state"]
    repo = str(parsed.get("canonical_name") or "unknown")
    changed = [str(item) for item in final_state.get("expected_changed_files") or []]
    tests = [str(item) for item in final_state.get("verification_targets") or []]
    symbols = [str(item) for item in final_state.get("key_symbols") or []]
    lang = language_family(changed + tests, repo)
    options = stable_options(f"{source.get('row_id')}::{TARGET_ROLE}::{variant}")
    label_by_value = {option["value"]: option["label"] for option in options}
    target_label = label_by_value[TARGET_ROLE]
    evidence_facts = {
        "candidate_change_surface": f"Evidence item E01: the concrete changed source/config surface is visible at `{changed[0]}`; changed-file preview: {path_preview(changed)}.",
        "verifier_and_test_constraint": f"Evidence item E02: selected verifier/test target is visible at `{tests[0]}`; verifier preview: {path_preview(tests)}; route: {final_state.get('test_selection_route') or 'PASS_TARGETED_TEST_SELECTION'}.",
        "symptom_or_call_path_analogue": f"Evidence item E03: execution or call-path analogue is indicated by key symbols: {path_preview(symbols, limit=4)}.",
        "nearby_definition_or_usage_context": "Evidence item E04: nearby definitions/usages are useful context but are not the most direct support for the changed surface.",
    }
    prompt = (
        f"Language: {lang}\n"
        "Perspective: evidence_citation\n"
        "Task: choose which evidence item is the most decisive support for the maintainer decision. Use the visible evidence, not option order or label prior.\n"
        f"Repository family: {repo}\n"
        f"Execution route: {final_state.get('execution_route') or 'unknown'}\n\n"
        "Visible evidence ledger:\n"
        f"{evidence_facts['candidate_change_surface']}\n"
        f"{evidence_facts['verifier_and_test_constraint']}\n"
        f"{evidence_facts['symptom_or_call_path_analogue']}\n"
        f"{evidence_facts['nearby_definition_or_usage_context']}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in options)
        + "\nAnswer:"
    )
    row_id = f"stage11474::{source.get('row_id')}::{TARGET_ROLE}::{variant}"
    return {
        "row_id": row_id,
        "root_id": f"stage11474::{source.get('row_id')}",
        "source_root_id": source.get("row_id"),
        "repo_family": repo,
        "language_family": lang,
        "task_type": "evidence_citation",
        "split": "train",
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "expected_enabled_loss": "decoder_ce",
        "disable_losses": [],
        "loss_mask": {"decoder_ce": True},
        "target_token_len": 1,
        "target": {
            "decoder_text": target_label,
            "target_text": target_label,
            "bounded_choice_target_label": target_label,
        },
        "bounded_choice_target_label": target_label,
        "opaque_options": options,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "fresh_long_context_root": True,
            "opaque_labels": True,
            "target_role_not_named_before_options": True,
            "target_path_strings_hidden_pre_options": True,
            "explicit_selected_test_ledger": True,
            "same_surface_eval_admissible": False,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage11474_residual50_counterfamily_topup",
            "source_row_id": source.get("row_id"),
            "source_canonical_name": repo,
            "gold_value": TARGET_ROLE,
            "gold_label": target_label,
            "opaque_options": options,
            "evidence_facts": evidence_facts,
            "changed_files": changed,
            "verification_targets": tests,
            "key_symbols_preview": symbols[:16],
            "variant": variant,
        },
    }


def role_leak_before_options(row: dict[str, Any]) -> bool:
    before_options = str(row.get("input_text") or "").split("\nOptions:\n", 1)[0]
    return any(role in before_options for role in ROLE_OPTIONS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    existing_stage11205 = iter_jsonl(STAGE11205_ADMITTED)
    used_roots = {str(row.get("source_root_id") or row.get("root_id") or "") for row in existing_stage11205}
    used_repos = {str(row.get("repo_family") or "") for row in existing_stage11205 if row.get("repo_family")}

    residual = load_json(RESIDUAL_BANK)
    for miss in residual.get("row_cards") or []:
        used_repos.add(str(miss.get("repo_family") or ""))
        used_roots.add(str(miss.get("row_id") or ""))

    retrieval_rows = iter_jsonl(RETRIEVAL_ROWS)
    selected: list[dict[str, Any]] = []
    selected_counts: Counter[str] = Counter()
    selected_repos: set[str] = set()
    for source in retrieval_rows:
        parsed = parse_retrieval(source)
        if parsed is None:
            continue
        source_id = str(source.get("row_id") or "")
        repo = str(parsed.get("canonical_name") or "unknown")
        final_state = parsed["final_state"]
        lang = language_family(
            [str(item) for item in (final_state.get("expected_changed_files") or [])]
            + [str(item) for item in (final_state.get("verification_targets") or [])],
            repo,
        )
        if lang not in {"python", "c_cpp"}:
            continue
        if selected_counts[lang] >= 2:
            continue
        if source_id in used_roots or repo in used_repos or repo in selected_repos:
            continue
        row = make_row(source, parsed, variant=f"{lang}_counter_{selected_counts[lang]:02d}")
        selected.append(row)
        selected_counts[lang] += 1
        selected_repos.add(repo)
        if selected_counts["python"] >= 2 and selected_counts["c_cpp"] >= 2:
            break

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in selected:
        reasons: list[str] = []
        if role_leak_before_options(row):
            reasons.append("role_name_before_options")
        if len(row.get("opaque_options") or []) != 4:
            reasons.append("wrong_option_count")
        if not row.get("anti_cheat", {}).get("deterministic_option_shuffle"):
            reasons.append("missing_deterministic_shuffle")
        if not row.get("anti_cheat", {}).get("target_path_strings_hidden_pre_options"):
            reasons.append("target_path_leak_control_missing")
        if (row.get("standalone_projection_source") or {}).get("gold_value") != TARGET_ROLE:
            reasons.append("wrong_gold_role")
        if reasons:
            blocked_row = dict(row)
            blocked_row["block_reasons"] = reasons
            blocked.append(blocked_row)
        else:
            admitted.append(row)

    write_jsonl(ROWS, selected)
    write_jsonl(ADMITTED, admitted)
    write_jsonl(BLOCKED, blocked)

    by_language = Counter(row.get("language_family") for row in admitted)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": by_language.get("python") == 2 and by_language.get("c_cpp") == 2 and not blocked,
        "decision": "python_cpp_counterfamily_topup_admitted"
        if by_language.get("python") == 2 and by_language.get("c_cpp") == 2 and not blocked
        else "python_cpp_counterfamily_topup_incomplete_or_blocked",
        "targeted_residual50_gap": {
            "python_evidence_verifier_constraint_vs_candidate_surface": "add 2 candidate_change_surface counterfamily roots",
            "cpp_evidence_verifier_constraint_vs_candidate_surface": "add 2 candidate_change_surface counterfamily roots",
        },
        "metrics": {
            "retrieval_rows_scanned": len(retrieval_rows),
            "selected_rows": len(selected),
            "admitted_rows": len(admitted),
            "blocked_rows": len(blocked),
            "admitted_by_language": dict(sorted(by_language.items())),
            "admitted_unique_roots": len({row.get("root_id") for row in admitted}),
            "admitted_unique_repos": len({row.get("repo_family") for row in admitted}),
            "excluded_stage11205_roots": len(used_roots),
            "excluded_stage11205_or_residual_repos": len(used_repos),
        },
        "source_artifacts": {
            "inventory": rel(INVENTORY),
            "retrieval_rows": rel(RETRIEVAL_ROWS),
            "stage11205_admitted": rel(STAGE11205_ADMITTED),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "rows": rel(ROWS),
            "admitted": rel(ADMITTED),
            "blocked": rel(BLOCKED),
        },
        "notes": [
            "Rows are train-support-only counterfamily analogues and must not be used as strict heldout.",
            "This stage does not solve the Rust symptom/call-path residual family.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
