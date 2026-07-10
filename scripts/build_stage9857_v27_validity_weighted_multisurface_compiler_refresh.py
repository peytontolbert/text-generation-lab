#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from curriculum_compiler import compile_rows
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import load_locked_source_ids_from_exclusions
except ModuleNotFoundError:
    from scripts.curriculum_compiler import compile_rows  # type: ignore
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import load_locked_source_ids_from_exclusions  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9857
NAME = "stage9857_v27_validity_weighted_multisurface_compiler_refresh"
LOCKED_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREPARED = OUT_DIR / "validity_weighted_multisurface_prepared_rows.jsonl"
COMPILED_DIR = OUT_DIR / "compiled"
AUDIT = OUT_DIR / "validity_weighted_multisurface_compiler_refresh_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_VALIDITY_WEIGHTED_MULTISURFACE_COMPILER_REFRESH_STAGE9857.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

_stage9693_path = ROOT / "scripts/build_stage9693_locked_guarded_source_backed_multisurface_compiler_refresh.py"
_stage9693_spec = importlib.util.spec_from_file_location("stage9693_for_9857", _stage9693_path)
_stage9693 = importlib.util.module_from_spec(_stage9693_spec)
assert _stage9693_spec and _stage9693_spec.loader
sys.modules["stage9693_for_9857"] = _stage9693
_stage9693_spec.loader.exec_module(_stage9693)

SOURCES = {
    "symbol_binding": {
        "kind": "normalize_from_source_candidate",
        "path": ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl",
        "target_loss": "symbol_binding_ce",
        "source_audit": ROOT / "runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit.json",
    },
    "edit_localization": {
        "kind": "direct_ready_rows",
        "path": ROOT / "runs/local/artifacts/stage9833_permuted_choice_execution_manifest/permuted_choice_execution_manifest.jsonl",
        "target_loss": "edit_localization_ce",
        "source_audit": ROOT / "runs/summaries/stage9833_permuted_choice_execution_manifest.json",
    },
    "patch_operator_selection": {
        "kind": "direct_ready_rows",
        "path": ROOT / "runs/local/artifacts/stage9854_multisurface_abstention_honesty_manifests/multilingual_patch_operator_abstention_honesty.jsonl",
        "target_loss": "patch_operator_ce",
        "source_audit": ROOT / "runs/summaries/stage9854_multisurface_abstention_honesty_manifests.json",
    },
    "verifier_failure_repair_or_abstain": {
        "kind": "direct_ready_rows",
        "path": ROOT / "runs/local/artifacts/stage9854_multisurface_abstention_honesty_manifests/multilingual_verifier_repair_abstention_honesty.jsonl",
        "target_loss": "verifier_repair_ce",
        "source_audit": ROOT / "runs/summaries/stage9854_multisurface_abstention_honesty_manifests.json",
    },
    "bounded_argument_rendering": {
        "kind": "normalize_from_source_candidate",
        "path": ROOT / "runs/local/artifacts/stage9240_source_backed_multilang_bounded_decoder_tiny_package/source_backed_multilang_bounded_decoder_tiny_manifest.jsonl",
        "target_loss": "decoder_ce",
        "source_audit": ROOT / "runs/summaries/stage9241_multilang_source_backed_target_100m_contract_only_preflight.json",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def _normalize_ready_row(row: dict[str, Any], skill: str, target_loss: str, source_audit: Path) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    source_audit_path = source_audit if source_audit.is_absolute() else (ROOT / source_audit)
    out["row_id"] = f"stage9857_{skill}_{row.get('row_id')}"
    out["source_row_id"] = row.get("source_row_id") or row.get("row_id")
    out["source_skill_area"] = skill
    out["expected_enabled_loss"] = target_loss
    out["gate_status_materialized_from"] = str(source_audit_path.relative_to(ROOT))
    out["locked_guard_refresh_stage"] = NAME
    out["authority"] = dict(AUTHORITY_CLOSED)
    anti = out.get("anti_cheat") if isinstance(out.get("anti_cheat"), dict) else {}
    anti["stage9857_validity_weighted_refresh"] = True
    out["anti_cheat"] = anti
    return out


def build_prepared_rows() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for skill, spec in SOURCES.items():
        source_rows = read_jsonl(spec["path"])
        audit = load_json(spec["source_audit"])
        if not source_rows:
            failures.append(f"missing_source_rows:{skill}")
            continue
        if audit.get("passed") is not True:
            failures.append(f"source_audit_not_passed:{skill}")
            continue
        if spec["kind"] == "normalize_from_source_candidate":
            for row in source_rows:
                rows.append(_stage9693.normalize_row(row, skill, str(spec["target_loss"])))
        elif spec["kind"] == "direct_ready_rows":
            for row in source_rows:
                rows.append(_normalize_ready_row(row, skill, str(spec["target_loss"]), Path(spec["source_audit"])))
        else:
            failures.append(f"unknown_source_kind:{skill}")
    return rows, failures


def audit_compiled(prepared: list[dict[str, Any]], compile_card: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    expected_loss_counts = Counter(str(row.get("expected_enabled_loss") or "") for row in prepared)
    actual_loss_counts = Counter({key: count for key, count in (compile_card.get("loss_counts") or {}).items() if count})
    if dict(actual_loss_counts) != dict(expected_loss_counts):
        failures.append("loss_counts_do_not_match_expected_single_surface_masks")
    if compile_card.get("gate_rejected_rows") != 0:
        failures.append("gate_rejected_rows_nonzero")
    if compile_card.get("locked_source_exclusion_rows") != 0:
        failures.append("locked_source_exclusion_rows_nonzero")
    if (compile_card.get("loss_counts") or {}).get("denoise_ce", 0) != 0 or (compile_card.get("loss_counts") or {}).get("runtime_reward", 0) != 0:
        failures.append("forbidden_loss_enabled")
    skill_counts = Counter(str(row.get("source_skill_area") or "") for row in prepared)
    split_counts = Counter(str(row.get("split") or "") for row in prepared)
    language_counts = Counter(str(row.get("language_family") or "") for row in prepared)
    return {
        "passed": not failures,
        "failures": failures,
        "rows": len(prepared),
        "skill_counts": dict(sorted(skill_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "expected_loss_counts": dict(sorted(expected_loss_counts.items())),
        "actual_loss_counts": dict(sorted(actual_loss_counts.items())),
        "compiler_card": compile_card,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    prepared, failures = build_prepared_rows()
    write_jsonl(PREPARED, prepared)
    locked_source_ids = load_locked_source_ids_from_exclusions(LOCKED_EXCLUSIONS)
    buckets, compile_card = compile_rows(
        prepared,
        allow_decoder=True,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=True,
        locked_source_ids=locked_source_ids,
    )
    COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    for objective, rows in buckets.items():
        write_jsonl(COMPILED_DIR / f"{objective}.jsonl", rows)
    (COMPILED_DIR / "compile_card.json").write_text(json.dumps(compile_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit = audit_compiled(prepared, compile_card)
    failures.extend(audit["failures"])
    audit["passed"] = not failures
    audit["failures"] = failures
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this validity-weighted compiled package as the next v2.7 training mix: stronger multilingual edit-localization winner surface in, abstention-only patch/verifier guardrails in, and stale forced-action rows out."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": failures,
            "rows": audit["rows"],
            "skill_counts": audit["skill_counts"],
            "split_counts": audit["split_counts"],
            "language_counts": audit["language_counts"],
            "loss_counts": audit["actual_loss_counts"],
        },
        "artifacts": {
            "prepared_manifest": str(PREPARED.relative_to(ROOT)),
            "compiled_dir": str(COMPILED_DIR.relative_to(ROOT)),
            "compile_card": str((COMPILED_DIR / "compile_card.json").relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built a validity-weighted successor to the old v2.7 multisurface compiler refresh: the stronger multilingual edit-localization winner packet replaces the stale source candidate bank, and the structurally invalid patch/verifier forced-action banks are replaced by abstention-only honesty manifests.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9857 V2.7 Validity-Weighted Multisurface Compiler Refresh",
                "",
                f"Passed: `{summary['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Skill counts: `{audit['skill_counts']}`",
                f"Loss counts: `{audit['actual_loss_counts']}`",
                "",
                "This stage replaces the old v2.7 multisurface training mix with a validity-weighted successor: stronger multilingual edit localization goes in, explicit abstention guardrails replace invalid hard surfaces, and single-surface loss masks remain enforced.",
                "",
                "No runtime, source/body emission, Gemma, harness, scoring, model execution, checkpoint export, or promotion is authorized by this stage.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": audit["rows"], "skill_counts": audit["skill_counts"], "loss_counts": audit["actual_loss_counts"], "failures": failures}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
