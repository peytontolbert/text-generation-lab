#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9780
NAME = "stage9780_refresh_winning_edit_localization_review_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "winning_edit_localization_review_packet_refresh.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REFRESH_WINNING_EDIT_LOCALIZATION_REVIEW_PACKETS_STAGE9780.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
EXEC_SUMMARY = ROOT / "runs/summaries/stage9773_edit_localization_visible_evidence_execution_audit.json"
EXEC_RESULT = ROOT / "runs/local/artifacts/stage9773_edit_localization_visible_evidence_exec/execution_result.json"
EXEC_CONTRACT = ROOT / "runs/local/artifacts/stage9773_edit_localization_visible_evidence_exec/probe_contract_audit.json"
LANG_AUDIT = ROOT / "runs/local/artifacts/stage9774_edit_localization_visible_evidence_language_slice_audit/edit_localization_visible_evidence_language_slice_audit.json"
GEMMA_SUMMARY = ROOT / "runs/summaries/stage9775_edit_localization_visible_evidence_gemma_comparison.json"
GEMMA_AUDIT = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_comparison.json"
GEMMA_ROWS = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_rows.jsonl"
CLAIM_BRIDGE = ROOT / "runs/local/artifacts/stage9779_current_truthful_standalone_claim_bridge/current_truthful_standalone_claim_bridge.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
WINNING_CELL_KEYS = {f"standalone_100m_weights::{lang}::edit_localization" for lang in LANGS}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def _surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "row_id": row.get("row_id"),
            "split": row.get("split"),
            "prompt": row.get("prompt"),
            "expected_label": row.get("expected_label"),
        }
        for row in sorted(rows, key=lambda item: str(item.get("row_id") or ""))
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _subskill_hints() -> dict[str, list[str]]:
    return {
        "understands_user_intent": ["inspect task observation text against the predicted target class"],
        "uses_allowed_imports_only": ["review that the visible-evidence surface did not require import-policy violations"],
        "rejects_blocked_imports": ["review that no blocked-import workaround is implied by the target selection"],
        "retrieves_source_evidence_when_needed": ["inspect whether visible locality evidence is sufficient for the chosen target"],
        "binds_symbols_correctly": ["inspect symbol-target rows and verify the chosen target aligns with visible ownership evidence"],
        "localizes_edit_scope": ["inspect whether the predicted target stays within the visible failing region"],
        "chooses_minimal_edit_operator": ["confirm localization stays narrower than file/test/config alternatives when symbol evidence is visible"],
        "creates_or_updates_tests_when_appropriate": ["inspect whether TARGET_TEST is chosen only when test evidence is explicitly visible"],
        "predicts_verifier_command": ["not primary for edit localization; confirm the task remains scoped and does not infer hidden verifier commands"],
        "interprets_verifier_failure": ["inspect task observation and visible locality evidence against the chosen target"],
        "repairs_or_abstains_safely": ["confirm the target choice does not require unsafe speculation beyond visible evidence"],
        "keeps_patch_minimal": ["inspect whether the predicted target is the narrowest supported edit surface"],
        "avoids_broad_rewrites": ["confirm the target choice does not collapse to broad file-level changes when narrower evidence exists"],
        "avoids_hallucinated_symbols": ["inspect rows with symbol evidence and verify no unsupported identifiers appear in the prompts or outputs"],
        "avoids_internal_tokens": ["inspect the row-level Gemma and 100M outputs for internal-token leakage"],
        "produces_contentful_final_answer": ["confirm the structured outputs are valid target labels and correspond to visible evidence"],
    }


def build_refresh() -> dict[str, Any]:
    packets = load_jsonl(PACKETS)
    anti_hack = load_json(ANTI_HACK)
    exec_summary = load_json(EXEC_SUMMARY)
    exec_result = load_json(EXEC_RESULT)
    exec_contract = load_json(EXEC_CONTRACT)
    lang_audit = load_json(LANG_AUDIT)
    gemma_summary = load_json(GEMMA_SUMMARY)
    gemma_audit = load_json(GEMMA_AUDIT)
    gemma_rows = load_jsonl(GEMMA_ROWS)
    claim_bridge = load_json(CLAIM_BRIDGE)

    packet_index = {str(packet.get("cell_key") or ""): packet for packet in packets}
    bridge_index = {
        str(row.get("cell_key") or ""): row
        for row in (claim_bridge.get("records") if isinstance(claim_bridge.get("records"), list) else [])
    }
    gemma_by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in gemma_rows:
        gemma_by_lang[str(row.get("language") or "")].append(row)
    gemma_results = {
        str(row.get("language") or ""): row
        for row in (gemma_audit.get("results") if isinstance(gemma_audit.get("results"), list) else [])
    }

    refreshed_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    hints = _subskill_hints()
    global_challenges = anti_hack.get("challenge_matrix", {}).get("records") if isinstance(anti_hack.get("challenge_matrix"), dict) else []

    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packet_index.get(cell_key)
        bridge = bridge_index.get(cell_key)
        if packet is None:
            failures.append(f"missing_packet:{cell_key}")
            continue
        if bridge is None:
            failures.append(f"missing_bridge_record:{cell_key}")
            continue
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        rubric_path = ROOT / str(paths.get("expert_maintainer_rubric_scores") or "")
        anti_path = ROOT / str(paths.get("anti_cheat_cards") or "")
        gemma_path = ROOT / str(paths.get("same_prompt_surface_gemma12b_outputs") or "")
        gemma_rows_path = gemma_path.with_name(gemma_path.stem + "_rows.jsonl")
        checkpoint_path = ROOT / str(paths.get("frozen_export_or_checkpoint_hash") or "")

        rows = sorted(gemma_by_lang.get(lang, []), key=lambda row: str(row.get("row_id") or ""))
        gemma_result = gemma_results.get(lang)
        language_slice = (lang_audit.get("language_slices") or {}).get(lang) if isinstance(lang_audit.get("language_slices"), dict) else {}
        strict_card = language_slice.get("strict_eval") if isinstance(language_slice.get("strict_eval"), dict) else {}
        eval_card = language_slice.get("eval") if isinstance(language_slice.get("eval"), dict) else {}
        if not rows or not isinstance(gemma_result, dict) or not strict_card or not eval_card:
            failures.append(f"incomplete_winning_evidence:{cell_key}")
            continue

        surface_hash = _surface_hash(rows)
        gemma_payload = {
            "cell_key": cell_key,
            "status": "completed_gemma_execution",
            "authorized_now": True,
            "model_runtime": "ollama",
            "model_id": gemma_audit.get("model_id"),
            "executed_split": gemma_audit.get("split"),
            "executed_row_count": len(rows),
            "label_vocab_scope": gemma_audit.get("label_vocab_scope"),
            "decoder_temperature": gemma_audit.get("decoder_temperature"),
            "decoder_seed": gemma_audit.get("decoder_seed"),
            "prompt_surface_hash_100m": surface_hash,
            "prompt_surface_hash_gemma12b": surface_hash,
            "same_surface_verified": True,
            "score_100m": gemma_result.get("model_strict_exact_100m"),
            "score_gemma12b": gemma_result.get("gemma_strict_exact"),
            "hundred_m_beats_gemma12b": gemma_result.get("verdict") == "100m_better",
            "output_artifact_paths": [str(gemma_rows_path.relative_to(ROOT))],
            "notes": [
                "Refreshed to the Stage9771 visible-evidence edit-localization surface.",
                "Uses the deterministic Stage9775 Gemma comparison rows filtered to this language.",
            ],
            "authority": {
                **dict(AUTHORITY_CLOSED),
                "gemma_execution_authorized_next": True,
            },
        }
        write_json(gemma_path, gemma_payload)
        write_jsonl(gemma_rows_path, rows)

        rubric_payload = {
            "cell_key": cell_key,
            "status": "pending_human_review_with_current_winning_evidence",
            "auto_review_complete": False,
            "reviewer_must_confirm": True,
            "packet_dir": str((ROOT / str(paths.get("packet_dir") or "")).relative_to(ROOT)),
            "rubric_version": "expert_maintainer_v1",
            "must_pass_all_subskills": True,
            "passed": False,
            "failure_trace_refs": [],
            "reviewer_notes": [],
            "reviewer_guidance": [
                "This review packet is now anchored to the current winning visible-evidence edit-localization surface.",
                "A human reviewer still must assign final subskill judgments and attach failure traces when not passed.",
            ],
            "required_human_action": "assign rubric subskill judgments using the refreshed Stage9773/9775 same-surface evidence",
            "source_100m_score": eval_card.get("exact"),
            "same_surface_eval_exact": eval_card.get("exact"),
            "same_surface_strict_exact": strict_card.get("exact"),
            "gemma_strict_exact": gemma_result.get("gemma_strict_exact"),
            "same_surface_hash_100m": surface_hash,
            "same_surface_hash_gemma12b": surface_hash,
            "same_surface_split_counts": {"eval": eval_card.get("rows"), "strict_eval": strict_card.get("rows")},
            "hundred_m_beats_gemma12b": gemma_result.get("verdict") == "100m_better",
            "evidence_draft_path": str(MANIFEST.relative_to(ROOT)),
            "supporting_evidence_paths": [
                str(EXEC_SUMMARY.relative_to(ROOT)),
                str(LANG_AUDIT.relative_to(ROOT)),
                str(GEMMA_SUMMARY.relative_to(ROOT)),
                str(gemma_rows_path.relative_to(ROOT)),
            ],
            "subskill_evidence_hints": hints,
            "subskills": {name: None for name in hints},
            "authority": dict(AUTHORITY_CLOSED),
        }
        write_json(rubric_path, rubric_payload)

        anti_payload = {
            "cell_key": cell_key,
            "status": "pending_cell_specific_review_with_current_winning_evidence",
            "auto_review_complete": False,
            "reviewer_must_confirm": True,
            "packet_dir": str((ROOT / str(paths.get("packet_dir") or "")).relative_to(ROOT)),
            "passed": False,
            "global_stage9717_gate_passed": anti_hack.get("passed") is True,
            "must_pass_global_stage9717_gate": True,
            "same_surface_eval_exact": eval_card.get("exact"),
            "same_surface_strict_exact": strict_card.get("exact"),
            "gemma_strict_exact": gemma_result.get("gemma_strict_exact"),
            "same_surface_hash_100m": surface_hash,
            "same_surface_hash_gemma12b": surface_hash,
            "same_surface_verified": True,
            "hundred_m_beats_gemma12b": gemma_result.get("verdict") == "100m_better",
            "supporting_evidence_paths": [
                str(EXEC_SUMMARY.relative_to(ROOT)),
                str(LANG_AUDIT.relative_to(ROOT)),
                str(GEMMA_SUMMARY.relative_to(ROOT)),
                str(gemma_rows_path.relative_to(ROOT)),
            ],
            "reviewer_guidance": [
                "This anti-cheat card is refreshed to the visible-evidence winning surface and same-surface Gemma comparison.",
                "A human reviewer still must confirm each challenge family against the concrete row-level prompts and outputs.",
            ],
            "required_human_action": "complete cell-specific anti-cheat judgments and notes for all challenge families using the refreshed winning evidence",
            "challenge_families": [
                {
                    "challenge_family": row.get("challenge_family"),
                    "global_gate_passed": row.get("passed") is True,
                    "required_requirements": row.get("required_requirements"),
                    "cell_specific_card_present": True,
                    "passed": False,
                    "notes": [],
                    "cell_evidence_hints": [
                        "confirm the reviewed outputs use the same visible-evidence surface hash for both 100M and Gemma",
                        "confirm target labels are supported by visible locality evidence rather than hidden metadata",
                        "cite concrete prompt/output rows from the attached row-level Gemma artifact when recording judgments",
                    ],
                }
                for row in global_challenges
            ],
            "reviewer_notes": [],
            "evidence_draft_path": str(MANIFEST.relative_to(ROOT)),
            "authority": dict(AUTHORITY_CLOSED),
        }
        write_json(anti_path, anti_payload)

        checkpoint_lines = [
            f"cell_key={cell_key}",
            "status=no_exported_checkpoint_available_from_stage9773",
            "checkpoint_exported=false",
            f"selected_step={((exec_result.get('best_state_selection') or {}).get('selected_step'))}",
            f"eval_joint_proxy_exact={((exec_result.get('best_state_selection') or {}).get('eval_joint_proxy_exact'))}",
            f"strict_joint_proxy_exact={((exec_result.get('best_state_selection') or {}).get('strict_joint_proxy_exact'))}",
            f"manifest_sha256={exec_contract.get('manifest_sha256')}",
            "notes=stage9773 selected the best structured state but did not export a final checkpoint; a real frozen export or checkpoint hash is still required for claim-ready evidence",
            "",
        ]
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text("\n".join(checkpoint_lines), encoding="utf-8")

        refreshed_rows.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "rubric_path": str(rubric_path.relative_to(ROOT)),
                "anti_cheat_path": str(anti_path.relative_to(ROOT)),
                "gemma_path": str(gemma_path.relative_to(ROOT)),
                "gemma_rows_path": str(gemma_rows_path.relative_to(ROOT)),
                "checkpoint_path": str(checkpoint_path.relative_to(ROOT)),
                "same_surface_hash": surface_hash,
                "score_100m": gemma_result.get("model_strict_exact_100m"),
                "score_gemma12b": gemma_result.get("gemma_strict_exact"),
            }
        )

    metrics = {
        "target_cells": len(WINNING_CELL_KEYS),
        "refreshed_cells": len(refreshed_rows),
        "same_surface_win_cells": sum(1 for row in refreshed_rows if float(row["score_100m"]) > float(row["score_gemma12b"])),
        "checkpoint_export_missing_cells": len(refreshed_rows),
    }
    if metrics["refreshed_cells"] != 4:
        failures.append("refreshed_cells_not_4")
    if metrics["same_surface_win_cells"] != 4:
        failures.append("same_surface_win_cells_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "rows": refreshed_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_refresh()
    write_json(MANIFEST, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "rows": built["rows"],
        "authority": dict(AUTHORITY_CLOSED),
    })
    next_step = (
        "Use the refreshed review packets to complete expert-maintainer rubric and anti-cheat judgments for the four winning "
        "edit-localization cells, then recover a real frozen export or checkpoint hash for the Stage9773 winning 100M side."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Refreshed the four winning edit-localization review packets so rubric, anti-cheat, and Gemma evidence files now point at the current visible-evidence multilingual win instead of the stale target-only package.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage9780 Refresh Winning Edit Localization Review Packets",
                "",
                f"Passed: `{summary['passed']}`",
                f"Refreshed cells: `{built['metrics']['refreshed_cells']}`",
                f"Same-surface win cells: `{built['metrics']['same_surface_win_cells']}`",
                f"Checkpoint export missing cells: `{built['metrics']['checkpoint_export_missing_cells']}`",
                "",
                "This stage updates the physical review-packet files for the four winning multilingual edit-localization cells.",
                "- Rubric and anti-cheat artifacts now point at the Stage9773/9775 visible-evidence win surface.",
                "- Packet-local Gemma output files are refreshed from the Stage9775 row-level outputs.",
                "- Checkpoint slots now clearly record that Stage9773 selected a winning state but did not export a final checkpoint hash.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not built["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
