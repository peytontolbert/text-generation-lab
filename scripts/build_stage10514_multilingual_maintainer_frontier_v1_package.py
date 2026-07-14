from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10514
NAME = "stage10514_multilingual_maintainer_frontier_v1_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

PACKAGE_JSON = OUT_DIR / "multilingual_maintainer_frontier_v1_package.json"
ROWS_JSONL = OUT_DIR / "multilingual_maintainer_frontier_v1_rows.jsonl"
TRAIN_SUPPORT_JSONL = OUT_DIR / "bootstrap_train_support_rows.jsonl"
VALIDATION_SEED_JSONL = OUT_DIR / "bootstrap_validation_seed_rows.jsonl"
DIAGNOSTIC_JSONL = OUT_DIR / "diagnostic_support_only_rows.jsonl"
LEGACY_REFERENCE_JSONL = OUT_DIR / "legacy_reviewed_eval_reference_rows.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

V27_PACKAGE = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
V27_ROWS = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_bounded_rows.jsonl"
PYTHON_SEEDS = ROOT / "runs/local/artifacts/stage10512_python_verifier_bvc_frontier_materializer/python_verifier_bvc_seed_manifest.jsonl"
RUST_SEEDS = ROOT / "runs/local/artifacts/stage10513_rust_citation_ef_frontier_materializer/rust_citation_ef_seed_manifest.jsonl"
RUST_DIAGNOSTIC = ROOT / "runs/local/artifacts/stage10513_rust_citation_ef_frontier_materializer/rust_citation_ef_diagnostic_seed_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def package_role_for_seed_split(split: str) -> str:
    if split == "train_support":
        return "bootstrap_train_support"
    if split == "train_support_geometry_rebuild":
        return "bootstrap_train_support_geometry_rebuild"
    if split == "validation_seed_abstention_heavy":
        return "bootstrap_validation_seed_abstention_heavy"
    return "bootstrap_support_other"


def annotate_legacy_reference(row: dict[str, Any]) -> dict[str, Any]:
    tagged = dict(row)
    if tagged.get("objective_family") == "bounded_decoder_ce" and tagged.get("target_family") is None:
        tagged["target_family"] = "bounded_decision"
    tagged.setdefault("target_subtype", tagged.get("task_type", "bounded_choice"))
    tagged["package_stage"] = STAGE
    tagged["package_name"] = NAME
    tagged["package_role"] = "legacy_reviewed_eval_reference"
    tagged["claim_role"] = "historical_reviewed_reference_only"
    tagged["bootstrap_family"] = "legacy_reviewed_v27"
    tagged["fresh_multilingual_heldout_admissible"] = False
    tagged["package_split"] = f"legacy_{row.get('split', 'unknown')}"
    tagged["package_notes"] = [
        "Carried forward from the reviewed v2.7 bounded package.",
        "Useful as a regression and reference slice for C/C++ and Web only.",
        "Not a fresh multilingual heldout frontier for promotion claims.",
    ]
    return tagged


def annotate_seed_row(row: dict[str, Any], *, diagnostic_only: bool = False) -> dict[str, Any]:
    tagged = dict(row)
    split = row.get("split", "unknown")
    if diagnostic_only:
        row_id = str(tagged.get("row_id", ""))
        source_bundle_id = str(tagged.get("source_bundle_id", ""))
        tagged.setdefault("episode_id", source_bundle_id or row_id)
        tagged.setdefault("root_lineage_key", source_bundle_id or row_id)
        tagged.setdefault("source_family_id", "stage10513_rust_diagnostic_seed")
        tagged.setdefault("repo_id", "candle")
        tagged.setdefault("repo_family", "candle")
        tagged.setdefault("language_family", "rust")
        tagged.setdefault("task_type", "evidence_citation" if "::evidence_citation::" in row_id else "unknown")
        tagged.setdefault("target_family", "bounded_decision")
        tagged.setdefault("target_subtype", "visible_evidence_key")
        tagged.setdefault("anti_cheat", {"prompt_target_leak": False, "source_heldout_admissible": False})
    tagged["package_stage"] = STAGE
    tagged["package_name"] = NAME
    tagged["package_role"] = "diagnostic_support_only" if diagnostic_only else package_role_for_seed_split(split)
    tagged["claim_role"] = "bootstrap_seed_only"
    tagged["bootstrap_family"] = "diagnostic_seed" if diagnostic_only else "reviewed_seq2seq_seed"
    tagged["fresh_multilingual_heldout_admissible"] = False
    tagged["package_split"] = tagged["package_role"]
    notes = [
        "Bootstrap seq2seq seed row for frontier expansion.",
        "Not a promotable multilingual heldout evaluation row.",
    ]
    if diagnostic_only:
        notes.append("Diagnostic-only support from prior Rust citation inventory.")
    elif split == "train_support_geometry_rebuild":
        notes.append("Geometry-rebuild support only; do not use as evidence of heldout capability.")
    elif split == "validation_seed_abstention_heavy":
        notes.append("Reviewed Rust seed is abstention-heavy and should support honesty/robustness work.")
    tagged["package_notes"] = notes
    return tagged


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    v27_package = load_json(V27_PACKAGE)
    v27_rows = load_jsonl(V27_ROWS)
    python_seed_rows = load_jsonl(PYTHON_SEEDS)
    rust_seed_rows = load_jsonl(RUST_SEEDS)
    rust_diagnostic_rows = load_jsonl(RUST_DIAGNOSTIC)

    legacy_reference_rows = [
        annotate_legacy_reference(row)
        for row in v27_rows
        if row.get("language_family") in {"c_cpp", "web_js_ts_html"}
    ]
    python_rows = [annotate_seed_row(row) for row in python_seed_rows]
    rust_rows = [annotate_seed_row(row) for row in rust_seed_rows]
    rust_diagnostic_tagged = [annotate_seed_row(row, diagnostic_only=True) for row in rust_diagnostic_rows]

    all_rows = legacy_reference_rows + python_rows + rust_rows + rust_diagnostic_tagged

    train_support_rows = [
        row for row in all_rows
        if row["package_role"] in {"bootstrap_train_support", "bootstrap_train_support_geometry_rebuild"}
    ]
    validation_seed_rows = [
        row for row in all_rows
        if row["package_role"] == "bootstrap_validation_seed_abstention_heavy"
    ]
    diagnostic_rows = [row for row in all_rows if row["package_role"] == "diagnostic_support_only"]

    metrics = {
        "total_rows": len(all_rows),
        "legacy_reviewed_eval_reference_rows": len(legacy_reference_rows),
        "bootstrap_train_support_rows": len(train_support_rows),
        "bootstrap_validation_seed_rows": len(validation_seed_rows),
        "diagnostic_support_only_rows": len(diagnostic_rows),
        "rows_by_language": dict(sorted(Counter((row.get("language_family") or "unknown") for row in all_rows).items())),
        "rows_by_package_role": dict(sorted(Counter((row.get("package_role") or "unknown") for row in all_rows).items())),
        "rows_by_target_family": dict(sorted(Counter((row.get("target_family") or "unknown") for row in all_rows).items())),
        "rows_by_repo": dict(sorted(Counter((row.get("repo_id") or "unknown") for row in all_rows).items())),
        "rows_by_original_split": dict(sorted(Counter((row.get("split") or "unknown") for row in all_rows).items())),
        "legacy_reference_languages": dict(sorted(Counter((row.get("language_family") or "unknown") for row in legacy_reference_rows).items())),
        "bootstrap_seed_languages": dict(sorted(Counter((row.get("language_family") or "unknown") for row in python_rows + rust_rows).items())),
        "diagnostic_languages": dict(sorted(Counter((row.get("language_family") or "unknown") for row in diagnostic_rows).items())),
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_boundary": [
            "This package is a multilingual bootstrap package, not a promotable fresh heldout benchmark.",
            "C/C++ and Web rows are carried forward as legacy reviewed eval references from stage10420.",
            "Python rows are bootstrap verifier seeds from stage10512, including geometry-rebuild-only support.",
            "Rust rows are bootstrap citation seeds from stage10513 plus diagnostic-only candle-core support.",
            "No fresh multilingual 100M-vs-Gemma claim should be made from this package alone.",
        ],
        "source_artifacts": {
            "legacy_reviewed_v27_package": str(V27_PACKAGE.relative_to(ROOT)),
            "legacy_reviewed_v27_rows": str(V27_ROWS.relative_to(ROOT)),
            "python_seed_manifest": str(PYTHON_SEEDS.relative_to(ROOT)),
            "rust_seed_manifest": str(RUST_SEEDS.relative_to(ROOT)),
            "rust_diagnostic_rows": str(RUST_DIAGNOSTIC.relative_to(ROOT)),
        },
        "package_roles": {
            "legacy_reviewed_eval_reference": "Historical reviewed bounded rows retained for C/C++ and Web regression/reference use.",
            "bootstrap_train_support": "Fresh Python support seeds that are trainable but not promotable.",
            "bootstrap_train_support_geometry_rebuild": "Fresh Python geometry-rebuild seeds that should remain support-only.",
            "bootstrap_validation_seed_abstention_heavy": "Fresh reviewed Rust seed rows with abstention-heavy evaluation semantics.",
            "diagnostic_support_only": "Diagnostic-only Rust citation rows that should not enter any promotable claim path.",
        },
        "metrics": metrics,
        "lineage_notes": {
            "legacy_reference_origin": v27_package.get("stage_name"),
            "legacy_reference_boundary": "C/C++ and Web only",
            "python_bootstrap_origin": "stage10512_python_verifier_bvc_frontier_materializer",
            "rust_bootstrap_origin": "stage10513_rust_citation_ef_frontier_materializer",
        },
        "next_best_step": (
            "Use this package as a bootstrap training/reference substrate while building fresh multilingual heldout roots. "
            "Do not run a promotion-style Gemma comparison until Python and Rust have true fresh heldout rows and C/C++/Web "
            "are no longer relying on legacy reviewed reference carryover."
        ),
        "outputs": {
            "all_rows": str(ROWS_JSONL.relative_to(ROOT)),
            "train_support_rows": str(TRAIN_SUPPORT_JSONL.relative_to(ROOT)),
            "validation_seed_rows": str(VALIDATION_SEED_JSONL.relative_to(ROOT)),
            "diagnostic_rows": str(DIAGNOSTIC_JSONL.relative_to(ROOT)),
            "legacy_reference_rows": str(LEGACY_REFERENCE_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(ROWS_JSONL, all_rows)
    write_jsonl(TRAIN_SUPPORT_JSONL, train_support_rows)
    write_jsonl(VALIDATION_SEED_JSONL, validation_seed_rows)
    write_jsonl(DIAGNOSTIC_JSONL, diagnostic_rows)
    write_jsonl(LEGACY_REFERENCE_JSONL, legacy_reference_rows)
    write_json(PACKAGE_JSON, payload)
    write_json(SUMMARY_JSON, payload)


if __name__ == "__main__":
    main()
