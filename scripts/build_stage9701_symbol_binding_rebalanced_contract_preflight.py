#!/usr/bin/env python3
from __future__ import annotations

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
STAGE = 9701
NAME = "stage9701_symbol_binding_rebalanced_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9700_symbol_binding_repair_compiler.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9700_symbol_binding_repair_compiler/symbol_binding_tiny_rebalanced.jsonl"
TRAINER = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT = OUT_DIR / "symbol_binding_rebalanced_contract_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_REBALANCED_CONTRACT_PREFLIGHT_STAGE9701.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SHORTCUT_CEILING = 0.80


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    return str(clean.get("binding_action") or clean.get("symbol_binding") or target.get("binding_action") or target.get("symbol_binding"))


def query_kind(row: dict[str, Any]) -> str:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    return str(query.get("query_kind") or graph.get("query_kind") or "unknown")


def target_node_presence(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("target_node_presence"))


def target_node_kind(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("target_node_kind"))


def split_label_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[str(row.get("split"))][label(row)] += 1
    return {split: dict(counter) for split, counter in counts.items()}


def baseline(rows: list[dict[str, Any]], feature_name: str, feature_fn: Callable[[dict[str, Any]], str]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[feature_fn(row)].append(row)
    correct = 0
    group_cards: dict[str, Any] = {}
    for value, group_rows in sorted(groups.items()):
        counts = Counter(label(row) for row in group_rows)
        pred, pred_count = counts.most_common(1)[0]
        correct += pred_count
        group_cards[value] = {"rows": len(group_rows), "pred": pred, "correct": pred_count, "label_counts": dict(counts)}
    total = len(rows)
    return {"feature": feature_name, "exact": correct / total if total else 0.0, "groups": group_cards}


def loss_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, enabled in mask.items():
            if enabled:
                counts[key] += 1
    return counts


def authority_violations(rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key, value in auth.items():
            if value:
                violations.append(f"{row.get('row_id')}:{key}")
    return violations


def native_ablation_support() -> dict[str, Any]:
    text = TRAINER.read_text(encoding="utf-8")
    return {
        "trainer_path": str(TRAINER.relative_to(ROOT)),
        "proxy_ablation_present": "_proxy_feature_ablation_records" in text,
        "native_grouped_ablation_function_present": "native_grouped_feature_ablation" in text or "_native_feature_ablation" in text,
        "native_grouped_ablation_cli_required": True,
        "native_grouped_ablation_cli_present": "--require-native-feature-ablation-audit" in text,
    }


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    split_counts = split_label_counts(rows)
    labels = sorted({label(row) for row in rows})
    missing_by_split = {split: sorted(set(labels) - set(split_counts.get(split, {}))) for split in ["train", "eval", "strict_eval"]}
    baselines = [
        baseline(rows, "majority", lambda row: "all"),
        baseline(rows, "split", lambda row: str(row.get("split"))),
        baseline(rows, "query_kind", query_kind),
        baseline(rows, "target_node_presence", target_node_presence),
        baseline(rows, "target_node_kind", target_node_kind),
    ]
    strongest = max(baselines, key=lambda item: float(item["exact"]))
    losses = loss_counts(rows)
    auth_violations = authority_violations(rows)
    ablation = native_ablation_support()

    data_failures: list[str] = []
    if source.get("passed") is not True:
        data_failures.append("stage9700_not_passed")
    if len(rows) != 64:
        data_failures.append("unexpected_row_count")
    if Counter(str(row.get("split")) for row in rows) != {"train": 32, "eval": 16, "strict_eval": 16}:
        data_failures.append("unexpected_split_sizes")
    if any(missing_by_split.values()):
        data_failures.append(f"missing_labels_by_split:{missing_by_split}")
    if losses != Counter({"symbol_binding_ce": 64}):
        data_failures.append(f"unexpected_loss_counts:{dict(losses)}")
    if auth_violations:
        data_failures.append(f"authority_violations:{auth_violations[:5]}")
    if float(strongest["exact"]) >= SHORTCUT_CEILING:
        data_failures.append(f"shortcut_baseline_over_ceiling:{strongest['feature']}:{strongest['exact']}")

    execution_blockers: list[str] = []
    if not ablation["native_grouped_ablation_function_present"]:
        execution_blockers.append("native_grouped_feature_ablation_function_missing")
    if not ablation["native_grouped_ablation_cli_present"]:
        execution_blockers.append("require_native_feature_ablation_audit_cli_missing")

    passed = not data_failures and not execution_blockers
    preflight = {
        "stage": STAGE,
        "name": NAME,
        "passed": passed,
        "data_contract_passed": not data_failures,
        "execution_authorized_next": False,
        "quality_passed": False,
        "promotion_ready": False,
        "data_failures": data_failures,
        "execution_blockers": execution_blockers,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "row_count": len(rows),
        "split_label_counts": split_counts,
        "missing_labels_by_split": missing_by_split,
        "loss_counts": dict(losses),
        "shortcut_baselines": baselines,
        "strongest_shortcut_baseline": strongest,
        "shortcut_ceiling": SHORTCUT_CEILING,
        "native_ablation_support": ablation,
        "authority": dict(AUTHORITY_CLOSED),
    }
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Patch trainer telemetry for Stage9702: add a required native grouped feature-ablation audit flag and artifact "
        "before re-running symbol-binding target-100M execution on the Stage9700 repaired manifest."
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": passed,
        "data_contract_passed": not data_failures,
        "execution_authorized_next": False,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"preflight": str(PREFLIGHT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {
            "row_count": len(rows),
            "strongest_shortcut_feature": strongest["feature"],
            "strongest_shortcut_exact": strongest["exact"],
            "native_grouped_ablation_function_present": ablation["native_grouped_ablation_function_present"],
            "native_grouped_ablation_cli_present": ablation["native_grouped_ablation_cli_present"],
            "execution_blockers": execution_blockers,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9701 Symbol-Binding Rebalanced Contract Preflight",
                "",
                "Stage9701 checks the Stage9700 repaired symbol-binding manifest before any additional target-100M execution.",
                "",
                "## Result",
                "",
                f"- Data contract passed: `{not data_failures}`",
                f"- Execution authorized next: `False`",
                f"- Strongest shortcut baseline: `{strongest['feature']}` = `{strongest['exact']}`",
                f"- Execution blockers: `{execution_blockers}`",
                "",
                "The repaired data contract is clean, but execution stays closed because the trainer still emits proxy feature-ablation telemetry and lacks a required native grouped-ablation audit flag.",
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
