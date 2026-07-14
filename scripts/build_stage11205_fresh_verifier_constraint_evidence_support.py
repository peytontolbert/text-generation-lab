#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11205
NAME = "stage11205_fresh_verifier_constraint_evidence_support"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_verifier_constraint_evidence_support.json"
ROWS_JSONL = OUT_DIR / "fresh_verifier_constraint_evidence_rows.jsonl"
ADMITTED_JSONL = OUT_DIR / "admitted_fresh_verifier_constraint_evidence_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "blocked_fresh_verifier_constraint_evidence_rows.jsonl"
RETRIEVAL_ROWS = ARTIFACTS / "strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
CURRENT_TRAIN = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_train.jsonl"
CURRENT_VALIDATION = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_validation.jsonl"
CURRENT_STRICT = ARTIFACTS / "stage11198_role_focused_residual_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"

ROLE_OPTIONS = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
]
LABELS = list("ABCD")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def language_family(files: list[str], repo: str) -> str:
    blob = " ".join(files).lower()
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


def stable_permutation(seed: str) -> list[str]:
    values = list(ROLE_OPTIONS)
    values.sort(key=lambda v: hashlib.sha256(f"{seed}::{v}".encode()).hexdigest())
    return values


def make_row(source: dict[str, Any], parsed: dict[str, Any], *, gold_value: str, variant: str) -> dict[str, Any]:
    fs = parsed["final_state"]
    repo = str(parsed.get("canonical_name") or "unknown")
    changed = [str(x) for x in fs.get("expected_changed_files") or []]
    tests = [str(x) for x in fs.get("verification_targets") or []]
    symbols = [str(x) for x in fs.get("key_symbols") or []]
    lang = language_family(changed + tests, repo)
    seed = f"{source.get('row_id')}::{gold_value}::{variant}"
    values = stable_permutation(seed)
    options = [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]
    label_by_value = {opt["value"]: opt["label"] for opt in options}
    gold_label = label_by_value[gold_value]
    evidence_facts = {
        "candidate_change_surface": f"Evidence item E01: modified implementation/configuration surface is visible at `{changed[0]}`; changed-file preview: {path_preview(changed)}.",
        "verifier_and_test_constraint": f"Evidence item E02: selected verifier/test target is visible at `{tests[0]}`; verifier preview: {path_preview(tests)}; route: {fs.get('test_selection_route') or 'PASS_TARGETED_TEST_SELECTION'}.",
        "symptom_or_call_path_analogue": f"Evidence item E03: execution or call-path analogue is indicated by key symbols: {path_preview(symbols, limit=4)}.",
        "nearby_definition_or_usage_context": "Evidence item E04: nearby definitions/usages provide context, but are not uniquely decisive without the selected verifier or changed-surface evidence.",
    }
    prompt = (
        f"Language: {lang}\n"
        "Perspective: evidence_citation\n"
        "Task: choose which evidence item is the most decisive support for the maintainer decision. Use the visible evidence, not option order or label prior.\n"
        f"Repository family: {repo}\n"
        f"Execution route: {fs.get('execution_route') or 'unknown'}\n\n"
        "Visible evidence ledger:\n"
        f"{evidence_facts['candidate_change_surface']}\n"
        f"{evidence_facts['verifier_and_test_constraint']}\n"
        f"{evidence_facts['symptom_or_call_path_analogue']}\n"
        f"{evidence_facts['nearby_definition_or_usage_context']}\n\n"
        "Options:\n"
        + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
        + "\nAnswer:"
    )
    row_id = f"stage11205::{source.get('row_id')}::{gold_value}::{variant}"
    return {
        "row_id": row_id,
        "root_id": f"stage11205::{source.get('row_id')}",
        "source_root_id": source.get("row_id"),
        "repo_family": repo,
        "language_family": lang,
        "task_type": "evidence_citation",
        "split": "train",
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": gold_label,
        "decoder_text": gold_label,
        "expected_enabled_loss": "decoder_ce",
        "disable_losses": [],
        "loss_mask": {"decoder_ce": True},
        "target_token_len": 1,
        "target": {
            "decoder_text": gold_label,
            "target_text": gold_label,
            "bounded_choice_target_label": gold_label,
        },
        "bounded_choice_target_label": gold_label,
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
            "projection_mode": "stage11205_fresh_verifier_constraint_evidence_support",
            "source_row_id": source.get("row_id"),
            "source_canonical_name": repo,
            "gold_value": gold_value,
            "gold_label": gold_label,
            "opaque_options": options,
            "evidence_facts": evidence_facts,
            "changed_files": changed,
            "verification_targets": tests,
            "key_symbols_preview": symbols[:16],
            "variant": variant,
        },
    }


def parse_retrieval(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        parsed = json.loads(row.get("target_text") or "{}")
    except Exception:
        return None
    fs = parsed.get("final_state") or {}
    if not isinstance(fs, dict):
        return None
    changed = fs.get("expected_changed_files") or []
    tests = fs.get("verification_targets") or []
    if not changed or not tests:
        return None
    repo = str(parsed.get("canonical_name") or "unknown")
    lang = language_family([str(x) for x in changed + tests], repo)
    if lang not in {"python", "c_cpp"}:
        return None
    return parsed


def prompt_prefix_has_role_leak(row: dict[str, Any]) -> bool:
    prompt = str(row.get("input_text") or "")
    before_options = prompt.split("\nOptions:\n", 1)[0]
    return any(role in before_options for role in ROLE_OPTIONS)


def main() -> None:
    existing_rows: list[dict[str, Any]] = []
    for path in [CURRENT_TRAIN, CURRENT_VALIDATION, CURRENT_STRICT, RESIDUAL_BANK]:
        existing_rows.extend(load_jsonl(path))
    used_roots = {str(row.get("root_id") or row.get("source_root_id") or "") for row in existing_rows}
    used_repos = {str(row.get("repo_family") or "") for row in existing_rows if row.get("repo_family")}

    retrieval_rows = load_jsonl(RETRIEVAL_ROWS)
    candidates: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    seen_repo_counts: Counter[str] = Counter()
    for source in retrieval_rows:
        parsed = parse_retrieval(source)
        if parsed is None:
            continue
        repo = str(parsed.get("canonical_name") or "unknown")
        source_id = str(source.get("row_id") or "")
        lang = language_family([str(x) for x in (parsed.get("final_state") or {}).get("expected_changed_files", []) + (parsed.get("final_state") or {}).get("verification_targets", [])], repo)
        if source_id in used_roots or f"stage11205::{source_id}" in used_roots:
            continue
        if repo in used_repos:
            continue
        if seen_repo_counts[repo] >= 2:
            continue
        candidates.append((source, parsed, lang))
        seen_repo_counts[repo] += 1

    selected: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []
    selected_keys: set[tuple[str, str]] = set()
    quotas = {("python", "verifier_and_test_constraint"): 24, ("c_cpp", "verifier_and_test_constraint"): 24, ("python", "candidate_change_surface"): 8, ("c_cpp", "candidate_change_surface"): 8}
    counts: Counter[tuple[str, str]] = Counter()
    for key, quota in quotas.items():
        want_lang, want_gold = key
        for source, parsed, lang in candidates:
            source_key = (str(source.get("row_id") or ""), want_gold)
            if lang != want_lang or source_key in selected_keys:
                continue
            selected.append((source, parsed, lang, want_gold))
            selected_keys.add(source_key)
            counts[key] += 1
            if counts[key] >= quota:
                break

    rows: list[dict[str, Any]] = []
    for idx, (source, parsed, _lang, gold) in enumerate(selected):
        rows.append(make_row(source, parsed, gold_value=gold, variant=f"v{idx:03d}"))

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        reasons = []
        if row["row_id"] in seen_ids:
            reasons.append("duplicate_row_id")
        seen_ids.add(row["row_id"])
        if prompt_prefix_has_role_leak(row):
            reasons.append("role_name_before_options")
        opts = (row.get("standalone_projection_source") or {}).get("opaque_options") or []
        if len(opts) < 4:
            reasons.append("too_few_options")
        values = {opt.get("value") for opt in opts if isinstance(opt, dict)}
        if len(values) != len(opts):
            reasons.append("duplicate_option_values")
        if (row.get("standalone_projection_source") or {}).get("gold_label") != row.get("target_text"):
            reasons.append("target_label_mismatch")
        if reasons:
            bad = dict(row)
            bad["block_reasons"] = reasons
            blocked.append(bad)
        else:
            admitted.append(row)

    write_jsonl(ROWS_JSONL, rows)
    write_jsonl(ADMITTED_JSONL, admitted)
    write_jsonl(BLOCKED_JSONL, blocked)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": len(admitted) >= 40 and not blocked,
        "decision": "fresh_verifier_constraint_support_admitted" if len(admitted) >= 40 and not blocked else "fresh_verifier_constraint_support_incomplete_or_blocked",
        "metrics": {
            "retrieval_rows_scanned": len(retrieval_rows),
            "candidate_roots_after_exclusions": len(candidates),
            "materialized_rows": len(rows),
            "admitted_rows": len(admitted),
            "blocked_rows": len(blocked),
            "admitted_unique_roots": len({row.get("root_id") for row in admitted}),
            "admitted_unique_repos": len({row.get("repo_family") for row in admitted}),
            "admitted_by_language": dict(Counter(row.get("language_family") for row in admitted)),
            "admitted_by_gold_value": dict(Counter((row.get("standalone_projection_source") or {}).get("gold_value") for row in admitted)),
            "selected_quota_counts": {f"{k[0]}::{k[1]}": v for k, v in counts.items()},
            "excluded_existing_repo_families": len(used_repos),
            "excluded_existing_roots": len(used_roots),
        },
        "source_artifacts": {
            "retrieval_rows": rel(RETRIEVAL_ROWS),
            "current_train": rel(CURRENT_TRAIN),
            "current_validation": rel(CURRENT_VALIDATION),
            "current_strict": rel(CURRENT_STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "all_rows_jsonl": rel(ROWS_JSONL),
            "admitted_rows_jsonl": rel(ADMITTED_JSONL),
            "blocked_rows_jsonl": rel(BLOCKED_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
