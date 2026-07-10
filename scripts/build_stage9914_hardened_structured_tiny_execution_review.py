#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9914
NAME = "stage9914_hardened_structured_tiny_execution_review"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9913_v27_hardened_multisurface_compiler_refresh.json"
SOURCE_STRUCTURED = ROOT / "runs/local/artifacts/stage9913_v27_hardened_multisurface_compiler_refresh/compiled/structured_state.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TINY_DIR = OUT_DIR / "tiny_structured_manifests"
RUNS_DIR = OUT_DIR / "surface_runs"
AUDIT = OUT_DIR / "hardened_structured_tiny_execution_review_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARDENED_STRUCTURED_TINY_EXECUTION_REVIEW_STAGE9914.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
CAPS = {"train": 32, "eval": 16, "strict_eval": 16}
SURFACES = {
    "symbol_binding": {"mode": "symbol_binding_probe", "loss": "symbol_binding_ce"},
    "edit_localization": {"mode": "edit_localization_probe", "loss": "edit_localization_ce"},
    "patch_operator_selection": {"mode": "patch_operator_probe", "loss": "patch_operator_ce"},
    "verifier_failure_repair_or_abstain": {"mode": "verifier_repair_probe", "loss": "verifier_repair_ce"},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or "unknown")


def cap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for split, cap in CAPS.items():
        split_rows = [row for row in rows if str(row.get("split") or "other") == split]
        if len(split_rows) <= cap:
            selected.extend(split_rows)
            continue
        by_language: dict[str, list[dict[str, Any]]] = {}
        language_order: list[str] = []
        for row in split_rows:
            language = row_language(row)
            if language not in by_language:
                by_language[language] = []
                language_order.append(language)
            by_language[language].append(row)
        picked: list[dict[str, Any]] = []
        while len(picked) < cap:
            progressed = False
            for language in language_order:
                bucket = by_language[language]
                if bucket and len(picked) < cap:
                    picked.append(bucket.pop(0))
                    progressed = True
            if not progressed:
                break
        selected.extend(picked)
    return selected


def surface_rows(surface: str) -> list[dict[str, Any]]:
    loss = SURFACES[surface]["loss"]
    rows = read_jsonl(SOURCE_STRUCTURED)
    filtered = [row for row in rows if str(row.get("source_skill_area") or "") == surface and str(row.get("expected_enabled_loss") or "") == loss]
    return cap_rows(filtered)


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {"train": 0, "eval": 0, "strict_eval": 0}
    for row in rows:
        split = str(row.get("split") or "other")
        if split in out:
            out[split] += 1
    return out


def trainer_command(surface: str, manifest: Path, rows: list[dict[str, Any]]) -> list[str]:
    counts = split_counts(rows)
    out_dir = RUNS_DIR / surface
    return [
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(manifest.relative_to(ROOT)),
        "--mode", SURFACES[surface]["mode"],
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG.relative_to(ROOT)),
        "--tokenizer-json", str(TOKENIZER_JSON.relative_to(ROOT)),
        "--tokenizer-config", str(TOKENIZER_CONFIG.relative_to(ROOT)),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK.relative_to(ROOT)),
        "--max-train-rows", str(counts["train"]),
        "--max-eval-rows", str(counts["eval"]),
        "--max-strict-rows", str(counts["strict_eval"]),
        "--max-steps", "8",
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
        "--output-dir", str(out_dir.relative_to(ROOT)),
        "--run-id", f"{NAME}_{surface}",
        "--execution-authorized-for-recovery-probe",
    ]


def surface_metric(surface: str, result: dict[str, Any]) -> dict[str, float | None]:
    eval_card = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    field_name = {
        "symbol_binding": "symbol_binding",
        "edit_localization": "edit_localization",
        "patch_operator_selection": "patch_operator",
        "verifier_failure_repair_or_abstain": "verifier_repair",
    }[surface]
    out: dict[str, float | None] = {}
    for split in ("eval", "strict_eval"):
        split_card = eval_card.get(split) if isinstance(eval_card.get(split), dict) else {}
        exact = (((split_card.get("field_exact") or {}).get(field_name)) or {}).get("exact")
        out[f"{split}_exact"] = exact
    return out


def run_surface(surface: str) -> dict[str, Any]:
    manifest = TINY_DIR / f"{surface}_tiny.jsonl"
    rows = surface_rows(surface)
    write_jsonl(manifest, rows)
    env = dict(os.environ)
    env.update({"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)})
    run = subprocess.run(trainer_command(surface, manifest, rows), cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    out_dir = RUNS_DIR / surface
    result = load_json(out_dir / "execution_result.json")
    out = {
        "surface": surface,
        "rows": len(rows),
        "trainer_returncode": run.returncode,
        "passed": run.returncode == 0 and bool(result.get("required_artifacts_written")),
        "execution_result": result,
        "stdout_tail": run.stdout[-2000:],
        "stderr_tail": run.stderr[-2000:],
    }
    out.update(surface_metric(surface, result))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TINY_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9913_not_passed")
    surface_results = []
    if not failures:
        for surface in SURFACES:
            res = run_surface(surface)
            surface_results.append(res)
            if not res["passed"]:
                failures.append(f"surface_execution_failed:{surface}")
    compact_results = [{k: v for k, v in row.items() if k not in {"execution_result", "stdout_tail", "stderr_tail"}} for row in surface_results]
    audit = {"passed": not failures, "failures": failures, "surface_results": compact_results, "authority": dict(AUTHORITY_CLOSED)}
    write_json(AUDIT, audit)
    next_step = "Use this hardened structured review to decide whether the full v2.7 package should now treat the opaque-choice edit-localization source as the default training/eval packet rather than the older geometry-aware remap."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, "surface_results": compact_results},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "run_dir": str(RUNS_DIR.relative_to(ROOT)), "tiny_manifest_dir": str(TINY_DIR.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Executed a capped target-100M structured tiny review on the Stage9913 hardened v2.7 surfaces to verify whether the no-label-list opaque-choice edit-localization source carries through the actual multisurface execution path.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text("\n".join([
        "# Stage9914 Hardened Structured Tiny Execution Review",
        "",
        f"Passed: `{summary['passed']}`",
        f"Failures: `{failures}`",
        f"Surfaces: `{compact_results}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures, "surface_results": compact_results}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
