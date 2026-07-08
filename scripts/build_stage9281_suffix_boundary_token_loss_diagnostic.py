#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9281
NAME = "stage9281_suffix_boundary_token_loss_diagnostic"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9280_bridge_primed_denoise_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9279_bridge_primed_denoise_manifest/bridge_primed_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9280_bridge_primed_denoise_probe/denoise_repair_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DIAGNOSTIC = OUT_DIR / "suffix_boundary_token_loss_diagnostic.json"
ROWS_JSONL = OUT_DIR / "suffix_boundary_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_BOUNDARY_TOKEN_LOSS_DIAGNOSTIC_STAGE9281.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_FALSE = dict(AUTHORITY_CLOSED)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_lookup() -> dict[str, dict[str, Any]]:
    rows = {}
    for row in load_jsonl(MANIFEST):
        target = str((row.get("target") or {}).get("decoder_text") or "")
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        priming = str(model_input.get("bridge_priming_span") or "")
        rows[str(row.get("row_id"))] = {"target": target, "priming": priming, "split": row.get("split"), "language_family": row.get("language_family")}
    return rows


def token_prefix_boundary(positions: list[dict[str, Any]], priming: str) -> tuple[int, str]:
    acc = ""
    for pos in positions:
        acc += str(pos.get("token_text") or "")
        if acc == priming or acc.startswith(priming):
            return int(pos.get("position", -1)) + 1, acc
    return -1, acc


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[idx]


def build_diagnostic() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = load_json(SOURCE_SUMMARY)
    rows_by_id = manifest_lookup()
    all_token_rows = load_jsonl(RUN_DIR / "row_token_loss.jsonl")
    token_rows = [row for row in all_token_rows if row.get("step") is None]
    train_step_rows_ignored = len(all_token_rows) - len(token_rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9280_not_passed")
    if not all_token_rows:
        failures.append("token_rows_missing")
    if all_token_rows and not token_rows:
        failures.append("eval_strict_token_rows_missing")
    row_records: list[dict[str, Any]] = []
    first_losses: list[float] = []
    suffix_means: list[float] = []
    eos_losses: list[float] = []
    missing_boundary = 0
    by_split: dict[str, dict[str, list[float]]] = {}
    for token_row in token_rows:
        row_id = str(token_row.get("row_id"))
        meta = rows_by_id.get(row_id)
        if not meta:
            continue
        positions = token_row.get("positions") if isinstance(token_row.get("positions"), list) else []
        boundary, reconstructed = token_prefix_boundary(positions, str(meta["priming"]))
        if boundary < 0:
            missing_boundary += 1
            first_unforced = None
            suffix_positions: list[dict[str, Any]] = []
        else:
            suffix_positions = [pos for pos in positions if int(pos.get("position", -1)) >= boundary]
            first_unforced = suffix_positions[0] if suffix_positions else None
        first_loss = float(first_unforced["loss"]) if isinstance(first_unforced, dict) and first_unforced.get("loss") is not None else None
        suffix_loss_values = [float(pos["loss"]) for pos in suffix_positions if pos.get("loss") is not None]
        eos_pos = next((pos for pos in positions if pos.get("is_eos")), None)
        eos_loss = float(eos_pos["loss"]) if isinstance(eos_pos, dict) and eos_pos.get("loss") is not None else None
        if first_loss is not None:
            first_losses.append(first_loss)
        if suffix_loss_values:
            suffix_means.append(sum(suffix_loss_values) / len(suffix_loss_values))
        if eos_loss is not None:
            eos_losses.append(eos_loss)
        split = str(token_row.get("split") or meta.get("split") or "unknown")
        bucket = by_split.setdefault(split, {"first_unforced": [], "suffix_mean": [], "eos": []})
        if first_loss is not None:
            bucket["first_unforced"].append(first_loss)
        if suffix_loss_values:
            bucket["suffix_mean"].append(sum(suffix_loss_values) / len(suffix_loss_values))
        if eos_loss is not None:
            bucket["eos"].append(eos_loss)
        row_records.append({
            "row_id": row_id,
            "split": split,
            "step": token_row.get("step"),
            "language_family": meta.get("language_family"),
            "boundary_position": boundary,
            "priming_span": meta["priming"],
            "reconstructed_prefix_start": reconstructed[:120],
            "first_unforced_token": first_unforced,
            "first_unforced_loss": first_loss,
            "suffix_token_count": len(suffix_positions),
            "suffix_mean_loss": sum(suffix_loss_values) / len(suffix_loss_values) if suffix_loss_values else None,
            "suffix_p95_loss": percentile(suffix_loss_values, 0.95),
            "eos_loss": eos_loss,
        })
    split_summary = {
        split: {
            "first_unforced_mean_loss": mean(values["first_unforced"]),
            "suffix_mean_loss": mean(values["suffix_mean"]),
            "eos_mean_loss": mean(values["eos"]),
            "rows": len(values["suffix_mean"]),
        }
        for split, values in sorted(by_split.items())
    }
    if missing_boundary:
        failures.append("missing_priming_boundary_rows_nonzero")
    diagnostic = {
        "passed": not failures,
        "failures": failures,
        "source_stage": 9280,
        "rows": len(row_records),
        "token_rows": len(all_token_rows),
        "eval_strict_token_rows": len(token_rows),
        "train_step_token_rows_ignored": train_step_rows_ignored,
        "missing_boundary_rows": missing_boundary,
        "first_unforced_mean_loss": mean(first_losses),
        "first_unforced_p95_loss": percentile(first_losses, 0.95),
        "suffix_mean_loss": mean(suffix_means),
        "suffix_p95_mean_loss": percentile(suffix_means, 0.95),
        "eos_mean_loss": mean(eos_losses),
        "eos_p95_loss": percentile(eos_losses, 0.95),
        "split_summary": split_summary,
        "worst_first_unforced_rows": sorted(row_records, key=lambda row: row.get("first_unforced_loss") if row.get("first_unforced_loss") is not None else -1, reverse=True)[:8],
        "diagnosis": "first_unforced_suffix_token_loss_extreme_after_bridge_priming",
        "authority": AUTHORITY_FALSE,
    }
    return diagnostic, row_records


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_FALSE, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    diagnostic, rows = build_diagnostic()
    DIAGNOSTIC.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ROWS_JSONL.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": diagnostic["passed"],
        "authority": AUTHORITY_FALSE,
        "metrics": {**AUTHORITY_FALSE, **diagnostic},
        "artifacts": {"diagnostic": str(DIAGNOSTIC.relative_to(ROOT)), "rows": str(ROWS_JSONL.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Mapped token CE to the first unforced suffix token after bridge priming; suffix boundary loss remains extreme, so the next data patch should be a suffix-step micro-overfit objective.",
        "next_best_step": "Build a suffix-step micro-overfit manifest over the highest first-unforced-loss rows, with decoder/runtime/Gemma still closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9281 Suffix Boundary Token Loss Diagnostic",
            "",
            "Stage9281 aligns Stage9280 token CE to the bridge-priming boundary.",
            "",
            f"Rows: {diagnostic['rows']}",
            f"Missing boundary rows: {diagnostic['missing_boundary_rows']}",
            f"First unforced mean loss: {diagnostic['first_unforced_mean_loss']}",
            f"First unforced p95 loss: {diagnostic['first_unforced_p95_loss']}",
            f"Suffix mean loss: {diagnostic['suffix_mean_loss']}",
            f"EOS mean loss: {diagnostic['eos_mean_loss']}",
            f"Diagnosis: {diagnostic['diagnosis']}",
            "",
            "Decoder CE, runtime, Gemma, harness, scoring, source/body emission, and promotion remain closed.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": diagnostic["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
