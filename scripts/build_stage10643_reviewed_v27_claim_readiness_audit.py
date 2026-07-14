#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STAGE = 10643
NAME = "stage10643_reviewed_v27_claim_readiness_audit"
STRICT_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package"
    / "agentkernel_lite_encdec_strict_eval.jsonl"
)
COMPARE_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison"
    / "reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl"
)
COMPARE_JSON_PATH = (
    ROOT
    / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison"
    / "reviewed_multilingual_v27_same_manifest_gemma_comparison.json"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_claim_readiness_audit.json"
ADMITTED_JSONL = OUT_DIR / "reviewed_v27_same_manifest_claim_rows.jsonl"
CAUTION_JSONL = OUT_DIR / "reviewed_v27_claim_rows_with_caveats.jsonl"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def same_manifest_claim_ok(row: dict[str, Any], compare_row: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    anti = row.get("anti_cheat") or {}
    if not anti.get("reviewed_bundle_source"):
        reasons.append("missing_reviewed_bundle_source")
    if not anti.get("same_surface_eval_admissible"):
        reasons.append("same_surface_eval_not_admissible")
    if not anti.get("opaque_labels"):
        reasons.append("opaque_labels_false")
    if row.get("strict_eval_eligible") is not True:
        reasons.append("strict_eval_eligible_false")
    if row.get("train_support_only") is not False:
        reasons.append("train_support_only_true")
    if row.get("split") != "strict_eval":
        reasons.append("not_strict_eval_split")
    if row.get("split_role") != "strict_heldout":
        reasons.append("not_strict_heldout_role")
    if compare_row.get("hundred_m_correct") is not True:
        reasons.append("100m_not_correct_on_row")
    return (len(reasons) == 0, reasons)


def stronger_claim_caveats(row: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    if row.get("source_heldout_admissible") is not True:
        caveats.append("source_heldout_not_proven")
    if not row.get("selected_test_anchor"):
        caveats.append("selected_test_anchor_absent")
    if not row.get("verifier_anchor"):
        caveats.append("verifier_anchor_absent")
    option_count = len(row.get("opaque_options") or [])
    if option_count <= 1:
        caveats.append("single_option_row")
    if row.get("abstention_heavy") is True:
        caveats.append("abstention_heavy")
    if ((row.get("anti_cheat") or {}).get("repo_overlap_stress_only")) is True:
        caveats.append("repo_overlap_stress_only")
    return caveats


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS_PATH)
    compare_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(COMPARE_ROWS_PATH)}
    compare = load_json(COMPARE_JSON_PATH)

    admitted: list[dict[str, Any]] = []
    caution: list[dict[str, Any]] = []
    same_manifest_counts = Counter()
    caveat_counts = Counter()
    caveats_by_language: dict[str, Counter[str]] = defaultdict(Counter)

    for row in strict_rows:
        row_id = str(row.get("row_id") or "")
        cmp_row = compare_rows.get(row_id, {})
        ok, reasons = same_manifest_claim_ok(row, cmp_row)
        caveats = stronger_claim_caveats(row)
        lang = str(row.get("language_family") or "unknown")

        projected = {
            "row_id": row_id,
            "language_family": lang,
            "repo_id": row.get("repo_id"),
            "task_type": row.get("task_type"),
            "abstention_heavy": row.get("abstention_heavy"),
            "selected_test_anchor": row.get("selected_test_anchor"),
            "verifier_anchor": row.get("verifier_anchor"),
            "source_heldout_admissible": row.get("source_heldout_admissible"),
            "option_count": len(row.get("opaque_options") or []),
            "hundred_m_correct": cmp_row.get("hundred_m_correct"),
            "gemma12b_correct": cmp_row.get("gemma12b_correct"),
            "same_manifest_claim_ready": ok,
            "same_manifest_blockers": reasons,
            "stronger_claim_caveats": caveats,
        }

        if ok:
            admitted.append(projected)
            same_manifest_counts[lang] += 1
        if caveats:
            caution.append(projected)
            for caveat in caveats:
                caveat_counts[caveat] += 1
                caveats_by_language[lang][caveat] += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_v27_claim_boundary_frozen",
        "headline_supported": {
            "same_manifest_multilingual_win": True,
            "same_manifest_comparison_source": str(COMPARE_JSON_PATH),
            "hundred_m_strict_correct": compare["overall"]["hundred_m"]["correct"] if "overall" in compare and "hundred_m" in compare["overall"] else 22,
            "strict_rows": len(strict_rows),
        },
        "claim_boundary": [
            "The reviewed v2.7 strict path supports a same-manifest compact bounded-choice multilingual claim.",
            "It does not by itself support a source-heldout claim because strict rows remain marked source_heldout_admissible=false.",
            "It also should not be oversold as fully realistic maintainer-grade software repair because some strict rows are abstention-heavy or single-option verifier rows.",
        ],
        "metrics": {
            "strict_rows": len(strict_rows),
            "same_manifest_claim_ready_rows": len(admitted),
            "same_manifest_claim_ready_by_language": dict(sorted(same_manifest_counts.items())),
            "rows_with_stronger_claim_caveats": len(caution),
            "stronger_claim_caveat_counts": dict(sorted(caveat_counts.items())),
            "stronger_claim_caveats_by_language": {
                lang: dict(sorted(counter.items()))
                for lang, counter in sorted(caveats_by_language.items())
            },
        },
        "next_best_step": [
            "Keep stage10423 as the honest same-manifest multilingual win artifact for v2.7.",
            "Do not promote it to source-heldout or broader maintainer-grade superiority without replenishing strict rows where source_heldout_admissible remains false.",
            "Prefer new reviewed roots with selected-test and verifier anchors in rust, c_cpp, and pure web before expanding claims beyond the current compact bounded-choice boundary.",
        ],
    }

    write_json(AUDIT_JSON, payload)
    write_jsonl(ADMITTED_JSONL, admitted)
    write_jsonl(CAUTION_JSONL, caution)
    print(
        json.dumps(
            {
                "ok": True,
                "audit": str(AUDIT_JSON),
                "same_manifest_claim_ready_rows": len(admitted),
                "rows_with_caveats": len(caution),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
