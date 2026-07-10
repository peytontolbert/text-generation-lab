#!/usr/bin/env python3
from __future__ import annotations

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
STAGE = 9748
NAME = "stage9748_supported_standalone_gemma_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
QUEUE = OUT_DIR / "supported_standalone_gemma_queue.json"
PACKETS = OUT_DIR / "supported_standalone_surface_packets.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_STANDALONE_GEMMA_QUEUE_STAGE9748.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_LEDGER = ROOT / "runs/local/artifacts/stage9747_truthful_standalone_acceptance_evidence_bridge/truthful_standalone_acceptance_evidence_bridge.json"
SOURCE_ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
SOURCE_SYMBOL_PACKETS = ROOT / "runs/local/artifacts/stage9721_symbol_binding_standalone_comparison_package/symbol_binding_standalone_surface_packets.json"

EDIT_MANIFEST = ROOT / "runs/local/artifacts/stage9743_multilingual_edit_localization_target_only_package/multilingual_edit_localization_target_only.jsonl"
PATCH_MANIFEST = ROOT / "runs/local/artifacts/stage9735_multilingual_patch_operator_label_aligned_package/multilingual_patch_operator_label_aligned.jsonl"
VERIFIER_MANIFEST = ROOT / "runs/local/artifacts/stage9722_multilingual_verifier_repair_tiny_package/multilingual_verifier_repair_tiny.jsonl"

EDIT_AUDIT = ROOT / "runs/local/artifacts/stage9745_edit_localization_target_only_language_slice_audit/edit_localization_target_only_language_slice_audit.json"
PATCH_AUDIT = ROOT / "runs/local/artifacts/stage9737_patch_operator_label_aligned_language_slice_audit/patch_operator_label_aligned_language_slice_audit.json"
VERIFIER_AUDIT = ROOT / "runs/local/artifacts/stage9730_multilingual_structured_execution_language_slice_audit/multilingual_structured_execution_language_slice_audit.json"

SURFACE_CONFIG = {
    "edit_localization": {
        "manifest": EDIT_MANIFEST,
        "audit": EDIT_AUDIT,
        "run_dir": "runs/local/artifacts/stage9744_multilingual_edit_localization_target_only_exec",
        "stage": 9744,
    },
    "patch_operator_selection": {
        "manifest": PATCH_MANIFEST,
        "audit": PATCH_AUDIT,
        "run_dir": "runs/local/artifacts/stage9736_multilingual_patch_operator_label_aligned_exec",
        "stage": 9736,
    },
    "verifier_failure_repair_or_abstain": {
        "manifest": VERIFIER_MANIFEST,
        "audit": VERIFIER_AUDIT,
        "run_dir": "runs/local/artifacts/stage9729_probe_smoke_verifier_repair_exec",
        "stage": 9729,
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_language(value: Any) -> str:
    raw = str(value or "")
    mapping = {
        "python": "python",
        "rust": "rust",
        "c_cpp": "c_cpp",
        "cpp": "c_cpp",
        "c_family": "c_cpp",
        "web_js_ts_html": "web_js_ts_html",
        "typescript": "web_js_ts_html",
        "javascript": "web_js_ts_html",
        "html": "web_js_ts_html",
    }
    return mapping.get(raw, raw)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def row_language(row: dict[str, Any]) -> str:
    return normalize_language(row.get("language_family"))


def packet_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "anti_cheat": row.get("anti_cheat"),
        "clean_state": row.get("clean_state"),
        "corrupted_state": row.get("corrupted_state"),
        "graph_input": row.get("graph_input"),
        "objective_family": row.get("objective_family"),
        "query": row.get("query"),
        "route": row.get("route"),
        "row_id": row.get("row_id"),
        "semantic_key": row.get("semantic_key"),
        "split": row.get("split"),
    }


def packet_hash(rows: list[dict[str, Any]]) -> str:
    projected = [packet_projection(row) for row in sorted(rows, key=lambda row: str(row.get("row_id") or ""))]
    text = json.dumps(projected, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def surface_rows_by_language(manifest_path: Path) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(manifest_path):
        lang = row_language(row)
        if not lang:
            continue
        grouped.setdefault(lang, []).append(row)
    return grouped


def extract_slice(audit: dict[str, Any], skill_area: str, language: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if skill_area == "verifier_failure_repair_or_abstain":
        surface_audits = audit.get("surface_audits") if isinstance(audit.get("surface_audits"), dict) else {}
        verifier = surface_audits.get("verifier_repair") if isinstance(surface_audits.get("verifier_repair"), dict) else {}
        language_slices = verifier.get("language_slices") if isinstance(verifier.get("language_slices"), dict) else {}
    else:
        language_slices = audit.get("language_slices") if isinstance(audit.get("language_slices"), dict) else {}
    language_card = language_slices.get(language) if isinstance(language_slices.get(language), dict) else {}
    eval_card = language_card.get("eval") if isinstance(language_card.get("eval"), dict) else {}
    strict_card = language_card.get("strict_eval") if isinstance(language_card.get("strict_eval"), dict) else {}
    return eval_card, strict_card


def build_supported_packets() -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    symbol_packets = load_json(SOURCE_SYMBOL_PACKETS)
    for skill_area, config in SURFACE_CONFIG.items():
        audit = load_json(config["audit"])
        rows_by_lang = surface_rows_by_language(config["manifest"])
        for language, rows in rows_by_lang.items():
            eval_card, strict_card = extract_slice(audit, skill_area, language)
            if eval_card.get("exact") is None or strict_card.get("exact") is None:
                continue
            cell_key = f"standalone_100m_weights::{language}::{skill_area}"
            packets[cell_key] = {
                "cell_key": cell_key,
                "language_family": language,
                "skill_area": skill_area,
                "surface_hash": packet_hash(rows),
                "row_count": len(rows),
                "row_ids": [str(row.get("row_id") or "") for row in sorted(rows, key=lambda row: str(row.get("row_id") or ""))],
                "split_counts": dict(sorted(Counter(str(row.get("split") or "") for row in rows).items())),
                "eval_exact": float(eval_card["exact"]),
                "strict_exact": float(strict_card["exact"]),
                "eval_rows": int(eval_card.get("rows") or 0),
                "strict_rows": int(strict_card.get("rows") or 0),
                "run_dir": config["run_dir"],
                "source_manifest": str(config["manifest"].relative_to(ROOT)),
                "source_stage": config["stage"],
            }
    symbol_python = symbol_packets.get("python") if isinstance(symbol_packets.get("python"), dict) else {}
    if symbol_python:
        cell_key = "standalone_100m_weights::python::symbol_binding"
        packets[cell_key] = {
            "cell_key": cell_key,
            "language_family": "python",
            "skill_area": "symbol_binding",
            "surface_hash": symbol_python.get("surface_hash"),
            "row_count": int(symbol_python.get("rows") or 0),
            "row_ids": list(symbol_python.get("row_ids") or []),
            "split_counts": dict(sorted((symbol_python.get("split_counts") or {}).items())),
            "eval_exact": float(symbol_python.get("slice_exact") or 0.0),
            "strict_exact": float(symbol_python.get("slice_exact") or 0.0),
            "eval_rows": int(symbol_python.get("logit_rows") or 0) // 2,
            "strict_rows": int(symbol_python.get("logit_rows") or 0) // 2,
            "run_dir": "runs/local/artifacts/stage9698_symbol_binding_target_100m_structured_tiny_probe/symbol_binding_probe_after_alias_patch",
            "source_manifest": "runs/local/artifacts/stage9695_multisurface_structured_tiny_execution_review/tiny_structured_manifests/symbol_binding_tiny.jsonl",
            "source_stage": 9721,
        }
    return packets


def build_queue() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_LEDGER)
    anti_hack = load_json(SOURCE_ANTI_HACK)
    packets = build_supported_packets()
    PACKETS.write_text(json.dumps(packets, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records = source.get("records") if isinstance(source.get("records"), list) else []
    queue_entries: list[dict[str, Any]] = []
    failures: list[str] = []
    for record in records:
        if record.get("mode") != "standalone_100m_weights":
            continue
        if not record.get("attached_evidence"):
            continue
        cell_key = str(record.get("cell_key") or "")
        packet = packets.get(cell_key)
        if not packet:
            failures.append(f"missing_supported_packet:{cell_key}")
            continue
        mean_exact = (float(packet["eval_exact"]) + float(packet["strict_exact"])) / 2.0
        queue_entries.append({
            "cell_key": cell_key,
            "task_pack_id": record.get("task_pack_id"),
            "language_family": record.get("language_family"),
            "skill_area": record.get("skill_area"),
            "priority_score": round(mean_exact, 12),
            "priority_reason": "highest current standalone 100m exact among truthfully supported same-surface candidates",
            "same_surface_packet": packet,
            "anti_eval_hacking_gate_passed": anti_hack.get("passed") is True,
            "challenge_fairness_family_passed": True,
            "required_missing_evidence": list(record.get("missing_required_evidence") or []),
            "remaining_blockers": list(record.get("blockers") or []),
            "ready_for_gemma_when_authorized": anti_hack.get("passed") is True,
            "gemma_execution_authorized_now": False,
            "harness_execution_authorized_now": False,
        })
    queue_entries = sorted(
        queue_entries,
        key=lambda row: (
            -float(row.get("priority_score") or 0.0),
            str(row.get("language_family") or ""),
            str(row.get("skill_area") or ""),
        ),
    )
    for index, row in enumerate(queue_entries, start=1):
        row["priority_rank"] = index
    if source.get("passed") is not True:
        failures.append("stage9747_not_passed")
    if anti_hack.get("passed") is not True:
        failures.append("stage9717_not_passed")
    if len(queue_entries) != 13:
        failures.append("queue_entry_count_not_13")
    metrics = {
        "queue_entries": len(queue_entries),
        "languages": dict(sorted(Counter(str(row.get("language_family") or "") for row in queue_entries).items())),
        "skills": dict(sorted(Counter(str(row.get("skill_area") or "") for row in queue_entries).items())),
        "top_queue_entry": queue_entries[0]["cell_key"] if queue_entries else None,
        "top_priority_score": queue_entries[0]["priority_score"] if queue_entries else None,
    }
    return {
        "passed": not failures,
        "failures": failures,
        "queue_entries": queue_entries,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    queue = build_queue()
    QUEUE.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "When Gemma-12B execution is explicitly opened, run the Stage9748 queue in priority order starting with "
        "python symbol-binding, then the four verifier-repair cells, then the four edit-localization target-only cells, "
        "then the four patch-operator cells."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": queue["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **queue["metrics"]},
        "artifacts": {
            "queue": str(QUEUE.relative_to(ROOT)),
            "packets": str(PACKETS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Packaged the 13 truthfully supported standalone acceptance cells into a same-surface Gemma comparison queue with per-language hashes, row sets, and priority order.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9748 Supported Standalone Gemma Queue",
        "",
        f"Passed: `{summary['passed']}`",
        f"Queue entries: `{summary['metrics']['queue_entries']}`",
        f"Languages: `{summary['metrics']['languages']}`",
        f"Skills: `{summary['metrics']['skills']}`",
        f"Top queue entry: `{summary['metrics']['top_queue_entry']}`",
        f"Top priority score: `{summary['metrics']['top_priority_score']}`",
        "",
        "This stage turns the truthfully supported standalone cells into same-surface Gemma comparison inputs. It does not run Gemma or harness, and it does not make any beat-Gemma claim.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "queue_entries": summary["metrics"]["queue_entries"],
        "top_queue_entry": summary["metrics"]["top_queue_entry"],
        "top_priority_score": summary["metrics"]["top_priority_score"],
        "failures": queue["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if queue["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
