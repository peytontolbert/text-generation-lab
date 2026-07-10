#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9888
NAME = "stage9888_current_margin_position_bias_diagnostics"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9887_current_margin_hybrid_counterfactual_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9885_current_margin_hybrid_counterfactual_execution_manifest/current_margin_hybrid_counterfactual_execution_manifest.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9886_current_margin_hybrid_counterfactual_target_100m_probe/edit_localization_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_margin_position_bias_diagnostics.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_POSITION_BIAS_DIAGNOSTICS_STAGE9888.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
NEXT_MANIFEST = OUT_DIR / "current_margin_position_debiased_manifest.jsonl"
NEXT_CANDIDATE = OUT_DIR / "stage9889_current_margin_position_debiased_probe_candidate.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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


def target_label(row: dict[str, Any]) -> str:
    tgt = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(tgt.get("decoder_text") or tgt.get("edit_localization") or row.get("edit_localization_target") or "")


def target_choice_position_and_desc(row: dict[str, Any]) -> tuple[int | None, str | None]:
    choices = ((row.get("input_state") or {}).get("candidate_choices") or []) if isinstance(row.get("input_state"), dict) else []
    tgt = target_label(row)
    for idx, choice in enumerate(choices):
        text = str(choice)
        if text.split(":", 1)[0].strip() == f"option {tgt}":
            return idx, text.split(":", 1)[1].strip()
    return None, None


def position_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_target = defaultdict(Counter)
    by_semantic = defaultdict(Counter)
    for row in rows:
        pos, desc = target_choice_position_and_desc(row)
        if pos is None or desc is None:
            continue
        by_target[target_label(row)][pos] += 1
        by_semantic[desc][pos] += 1
    return {
        "target_position_counts": {k: dict(v) for k, v in sorted(by_target.items())},
        "semantic_target_position_counts": {k: dict(v) for k, v in sorted(by_semantic.items())},
        "every_target_spans_at_least_three_positions": all(len(v) >= 3 for v in by_target.values()),
        "every_semantic_surface_spans_at_least_three_positions": all(len(v) >= 3 for v in by_semantic.values()),
    }


def collapse_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_target = defaultdict(lambda: {"rows": 0, "pred_counts": Counter(), "mean_margin_sum": 0.0, "mean_confidence_sum": 0.0})
    for record in records:
        tgt = str(record.get("target") or "")
        pred = str(record.get("pred") or "")
        card = by_target[tgt]
        card["rows"] += 1
        card["pred_counts"][pred] += 1
        card["mean_margin_sum"] += float(record.get("margin") or 0.0)
        card["mean_confidence_sum"] += float(record.get("confidence") or 0.0)
    out = {}
    for tgt, card in sorted(by_target.items()):
        rows = max(1, int(card["rows"]))
        out[tgt] = {
            "rows": card["rows"],
            "pred_counts": dict(sorted(card["pred_counts"].items())),
            "mean_margin": card["mean_margin_sum"] / rows,
            "mean_confidence": card["mean_confidence_sum"] / rows,
        }
    return out


def _rotation_offset(row: dict[str, Any]) -> int:
    row_id = str(row.get("row_id") or "")
    label = target_label(row)
    _, desc = target_choice_position_and_desc(row)
    digest = hashlib.sha256(f"{row_id}:{label}:{desc}:stage9889".encode("utf-8")).digest()
    return digest[0] % 5


def build_position_debiased_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out_rows: list[dict[str, Any]] = []
    by_target = defaultdict(Counter)
    by_semantic = defaultdict(Counter)
    offsets = defaultdict(Counter)
    for row in rows:
        cloned = json.loads(json.dumps(row))
        input_state = cloned.get("input_state") if isinstance(cloned.get("input_state"), dict) else {}
        choices = list(input_state.get("candidate_choices") or [])
        if len(choices) != 5:
            out_rows.append(cloned)
            continue
        offset = _rotation_offset(cloned)
        rotated = choices[offset:] + choices[:offset]
        input_state["candidate_choices"] = rotated
        cloned["input_state"] = input_state
        anti = cloned.get("anti_cheat") if isinstance(cloned.get("anti_cheat"), dict) else {}
        anti["stage9889_candidate_choice_order_rotated"] = True
        anti["stage9889_rotation_offset"] = offset
        cloned["anti_cheat"] = anti
        pos, desc = target_choice_position_and_desc(cloned)
        if pos is not None and desc is not None:
            by_target[target_label(cloned)][pos] += 1
            by_semantic[desc][pos] += 1
            offsets[target_label(cloned)][offset] += 1
        out_rows.append(cloned)
    card = {
        "target_position_counts": {k: dict(v) for k, v in sorted(by_target.items())},
        "semantic_target_position_counts": {k: dict(v) for k, v in sorted(by_semantic.items())},
        "per_target_offsets": {k: dict(v) for k, v in sorted(offsets.items())},
        "every_target_spans_at_least_three_positions": all(len(v) >= 3 for v in by_target.values()),
        "every_semantic_surface_spans_at_least_three_positions": all(len(v) >= 3 for v in by_semantic.values()),
    }
    return out_rows, card


def build_candidate_command() -> list[str]:
    return [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root", str(ROOT),
        "--manifest", str(NEXT_MANIFEST.relative_to(ROOT)),
        "--mode", "edit_localization_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
        "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
        "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
        "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
        "--max-train-rows", "16",
        "--max-eval-rows", "16",
        "--max-strict-rows", "16",
        "--max-steps", "32",
        "--batch-size", "2",
        "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", "runs/local/artifacts/stage9889_current_margin_position_debiased_target_100m_probe/edit_localization_probe",
        "--run-id", "stage9889_current_margin_position_debiased_target_100m_probe",
        "--execution-authorized-for-recovery-probe",
        "--eval-interval", "1",
        "--restore-best-structured-state",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = read_jsonl(MANIFEST)
    logits = read_jsonl(LOGITS)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9887_not_passed")
    if not rows:
        failures.append("missing_manifest_rows")
    if not logits:
        failures.append("missing_logit_rows")

    position = position_stats(rows)
    collapse = collapse_stats(logits)
    debiased_rows, debiased = build_position_debiased_rows(rows)
    write_jsonl(NEXT_MANIFEST, debiased_rows)
    write_json(
        NEXT_CANDIDATE,
        {
            "future_stage": 9889,
            "future_stage_name": "stage9889_current_margin_position_debiased_target_100m_probe",
            "selected_surface": "edit_localization",
            "reason": "Stage9888 found that the current frontier packet still gives target token K and some semantic target surfaces restricted position support. Stage9889 keeps the same rows and labels but rotates displayed choice order to reduce position priors on the current multilingual packet.",
            "command": build_candidate_command(),
            "requires_explicit_user_confirmation_before_execution": True,
            "requires_this_stage_passed": True,
            "authority": dict(AUTHORITY_CLOSED),
        },
    )

    if position["every_target_spans_at_least_three_positions"]:
        failures.append("source_manifest_already_spreads_targets")
    if not debiased["every_target_spans_at_least_three_positions"]:
        failures.append("debiased_manifest_target_positions_still_too_narrow")
    if not debiased["every_semantic_surface_spans_at_least_three_positions"]:
        failures.append("debiased_manifest_semantic_positions_still_too_narrow")

    next_step = "Run Stage9889 on the position-debiased current-frontier manifest, then compare whether K exact rises above 0.0 and whether multilingual strict exact recovers without reintroducing shortcut-sensitive gains."
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "failures": failures,
        "source_position_diagnostics": position,
        "stage9886_collapse_diagnostics": collapse,
        "debiased_manifest_diagnostics": debiased,
        "next_execution_candidate": str(NEXT_CANDIDATE.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_json(AUDIT, audit)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": failures,
            "source_target_position_counts": position["target_position_counts"],
            "debiased_target_position_counts": debiased["target_position_counts"],
            "debiased_every_target_spans_at_least_three_positions": debiased["every_target_spans_at_least_three_positions"],
            "debiased_every_semantic_surface_spans_at_least_three_positions": debiased["every_semantic_surface_spans_at_least_three_positions"],
            "k_pred_counts": collapse.get("K", {}).get("pred_counts", {}),
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "debiased_manifest": str(NEXT_MANIFEST.relative_to(ROOT)),
            "next_execution_candidate": str(NEXT_CANDIDATE.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "The current multilingual counterfactual guard packet still contains target-token and semantic-surface position skew, including narrow support for K. Stage9888 materializes a position-debiased variant for a like-for-like multilingual rerun.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage9888 Current Margin Position Bias Diagnostics",
                "",
                f"Passed: `{summary['passed']}`",
                f"Source target positions: `{position['target_position_counts']}`",
                f"Debiased target positions: `{debiased['target_position_counts']}`",
                f"K prediction counts: `{collapse.get('K', {}).get('pred_counts', {})}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "source_target_position_counts": position["target_position_counts"], "debiased_target_position_counts": debiased["target_position_counts"]}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
