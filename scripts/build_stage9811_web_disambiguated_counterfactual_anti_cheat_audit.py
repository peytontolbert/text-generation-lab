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
STAGE = 9811
NAME = "stage9811_web_disambiguated_counterfactual_anti_cheat_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "opaque_choice_counterfactual_anti_cheat_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_DISAMBIGUATED_COUNTERFACTUAL_ANTI_CHEAT_AUDIT_STAGE9811.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9807_web_disambiguated_opaque_choice_surface/web_disambiguated_opaque_choice_surface.jsonl"
STATE_HASH = ROOT / "runs/local/artifacts/stage9781_winning_edit_localization_state_hash/winning_edit_localization_state_hash.json"
ROW_LOGITS = ROOT / "runs/local/artifacts/stage9809_web_disambiguated_structured_exec/row_field_logits.jsonl"
GEMMA_ROWS = ROOT / "runs/local/artifacts/stage9810_web_disambiguated_gemma_comparison/web_disambiguated_gemma_rows.jsonl"
GEMMA_AUDIT = ROOT / "runs/local/artifacts/stage9810_web_disambiguated_gemma_comparison/web_disambiguated_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


RUNNER = _load_module("stage9795_runner", ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py")
FIELD = "edit_localization"


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


def manifest_rows() -> list[dict[str, Any]]:
    return load_jsonl(MANIFEST)


def manifest_by_lang() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows():
        if str(row.get("split") or "") != "strict_eval":
            continue
        grouped[str(row.get("language_family") or "")].append(row)
    for lang in grouped:
        grouped[lang].sort(key=lambda row: str(row.get("row_id") or ""))
    return grouped


def logits_index() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("row_id") or ""): row
        for row in load_jsonl(ROW_LOGITS)
        if row.get("field") == FIELD and row.get("split") == "strict_eval"
    }


def gemma_rows_by_lang() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in load_jsonl(GEMMA_ROWS):
        if str(row.get("split") or "") != "strict_eval":
            continue
        grouped[str(row.get("language") or "")].append(row)
    for lang in grouped:
        grouped[lang].sort(key=lambda row: str(row.get("row_id") or ""))
    return grouped


def gemma_results_by_lang() -> dict[str, dict[str, Any]]:
    rows = load_json(GEMMA_AUDIT).get("results") or []
    return {str(row.get("language") or ""): row for row in rows}


def label_vocab(rows: list[dict[str, Any]]) -> list[str]:
    labels = {
        str(((row.get("target") if isinstance(row.get("target"), dict) else {}).get("decoder_text") or ""))
        for row in rows
    }
    return sorted(label for label in labels if label)


def expected_label(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(target.get("decoder_text") or "")


def majority_baseline(rows: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [expected_label(row) for row in rows]
    counts = Counter(targets)
    winner = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]
    correct = sum(1 for target in targets if target == winner)
    return {"label": winner, "score": correct / len(rows), "support": counts[winner]}


def first_label_baseline(rows: list[dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    winner = labels[0]
    correct = sum(1 for row in rows if expected_label(row) == winner)
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
        target = expected_label(row)
        sig = signature(row)
        peers = [peer for j, peer in enumerate(rows) if j != idx and signature(peer) == sig]
        if peers:
            peer_counts = Counter(expected_label(peer) for peer in peers)
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


def prompt_surface_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_literal_rows: list[str] = []
    hidden_target_visible_rows: list[str] = []
    for row in rows:
        prompt = RUNNER.build_prompt(row=row, field=FIELD, labels=label_vocab(rows))
        row_id = str(row.get("row_id") or "")
        if "TARGET_" in prompt:
            target_literal_rows.append(row_id)
        hidden = str(((row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}).get("edit_localization_target_hidden") or ""))
        if hidden and hidden in prompt:
            hidden_target_visible_rows.append(row_id)
    return {
        "prompt_target_literal_rows": target_literal_rows,
        "prompt_hidden_target_literal_rows": hidden_target_visible_rows,
        "prompt_target_literal_row_count": len(target_literal_rows),
        "prompt_hidden_target_literal_row_count": len(hidden_target_visible_rows),
    }


def split_mapping_stability(rows: list[dict[str, Any]], language_family: str) -> dict[str, Any]:
    all_rows = [row for row in manifest_rows() if str(row.get("language_family") or "") == language_family]
    split_to_choices: dict[str, tuple[str, ...]] = {}
    for row in all_rows:
        split = str(row.get("split") or "")
        choices = tuple(((row.get("input_state") if isinstance(row.get("input_state"), dict) else {}).get("candidate_choices") or []))
        split_to_choices.setdefault(split, choices)
    unique_choice_orders = {choices for choices in split_to_choices.values()}
    return {
        "split_choice_orders": {split: list(choices) for split, choices in sorted(split_to_choices.items())},
        "stable_across_splits": len(unique_choice_orders) == 1 and len(split_to_choices) == 3,
    }


def run_prompt_probe(
    rows: list[dict[str, Any]],
    labels: list[str],
    generate_fn: Callable[[str], str],
    transform_name: str,
) -> dict[str, Any]:
    out_rows: list[dict[str, Any]] = []
    correct = 0
    changed = 0
    baseline_predictions: dict[str, str] = {}
    for idx, row in enumerate(rows):
        expected = expected_label(row)
        donor = rows[(idx + 1) % len(rows)]
        donor_expected = expected_label(donor)
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
        ok = pred == probe_expected
        correct += int(ok)
        baseline_pred = baseline_predictions.get(str(row.get("row_id") or ""))
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
        if transform_name == "label_order_permutation":
            baseline_predictions[str(row.get("row_id") or "")] = pred
    return {"score": correct / len(rows), "row_count": len(rows), "changed_prediction_count": changed, "rows": out_rows}


def build_audit(generate_fn: Callable[[str], str] | None = None) -> dict[str, Any]:
    strict_rows = manifest_by_lang()
    row_logits = logits_index()
    gemma_rows = gemma_rows_by_lang()
    gemma_results = gemma_results_by_lang()
    state_hash = load_json(STATE_HASH)
    failures: list[str] = []
    records: list[dict[str, Any]] = []

    def _generate(prompt: str) -> str:
        if generate_fn is not None:
            return generate_fn(prompt)
        return RUNNER.ollama_generate(model="gemma3:12b", prompt=prompt, seed=0, temperature=0.0)

    for lang in LANGS:
        rows = strict_rows.get(lang, [])
        if len(rows) != 5:
            failures.append(f"unexpected_strict_row_count:{lang}:{len(rows)}")
            continue
        labels = label_vocab(rows)
        logits_rows = [row_logits.get(str(row.get("row_id") or "")) for row in rows]
        if any(row is None for row in logits_rows):
            failures.append(f"missing_100m_logits:{lang}")
            continue
        raw_gemma_outputs = gemma_rows.get(lang, [])
        if len(raw_gemma_outputs) != 5:
            failures.append(f"missing_gemma_rows:{lang}:{len(raw_gemma_outputs)}")
        majority = majority_baseline(rows)
        first_label = first_label_baseline(rows, labels)
        metadata_only = metadata_only_baseline(rows)
        prompt_checks = prompt_surface_checks(rows)
        mapping = split_mapping_stability(rows, lang)
        permutation = run_prompt_probe(rows, labels, _generate, "label_order_permutation")
        decoy = run_prompt_probe(rows, labels, _generate, "decoy_label_injection")
        ablation = run_prompt_probe(rows, labels, _generate, "critical_evidence_ablation")
        causal = run_prompt_probe(rows, labels, _generate, "causal_flip")
        comparison = gemma_results.get(lang) or {}
        records.append(
            {
                "language_family": lang,
                "surface_manifest": str(MANIFEST.relative_to(ROOT)),
                "state_hash": state_hash.get("state_sha256"),
                "manifest_hash": load_json(ROOT / "runs/local/artifacts/stage9809_web_disambiguated_structured_exec/probe_contract_audit.json").get("manifest_sha256"),
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
                "raw_gemma_outputs": raw_gemma_outputs,
                "comparison_summary": {
                    "model_strict_exact_100m": comparison.get("model_strict_exact_100m"),
                    "gemma_strict_exact": comparison.get("gemma_strict_exact"),
                    "verdict": comparison.get("verdict"),
                },
                "prompt_surface_checks": prompt_checks,
                "mapping_stability": mapping,
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
                "expert_reviewer_judgment": {
                    "review_status": "pending_human_confirmation",
                    "appropriate_scope": "narrow_visible_evidence_edit_localization_only",
                    "not_general_intelligence": True,
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
            "prompt_target_literal_row_count": sum(row["prompt_surface_checks"]["prompt_target_literal_row_count"] for row in records),
            "prompt_hidden_target_literal_row_count": sum(row["prompt_surface_checks"]["prompt_hidden_target_literal_row_count"] for row in records),
            "stable_choice_mapping_language_count": sum(1 for row in records if row["mapping_stability"]["stable_across_splits"]),
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
        "Use the corrected opaque-choice anti-cheat cards to drive expert maintainer review and sealed heldout replication before promoting the multilingual win beyond a provisional same-surface result."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Packaged the web-disambiguated multilingual win into counterfactual anti-cheat cards with real Stage9809 100M row outputs, real Stage9810 Gemma row outputs, prompt-surface leakage checks, split-stable mapping checks, shallow baselines, and transformed prompt probes.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9811 Web Disambiguated Counterfactual Anti Cheat Audit",
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
                f"Prompt TARGET literal rows: `{audit['metrics']['prompt_target_literal_row_count']}`",
                f"Prompt hidden-target literal rows: `{audit['metrics']['prompt_hidden_target_literal_row_count']}`",
                f"Stable choice mapping languages: `{audit['metrics']['stable_choice_mapping_language_count']}`",
                "",
                "This stage does not promote the result to general intelligence. It packages the web-disambiguated multilingual edit-localization win with the anti-cheat and counterfactual evidence needed to judge whether the score survives prompt leakage checks, label-order changes, decoy mentions, evidence ablations, and causal swaps.",
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
