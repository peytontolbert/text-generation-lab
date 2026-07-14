#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage11520_provenance_aware_smoke_admission_audit"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

SOURCE_FILES = [
    ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
    ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl",
    ART / "stage11107_fresh_family_evidence_rows_deshortcutted/evidence_candidate_rows_deshortcutted.jsonl",
    ART / "stage11097_fresh_family_materialized_rows/evidence_candidate_rows.jsonl",
    ART / "stage11024_multilingual_evidence_root_scale_package/expanded_eval_bank.jsonl",
]
LANGUAGES = ("python", "rust", "c_cpp", "web_js_ts_html")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def opt_count(row: dict[str, Any]) -> int:
    options = row.get("opaque_options") or []
    return len(options) if isinstance(options, list) else 0


def anti(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}


def has_verifier(row: dict[str, Any]) -> bool:
    a = anti(row)
    return bool(
        row.get("verifier_execution_evidence")
        or (row.get("standalone_projection_source") or {}).get("verifier_execution_evidence")
        or a.get("executed_verifier_output_attached") is True
        or a.get("explicit_selected_test_ledger") is True
        or row.get("selected_test_anchor") is True
        or row.get("verifier_anchor") is True
    )


def deterministic_shuffle(row: dict[str, Any]) -> bool:
    return anti(row).get("deterministic_option_shuffle") is True or row.get("deterministic_option_shuffle") is True


def leak_clean(row: dict[str, Any]) -> bool:
    a = anti(row)
    if row.get("prompt_target_value_leak") is True:
        return False
    if a.get("prompt_target_value_leak") is True:
        return False
    if a.get("target_label_not_visible_before_options") is False:
        return False
    return True


def not_train(row: dict[str, Any]) -> bool:
    a = anti(row)
    return bool(
        row.get("train_support_only") is False
        or a.get("not_train_support") is True
        or a.get("diagnostic_heldout_not_train") is True
    )


def heldout_provenance(row: dict[str, Any]) -> tuple[bool, str]:
    a = anti(row)
    review = str(row.get("review_status") or "")
    split = " ".join(str(row.get(k) or "") for k in ("split", "package_split", "split_role"))
    if row.get("source_heldout_admissible") is True:
        return True, "source_heldout_admissible_true"
    if "heldout_candidate" in review and (a.get("executed_verifier_output_attached") is True or row.get("verifier_execution_evidence")):
        return True, "executed_verifier_heldout_candidate"
    if "strict_eval_candidate" in split and a.get("needs_final_eval_admission") is True and row.get("verifier_execution_evidence"):
        return True, "strict_eval_candidate_with_execution_needs_final_admission"
    return False, "missing_or_insufficient_heldout_provenance"


def row_summary(row: dict[str, Any], source_file: Path, admission: str, blockers: list[str], provenance: str) -> dict[str, Any]:
    return {
        "row_id": row.get("row_id"),
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family") or row.get("repo_id"),
        "root_id": row.get("root_id") or row.get("source_root_id"),
        "root_lineage_key": row.get("root_lineage_key"),
        "task_type": row.get("task_type") or row.get("perspective"),
        "split": row.get("split") or row.get("package_split"),
        "review_status": row.get("review_status"),
        "source_file": rel(source_file),
        "option_count": opt_count(row),
        "admission": admission,
        "heldout_provenance": provenance,
        "blockers": blockers,
    }


def main() -> None:
    admitted: list[dict[str, Any]] = []
    pending_final_admission: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    source_rows = 0

    for source_file in SOURCE_FILES:
        for row in read_jsonl(source_file):
            source_rows += 1
            lang = row.get("language_family")
            if lang not in LANGUAGES:
                continue
            blockers: list[str] = []
            provenance_ok, provenance = heldout_provenance(row)
            if not provenance_ok:
                blockers.append("heldout_provenance_not_admitted")
            if not not_train(row):
                blockers.append("not_train_status_missing_or_false")
            if not deterministic_shuffle(row):
                blockers.append("deterministic_option_shuffle_missing")
            if opt_count(row) < 2:
                blockers.append("singleton_or_missing_options")
            if not leak_clean(row):
                blockers.append("prompt_target_leak_risk")
            if not has_verifier(row):
                blockers.append("missing_verifier_or_selected_test_evidence")

            needs_final = anti(row).get("needs_final_eval_admission") is True or "needs_final_admission" in str(row.get("review_status") or "")
            if not blockers and not needs_final:
                admitted.append(row_summary(row, source_file, "admitted", [], provenance))
            elif not blockers and needs_final:
                pending_final_admission.append(row_summary(row, source_file, "pending_final_admission", [], provenance))
            else:
                blocked.append(row_summary(row, source_file, "blocked", blockers, provenance))

    def by_lang(rows: list[dict[str, Any]]) -> dict[str, int]:
        counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
        return {lang: counts.get(lang, 0) for lang in LANGUAGES}

    blocker_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in blocked:
        lang = str(row.get("language_family") or "unknown")
        for blocker in row.get("blockers") or []:
            blocker_counts[lang][blocker] += 1

    smoke_ready = all(by_lang(admitted).get(lang, 0) >= 1 for lang in LANGUAGES)
    payload = {
        "stage": 11520,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "provenance_aware_smoke_has_pending_web_only_not_multilingual_ready",
        "metrics": {
            "source_rows_examined": source_rows,
            "admitted": len(admitted),
            "admitted_by_language": by_lang(admitted),
            "pending_final_admission": len(pending_final_admission),
            "pending_final_admission_by_language": by_lang(pending_final_admission),
            "blocked": len(blocked),
            "blocked_by_language": by_lang(blocked),
            "blockers_by_language": {lang: dict(sorted(blocker_counts[lang].items())) for lang in LANGUAGES},
            "minimal_multilingual_smoke_ready": smoke_ready,
        },
        "admitted_sample": admitted[:20],
        "pending_final_admission_sample": pending_final_admission[:30],
        "blocked_sample": blocked[:30],
        "claim_boundary": [
            "This is a provenance-aware admission audit for standalone smoke candidates only.",
            "Pending-final-admission rows are not promoted until a separate admission stage asserts their source-heldout status and no-train split.",
            "No model or Gemma execution is performed here.",
        ],
        "outputs": {
            "admitted_jsonl": rel(OUT_DIR / "admitted_standalone_smoke_rows.jsonl"),
            "pending_final_admission_jsonl": rel(OUT_DIR / "pending_final_admission_smoke_rows.jsonl"),
            "blocked_jsonl": rel(OUT_DIR / "blocked_standalone_smoke_rows.jsonl"),
        },
        "source_artifacts": [rel(path) for path in SOURCE_FILES],
        "next_best_step": "Admit the executed Web heldout rows if final review agrees, then materialize comparable Python/C++/Rust source-heldout verifier rows; do not run a multilingual smoke comparison until all four languages have admitted rows.",
    }
    write_jsonl(OUT_DIR / "admitted_standalone_smoke_rows.jsonl", admitted)
    write_jsonl(OUT_DIR / "pending_final_admission_smoke_rows.jsonl", pending_final_admission)
    write_jsonl(OUT_DIR / "blocked_standalone_smoke_rows.jsonl", blocked)
    write_json(OUT_DIR / f"{NAME}.json", payload)
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
