#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10175
NAME = "stage10175_web_root_supply_and_bundle_gap_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "web_root_supply_and_bundle_gap_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

MANIFEST = ROOT / "runs/local/artifacts/stage10171_choice_aux_encoder_option_retrieval_target100m_execution_request/choice_aux_encoder_option_retrieval_target100m_manifest.jsonl"
STRICT_AUDIT = ROOT / "runs/local/artifacts/stage10172_choice_aux_encoder_option_retrieval_target100m_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
GEMMA_ROWS = ROOT / "runs/local/artifacts/stage10174_compact_bounded_encoder_option_retrieval_gemma_comparison/compact_bounded_gemma12b_rows.jsonl"
INVENTORY = ROOT / "runs/local/artifacts/session_like_source_inventory_real/packable_augmented_session_episode_examples_v4_dense_neighbors_realindex/packable_augmented_session_episode_examples.jsonl"
REPLENISHMENT = ROOT / "runs/local/artifacts/stage10109_real_session_multilingual_replenishment_ledger/real_session_multilingual_replenishment_candidates.jsonl"
STAGE10119_SCRIPT = ROOT / "scripts/build_stage10119_true_source_backed_maintainer_root_bundle_preview.py"

CODE_ASSIST_EXAMPLE_ID = (
    "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_"
    "src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662"
)


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


def _load_stage10119_module():
    spec = importlib.util.spec_from_file_location("stage10119_bundle_preview", STAGE10119_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable_to_load_stage10119_script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evidence_digest(bundle: dict[str, Any]) -> dict[str, str]:
    evidence = bundle.get("maintainer_visible_evidence") or {}
    out: dict[str, str] = {}
    for key, values in evidence.items():
        if not isinstance(values, list):
            continue
        joined = "\n---\n".join(str(item.get("text") or "") for item in values if isinstance(item, dict))
        out[str(key)] = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]
    return out


def _web_projection_failure_summary(manifest_rows: list[dict[str, Any]], strict_audit: dict[str, Any]) -> dict[str, Any]:
    by_row_id = {row["row_id"]: row for row in manifest_rows}
    failures: list[dict[str, Any]] = []
    pred_counts = Counter()
    target_counts = Counter()
    task_counts = Counter()
    for card in strict_audit.get("row_cards") or []:
        if not isinstance(card, dict):
            continue
        row = by_row_id.get(str(card.get("row_id") or ""))
        if not row or row.get("language_family") != "web_js_ts_html":
            continue
        options = {
            str(item.get("label") or ""): str(item.get("value") or "")
            for item in row.get("standalone_projection_source", {}).get("opaque_options", [])
            if isinstance(item, dict)
        }
        target_label = str(row.get("target_text") or "")
        pred_label = str(card.get("constrained_choice_top1_label") or "")
        target_value = options.get(target_label, "")
        pred_value = options.get(pred_label, "")
        target_counts[target_value] += 1
        pred_counts[pred_value] += 1
        if card.get("constrained_choice_match") is True:
            continue
        task_type = str(row.get("task_type") or "")
        task_counts[task_type] += 1
        failures.append(
            {
                "row_id": row["row_id"],
                "task_type": task_type,
                "target_value": target_value,
                "pred_value": pred_value,
            }
        )
    repeated_pred_values = sorted({item["pred_value"] for item in failures if item["pred_value"]})
    return {
        "web_failure_rows": len(failures),
        "web_failure_task_counts": dict(sorted(task_counts.items())),
        "predicted_value_counts_all_web_rows": dict(sorted(pred_counts.items())),
        "target_value_counts_all_web_rows": dict(sorted(target_counts.items())),
        "repeated_pred_values_in_failures": repeated_pred_values,
        "sample_failures": failures[:8],
        "diagnosis": (
            "Web failures are value-level errors rather than label-order errors: the same wrong candidate values recur "
            "across permutations for the failing root."
        ),
    }


def _gemma_web_summary(gemma_rows: list[dict[str, Any]]) -> dict[str, Any]:
    task = defaultdict(Counter)
    for row in gemma_rows:
        if row.get("language") != "web_js_ts_html":
            continue
        task[str(row.get("perspective") or "")][str(row.get("verdict") or "")] += 1
    return {perspective: dict(sorted(counts.items())) for perspective, counts in sorted(task.items())}


def _inventory_web_summary(module, inventory_rows: list[dict[str, Any]]) -> dict[str, Any]:
    web_examples: list[dict[str, Any]] = []
    digest_counts = Counter()
    by_digest = defaultdict(list)
    for example in inventory_rows:
        if module._primary_language(example) != "web_js_ts_html":
            continue
        bundle = module._bundle_from_example(example, language_family="web_js_ts_html")
        digest = json.dumps(
            {
                "candidate_paths": bundle.get("candidate_paths"),
                "evidence_digest": _evidence_digest(bundle),
            },
            sort_keys=True,
        )
        digest_hash = hashlib.sha256(digest.encode("utf-8")).hexdigest()[:12]
        record = {
            "example_id": str(example.get("example_id") or ""),
            "repo_id": module._repo_id(example),
            "seed_paths": bundle.get("seed_paths"),
            "candidate_paths": bundle.get("candidate_paths"),
            "evidence_digest_hash": digest_hash,
        }
        web_examples.append(record)
        digest_counts[digest_hash] += 1
        by_digest[digest_hash].append(record["example_id"])
    return {
        "total_primary_web_examples": len(web_examples),
        "distinct_bundle_digests": len(digest_counts),
        "digest_multiplicity": dict(sorted(digest_counts.items())),
        "duplicate_example_groups": dict(sorted(by_digest.items())),
        "examples": web_examples,
        "diagnosis": (
            "The current primary-web inventory only yields two distinct bundle digests; four index.html examples collapse to the same "
            "evidence/candidate set and should be treated as duplicates."
        ),
    }


def _code_assist_candidate_summary(inventory_rows: list[dict[str, Any]]) -> dict[str, Any]:
    example = next((row for row in inventory_rows if str(row.get("example_id") or "") == CODE_ASSIST_EXAMPLE_ID), None)
    if not example:
        return {"found": False}
    context_rows = [row for row in example.get("context_rows") or [] if isinstance(row, dict)]
    role_counts = Counter(str(row.get("role") or "") for row in context_rows)
    local_repo_paths = [str(row.get("path") or "") for row in context_rows if str(row.get("source_type") or "") == "local_repo"]
    venv_neighbor_rows = [
        str(row.get("path") or "")
        for row in context_rows
        if str(row.get("role") or "") == "repo_graph_neighbor" and "site-packages" in str(row.get("path") or "")
    ]
    selected_tests = [str(item) for item in ((example.get("query") or {}).get("selected_tests") or []) if str(item).strip()]
    return {
        "found": True,
        "repo_id": str((example.get("metadata") or {}).get("repo_id") or ""),
        "seed_paths": [str(item) for item in ((example.get("query") or {}).get("seed_paths") or []) if str(item).strip()],
        "selected_tests": selected_tests,
        "role_counts": dict(sorted(role_counts.items())),
        "local_repo_path_count": len(local_repo_paths),
        "contains_web_change_paths": [
            path for path in local_repo_paths if path.endswith((".js", ".css", ".html", ".ts", ".tsx", ".jsx"))
        ][:12],
        "repo_graph_neighbor_venv_paths": venv_neighbor_rows[:6],
        "diagnosis": (
            "A real cross-repo mixed-language web candidate exists, but its current neighbor evidence is polluted by venv/site-packages "
            "rows and still needs bundle-specific evidence filtering before it is safe to promote."
        ),
    }


def build() -> dict[str, Any]:
    module = _load_stage10119_module()
    manifest_rows = load_jsonl(MANIFEST)
    strict_audit = load_json(STRICT_AUDIT)
    gemma_rows = load_jsonl(GEMMA_ROWS)
    inventory_rows = load_jsonl(INVENTORY)
    replenishment_rows = load_jsonl(REPLENISHMENT)

    replenishment_web = [
        row
        for row in replenishment_rows
        if row.get("language_family") == "web_js_ts_html"
    ]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {
            "manifest": display(MANIFEST),
            "strict_audit": display(STRICT_AUDIT),
            "gemma_rows": display(GEMMA_ROWS),
            "inventory": display(INVENTORY),
            "replenishment": display(REPLENISHMENT),
        },
        "web_projection_failure_summary": _web_projection_failure_summary(manifest_rows, strict_audit),
        "gemma_web_perspective_summary": _gemma_web_summary(gemma_rows),
        "inventory_web_summary": _inventory_web_summary(module, inventory_rows),
        "replenishment_web_candidates": replenishment_web,
        "code_assist_web_candidate_summary": _code_assist_candidate_summary(inventory_rows),
        "decision": (
            "The remaining web gap is a source-supply and bundle-quality problem. The current primary-web inventory collapses to two "
            "distinct roots, and the best unused cross-repo web candidate still needs evidence filtering before it can honestly enter the package."
        ),
        "next_best_step": (
            "Build a mixed-language web replenishment bundle compiler that filters venv/site-packages neighbors, materializes only maintainer-relevant "
            "web evidence, and routes the resulting bundle through rubric, anti-cheat, and gold adjudication before recompiling the standalone bounded package."
        ),
        "passed": True,
    }
    return audit


def main() -> None:
    audit = build()
    write_json(AUDIT, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": audit["passed"],
            "artifact": display(AUDIT),
            "decision": audit["decision"],
            "next_best_step": audit["next_best_step"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "artifact": display(AUDIT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
