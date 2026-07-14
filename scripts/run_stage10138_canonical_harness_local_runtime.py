#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HANDOFF = ROOT / "runs/local/artifacts/stage10081_canonical_harness_backend_handoff_bundle/canonical_harness_backend_handoff_bundle.json"
DEFAULT_RUNTIME_ROOT = ROOT / "runs/local/artifacts/stage10138_canonical_harness_local_runtime"
DEFAULT_TEMPLATE = DEFAULT_RUNTIME_ROOT / "canonical_harness_runtime_payload_template.json"
DEFAULT_SUMMARY = DEFAULT_RUNTIME_ROOT / "canonical_harness_local_runtime_summary.json"

DEFAULT_100M_MODEL_CONFIG = "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
DEFAULT_TOKENIZER_JSON = "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
DEFAULT_TOKENIZER_CONFIG = "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
DEFAULT_TOKENIZER_HASHLOCK = "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


ADAPTER_VALIDATE_AND_WRITE = _load_symbol(
    "stage10138_stage10081_adapter",
    ROOT / "scripts" / "run_stage10081_canonical_harness_backend_adapter.py",
    "validate_and_write",
)
TRACE_CARD = _load_symbol(
    "stage10138_traced_eval_observability",
    ROOT / "scripts" / "traced_eval_observability.py",
    "trace_observability_card",
)
SCORE_PATCH_ROWS = _load_symbol(
    "stage10138_patch_minimality_complexity_meter",
    ROOT / "scripts" / "patch_minimality_complexity_meter.py",
    "score_rows",
)
VERIFIER_CARD = _load_symbol(
    "stage10138_semantic_equivalence_metamorphic_verifier",
    ROOT / "scripts" / "semantic_equivalence_metamorphic_verifier.py",
    "verifier_card",
)
VALIDATE_LOCKED_PACK = _load_symbol(
    "stage10138_golden_locked_eval_suite",
    ROOT / "scripts" / "golden_locked_eval_suite.py",
    "validate_pack",
)
RUN_ROWS_100M = _load_symbol(
    "stage10138_first_wave_bundle_inference",
    ROOT / "scripts" / "run_stage10140_first_wave_bundle_inference.py",
    "run_rows_100m",
)
ANSWER_CORRECT = _load_symbol(
    "stage10138_first_wave_answer_correct",
    ROOT / "scripts" / "run_stage10140_first_wave_bundle_inference.py",
    "answer_correct",
)
ROW_ANSWER_KIND = _load_symbol(
    "stage10138_first_wave_row_answer_kind",
    ROOT / "scripts" / "run_stage10140_first_wave_bundle_inference.py",
    "row_answer_kind",
)
ROW_EXPECTED_LABEL = _load_symbol(
    "stage10138_first_wave_row_expected_label",
    ROOT / "scripts" / "run_stage10140_first_wave_bundle_inference.py",
    "row_expected_label",
)
ROW_OPAQUE_OPTIONS = _load_symbol(
    "stage10138_first_wave_row_opaque_options",
    ROOT / "scripts" / "run_stage10140_first_wave_bundle_inference.py",
    "row_opaque_options",
)
NORMALIZE_OPAQUE_CHOICE_LABEL = _load_symbol(
    "stage10138_first_wave_normalize_opaque_choice_label",
    ROOT / "scripts" / "run_stage10140_first_wave_bundle_inference.py",
    "normalize_opaque_choice_label",
)


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def stable_json_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(text.encode("utf-8")).hexdigest()


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "cell"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute the canonical full-product harness task pack locally for 100M and Gemma, then populate the reserved machine artifacts."
    )
    parser.add_argument("payload", nargs="?", type=Path, help="Runtime payload JSON describing the locked task pack and both model backends.")
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF, help="Canonical stage10081 handoff bundle.")
    parser.add_argument("--cell-key", default=None, help="Optional single cell to execute from the payload.")
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT, help="Stage output root for runtime byproducts.")
    parser.add_argument("--emit-template", type=Path, default=None, help="Write a payload template and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Validate payload and prepare runtime artifacts without model execution or writeback.")
    parser.add_argument("--skip-writeback", action="store_true", help="Do not populate the reserved packet artifact paths.")
    return parser.parse_args()


def _cell_index(handoff: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)]
    return {str(row.get("cell_key") or ""): row for row in rows}


def _selected_runs(payload: dict[str, Any], *, cell_key: str | None) -> list[dict[str, Any]]:
    rows = [row for row in (payload.get("runs") or []) if isinstance(row, dict)]
    if cell_key:
        rows = [row for row in rows if str(row.get("cell_key") or "") == cell_key]
    return rows


def build_template(handoff: dict[str, Any]) -> dict[str, Any]:
    runs = []
    for cell in _cell_index(handoff).values():
        rows = [
            {
                "row_id": "placeholder_row_1",
                "split": "strict_eval",
                "prompt": "You are evaluating a locked full-product software-maintenance task.\nReturn only one label: A\n",
                "expected_label": "A",
                "candidate_patch": "diff --git a/example.py b/example.py\n--- a/example.py\n+++ b/example.py\n@@\n- return 200\n+ return 400\n",
                "verifier_row": {
                    "row_id": "placeholder_row_1",
                    "verifier_type": "property_contract",
                    "candidate": "def validate(x):\n    return x\n",
                    "properties": [{"property_id": "contains_validate", "kind": "must_define_symbol", "value": "validate"}],
                },
            }
        ]
        task_pack = {
            "task_pack_id": cell.get("task_pack_id"),
            "source_id": cell.get("source_id"),
            "lineage_hash": cell.get("lineage_hash"),
            "split_role": "locked_regression",
            "train_eligible": False,
            "promotion_only": True,
            "hidden_final": False,
            "language_family": cell.get("language_family"),
            "skill_area": cell.get("skill_area"),
            "slice_tags": list(cell.get("slice_tags") or [cell.get("language_family"), cell.get("skill_area")]),
            "thresholds": dict(cell.get("thresholds") or {}),
            "blocked_training_reason": "v27_locked_eval_pack_never_train_eligible",
            "rows": rows,
            "manifest_mode": "edit_localization_probe",
            "manifest_rows": [
                {
                    "row_id": "placeholder_row_1",
                    "split": "strict_eval",
                    "language_family": cell.get("language_family"),
                    "edit_localization_target": "A",
                    "clean_state": {"edit_localization_target": "A"},
                    "model_input": {"task_observation": "placeholder"},
                }
            ],
        }
        runs.append(
            {
                "cell_key": cell.get("cell_key"),
                "task_pack": task_pack,
                "hundred_m_backend": {
                    "kind": "target_100m_manifest_probe",
                    "mode": "edit_localization_probe",
                    "model_config": DEFAULT_100M_MODEL_CONFIG,
                    "tokenizer_json": DEFAULT_TOKENIZER_JSON,
                    "tokenizer_config": DEFAULT_TOKENIZER_CONFIG,
                    "tokenizer_hashlock": DEFAULT_TOKENIZER_HASHLOCK,
                    "max_steps": 16,
                    "batch_size": 2,
                    "learning_rate": 5e-5,
                    "max_encoder_tokens": 512,
                    "max_decoder_tokens": 8,
                },
                "gemma_backend": {
                    "kind": "ollama_generate",
                    "model": "gemma3:12b",
                    "seed": 0,
                    "temperature": 0.0,
                },
            }
        )
    return {
        "runtime_payload_version": "stage10138.v1",
        "created_at_utc": now_utc(),
        "notes": [
            "Replace placeholder task_pack rows and manifest_rows with the real locked task pack payload.",
            "Keep task_pack_id/source_id/lineage_hash aligned with stage10081 handoff cells.",
            "Gemma rows require prompt and expected_label.",
            "100M manifest_rows must be compatible with legacy_src/scripts/train_agentkernel_lite_encdec.py.",
        ],
        "runs": runs,
    }


def manifest_split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("split") or "") for row in rows)
    return {key: int(counts.get(key, 0)) for key in ("train", "eval", "strict_eval")}


def build_target_100m_command(*, manifest_path: Path, output_dir: Path, run_id: str, backend: Mapping[str, Any], manifest_rows: list[dict[str, Any]]) -> list[str]:
    counts = manifest_split_counts(manifest_rows)
    return [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(manifest_path),
        "--mode",
        str(backend.get("mode") or "edit_localization_probe"),
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(backend.get("model_config") or DEFAULT_100M_MODEL_CONFIG),
        "--tokenizer-json",
        str(backend.get("tokenizer_json") or DEFAULT_TOKENIZER_JSON),
        "--tokenizer-config",
        str(backend.get("tokenizer_config") or DEFAULT_TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(backend.get("tokenizer_hashlock") or DEFAULT_TOKENIZER_HASHLOCK),
        "--max-train-rows",
        str(counts["train"]),
        "--max-eval-rows",
        str(counts["eval"]),
        "--max-strict-rows",
        str(counts["strict_eval"]),
        "--max-steps",
        str(int(backend.get("max_steps") or 64)),
        "--batch-size",
        str(int(backend.get("batch_size") or 2)),
        "--learning-rate",
        str(float(backend.get("learning_rate") or 5e-5)),
        "--max-encoder-tokens",
        str(int(backend.get("max_encoder_tokens") or 512)),
        "--max-decoder-tokens",
        str(int(backend.get("max_decoder_tokens") or 8)),
        "--decoder-ce-weight",
        str(float(backend.get("decoder_ce_weight") or 0.0)),
        "--structured-aux-weight",
        str(float(backend.get("structured_aux_weight") or 1.0)),
        "--denoise-weight",
        str(float(backend.get("denoise_weight") or 0.0)),
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
        "--execution-authorized-for-recovery-probe",
    ]


def ollama_generate(*, model: str, prompt: str, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": seed, "temperature": temperature},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def start_trace(trace: list[dict[str, Any]], *, name: str, span_type: str, attrs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    span = {
        "span_id": f"{span_type}_{len(trace) + 1}",
        "span_type": span_type,
        "name": name,
        "start_time_utc": now_utc(),
        "started_at": time.time(),
        "attrs": dict(attrs or {}),
    }
    trace.append(span)
    return span


def finish_trace(span: dict[str, Any], *, failed: bool = False, error: str | None = None, metrics: Mapping[str, Any] | None = None) -> None:
    ended_at = time.time()
    span["end_time_utc"] = now_utc()
    span["duration_ms"] = round((ended_at - float(span.pop("started_at", ended_at))) * 1000.0, 3)
    span["failed"] = failed
    if error:
        span["error"] = error
    if metrics:
        span["metrics"] = dict(metrics)


def validate_runtime_run(run: Mapping[str, Any], cell: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), Mapping) else {}
    if str(run.get("cell_key") or "") != str(cell.get("cell_key") or ""):
        failures.append("cell_key_mismatch")
    for key in ("task_pack_id", "source_id", "lineage_hash", "language_family", "skill_area"):
        if str(task_pack.get(key) or "") != str(cell.get(key) or ""):
            failures.append(f"{key}_mismatch")
    pack_validation = VALIDATE_LOCKED_PACK(dict(task_pack), idx=0)
    if not pack_validation.get("passed"):
        failures.extend(f"locked_pack::{reason}" for reason in pack_validation.get("failures") or [])
    rows = task_pack.get("rows")
    if not isinstance(rows, list) or not rows:
        failures.append("missing_task_pack_rows")
    hundred_m = run.get("hundred_m_backend") if isinstance(run.get("hundred_m_backend"), Mapping) else {}
    hundred_m_kind = str(hundred_m.get("kind") or "")
    if hundred_m_kind == "target_100m_manifest_probe":
        if not isinstance(task_pack.get("manifest_rows"), list) or not task_pack.get("manifest_rows"):
            failures.append("missing_manifest_rows_for_target_100m")
    elif hundred_m_kind == "preserved_bounded_choice_scoring":
        if not str(hundred_m.get("runtime_model_bundle") or ""):
            failures.append("missing_runtime_model_bundle_for_preserved_bounded_choice")
    gemma = run.get("gemma_backend") if isinstance(run.get("gemma_backend"), Mapping) else {}
    if str(gemma.get("kind") or "") == "ollama_generate":
        for row in rows if isinstance(rows, list) else []:
            if not str((row if isinstance(row, Mapping) else {}).get("prompt") or ""):
                failures.append("gemma_row_missing_prompt")
                break
    return failures


def execute_target_100m(*, run: Mapping[str, Any], runtime_dir: Path, dry_run: bool, trace: list[dict[str, Any]]) -> dict[str, Any]:
    backend = run.get("hundred_m_backend") if isinstance(run.get("hundred_m_backend"), Mapping) else {}
    kind = str(backend.get("kind") or "")
    span = start_trace(trace, name="hundred_m_execution", span_type="model_execution", attrs={"backend_kind": kind})
    task_pack = run["task_pack"]
    model_dir = runtime_dir / "hundred_m"
    model_dir.mkdir(parents=True, exist_ok=True)
    if kind == "preserved_bounded_choice_scoring":
        rows = [dict(row) for row in task_pack.get("rows") or [] if isinstance(row, Mapping)]
        rows_path = model_dir / "rows.jsonl"
        write_jsonl(rows_path, rows)
        result = RUN_ROWS_100M(rows, backend, dry_run=dry_run, override_device=str(backend.get("device") or None), progress=False)
        output_rows = [dict(row) for row in result.get("rows") or [] if isinstance(row, Mapping)]
        predictions_path = model_dir / "predictions.jsonl"
        write_jsonl(predictions_path, output_rows)
        scored = [row for row in output_rows if row.get("correct") is not None]
        accuracy = (sum(1 for row in scored if bool(row.get("correct"))) / len(scored)) if scored else None
        finish_trace(
            span,
            failed=False,
            metrics={
                "rows": len(rows),
                "dry_run": dry_run,
                "exact_accuracy": accuracy,
            },
        )
        return {
            "status": str(result.get("status") or ("dry_run_ready" if dry_run else "completed")),
            "backend_kind": kind,
            "rows_path": display(rows_path),
            "predictions_path": display(predictions_path),
            "rows": len(rows),
            "exact_accuracy": accuracy,
            "device": result.get("device") or backend.get("device"),
            "bounded_choice_aux_source": result.get("bounded_choice_aux_source") or backend.get("bounded_choice_aux_source"),
        }
    if kind != "target_100m_manifest_probe":
        finish_trace(span, failed=True, error=f"unsupported_hundred_m_backend::{kind}")
        raise ValueError(f"unsupported hundred_m backend kind: {kind}")
    manifest_rows = list(task_pack.get("manifest_rows") or [])
    manifest_path = model_dir / "runtime_manifest.jsonl"
    write_jsonl(manifest_path, [row for row in manifest_rows if isinstance(row, Mapping)])
    output_dir = model_dir / "probe_output"
    run_id = slug(str(run.get("cell_key") or "cell")) + "_100m"
    command = build_target_100m_command(
        manifest_path=manifest_path,
        output_dir=output_dir,
        run_id=run_id,
        backend=backend,
        manifest_rows=manifest_rows,
    )
    command_path = model_dir / "command.json"
    write_json(command_path, {"command": command})
    if dry_run:
        finish_trace(span, metrics={"dry_run": True, "manifest_rows": len(manifest_rows)})
        return {
            "status": "dry_run_ready",
            "backend_kind": kind,
            "command": command,
            "command_path": display(command_path),
            "manifest_path": display(manifest_path),
            "output_dir": display(output_dir),
            "manifest_rows": len(manifest_rows),
            "split_counts": manifest_split_counts(manifest_rows),
        }
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
    stdout_path = model_dir / "stdout.txt"
    stderr_path = model_dir / "stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    probe_contract = load_json(output_dir / "probe_contract_audit.json")
    execution_result = load_json(output_dir / "execution_result.json")
    field_exact = load_json(output_dir / "field_exact_by_cell.json")
    failed = proc.returncode != 0
    finish_trace(
        span,
        failed=failed,
        error=f"returncode::{proc.returncode}" if failed else None,
        metrics={
            "returncode": proc.returncode,
            "manifest_rows": len(manifest_rows),
            "required_artifacts_written": bool(execution_result.get("required_artifacts_written")),
        },
    )
    if failed:
        raise RuntimeError(f"target_100m probe failed for {run.get('cell_key')} with return code {proc.returncode}")
    return {
        "status": "completed",
        "backend_kind": kind,
        "command": command,
        "command_path": display(command_path),
        "manifest_path": display(manifest_path),
        "output_dir": display(output_dir),
        "stdout_path": display(stdout_path),
        "stderr_path": display(stderr_path),
        "manifest_rows": len(manifest_rows),
        "split_counts": manifest_split_counts(manifest_rows),
        "probe_contract_audit": probe_contract,
        "execution_result": execution_result,
        "field_exact_by_cell": field_exact,
    }


def execute_gemma(*, run: Mapping[str, Any], runtime_dir: Path, dry_run: bool, trace: list[dict[str, Any]]) -> dict[str, Any]:
    backend = run.get("gemma_backend") if isinstance(run.get("gemma_backend"), Mapping) else {}
    kind = str(backend.get("kind") or "")
    span = start_trace(trace, name="gemma_execution", span_type="model_execution", attrs={"backend_kind": kind})
    if kind != "ollama_generate":
        finish_trace(span, failed=True, error=f"unsupported_gemma_backend::{kind}")
        raise ValueError(f"unsupported gemma backend kind: {kind}")
    model = str(backend.get("model") or "gemma3:12b")
    seed = int(backend.get("seed") or 0)
    temperature = float(backend.get("temperature") or 0.0)
    rows = [row for row in (run["task_pack"].get("rows") or []) if isinstance(row, Mapping)]
    output_rows: list[dict[str, Any]] = []
    correct = 0
    model_dir = runtime_dir / "gemma"
    for row in rows:
        prompt = str(row.get("prompt") or "")
        expected = ROW_EXPECTED_LABEL(row)
        answer_kind = ROW_ANSWER_KIND(row)
        raw_output = "[dry-run]" if dry_run else ollama_generate(model=model, prompt=prompt, seed=seed, temperature=temperature)
        predicted = raw_output.splitlines()[0].strip() if raw_output else ""
        if not dry_run and answer_kind == "opaque_choice":
            predicted = NORMALIZE_OPAQUE_CHOICE_LABEL(str(raw_output or ""), ROW_OPAQUE_OPTIONS(row))
        is_correct = None if dry_run or not expected else ANSWER_CORRECT(answer_kind, str(predicted or ""), expected)
        if is_correct:
            correct += 1
        output_rows.append(
            {
                "row_id": row.get("row_id"),
                "split": row.get("split"),
                "answer_kind": answer_kind,
                "expected_label": expected,
                "raw_output": raw_output,
                "predicted_label": None if dry_run else predicted,
                "correct": is_correct,
            }
        )
    rows_path = model_dir / "rows.jsonl"
    write_jsonl(rows_path, output_rows)
    accuracy = None if dry_run or not rows else (correct / len(rows))
    finish_trace(
        span,
        metrics={"rows": len(rows), "dry_run": dry_run, "accuracy": accuracy},
    )
    return {
        "status": "dry_run_ready" if dry_run else "completed",
        "backend_kind": kind,
        "model": model,
        "rows_path": display(rows_path),
        "rows": len(rows),
        "exact_accuracy": accuracy,
        "seed": seed,
        "temperature": temperature,
    }


def derive_verifier_rows(task_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(task_pack.get("verifier_rows"), list):
        return [dict(row) for row in task_pack.get("verifier_rows") or [] if isinstance(row, Mapping)]
    rows: list[dict[str, Any]] = []
    for item in task_pack.get("rows") or []:
        if not isinstance(item, Mapping):
            continue
        verifier_row = item.get("verifier_row")
        if isinstance(verifier_row, Mapping):
            rows.append(dict(verifier_row))
    return rows


def derive_patch_rows(task_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(task_pack.get("patch_rows"), list):
        return [dict(row) for row in task_pack.get("patch_rows") or [] if isinstance(row, Mapping)]
    rows: list[dict[str, Any]] = []
    for item in task_pack.get("rows") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("candidate_patch") or ""):
            rows.append({"row_id": item.get("row_id"), "candidate_patch": item.get("candidate_patch")})
    return rows


def score_verifier(*, run: Mapping[str, Any], runtime_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
    span = start_trace(trace, name="verifier_scoring", span_type="scoring")
    rows = derive_verifier_rows(run["task_pack"])
    rows_path = runtime_dir / "verifier_rows.jsonl"
    write_jsonl(rows_path, rows)
    card = VERIFIER_CARD(rows)
    finish_trace(span, metrics={"rows": len(rows), "passed": bool(card.get("passed"))})
    return {
        "cell_key": run.get("cell_key"),
        "status": "completed" if rows else "completed_no_verifier_rows",
        "passed": bool(card.get("passed")) if rows else True,
        "verifier_runs": card.get("checks") or [],
        "summary": {
            "rows": int(card.get("rows") or 0),
            "failed_rows": int(card.get("failed_rows") or 0),
            "input_rows_path": display(rows_path),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def score_patch_minimality(*, run: Mapping[str, Any], runtime_dir: Path, trace: list[dict[str, Any]]) -> dict[str, Any]:
    span = start_trace(trace, name="patch_minimality_scoring", span_type="scoring")
    rows = derive_patch_rows(run["task_pack"])
    rows_path = runtime_dir / "patch_rows.jsonl"
    write_jsonl(rows_path, rows)
    card = SCORE_PATCH_ROWS(rows)
    finish_trace(span, metrics={"rows": len(rows), "blocked_rows": int((card.get("metrics") or {}).get("blocked_rows") or 0)})
    return {
        "cell_key": run.get("cell_key"),
        "status": "completed" if rows else "completed_no_patch_rows",
        "passed": bool((card.get("metrics") or {}).get("blocked_rows", 0) == 0),
        "scores": card.get("records") or [],
        "summary": {
            "rows": int(card.get("rows") or 0),
            "metrics": dict(card.get("metrics") or {}),
            "input_rows_path": display(rows_path),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def build_trace_rows(*, cell_key: str, harness_run_id: str, trace: list[dict[str, Any]], task_pack_hash: str) -> list[dict[str, Any]]:
    raw = {
        "trace_id": harness_run_id,
        "eval_id": cell_key,
        "spans": [
            {
                "span_id": span["span_id"],
                "span_type": span["span_type"],
                "name": span["name"],
                "start_time_utc": span.get("start_time_utc"),
                "end_time_utc": span.get("end_time_utc"),
                "duration_ms": span.get("duration_ms"),
                "failed": span.get("failed", False),
                "attrs": {**dict(span.get("attrs") or {}), **({"metrics": span["metrics"]} if span.get("metrics") else {})},
            }
            for span in trace
        ],
        "metric_events": [{"metric": "task_pack_hash", "value": task_pack_hash}],
        "failed": any(bool(span.get("failed")) for span in trace),
    }
    TRACE_CARD([raw])
    return [raw]


def build_same_task_pack_payload(
    *,
    run: Mapping[str, Any],
    task_pack_hash: str,
    runtime_payload_hash: str,
    hundred_m_result: Mapping[str, Any],
    gemma_result: Mapping[str, Any],
    runtime_dir: Path,
) -> dict[str, Any]:
    rows = [row for row in (run["task_pack"].get("rows") or []) if isinstance(row, Mapping)]
    return {
        "cell_key": run.get("cell_key"),
        "status": "completed_same_task_pack_execution",
        "same_task_pack_verified": True,
        "same_task_pack_hash": task_pack_hash,
        "runtime_payload_hash": runtime_payload_hash,
        "row_count": len(rows),
        "row_ids": [str(row.get("row_id") or "") for row in rows],
        "hundred_m_runtime": dict(hundred_m_result),
        "gemma12b_runtime": dict(gemma_result),
        "runtime_dir": display(runtime_dir),
        "authority": dict(AUTHORITY_CLOSED),
    }


def execute_run(*, run: Mapping[str, Any], cell: Mapping[str, Any], runtime_root: Path, dry_run: bool, skip_writeback: bool, handoff_path: Path) -> dict[str, Any]:
    cell_key = str(run.get("cell_key") or "")
    runtime_dir = runtime_root / slug(cell_key)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    trace: list[dict[str, Any]] = []
    validation_span = start_trace(trace, name="validate_runtime_payload", span_type="validation")
    failures = validate_runtime_run(run, cell)
    finish_trace(validation_span, failed=bool(failures), error=";".join(failures) if failures else None, metrics={"failures": len(failures)})
    if failures:
        raise ValueError(f"{cell_key} runtime payload validation failed: {failures}")
    task_pack = dict(run.get("task_pack") or {})
    task_pack_hash = stable_json_hash(task_pack)
    runtime_payload_hash = stable_json_hash(run)
    write_json(runtime_dir / "runtime_payload.json", dict(run))

    hundred_m_result = execute_target_100m(run=run, runtime_dir=runtime_dir, dry_run=dry_run, trace=trace)
    gemma_result = execute_gemma(run=run, runtime_dir=runtime_dir, dry_run=dry_run, trace=trace)
    verifier_results = score_verifier(run=run, runtime_dir=runtime_dir, trace=trace)
    patch_scores = score_patch_minimality(run=run, runtime_dir=runtime_dir, trace=trace)
    harness_run_id = f"{slug(cell_key)}__{task_pack_hash[:12]}"
    trace_rows = build_trace_rows(cell_key=cell_key, harness_run_id=harness_run_id, trace=trace, task_pack_hash=task_pack_hash)
    same_task_pack_payload = build_same_task_pack_payload(
        run=run,
        task_pack_hash=task_pack_hash,
        runtime_payload_hash=runtime_payload_hash,
        hundred_m_result=hundred_m_result,
        gemma_result=gemma_result,
        runtime_dir=runtime_dir,
    )
    adapter_payload = {
        "runs": [
            {
                "cell_key": cell_key,
                "harness_run_id": harness_run_id,
                "same_task_pack_as_gemma12b": same_task_pack_payload,
                "tool_trace_spans": trace_rows,
                "verifier_results": verifier_results,
                "patch_minimality_or_abstain_scores": patch_scores,
            }
        ]
    }
    adapter_payload_path = runtime_dir / "adapter_payload.json"
    write_json(adapter_payload_path, adapter_payload)
    writeback_result = None
    if not skip_writeback:
        writeback_result = ADAPTER_VALIDATE_AND_WRITE(
            handoff_path=handoff_path,
            payload_path=adapter_payload_path,
            cell_key=cell_key,
            dry_run=dry_run,
        )
        write_json(runtime_dir / "writeback_result.json", writeback_result)
    return {
        "cell_key": cell_key,
        "harness_run_id": harness_run_id,
        "task_pack_hash": task_pack_hash,
        "runtime_payload_hash": runtime_payload_hash,
        "runtime_dir": display(runtime_dir),
        "hundred_m_runtime": hundred_m_result,
        "gemma12b_runtime": gemma_result,
        "same_task_pack_as_gemma12b": same_task_pack_payload,
        "tool_trace_spans_rows": len(trace_rows),
        "verifier_results": verifier_results,
        "patch_minimality_or_abstain_scores": patch_scores,
        "adapter_payload_path": display(adapter_payload_path),
        "writeback": writeback_result,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    args = parse_args()
    handoff = load_json(args.handoff)
    if args.emit_template:
        template = build_template(handoff)
        target = args.emit_template
        write_json(target, template)
        print(json.dumps({"template_path": display(target), "runs": len(template.get("runs") or [])}, indent=2, sort_keys=True))
        return
    if args.payload is None:
        raise SystemExit("payload is required unless --emit-template is used")

    payload = load_json(args.payload)
    selected_runs = _selected_runs(payload, cell_key=args.cell_key)
    if not selected_runs:
        raise SystemExit("payload contains no matching runs")
    cell_index = _cell_index(handoff)
    args.runtime_root.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for run in selected_runs:
        cell_key = str(run.get("cell_key") or "")
        cell = cell_index.get(cell_key)
        if cell is None:
            failures.append(f"unknown_cell_key::{cell_key}")
            continue
        try:
            results.append(
                execute_run(
                    run=run,
                    cell=cell,
                    runtime_root=args.runtime_root,
                    dry_run=args.dry_run,
                    skip_writeback=args.skip_writeback,
                    handoff_path=args.handoff,
                )
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            failures.append(f"{cell_key}::{exc}")

    summary = {
        "stage": 10138,
        "stage_name": "stage10138_canonical_harness_local_runtime",
        "passed": not failures and bool(results),
        "dry_run": args.dry_run,
        "skip_writeback": args.skip_writeback,
        "handoff": display(args.handoff),
        "payload": display(args.payload),
        "selected_cell_key": args.cell_key,
        "metrics": {
            "selected_runs": len(selected_runs),
            "completed_runs": len(results),
            "failed_runs": len(failures),
            "writeback_runs": sum(1 for row in results if row.get("writeback")),
        },
        "failures": failures,
        "results": results,
        "authority": dict(AUTHORITY_CLOSED),
        "created_at_utc": now_utc(),
    }
    write_json(DEFAULT_SUMMARY if args.runtime_root == DEFAULT_RUNTIME_ROOT else args.runtime_root / "canonical_harness_local_runtime_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
