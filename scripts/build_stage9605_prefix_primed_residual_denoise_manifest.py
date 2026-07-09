#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9605
NAME = "stage9605_prefix_primed_residual_denoise_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9604_two_phase_denoise_generation_failure_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "prefix_primed_residual_denoise_manifest.jsonl"
HOLDOUt = OUT_DIR / "prefix_primed_residual_denoise_clean_target_holdout.jsonl"
AUDIT = OUT_DIR / "prefix_primed_residual_denoise_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PREFIX_PRIMED_RESIDUAL_DENOISE_MANIFEST_STAGE9605.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GENERATION_PREFIX_FIELD = "model_input.active_generation_prefix_span"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def nested_value(row: dict[str, Any], path: str) -> Any:
    value: Any = row
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def prefix_from_target(target: str, max_words: int = 5) -> str:
    words = target.split()
    if len(words) <= max_words:
        return ""
    prefix = " ".join(words[:max_words])
    while len(prefix) > 96 and max_words > 1:
        max_words -= 1
        prefix = " ".join(words[:max_words])
    return prefix


def active_losses(row: dict[str, Any]) -> list[str]:
    loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    return sorted(key for key, value in loss.items() if bool(value))


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


def build_rows(source_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for index, source in enumerate(source_rows):
        clean_target = str(nested_value(source, "episode_transition.state_t_plus_1.decoder_text") or "").strip()
        if not clean_target:
            hold = copy.deepcopy(source)
            hold["stage9605_holdout_reason"] = "missing_clean_state_t_plus_1_decoder_text"
            holdout.append(hold)
            continue
        prefix = prefix_from_target(clean_target)
        if not prefix:
            hold = copy.deepcopy(source)
            hold["stage9605_holdout_reason"] = "target_too_short_for_prefix_priming"
            holdout.append(hold)
            continue
        row = copy.deepcopy(source)
        row_id = f"stage9605_prefix_residual_{index:04d}_{h(str(source.get('row_id')) + clean_target)}"
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        model_input = dict(model_input)
        for key in [
            "target",
            "target_text",
            "clean_target",
            "decoder_text",
            "remaining_suffix",
            "target_suffix",
            "first_suffix_word",
            "state_t_plus_1_decoder_text",
        ]:
            model_input.pop(key, None)
        model_input.update(
            {
                "active_generation_prefix_span": prefix,
                "active_generation_prefix_words": len(prefix.split()),
                "active_generation_prefix_source": "stage9605_clean_target_prefix_scaffold",
                "remaining_suffix_hidden_from_model_input": True,
                "clean_target_hidden_from_model_input": True,
                "target_rendering_patch_stage": STAGE,
                "target_surface_family": "natural_bounded_residual_repair_text",
                "symbolic_repair_bucket_not_decoder_target": True,
            }
        )
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        loss_mask = {key: False for key in loss_mask}
        loss_mask["denoise_ce"] = True
        loss_mask.setdefault("decoder_ce", False)
        loss_mask.setdefault("structured_aux", False)
        loss_mask.setdefault("runtime_reward", False)
        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        anti_cheat = dict(anti_cheat)
        anti_cheat.update(
            {
                "decoder_ce_closed": True,
                "runtime_closed": True,
                "full_clean_target_in_model_input": False,
                "prefix_visible_but_suffix_hidden": True,
                "generation_prefix_is_not_full_target": prefix != clean_target,
                "symbolic_label_removed_from_decoder_target": True,
            }
        )
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        original_target = dict(target)
        row.update(
            {
                "row_id": row_id,
                "source_stage9566_row_id": source.get("row_id"),
                "source_stage9605": True,
                "objective_family": "prefix_primed_residual_denoise_v1",
                "route": "PREFIX_PRIMED_RESIDUAL_DENOISE_CANDIDATE_CLOSED",
                "decoder_text": clean_target,
                "clean_target": clean_target,
                "target": {
                    **original_target,
                    "decoder_text": clean_target,
                    "target_ref": "",
                    "rendered_from": "episode_transition.state_t_plus_1.decoder_text",
                    "symbolic_label_previous": original_target.get("decoder_text") or original_target.get("label"),
                    "prefix_visible_suffix_hidden": True,
                    "target_authority": "stage9605_prefix_primed_clean_state_target",
                },
                "model_input": model_input,
                "loss_mask": loss_mask,
                "authority": dict(AUTHORITY_CLOSED),
                "anti_cheat": anti_cheat,
                "target_token_len_estimate": len(clean_target.split()),
                "generation_prefix_field": GENERATION_PREFIX_FIELD,
            }
        )
        rows.append(row)
    return rows, holdout


def audit_rows(rows: list[dict[str, Any]], holdout: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    split_counts = Counter(str(row.get("split")) for row in rows)
    language_counts = Counter(str(row.get("language_family")) for row in rows)
    repair_bucket_counts = Counter(str((row.get("target") or {}).get("repair_bucket")) for row in rows)
    active_loss_counts = Counter(tuple(active_losses(row)) for row in rows)
    prefix_bad: list[dict[str, str]] = []
    target_visible: list[str] = []
    unsafe_rows: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id"))
        target = str((row.get("target") or {}).get("decoder_text") or row.get("decoder_text") or "")
        prefix = str(nested_value(row, GENERATION_PREFIX_FIELD) or "")
        model_input_text = json.dumps(row.get("model_input") or {}, sort_keys=True)
        if not prefix:
            prefix_bad.append({"row_id": row_id, "reason": "missing_prefix"})
        elif len(prefix.split()) > 8 or len(prefix) > 96:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_over_cap"})
        elif prefix == target:
            prefix_bad.append({"row_id": row_id, "reason": "prefix_is_full_target"})
        elif not target.startswith(prefix):
            prefix_bad.append({"row_id": row_id, "reason": "prefix_not_target_start"})
        if target and target in model_input_text:
            target_visible.append(row_id)
        if any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED):
            unsafe_rows.append(row_id)
        if active_losses(row) != ["denoise_ce"]:
            unsafe_rows.append(row_id)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9604_not_passed")
    if len(rows) != 26:
        failures.append("unexpected_prefix_primed_row_count")
    if len(holdout) != 15:
        failures.append("unexpected_holdout_row_count")
    if prefix_bad:
        failures.append("prefix_contract_failures")
    if target_visible:
        failures.append("full_target_visible_in_model_input")
    if unsafe_rows:
        failures.append("unsafe_or_wrong_loss_rows")
    return {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "holdout": str(HOLDOUt.relative_to(ROOT)),
        "rows": len(rows),
        "holdout_rows": len(holdout),
        "split_counts": dict(split_counts),
        "language_counts": dict(language_counts),
        "repair_bucket_counts": dict(repair_bucket_counts),
        "active_loss_counts": {",".join(key): value for key, value in active_loss_counts.items()},
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "prefix_bad_rows": prefix_bad,
        "full_target_visible_rows": target_visible,
        "unsafe_rows": unsafe_rows,
        "decoder_ce_rows": 0,
        "runtime_rows": 0,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows, holdout = build_rows(load_jsonl(SOURCE_MANIFEST))
    write_jsonl(MANIFEST, rows)
    write_jsonl(HOLDOUt, holdout)
    audit = audit_rows(rows, holdout, source)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9606 contract-only two-phase preflight with --phase2-manifest Stage9605 and --generation-prefix-field model_input.active_generation_prefix_span."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "holdout": str(HOLDOUt.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Rebuilt residual denoise phase-2 rows on natural bounded clean targets with a short active generation prefix and denoise-only loss. Missing clean-target rows are held out.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9605 Prefix-Primed Residual Denoise Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Holdout rows: `{audit['holdout_rows']}`",
                f"Splits: `{audit['split_counts']}`",
                f"Generation prefix field: `{GENERATION_PREFIX_FIELD}`",
                "",
                "This patches the Stage9603 failure mode by replacing symbolic decoder targets such as `REPAIR_PREFIX_ONLY :: ...` with the natural bounded clean target from `episode_transition.state_t_plus_1.decoder_text`.",
                "",
                "The visible prefix is short and audited; the full target/suffix is not placed in model input. Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": audit["failures"], "rows": audit["rows"], "holdout_rows": audit["holdout_rows"], "next_best_step": next_step}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
