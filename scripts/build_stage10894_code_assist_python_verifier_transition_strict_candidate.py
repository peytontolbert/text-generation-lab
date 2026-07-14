#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10894
NAME = "stage10894_code_assist_python_verifier_transition_strict_candidate"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "code_assist_python_verifier_transition_strict_candidate.json"
ROW_JSONL = OUT_DIR / "strict_candidate_rows.jsonl"
BUNDLE_JSON = OUT_DIR / "strict_candidate_bundle.json"

SOURCE_BUNDLE_JSON = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10236__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662__python" / "fresh_python_bundle_preview.json"
SOURCE_GOLD_JSON = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10236__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662__python" / "perspective_gold_adjudication.json"
SOURCE_ANTI_CHEAT_JSON = ARTIFACTS / "stage10813_python_queue_aligned_admission" / "review_packets" / "stage10236__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662__python" / "anti_cheat_review_card.json"

TEST_ID_TO_TARGET = {
    "T1": {
        "source_path": "tests/integration/test_domain_knowledge_context_pack.py",
        "transition": "FAIL_TO_PASS",
        "focus": "compiled pack includes repository domain-knowledge evidence",
    },
    "T2": {
        "source_path": "tests/integration/test_incident_loop_in_context_pack.py",
        "transition": "FAIL_TO_PASS",
        "focus": "compiled pack carries incident artifact details into the task context",
    },
    "T3": {
        "source_path": "tests/integration/test_task_message_in_context_pack.py",
        "transition": "FAIL_TO_PASS",
        "focus": "compiled pack preserves user task-message content in chat history",
    },
    "T4": {
        "source_path": "tests/unit/test_context_pack_log_ref_path_safety.py",
        "transition": "FAIL_TO_PASS",
        "focus": "compiler ignores log references outside the artifacts directory",
    },
}
OPTION_LABELS = ["A", "B", "C", "D"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def short_text(text: str, limit: int = 340) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def evidence_snippets(bundle: dict[str, Any]) -> dict[str, list[str]]:
    evidence = bundle.get("maintainer_visible_evidence") or {}
    return {
        key: [short_text(item.get("text") or "") for item in values[:3] if isinstance(item, dict)]
        for key, values in evidence.items()
        if isinstance(values, list)
    }


def verifier_ledger() -> list[dict[str, str]]:
    return [
        {
            "test_id": test_id,
            "transition": meta["transition"],
            "focus": meta["focus"],
        }
        for test_id, meta in TEST_ID_TO_TARGET.items()
    ]


def prompt_text(bundle: dict[str, Any]) -> str:
    snippets = evidence_snippets(bundle)
    candidate_paths = list(bundle.get("candidate_paths") or [])
    lines = [
        "Language: python",
        "Perspective: verifier_outcome",
        "Task: Choose the most relevant verification target for the proposed compiler repair. The answer must identify which opaque verifier target is most directly expected to flip from FAIL to PASS if the best visible edit surface is repaired.",
        "Visible code candidates:",
    ]
    for idx, path in enumerate(candidate_paths, start=1):
        lines.append(f"P{idx}. {path}")
    lines.append("Evidence:")
    mapping = [
        ("candidate_change_surface", "E1"),
        ("nearby_definition_or_usage_context", "E2"),
        ("symptom_or_call_path_analogue", "E3"),
        ("verifier_and_test_constraint", "E4"),
    ]
    for key, eid in mapping:
        values = snippets.get(key) or []
        for i, value in enumerate(values, start=1):
            lines.append(f"{eid}.{i}: {value}")
    lines.append("Verifier target ledger:")
    for item in verifier_ledger():
        lines.append(f"{item['test_id']}: {item['transition']} | {item['focus']}")
    lines.append("Options:")
    for label, item in zip(OPTION_LABELS, verifier_ledger()):
        lines.append(f"{label}. {item['test_id']} | {item['transition']} | {item['focus']}")
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def main() -> None:
    bundle = load_json(SOURCE_BUNDLE_JSON)
    gold = load_json(SOURCE_GOLD_JSON)
    anti_cheat = load_json(SOURCE_ANTI_CHEAT_JSON)

    verifier_gold = None
    for answer in gold.get("perspective_gold_answers") or []:
        if answer.get("perspective") == "verifier_outcome":
            verifier_gold = answer
            break
    if verifier_gold is None:
        raise ValueError("missing verifier_outcome gold answer")

    gold_path = str(verifier_gold.get("gold_answer_value") or "")
    gold_test_id = None
    for test_id, meta in TEST_ID_TO_TARGET.items():
        if meta["source_path"] == gold_path:
            gold_test_id = test_id
            break
    if gold_test_id is None:
        raise ValueError(f"unmapped gold verifier path: {gold_path}")

    prompt = prompt_text(bundle)
    options = []
    target_label = None
    for label, item in zip(OPTION_LABELS, verifier_ledger()):
        value = f"{item['test_id']} | {item['transition']} | {item['focus']}"
        options.append({"label": label, "value": value})
        if item["test_id"] == gold_test_id:
            target_label = label
    if target_label is None:
        raise ValueError("failed to assign target label")

    row = {
        "anti_cheat": {
            "opaque_verifier_target_ids": True,
            "selected_test_paths_hidden_pre_options": True,
            "same_surface_eval_admissible": False,
            "strict_candidate_only": True,
            "source_packet_reviewed": True,
        },
        "decoder_text": target_label,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": "python",
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": options,
        "prompt_text": prompt,
        "query_text": "strict_candidate::python::verifier_transition::code_assist_context_pack",
        "repo_family": "code_assist",
        "repo_id": "code_assist",
        "row_id": "stage10894::code_assist::python::verifier_outcome_semantic_transition::strict_candidate_v1",
        "selected_test_anchor": True,
        "source_bundle_id": str(bundle.get("bundle_id") or ""),
        "source_heldout_admissible": False,
        "source_root_id": str(bundle.get("bundle_id") or ""),
        "split": "strict_eval_candidate",
        "split_role": "heldout_candidate_not_admitted",
        "standalone_projection_source": {
            "gold_test_id": gold_test_id,
            "gold_test_path": gold_path,
            "opaque_options": options,
            "projection_mode": "stage10894_semantic_verifier_transition_candidate_v1",
            "transition": TEST_ID_TO_TARGET[gold_test_id]["transition"],
        },
        "strict_eval_eligible": False,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": target_label,
        "target_token_len": 1,
        "task_type": "verifier_outcome_semantic_transition",
        "train_support_only": False,
        "verifier_anchor": True,
    }

    bundle_payload = {
        "bundle_id": "stage10894::code_assist::python::verifier_transition_strict_candidate",
        "source_bundle_id": bundle.get("bundle_id"),
        "repo_id": "code_assist",
        "language_family": "python",
        "claim_boundary": {
            "strict_candidate_only": True,
            "headline_eligible": False,
            "requires_review_before_scoring": True,
            "opaque_selected_test_ids": True,
            "explicit_transition_semantics": True,
        },
        "candidate_paths": list(bundle.get("candidate_paths") or []),
        "verifier_target_ledger": verifier_ledger(),
        "gold_verifier_target": {
            "test_id": gold_test_id,
            "transition": TEST_ID_TO_TARGET[gold_test_id]["transition"],
            "focus": TEST_ID_TO_TARGET[gold_test_id]["focus"],
        },
        "source_anti_cheat_rationale": anti_cheat.get("decision_rationale"),
        "strict_candidate_rows": [row],
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "code_assist_python_verifier_transition_strict_candidate_materialized",
        "headline_findings": [
            "The priority-1 code_assist verifier root is now materialized as a fresh strict-heldout candidate with opaque verifier IDs.",
            "The verifier options carry explicit transition semantics rather than raw test-path labels.",
            "The packet is still review-gated and not admitted into strict scoring until leak and identifiability audits pass.",
        ],
        "source_artifacts": {
            "source_bundle": rel(SOURCE_BUNDLE_JSON),
            "source_gold": rel(SOURCE_GOLD_JSON),
            "source_anti_cheat": rel(SOURCE_ANTI_CHEAT_JSON),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "bundle_json": rel(BUNDLE_JSON),
            "row_jsonl": rel(ROW_JSONL),
        },
        "next_best_step": "Run a leak/identifiability audit on this strict candidate, then decide whether it can enter a fresh heldout verifier slice before any new training run.",
    }

    write_json(SUMMARY_JSON, summary)
    write_json(BUNDLE_JSON, bundle_payload)
    write_jsonl(ROW_JSONL, [row])
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
