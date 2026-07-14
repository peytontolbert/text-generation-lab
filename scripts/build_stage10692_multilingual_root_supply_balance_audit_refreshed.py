#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10692
NAME = "stage10692_multilingual_root_supply_balance_audit_refreshed"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "multilingual_root_supply_balance_audit_refreshed.json"
BALANCE_JSONL = OUT_DIR / "language_supply_balance_rows_refreshed.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10691_root_admission_manifest_v2/root_admission_manifest_v2.json"
ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10691_root_admission_manifest_v2/root_admission_manifest_v2.jsonl"
SCALE_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"
LATEST_REVIEWED_PACKAGE = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_support_package.json"
LATEST_PROBE_AUDIT = ROOT / "runs/local/artifacts/stage10690_reviewed_v27_plus_two_fresh_rust_probe_audit/reviewed_v27_plus_two_fresh_rust_probe_audit.json"
HELDOUT_AUDIT = ROOT / "runs/local/artifacts/stage10522_multitarget_bootstrap_eval_hacking_audit_with_heldout/multitarget_bootstrap_eval_hacking_audit_with_heldout.json"

TARGET_LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def top_repo_families(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    counts = Counter(str(row.get("repo_family") or "unknown") for row in rows)
    return [{"repo_family": repo, "roots": count} for repo, count in counts.most_common(limit)]


def quality_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    scores = sorted(float(row.get("quality_score") or 0.0) for row in rows)
    n = len(scores)
    return {
        "rows": n,
        "min": scores[0],
        "p50": scores[n // 2],
        "p90": scores[min(n - 1, int(n * 0.9))],
        "max": scores[-1],
        "mean": round(sum(scores) / n, 4),
    }


def main() -> None:
    admission_summary = load_json(ADMISSION_SUMMARY)
    admission_rows = load_jsonl(ADMISSION_ROWS)
    scale_contract = load_json(SCALE_CONTRACT)
    latest_reviewed_package = load_json(LATEST_REVIEWED_PACKAGE)
    latest_probe_audit = load_json(LATEST_PROBE_AUDIT)
    heldout_audit = load_json(HELDOUT_AUDIT)

    language_rows: list[dict[str, Any]] = []
    for language in TARGET_LANGS:
        rows = [row for row in admission_rows if str(row.get("language_family") or "") == language]
        train_rows = [row for row in rows if str(row.get("admit_role") or "") == "train"]
        validation_rows = [row for row in rows if str(row.get("admit_role") or "") == "validation"]
        strict_rows = [row for row in rows if str(row.get("admit_role") or "") == "strict_eval"]
        diagnostic_rows = [row for row in rows if str(row.get("admit_role") or "") == "diagnostic"]
        quarantine_rows = [row for row in rows if str(row.get("admit_role") or "") == "quarantine"]
        reviewed_trainable = [row for row in train_rows if str(row.get("source_kind") or "") == "reviewed_bundle_root"]
        compiled_trainable = [row for row in train_rows if str(row.get("source_kind") or "") == "compiled_root_state"]
        quality_flags = next(
            (
                item.get("quality_flags")
                for item in (scale_contract.get("language_gaps") or [])
                if str(item.get("language_family") or "") == language
            ),
            [],
        )
        language_rows.append(
            {
                "language_family": language,
                "total_roots": len(rows),
                "train_roots": len(train_rows),
                "validation_roots": len(validation_rows),
                "strict_eval_roots": len(strict_rows),
                "diagnostic_roots": len(diagnostic_rows),
                "quarantine_roots": len(quarantine_rows),
                "reviewed_trainable_roots": len(reviewed_trainable),
                "compiled_trainable_roots": len(compiled_trainable),
                "train_repo_families": len({str(row.get("repo_family") or "") for row in train_rows}),
                "quarantine_repo_families": len({str(row.get("repo_family") or "") for row in quarantine_rows}),
                "train_top_repo_families": top_repo_families(train_rows, limit=5),
                "quarantine_top_repo_families": top_repo_families(quarantine_rows, limit=5),
                "train_quality": quality_stats(train_rows),
                "quarantine_quality": quality_stats(quarantine_rows),
                "quarantine_due_to_prompt_target_leak": sum(int(row.get("prompt_target_leak_rows") or 0) > 0 for row in quarantine_rows),
                "selected_test_anchor_train_roots": sum(bool(row.get("selected_test_anchor")) for row in train_rows),
                "verifier_anchor_train_roots": sum(bool(row.get("verifier_anchor")) for row in train_rows),
                "quality_flags": quality_flags,
            }
        )

    language_rows.sort(key=lambda row: row["language_family"])
    write_jsonl(BALANCE_JSONL, language_rows)

    train_rows_all = [row for row in admission_rows if str(row.get("admit_role") or "") == "train"]
    quarantine_rows_all = [row for row in admission_rows if str(row.get("admit_role") or "") == "quarantine"]
    repo_caps_needed = [
        {
            "language_family": row["language_family"],
            "repo_family": row["train_top_repo_families"][0]["repo_family"],
            "roots": row["train_top_repo_families"][0]["roots"],
        }
        for row in language_rows
        if row["train_top_repo_families"]
    ]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_supply_audited_refreshed",
        "claim_scope": [
            "Refresh the multilingual supply balance audit after adding two new reviewed Rust train-support roots.",
            "Keep the latest standalone strict frontier state explicit: the Rust supply increased but the 24-row frontier remained at 22/24.",
            "This remains a scaling and anti-cheat planning artifact, not a new model headline.",
        ],
        "source_artifacts": {
            "root_admission_summary": display(ADMISSION_SUMMARY),
            "root_admission_manifest": display(ADMISSION_ROWS),
            "scale_contract": display(SCALE_CONTRACT),
            "latest_reviewed_package": display(LATEST_REVIEWED_PACKAGE),
            "latest_probe_audit": display(LATEST_PROBE_AUDIT),
            "heldout_bootstrap_audit": display(HELDOUT_AUDIT),
        },
        "global_supply": {
            "roots_total": len(admission_rows),
            "role_counts": dict(sorted(Counter(str(row.get("admit_role") or "unknown") for row in admission_rows).items())),
            "train_repo_families_total": len({str(row.get("repo_family") or "") for row in train_rows_all}),
            "quarantine_repo_families_total": len({str(row.get("repo_family") or "") for row in quarantine_rows_all}),
            "quarantine_prompt_target_leak_roots": sum(int(row.get("prompt_target_leak_rows") or 0) > 0 for row in quarantine_rows_all),
            "reviewed_v27_plus_two_fresh_rust_train_rows": ((latest_reviewed_package.get("metrics") or {}).get("train_rows")),
            "bootstrap_heldout_rows": ((heldout_audit.get("global_findings") or {}).get("strict_rows_total")),
            "latest_strict_frontier_accuracy": ((latest_probe_audit.get("strict_eval_result") or {}).get("constrained_choice_top1_accuracy")),
        },
        "language_supply": language_rows,
        "dominance_and_gap_findings": {
            "repo_caps_needed": repo_caps_needed,
            "languages_with_single_train_root": [row["language_family"] for row in language_rows if row["train_roots"] <= 1],
            "languages_with_zero_compiled_trainable_roots": [row["language_family"] for row in language_rows if row["compiled_trainable_roots"] == 0],
            "languages_where_quarantine_exceeds_train_by_10x": [
                row["language_family"]
                for row in language_rows
                if row["quarantine_roots"] >= max(row["train_roots"] * 10, 10)
            ],
        },
        "headline_findings": [
            "The refreshed next training package can now draw from more reviewed Rust train roots than the earlier scale audit reflected.",
            "Most long-context scale is still blocked by prompt-target leakage and missing candidate contracts, not by raw source availability alone.",
            "Python remains the dominant trainable language and still needs repo-family caps before any large-scale package is honest.",
            "Rust supply improved, but the unchanged 22/24 frontier confirms that adding support roots alone is not sufficient without closer residual geometry or better interface contracts.",
        ],
        "required_next_actions": [
            "Use reviewed train-support Rust roots as support inventory, but stop expecting same-size support-only probes to lift the strict frontier by themselves.",
            "Prioritize interface rewrites that convert quarantined bootstrap roots into leak-clean candidate-contract rows.",
            "Add repo-family caps before building the next multilingual training package so Python and agentkernel-like families cannot dominate.",
            "Reserve fresh heldout roots per language before counting rewritten roots toward scale progress.",
        ],
        "recommended_next_stage": "stage10617_reviewed_plus_bootstrap_multilingual_training_package_fixed",
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "language_balance_rows": display(BALANCE_JSONL),
        },
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": audit["decision"],
            "audit": display(AUDIT_JSON),
            "rows": len(language_rows),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
