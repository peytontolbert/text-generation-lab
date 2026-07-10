#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10092
NAME = "stage10092_canonical_source_heldout_realistic_shell_shortcut_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "canonical_source_heldout_realistic_shell_shortcut_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_SOURCE_HELDOUT_REALISTIC_SHELL_SHORTCUT_AUDIT_STAGE10092.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10088_canonical_source_heldout_realistic_maintenance_shell/canonical_source_heldout_realistic_maintenance_shell_manifest.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage10091_canonical_source_heldout_realistic_shell_same_manifest_comparison_audit/canonical_source_heldout_realistic_shell_same_manifest_comparison_audit.json"

FIELD_NAMES = (
    "failure_text",
    "trace_excerpt",
    "relevant_snippets",
    "candidate_paths",
    "test_assertion",
    "expected_vs_actual",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def row_field(row: dict[str, Any], field: str) -> Any:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    return state.get(field)


def hidden_target(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("edit_localization_target_hidden") or "")


def split_value(row: dict[str, Any]) -> str:
    return str(row.get("split") or "")


def language_value(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or "")


def shell_signature(row: dict[str, Any]) -> str:
    payload = {field: row_field(row, field) for field in FIELD_NAMES}
    payload["language_family"] = language_value(row)
    return normalize(payload)


def _field_shortcut_metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    heldout_total = 0
    heldout_correct = 0
    for row in rows:
        key = normalize(row_field(row, field))
        buckets[key][hidden_target(row)] += 1
    for row in rows:
        if split_value(row) != "eval":
            continue
        heldout_total += 1
        key = normalize(row_field(row, field))
        predicted = buckets[key].most_common(1)[0][0]
        if predicted == hidden_target(row):
            heldout_correct += 1
    deterministic_values = sum(1 for counter in buckets.values() if len(counter) == 1)
    return {
        "unique_values": len(buckets),
        "deterministic_value_count": deterministic_values,
        "deterministic_value_rate": round(deterministic_values / max(len(buckets), 1), 6),
        "heldout_majority_lookup_exact": round(heldout_correct / max(heldout_total, 1), 6),
    }


def _per_language_shell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_lang[language_value(row)].append(row)
    payload: dict[str, Any] = {}
    for language, group in sorted(by_lang.items()):
        heldout = [row for row in group if split_value(row) in {"eval", "strict_eval"}]
        sig_to_targets: dict[str, set[str]] = defaultdict(set)
        for row in heldout:
            sig_to_targets[shell_signature(row)].add(hidden_target(row))
        exact = sum(1 for row in heldout if len(sig_to_targets[shell_signature(row)]) == 1) / max(len(heldout), 1)
        payload[language] = {
            "heldout_rows": len(heldout),
            "unique_shell_signatures": len(sig_to_targets),
            "hidden_target_families": len({hidden_target(row) for row in heldout}),
            "single_signature_to_single_target_rate": round(exact, 6),
        }
    return payload


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    comparison = load_json(COMPARISON)
    heldout = [row for row in rows if split_value(row) in {"eval", "strict_eval"}]
    field_metrics = {field: _field_shortcut_metrics(rows, field) for field in FIELD_NAMES}

    heldout_shell_buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for row in heldout:
        heldout_shell_buckets[shell_signature(row)][hidden_target(row)] += 1
    shell_lookup_exact = sum(
        1
        for row in heldout
        if heldout_shell_buckets[shell_signature(row)].most_common(1)[0][0] == hidden_target(row)
    ) / max(len(heldout), 1)

    metrics = {
        "rows": len(rows),
        "heldout_rows": len(heldout),
        "macro_exact_100m_l2_shell": ((comparison.get("metrics") or {}).get("macro_exact_100m")),
        "macro_exact_gemma_l2_shell": ((comparison.get("metrics") or {}).get("macro_exact_gemma")),
        "field_shortcut_metrics": field_metrics,
        "heldout_unique_shell_signatures": len(heldout_shell_buckets),
        "heldout_shell_signature_majority_lookup_exact": round(shell_lookup_exact, 6),
        "heldout_shell_signatures_per_target_family": {
            target: sum(1 for signature_targets in heldout_shell_buckets.values() if target in signature_targets)
            for target in sorted({hidden_target(row) for row in heldout})
        },
        "per_language_shell_metrics": _per_language_shell(rows),
    }

    failures: list[str] = []
    if metrics["heldout_rows"] != 55:
        failures.append("heldout_row_count_not_55")
    if metrics["heldout_shell_signature_majority_lookup_exact"] < 0.95:
        failures.append("shell_signature_shortcut_not_strong_enough_for_claim")

    findings = [
        "The realistic shell is materially harder for the 100M than the narrow canonical packet, but it remains a small family of synthetic templates rather than independent maintainer cases.",
        "The shell-signature lookup is effectively perfect on the heldout set, which means a deterministic template family mapping can recover the hidden target family without modeling real repository variation.",
        "The next honest move is to preserve the canonical labels and source-heldout split while replacing synthetic shell fields with source-backed failure, trace, snippet, and candidate evidence mined from independent roots.",
    ]

    next_best_step = (
        "Use the stage10092 shortcut findings to build a source-backed realistic successor request that materializes real heldout failure, trace, snippet, and candidate evidence from the preserved source-backed roots."
    )

    packet = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "manifest": display(MANIFEST),
            "comparison": display(COMPARISON),
        },
        "claim_boundary": {
            "expert_maintainer_realism_supported": False,
            "reason": "The prompt-visible L2 shell is still shortcutable through a small deterministic template family and remains synthetic rather than source-materialized.",
            "structured_realistic_shell_supported": True,
            "same_manifest_compare_subset": "eval_plus_strict_eval",
        },
        "metrics": metrics,
        "findings": findings,
        "failures": failures,
        "next_best_step": next_best_step,
    }
    return packet


def write_doc(packet: dict[str, Any]) -> None:
    metrics = packet["metrics"]
    lines = [
        "# Stage10092 Canonical Source Heldout Realistic Shell Shortcut Audit",
        "",
        f"Passed: `{packet['passed']}`",
        f"Heldout rows: `{metrics['heldout_rows']}`",
        f"Heldout unique shell signatures: `{metrics['heldout_unique_shell_signatures']}`",
        f"Heldout shell-signature lookup exact: `{metrics['heldout_shell_signature_majority_lookup_exact']}`",
        "",
        "The L2 realistic shell is harder than the narrow canonical taxonomy packet, but it is still too templated to count as expert-maintainer evidence. A deterministic shell-signature lookup recovers the hidden target family on the heldout rows, which means the current surface can still be solved through synthetic template families rather than broad maintenance reasoning.",
        "",
        "Next: Materialize a source-backed realistic successor that preserves the heldout split and canonical labels while replacing synthetic shell fields with mined failure text, traces, snippets, and candidate evidence from the underlying roots.",
        "",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    packet = build()
    write_json(PACKET, packet)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": packet["passed"],
        "artifacts": packet["artifacts"],
        "metrics": packet["metrics"],
        "next_best_step": packet["next_best_step"],
    }
    write_json(SUMMARY, summary)
    write_doc(packet)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": packet["passed"], "failures": packet["failures"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
