from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

ROUTE_TO_LOSSES = {
    "KEEP_STRUCTURED": [
        "surface_role_ce",
        "repair_surface_ce",
        "build_mode_ce",
        "allowed_import_policy_ce",
        "blocked_import_policy_ce",
        "repo_dependency_policy_ce",
        "action_sequence_ce",
        "file_plan_ce",
        "symbol_binding_ce",
        "edit_localization_ce",
        "patch_operator_ce",
        "verifier_repair_ce",
    ],
    "KEEP_BOUNDED_DECODER": ["decoder_ce"],
    "USE_FOR_DENOISE_REPAIR": ["denoise_ce"],
    "USE_AS_NEGATIVE": ["action_sequence_ce"],
    "NEEDS_RETRIEVAL": ["action_sequence_ce"],
    "HOLD_LONG_OUTPUT": [],
    "QUARANTINE_LABEL_CONFLICT": [],
    "DROP_DUPLICATE": [],
    "NEEDS_HUMAN_REVIEW": [],
}

LOSS_KEYS = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
]

OBJECTIVE_BY_ROUTE = {
    "KEEP_STRUCTURED": "structured_state",
    "KEEP_BOUNDED_DECODER": "bounded_decoder_ce",
    "USE_FOR_DENOISE_REPAIR": "denoise_repair",
    "USE_AS_NEGATIVE": "negative_control",
    "NEEDS_RETRIEVAL": "retrieval_control",
    "HOLD_LONG_OUTPUT": "long_output_holdout",
    "QUARANTINE_LABEL_CONFLICT": "quarantine",
    "DROP_DUPLICATE": "drop_duplicate",
    "NEEDS_HUMAN_REVIEW": "human_review",
}

REQUIRED_RECOVERED_GATE_REFERENCES = [
    "source_inventory_lineage",
    "source_provenance",
    "contamination_leakage_detector",
    "golden_locked_eval_suite",
    "drift_canary_regression_monitor",
    "cluster_slice_near_duplicate_detector",
    "dataset_junk_ood_ranker_v1",
    "schema_drift_detector",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("row must be object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def split_of(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "train")


def route_of(row: dict[str, Any]) -> str:
    return str(row.get("route") or row.get("risk_bucket") or row.get("dataset_route") or "KEEP_STRUCTURED")


def gate_status_of(row: dict[str, Any]) -> dict[str, bool]:
    status = row.get("gate_status")
    if isinstance(status, dict):
        return {str(key): bool(value) for key, value in status.items()}
    return {}


def missing_or_failed_recovered_gates(row: dict[str, Any]) -> list[str]:
    status = gate_status_of(row)
    return [key for key in REQUIRED_RECOVERED_GATE_REFERENCES if status.get(key) is not True]


def build_loss_mask(route: str, row: dict[str, Any], *, allow_decoder: bool, allow_denoise: bool, allow_runtime: bool) -> dict[str, bool]:
    mask = {key: False for key in LOSS_KEYS}
    for key in ROUTE_TO_LOSSES.get(route, []):
        mask[key] = True
    if not allow_decoder:
        mask["decoder_ce"] = False
    if not allow_denoise:
        mask["denoise_ce"] = False
    if not allow_runtime:
        mask["runtime_reward"] = False
    # Explicit per-row overrides can only disable losses in the compiler.
    disabled = row.get("disable_losses") if isinstance(row.get("disable_losses"), list) else []
    for key in disabled:
        if key in mask:
            mask[key] = False
    return mask


def compile_rows(rows: list[dict[str, Any]], *, allow_decoder: bool, allow_denoise: bool, allow_runtime: bool, require_recovered_gates: bool = False) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    loss_counts: Counter[str] = Counter()
    rejected: list[dict[str, Any]] = []
    gate_rejected: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        route = route_of(row)
        failed_gates = missing_or_failed_recovered_gates(row) if require_recovered_gates else []
        if failed_gates:
            route = "NEEDS_HUMAN_REVIEW"
        objective = OBJECTIVE_BY_ROUTE.get(route, "quarantine")
        route_counts[route] += 1
        split_counts[split_of(row)] += 1
        out = dict(row)
        out.setdefault("row_id", f"compiled_row_{index:06d}")
        out["route"] = route
        out["objective_family"] = objective
        out["authority"] = dict(AUTHORITY_CLOSED)
        if failed_gates:
            out["compiler_block_reasons"] = ["missing_or_failed_recovered_gates"]
            out["missing_or_failed_recovered_gates"] = failed_gates
        out["loss_mask"] = build_loss_mask(route, row, allow_decoder=allow_decoder, allow_denoise=allow_denoise, allow_runtime=allow_runtime)
        for key, enabled in out["loss_mask"].items():
            loss_counts[key] += int(enabled)
        if objective in {"quarantine", "drop_duplicate", "human_review"}:
            rejected.append({"row_id": out["row_id"], "route": route, "objective_family": objective})
        if failed_gates:
            gate_rejected.append({"row_id": out["row_id"], "missing_or_failed_recovered_gates": failed_gates})
        buckets[objective].append(out)
    card = {
        "rows": len(rows),
        "route_counts": dict(route_counts),
        "split_counts": dict(split_counts),
        "loss_counts": dict(loss_counts),
        "objective_counts": {key: len(value) for key, value in buckets.items()},
        "rejected_or_holdout_examples": rejected[:100],
        "gate_rejected_examples": gate_rejected[:100],
        "gate_rejected_rows": len(gate_rejected),
        "required_recovered_gate_references": REQUIRED_RECOVERED_GATE_REFERENCES,
        "authority": dict(AUTHORITY_CLOSED),
        "compiler_options": {
            "allow_decoder": allow_decoder,
            "allow_denoise": allow_denoise,
            "allow_runtime": allow_runtime,
            "require_recovered_gates": require_recovered_gates,
        },
    }
    return dict(buckets), card


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compile routed dataset rows into objective-specific training manifests with loss masks.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--allow-decoder", action="store_true")
    p.add_argument("--allow-denoise", action="store_true")
    p.add_argument("--allow-runtime", action="store_true")
    p.add_argument("--require-recovered-gates", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    buckets, card = compile_rows(read_jsonl(args.input), allow_decoder=args.allow_decoder, allow_denoise=args.allow_denoise, allow_runtime=args.allow_runtime, require_recovered_gates=args.require_recovered_gates)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for objective, rows in buckets.items():
        write_jsonl(args.output_dir / f"{objective}.jsonl", rows)
    (args.output_dir / "compile_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
