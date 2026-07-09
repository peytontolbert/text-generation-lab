#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from collections import Counter, defaultdict

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9482
NAME = "stage9482_target_prefix_positive_repair_queue"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9479_episode_target_prefix_balance_manifest/episode_target_prefix_balance_manifest.jsonl"
SOURCE_AUDIT = ROOT / "runs/summaries/stage9481_episode_target_prefix_balance_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9482_target_prefix_positive_repair_queue"
QUEUE = OUT_DIR / "target_prefix_positive_repair_queue.jsonl"
CARD = OUT_DIR / "target_prefix_positive_repair_queue_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_PREFIX_POSITIVE_REPAIR_QUEUE_STAGE9482.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TARGET_LANGS = ["cpp", "python", "web_js_ts_html"]
MIN_POSITIVE_PER_LANG = 6


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def target_prefix_label(row: dict) -> bool:
    return bool(row["episode_transition"]["observation_t"].get("target_prefix_match"))


def prefix_family(row: dict) -> str:
    prefix = str(row["episode_transition"]["state_t"].get("active_generation_prefix_span", ""))
    words = prefix.split()
    return "_".join(words[:5]).lower() or "unknown_prefix"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(SOURCE_MANIFEST)
    source_audit = load_json(SOURCE_AUDIT)
    by_lang_label = Counter((row.get("language_family"), target_prefix_label(row)) for row in rows)
    negative_examples: dict[str, list[dict]] = defaultdict(list)
    positive_examples: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        lang = str(row.get("language_family"))
        if target_prefix_label(row):
            positive_examples[lang].append(row)
        else:
            negative_examples[lang].append(row)

    high_conf_wrong = source_audit.get("metrics", {}).get("high_confidence_wrong_rows", [])
    queue_rows: list[dict] = []
    template_plan = {
        "cpp": [
            ("cpp_positive_constant_value", "Select the small constant that preserves the", "Select the small constant that preserves the expected assertion behavior. Keep the value small"),
            ("cpp_positive_callable_endpoint", "Select the callable endpoint that the verified", "Select the callable endpoint that the verified patch operator should update. Use the repo"),
            ("cpp_positive_library_entry", "Choose the approved library entry needed by", "Choose the approved library entry needed by the wrapper plan. Keep the answer focused"),
            ("cpp_positive_symbol_path", "Emit the path reference linked to the", "Emit the path reference linked to the checked symbol evidence. Keep the decision compatible"),
            ("cpp_positive_dependency_handle", "Emit the dependency handle that keeps the", "Emit the dependency handle that keeps the patch inside the whitelist. Use the symbol"),
            ("cpp_positive_file_path", "Select the file path associated with the", "Select the file path associated with the localized edit target. Keep the path reference"),
        ],
        "python": [
            ("python_positive_constant_value", "Return the constant value required by the", "Return the constant value required by the checked verifier condition. Do not introduce an"),
            ("python_positive_file_path", "Select the file path associated with the", "Select the file path associated with the localized edit target. Keep the path reference"),
            ("python_positive_dependency_handle", "Emit the dependency handle that keeps the", "Emit the dependency handle that keeps the patch inside the whitelist. Use the symbol"),
            ("python_positive_callable_endpoint", "Select the callable endpoint that the verified", "Select the callable endpoint that the verified patch operator should update. Use the repo"),
            ("python_positive_library_entry", "Choose the approved library entry needed by", "Choose the approved library entry needed by the wrapper plan. Keep the answer focused"),
            ("python_positive_invariant_value", "Choose the concrete value tied to the", "Choose the concrete value tied to the current repair invariant. Do not introduce an"),
        ],
        "web_js_ts_html": [
            ("web_positive_invariant_value", "Choose the concrete value tied to the", "Choose the concrete value tied to the current repair invariant. Do not introduce an"),
            ("web_positive_dependency_handle", "Emit the dependency handle that keeps the", "Emit the dependency handle that keeps the patch inside the whitelist. Use the symbol"),
            ("web_positive_file_path", "Select the file path associated with the", "Select the file path associated with the localized edit target. Keep the path reference"),
            ("web_positive_callable_endpoint", "Select the callable endpoint that the verified", "Select the callable endpoint that the verified patch operator should update. Use the repo"),
            ("web_positive_library_entry", "Choose the approved library entry needed by", "Choose the approved library entry needed by the wrapper plan. Keep the answer focused"),
            ("web_positive_constant_value", "Return the constant value required by the", "Return the constant value required by the checked verifier condition. Do not introduce an"),
        ],
    }

    for lang in TARGET_LANGS:
        existing_positive = len(positive_examples.get(lang, []))
        needed = max(0, MIN_POSITIVE_PER_LANG - existing_positive)
        candidate_negatives = negative_examples.get(lang, [])
        for index, (task_kind, prefix, clean_output) in enumerate(template_plan[lang][:needed]):
            source_negative = candidate_negatives[index % len(candidate_negatives)]["row_id"] if candidate_negatives else None
            queue_rows.append(
                {
                    "queue_id": f"stage9482_{lang}_positive_target_prefix_{index:02d}",
                    "repair_type": "construct_positive_target_prefix_example",
                    "language_family": lang,
                    "desired_target_prefix_match": True,
                    "desired_boundary_next_token_match": True,
                    "task_kind": task_kind,
                    "active_generation_prefix_span": prefix,
                    "clean_generated_text": clean_output,
                    "clean_decoder_text": clean_output,
                    "source_negative_row_id": source_negative,
                    "minimal_discriminating_features": [
                        "observation.generated_text_starts_with_active_generation_prefix_span",
                        "observation.generated_text_equals_clean_decoder_text_or_verified_prefix",
                        "reward.failure_type_none",
                    ],
                    "forbidden_shortcuts": [
                        "target_prefix_match_visible_in_encoder_input",
                        "failure_type_visible_in_encoder_input_for_pre_action_policy",
                        "stage_or_queue_label_visible_as_model_feature",
                    ],
                    "materialization_requirements": {
                        "distinct_encoder_state_from_negative_source": True,
                        "authority_closed": True,
                        "decoder_ce_closed": True,
                        "denoise_ce_closed": True,
                        "runtime_reward_closed": True,
                        "loss_mask_only_episode_target_prefix_match_ce": True,
                    },
                    "authority": dict(AUTHORITY_CLOSED),
                }
            )

    write_jsonl(QUEUE, queue_rows)
    queue_by_lang = Counter(row["language_family"] for row in queue_rows)
    projected_positive_by_lang = {lang: by_lang_label.get((lang, True), 0) + queue_by_lang.get(lang, 0) for lang in TARGET_LANGS}
    failures: list[str] = []
    if not queue_rows:
        failures.append("empty_repair_queue")
    for lang in TARGET_LANGS:
        if projected_positive_by_lang.get(lang, 0) < MIN_POSITIVE_PER_LANG:
            failures.append(f"projected_positive_coverage_below_min:{lang}")
    if any(any(row.get("authority", {}).values()) for row in queue_rows):
        failures.append("authority_open_in_queue")
    if not high_conf_wrong:
        failures.append("source_stage9481_high_conf_wrong_missing")

    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "source_audit": str(SOURCE_AUDIT.relative_to(ROOT)),
        "queue": str(QUEUE.relative_to(ROOT)),
        "queue_rows": len(queue_rows),
        "target_languages": TARGET_LANGS,
        "minimum_positive_per_language": MIN_POSITIVE_PER_LANG,
        "existing_target_prefix_counts_by_language_label": {f"{lang}::{label}": count for (lang, label), count in sorted(by_lang_label.items(), key=lambda kv: str(kv[0]))},
        "queued_positive_rows_by_language": dict(sorted(queue_by_lang.items())),
        "projected_positive_rows_by_language": projected_positive_by_lang,
        "stage9481_high_confidence_wrong_rows": high_conf_wrong,
        "diagnosis": "Stage9481 failed on a high-confidence CPP positive target-prefix row. Python and web have zero positive target-prefix rows, and CPP has only two. Queue constructs distinct positive target-prefix examples for CPP/Python/web before another probe.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    authority = dict(AUTHORITY_CLOSED)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": authority,
        "metrics": {**authority, **card},
        "artifacts": {"queue": str(QUEUE.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Queued language-balanced positive target-prefix repairs for CPP, Python, and web after Stage9481 isolated sparse non-Rust positive coverage.",
        "next_best_step": "Materialize Stage9483 target-prefix positive repair manifest from the Stage9482 queue with distinct encoder states and only episode_target_prefix_match_ce enabled.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9482 Target-Prefix Positive Repair Queue",
        "",
        f"Passed: `{card['passed']}`",
        f"Queue rows: `{len(queue_rows)}`",
        f"Existing target-prefix counts: `{card['existing_target_prefix_counts_by_language_label']}`",
        f"Queued positives by language: `{card['queued_positive_rows_by_language']}`",
        f"Projected positives by language: `{projected_positive_by_lang}`",
        "",
        card["diagnosis"],
        "",
        "This is a data repair queue only. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "queue_rows": len(queue_rows), "queued_positive_rows_by_language": dict(queue_by_lang)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
