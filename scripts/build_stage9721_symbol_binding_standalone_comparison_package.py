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

try:
    from build_stage9719_multilingual_comparison_evidence_bundle_contract import build_template
except ModuleNotFoundError:
    from scripts.build_stage9719_multilingual_comparison_evidence_bundle_contract import build_template  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9721
NAME = "stage9721_symbol_binding_standalone_comparison_package"
SOURCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9695_multisurface_structured_tiny_execution_review/tiny_structured_manifests/symbol_binding_tiny.jsonl"
SOURCE_EXECUTION = ROOT / "runs/local/artifacts/stage9698_symbol_binding_target_100m_structured_tiny_probe/symbol_binding_probe_after_alias_patch/execution_result.json"
SOURCE_LOGITS = ROOT / "runs/local/artifacts/stage9698_symbol_binding_target_100m_structured_tiny_probe/symbol_binding_probe_after_alias_patch/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLES = OUT_DIR / "symbol_binding_standalone_prefilled_comparison_bundles.jsonl"
SURFACES = OUT_DIR / "symbol_binding_standalone_surface_packets.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_STANDALONE_COMPARISON_PACKAGE_STAGE9721.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize_language(value: Any) -> str:
    raw = str(value or "")
    mapping = {
        "cpp": "c_cpp",
        "c_family": "c_cpp",
        "c_cpp": "c_cpp",
        "python": "python",
        "rust": "rust",
        "web_js_ts_html": "web_js_ts_html",
        "typescript": "web_js_ts_html",
        "javascript": "web_js_ts_html",
        "html": "web_js_ts_html",
    }
    return mapping.get(raw, raw)


def row_language(row: dict[str, Any]) -> str:
    top = normalize_language(row.get("language_family"))
    if top and top != "unknown":
        return top
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        features = node.get("features") if isinstance(node.get("features"), dict) else {}
        lang = normalize_language(features.get("language_family"))
        if lang:
            return lang
    return "unknown"


def surface_row_projection(row: dict[str, Any]) -> dict[str, Any]:
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    retrieval = row.get("retrieval_control") if isinstance(row.get("retrieval_control"), dict) else {}
    return {
        "clean_state": clean,
        "graph_id": graph.get("graph_id"),
        "graph_query_kind": graph.get("query_kind"),
        "node_count": len(graph.get("nodes") or []),
        "edge_count": len(graph.get("edges") or []),
        "query": query,
        "retrieval_control": retrieval,
        "row_id": row.get("row_id"),
        "semantic_key": row.get("semantic_key"),
        "split": row.get("split"),
    }


def prompt_surface_hash(rows: list[dict[str, Any]]) -> str:
    payload = [surface_row_projection(row) for row in sorted(rows, key=lambda row: str(row.get("row_id") or ""))]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_language_packets(manifest_rows: list[dict[str, Any]], logit_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    manifest_by_row = {str(row.get("row_id") or ""): row for row in manifest_rows}
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        lang = row_language(row)
        if lang in LANGS:
            grouped_rows[lang].append(row)
    packet: dict[str, dict[str, Any]] = {}
    logits_by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in logit_rows:
        source = manifest_by_row.get(str(row.get("row_id") or ""))
        if not source:
            continue
        lang = row_language(source)
        if lang in LANGS:
            logits_by_lang[lang].append(row)
    for lang in LANGS:
        rows = grouped_rows.get(lang, [])
        logits = logits_by_lang.get(lang, [])
        split_counts = Counter(str(row.get("split") or "") for row in rows)
        correct = sum(1 for row in logits if row.get("correct"))
        total = len(logits)
        packet[lang] = {
            "language_family": lang,
            "surface_hash": prompt_surface_hash(rows),
            "rows": len(rows),
            "split_counts": dict(sorted(split_counts.items())),
            "slice_exact": (correct / total) if total else None,
            "logit_rows": total,
            "row_ids": [str(row.get("row_id") or "") for row in rows],
        }
    return packet


def build_prefilled_bundles(
    ledger_records: list[dict[str, Any]],
    packets: dict[str, dict[str, Any]],
    execution: dict[str, Any],
) -> list[dict[str, Any]]:
    bundles: list[dict[str, Any]] = []
    for record in ledger_records:
        if record.get("mode") != "standalone_100m_weights" or record.get("skill_area") != "symbol_binding":
            continue
        lang = str(record.get("language_family") or "")
        packet = packets[lang]
        bundle = build_template(record)
        if packet["rows"] > 0 and packet["logit_rows"] > 0 and packet["slice_exact"] is not None:
            bundle["same_surface_comparison"]["present"] = True
            bundle["same_surface_comparison"]["prompt_surface_hash_100m"] = packet["surface_hash"]
            bundle["same_surface_comparison"]["score_100m"] = packet["slice_exact"]
            bundle["same_surface_comparison"]["scoring_constraints_hash"] = hashlib.sha256(
                json.dumps(
                    {
                        "fields": execution.get("fields"),
                        "mode": execution.get("mode"),
                        "probe_scale": (execution.get("implementation") or {}).get("probe_scale"),
                        "split_counts": packet["split_counts"],
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            bundle["evidence_artifacts"]["standalone_generation_or_structured_action_outputs"] = str(SOURCE_EXECUTION.relative_to(ROOT))
            bundle["evidence_artifacts"]["language_slice_scores"] = str(SURFACES.relative_to(ROOT))
            bundle["evidence_artifacts"]["telemetry_bundle"] = str(SOURCE_LOGITS.relative_to(ROOT))
            bundle["notes"].append("prefilled_with_100m_side_only")
            bundle["notes"].append("gemma12b_side_and_rubric_still_required")
        else:
            bundle["notes"].append("no_current_100m_side_surface_for_language")
        bundles.append(bundle)
    return bundles


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    ledger = load_json(SOURCE_LEDGER)
    manifest_rows = load_jsonl(SOURCE_MANIFEST)
    execution = load_json(SOURCE_EXECUTION)
    logits = load_jsonl(SOURCE_LOGITS)
    records = ledger.get("records") if isinstance(ledger, dict) else []
    if not isinstance(records, list):
        records = []

    packets = build_language_packets(manifest_rows, logits)
    SURFACES.write_text(json.dumps(packets, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bundles = build_prefilled_bundles(records, packets, execution)
    write_jsonl(BUNDLES, bundles)

    failures: list[str] = []
    if len(bundles) != 4:
        failures.append("prefilled_bundle_count_not_4")
    available_langs = sorted(lang for lang, packet in packets.items() if packet["rows"] > 0 and packet["logit_rows"] > 0 and packet["slice_exact"] is not None)
    unavailable_langs = sorted(lang for lang, packet in packets.items() if lang not in available_langs)
    if not available_langs:
        failures.append("no_available_100m_side_language_packets")

    next_step = (
        "Run Gemma-12B on the four Stage9721 standalone symbol-binding surface packets, attach same-surface Gemma outputs "
        "and expert-rubric results into the prefilled bundles, then rerun Stage9720."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "bundles": len(bundles),
            "language_rows": {lang: packet["rows"] for lang, packet in packets.items()},
            "language_logit_rows": {lang: packet["logit_rows"] for lang, packet in packets.items()},
            "language_slice_exact": {lang: packet["slice_exact"] for lang, packet in packets.items()},
            "available_100m_side_languages": available_langs,
            "unavailable_100m_side_languages": unavailable_langs,
            "failures": failures,
        },
        "artifacts": {
            "bundles": str(BUNDLES.relative_to(ROOT)),
            "surface_packets": str(SURFACES.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Packaged the four standalone symbol-binding language slices with current 100M-side surface hashes and slice scores, making clear that only Python currently has executed comparison-ready 100M evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9721 Symbol-Binding Standalone Comparison Package",
        "",
        f"Passed: `{summary['passed']}`",
        f"Prefilled bundles: `{summary['metrics']['bundles']}`",
        f"Slice exact by language: `{summary['metrics']['language_slice_exact']}`",
        f"Available 100M-side languages: `{summary['metrics']['available_100m_side_languages']}`",
        "",
        "This stage packages the four standalone symbol-binding language cells for comparison. The current executed 100M-side evidence only covers Python; the other three bundles stay unfilled on the 100M side until multilingual symbol-binding execution exists.",
        "",
        "No Gemma, harness, runtime, scoring, training, source/body emission, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "bundles": len(bundles),
        "language_slice_exact": {lang: packet["slice_exact"] for lang, packet in packets.items()},
        "available_100m_side_languages": available_langs,
        "next_best_step": next_step,
        "failures": failures,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
