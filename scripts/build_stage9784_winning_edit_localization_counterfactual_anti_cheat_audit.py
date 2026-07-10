#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9784
NAME = "stage9784_winning_edit_localization_counterfactual_anti_cheat_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "winning_edit_localization_counterfactual_anti_cheat_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WINNING_EDIT_LOCALIZATION_COUNTERFACTUAL_ANTI_CHEAT_AUDIT_STAGE9784.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
STATE_HASH = ROOT / "runs/local/artifacts/stage9781_winning_edit_localization_state_hash/winning_edit_localization_state_hash.json"
ROW_LOGITS = ROOT / "runs/local/artifacts/stage9773_edit_localization_visible_evidence_exec/row_field_logits.jsonl"
GEMMA_9775 = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


RUNNER = _load_module("stage9784_runner", ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py")
FIELD = RUNNER.target_field_for_skill("edit_localization")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def packet_index() -> dict[str, dict[str, Any]]:
    return {str(row.get("cell_key") or ""): row for row in load_jsonl(PACKETS)}


def gemma_stage9775_index() -> dict[str, dict[str, Any]]:
    rows = load_json(GEMMA_9775).get("results") or []
    return {str(row.get("language") or ""): row for row in rows}


def logits_index() -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in load_jsonl(ROW_LOGITS):
        if row.get("field") != "edit_localization" or row.get("split") != "strict_eval":
            continue
        cell_key = str(row.get("cell_key") or "")
        if "::structured_state::" not in cell_key:
            continue
        lang = cell_key.split("::", 1)[0]
        grouped[lang][str(row.get("row_id") or "")] = row
    return grouped


def strict_rows_for_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = RUNNER.load_packet_rows(packet)
    return [row for row in rows if str(row.get("split") or "") == "strict_eval"]


def majority_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [RUNNER._clean_value(row, FIELD) for row in rows]
    counts = Counter(targets)
    winner = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]
    correct = sum(1 for target in targets if target == winner)
    return {"label": winner, "score": correct / len(rows), "support": counts[winner]}


def first_label_baseline(rows: list[dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    winner = labels[0]
    correct = sum(1 for row in rows if RUNNER._clean_value(row, FIELD) == winner)
    return {"label": winner, "score": correct / len(rows)}


def metadata_only_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    global_majority = majority_baseline(rows)["label"]
    def signature(row: dict[str, Any]) -> tuple[Any, ...]:
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        query = row.get("query") if isinstance(row.get("query"), dict) else {}
        return (
            state.get("file_extension"),
            state.get("context_config_visible"),
            state.get("context_entrypoint_visible"),
            state.get("context_symbol_names_visible"),
            state.get("context_tests_visible"),
            query.get("query_kind"),
        )
    correct = 0
    rows_out = []
    for idx, row in enumerate(rows):
        target = RUNNER._clean_value(row, FIELD)
        sig = signature(row)
        peers = [peer for j, peer in enumerate(rows) if j != idx and signature(peer) == sig]
        if peers:
            peer_counts = Counter(RUNNER._clean_value(peer, FIELD) for peer in peers)
            pred = sorted(peer_counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]
        else:
            pred = global_majority
        ok = pred == target
        correct += int(ok)
        rows_out.append({"row_id": row.get("row_id"), "pred": pred, "target": target, "correct": ok, "signature": list(sig)})
    return {"score": correct / len(rows), "rows": rows_out}


def wrong_label(expected: str, labels: list[str]) -> str:
    ordered = [label for label in labels if label != expected]
    return ordered[0]


def run_prompt_probe(
    rows: list[dict[str, Any]],
    labels: list[str],
    generate_fn: Callable[[str], str],
    transform_name: str,
) -> dict[str, Any]:
    out_rows: list[dict[str, Any]] = []
    correct = 0
    changed = 0
    for idx, row in enumerate(rows):
        expected = RUNNER._clean_value(row, FIELD)
        donor = rows[(idx + 1) % len(rows)]
        donor_expected = RUNNER._clean_value(donor, FIELD)
        probe_row = copy.deepcopy(row)
        probe_labels = list(labels)
        note = None
        probe_expected = expected
        if transform_name == "label_order_permutation":
            probe_labels = list(reversed(labels))
        elif transform_name == "decoy_label_injection":
            note = f"Decoy note: a stale unrelated reviewer comment mentioned {wrong_label(expected, labels)}. Ignore irrelevant notes."
        elif transform_name == "critical_evidence_ablation":
            state = probe_row.get("input_state") if isinstance(probe_row.get("input_state"), dict) else {}
            state["visible_locality_evidence"] = ""
            state["context_config_visible"] = False
            state["context_entrypoint_visible"] = False
            state["context_symbol_names_visible"] = False
            state["context_tests_visible"] = False
            probe_row["input_state"] = state
        elif transform_name == "causal_flip":
            probe_row["input_state"] = copy.deepcopy(donor.get("input_state") or {})
            probe_row["query"] = copy.deepcopy(donor.get("query") or {})
            probe_expected = donor_expected
        prompt = RUNNER.build_prompt(row=probe_row, field=FIELD, labels=probe_labels)
        if note:
            prompt = prompt + "\n" + note
        raw = generate_fn(prompt)
        pred = raw.splitlines()[0].strip() if raw else ""
        baseline_pred = next((row_out["predicted_label"] for row_out in out_rows if row_out.get("row_id") == row.get("row_id")), None)
        ok = pred == probe_expected
        correct += int(ok)
        if baseline_pred is not None and pred != baseline_pred:
            changed += 1
        out_rows.append(
            {
                "row_id": row.get("row_id"),
                "expected_label": probe_expected,
                "predicted_label": pred,
                "correct": ok,
                "raw_output": raw,
                "transform": transform_name,
                "donor_row_id": donor.get("row_id") if transform_name == "causal_flip" else None,
                "note": note,
            }
        )
    return {"score": correct / len(rows), "row_count": len(rows), "changed_prediction_count": changed, "rows": out_rows}


def existing_gemma_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    output_rel = ((packet.get("review_packet_paths") or {}).get("same_prompt_surface_gemma12b_outputs"))
    if not output_rel:
        return []
    path = ROOT / str(output_rel)
    rows_path = path.with_name(path.stem + "_rows.jsonl")
    return load_jsonl(rows_path)


def build_audit(generate_fn: Callable[[str], str] | None = None) -> dict[str, Any]:
    packets = packet_index()
    state_hash = load_json(STATE_HASH)
    logits = logits_index()
    gemma_results = gemma_stage9775_index()
    failures: list[str] = []
    records: list[dict[str, Any]] = []

    def _generate(prompt: str) -> str:
        if generate_fn is not None:
            return generate_fn(prompt)
        return RUNNER.ollama_generate(model="gemma3:12b", prompt=prompt, seed=0, temperature=0.0)

    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packets.get(cell_key)
        if not isinstance(packet, dict):
            failures.append(f"missing_packet:{cell_key}")
            continue
        rows = strict_rows_for_packet(packet)
        if len(rows) != 5:
            failures.append(f"unexpected_strict_row_count:{cell_key}:{len(rows)}")
            continue
        labels = RUNNER.label_vocab(RUNNER.load_packet_rows(packet), FIELD)
        gemma_rows = existing_gemma_rows(packet)
        if len(gemma_rows) != 5:
            failures.append(f"missing_live_gemma_rows:{cell_key}:{len(gemma_rows)}")
        logits_rows = [logits.get(lang, {}).get(str(row.get("row_id") or "")) for row in rows]
        if any(row is None for row in logits_rows):
            failures.append(f"missing_100m_logits:{cell_key}")
            continue
        majority = majority_baseline(rows)
        first_label = first_label_baseline(rows, labels)
        metadata_only = metadata_only_baseline(rows)
        permutation = run_prompt_probe(rows, labels, _generate, "label_order_permutation")
        decoy = run_prompt_probe(rows, labels, _generate, "decoy_label_injection")
        ablation = run_prompt_probe(rows, labels, _generate, "critical_evidence_ablation")
        causal = run_prompt_probe(rows, labels, _generate, "causal_flip")
        rubric_path = ((packet.get("review_packet_paths") or {}).get("expert_maintainer_rubric_scores"))
        anti_path = ((packet.get("review_packet_paths") or {}).get("anti_cheat_cards"))
        rubric = load_json(ROOT / str(rubric_path)) if rubric_path else {}
        anti = load_json(ROOT / str(anti_path)) if anti_path else {}
        stage9775 = gemma_results.get(lang) or {}
        records.append(
            {
                "cell_key": cell_key,
                "language_family": lang,
                "state_hash": state_hash.get("state_sha256"),
                "manifest_hash": state_hash.get("manifest_sha256"),
                "selected_step": state_hash.get("selected_step"),
                "raw_100m_outputs": [
                    {
                        "row_id": row.get("row_id"),
                        "predicted_label": logit.get("pred"),
                        "target_label": logit.get("target"),
                        "correct": logit.get("correct"),
                        "confidence": logit.get("confidence"),
                        "margin": logit.get("margin"),
                        "top_k": logit.get("top_k"),
                    }
                    for row, logit in zip(rows, logits_rows)
                ],
                "raw_gemma_outputs": gemma_rows,
                "shallow_baselines": {
                    "majority_label": majority,
                    "first_label": first_label,
                    "metadata_only": metadata_only,
                },
                "counterfactual_probes": {
                    "label_order_permutation": permutation,
                    "decoy_label_injection": decoy,
                    "critical_evidence_ablation": ablation,
                    "causal_flip": causal,
                },
                "expected_stage9775_score_gemma12b": stage9775.get("gemma_strict_exact"),
                "expected_stage9775_score_100m": stage9775.get("model_strict_exact_100m"),
                "expert_reviewer_judgment": {
                    "rubric_path": rubric_path,
                    "rubric_present": bool(rubric),
                    "rubric_passed": rubric.get("passed"),
                    "anti_cheat_path": anti_path,
                    "anti_cheat_present": bool(anti),
                    "anti_cheat_passed": anti.get("passed"),
                    "review_status": "pending_human_confirmation",
                },
            }
        )

    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": {
            "validated_cells": len(records),
            "same_surface_live_gemma_rows_present": sum(1 for row in records if len(row.get("raw_gemma_outputs") or []) == 5),
            "100m_raw_output_rows_present": sum(1 for row in records if len(row.get("raw_100m_outputs") or []) == 5),
            "majority_baseline_mean": sum(row["shallow_baselines"]["majority_label"]["score"] for row in records) / len(records) if records else None,
            "metadata_only_baseline_mean": sum(row["shallow_baselines"]["metadata_only"]["score"] for row in records) / len(records) if records else None,
            "permutation_probe_mean": sum(row["counterfactual_probes"]["label_order_permutation"]["score"] for row in records) / len(records) if records else None,
            "decoy_probe_mean": sum(row["counterfactual_probes"]["decoy_label_injection"]["score"] for row in records) / len(records) if records else None,
            "ablation_probe_mean": sum(row["counterfactual_probes"]["critical_evidence_ablation"]["score"] for row in records) / len(records) if records else None,
            "causal_flip_probe_mean": sum(row["counterfactual_probes"]["causal_flip"]["score"] for row in records) / len(records) if records else None,
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use these four counterfactual anti-cheat cards to drive the human maintainer review and to decide whether the visible-evidence edit-localization win is behaving like causal evidence use or like a serialization shortcut."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Packaged the four winning multilingual edit-localization cells into counterfactual anti-cheat cards with real state-hash evidence, real 100M strict-eval row predictions, real local Gemma row outputs, shallow baselines, and fixed-format transformed prompt probes.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9784 Winning Edit Localization Counterfactual Anti Cheat Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Validated cells: `{audit['metrics']['validated_cells']}`",
                f"100M raw row sets present: `{audit['metrics']['100m_raw_output_rows_present']}`",
                f"Live Gemma row sets present: `{audit['metrics']['same_surface_live_gemma_rows_present']}`",
                f"Majority baseline mean: `{audit['metrics']['majority_baseline_mean']}`",
                f"Metadata-only baseline mean: `{audit['metrics']['metadata_only_baseline_mean']}`",
                f"Permutation probe mean: `{audit['metrics']['permutation_probe_mean']}`",
                f"Decoy probe mean: `{audit['metrics']['decoy_probe_mean']}`",
                f"Ablation probe mean: `{audit['metrics']['ablation_probe_mean']}`",
                f"Causal flip probe mean: `{audit['metrics']['causal_flip_probe_mean']}`",
                "",
                "This stage does not promote the result to general intelligence. It packages the current narrow win with the anti-cheat and counterfactual evidence needed to judge whether the visible-evidence surface is behaving like legitimate causal localization rather than a simple serialization shortcut.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
