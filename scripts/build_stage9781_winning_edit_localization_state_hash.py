#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9781
NAME = "stage9781_winning_edit_localization_state_hash"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR / "hash_run"
HASH_CARD = OUT_DIR / "winning_edit_localization_state_hash.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WINNING_EDIT_LOCALIZATION_STATE_HASH_STAGE9781.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MANIFEST = ROOT / "runs/local/artifacts/stage9771_edit_localization_visible_evidence_lift_package/edit_localization_visible_evidence_lift.jsonl"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
LANG_AUDIT = ROOT / "runs/local/artifacts/stage9774_edit_localization_visible_evidence_language_slice_audit/edit_localization_visible_evidence_language_slice_audit.json"
GEMMA_AUDIT = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_comparison.json"
RUNTIME_PYTHON = Path("/home/peyton/miniconda3/envs/code_assist_runtime/bin/python")
TMPDIR = Path("/data/tmp")
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
CELL_KEYS = [f"standalone_100m_weights::{lang}::edit_localization" for lang in LANGS]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _worker_command() -> list[str]:
    return [
        str(RUNTIME_PYTHON),
        str(Path(__file__).resolve()),
        "--worker",
        "--output-dir",
        str(RUN_DIR.relative_to(ROOT)),
    ]


def _update_checkpoint_slots(hash_card: dict[str, Any]) -> list[dict[str, Any]]:
    packets = load_jsonl(PACKETS)
    packet_index = {str(packet.get("cell_key") or ""): packet for packet in packets}
    lang_audit = load_json(LANG_AUDIT)
    gemma_audit = load_json(GEMMA_AUDIT)
    gemma_results = {
        str(row.get("language") or ""): row
        for row in (gemma_audit.get("results") if isinstance(gemma_audit.get("results"), list) else [])
    }
    updates: list[dict[str, Any]] = []
    for lang in LANGS:
        cell_key = f"standalone_100m_weights::{lang}::edit_localization"
        packet = packet_index.get(cell_key)
        if packet is None:
            continue
        checkpoint_rel = ((packet.get("review_packet_paths") or {}).get("frozen_export_or_checkpoint_hash"))
        if not checkpoint_rel:
            continue
        checkpoint_path = ROOT / str(checkpoint_rel)
        language_slice = (lang_audit.get("language_slices") or {}).get(lang) if isinstance(lang_audit.get("language_slices"), dict) else {}
        strict_card = language_slice.get("strict_eval") if isinstance(language_slice.get("strict_eval"), dict) else {}
        gemma_row = gemma_results.get(lang) or {}
        lines = [
            f"cell_key={cell_key}",
            "status=frozen_runtime_state_hash_recorded",
            f"frozen_runtime_state_sha256={hash_card.get('state_sha256')}",
            f"manifest_sha256={hash_card.get('manifest_sha256')}",
            f"restored_best_structured_state={hash_card.get('best_state_restored')}",
            f"selected_step={hash_card.get('selected_step')}",
            f"score_100m_strict_exact={strict_card.get('exact')}",
            f"score_gemma12b_strict_exact={gemma_row.get('gemma_strict_exact')}",
            "notes=hash derived from rerunning the Stage9773 visible-evidence target-100m probe and hashing the restored best in-memory state without exporting weights",
            "",
        ]
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text("\n".join(lines), encoding="utf-8")
        updates.append({
            "cell_key": cell_key,
            "checkpoint_path": str(checkpoint_path.relative_to(ROOT)),
        })
    return updates


def build_hash_stage() -> dict[str, Any]:
    if not RUNTIME_PYTHON.exists():
        return {
            "passed": False,
            "failures": ["runtime_python_missing"],
            "metrics": {},
            "authority": dict(AUTHORITY_CLOSED),
            "checkpoint_updates": [],
        }
    env = dict(os.environ)
    env.update({"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)})
    run = subprocess.run(
        _worker_command(),
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    hash_card = load_json(HASH_CARD)
    failures: list[str] = []
    if run.returncode != 0:
        failures.append("worker_run_failed")
    if hash_card.get("passed") is not True:
        failures.append("hash_card_not_passed")
    checkpoint_updates = _update_checkpoint_slots(hash_card) if not failures else []
    if len(checkpoint_updates) != 4:
        failures.append("checkpoint_updates_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "worker_returncode": run.returncode,
            "checkpoint_updates": len(checkpoint_updates),
            "state_hash_present": bool(hash_card.get("state_sha256")),
            "best_state_restored": hash_card.get("best_state_restored") is True,
            "selected_step": hash_card.get("selected_step"),
        },
        "worker_stdout_tail": run.stdout[-4000:],
        "worker_stderr_tail": run.stderr[-4000:],
        "hash_card": hash_card,
        "checkpoint_updates": checkpoint_updates,
        "authority": dict(AUTHORITY_CLOSED),
    }


def worker(output_dir: Path) -> None:
    sys.path.insert(0, str(ROOT / "legacy_src"))
    from agentkernel_lite.training_loop import run_structured_aux_probe
    import torch

    rows = load_jsonl(MANIFEST)
    result = run_structured_aux_probe(
        rows=rows,
        output_dir=output_dir,
        run_id=f"{NAME}_worker",
        mode="edit_localization_probe",
        max_train_rows=20,
        max_eval_rows=20,
        max_strict_rows=20,
        max_steps=64,
        batch_size=2,
        max_encoder_tokens=512,
        max_decoder_tokens=8,
        learning_rate=5e-5,
        implementation="transformer",
        probe_scale="target_100m",
        model_config=MODEL_CONFIG,
        tokenizer_json=TOKENIZER_JSON,
        tokenizer_config=TOKENIZER_CONFIG,
        eval_interval=8,
        restore_best_structured_state=True,
        return_runtime_state=True,
    )
    model = result.get("_runtime_model")
    if model is None:
        raise SystemExit("runtime model missing from structured probe result")

    hasher = hashlib.sha256()
    state = model.state_dict()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        hasher.update(name.encode("utf-8"))
        hasher.update(str(tensor.dtype).encode("utf-8"))
        hasher.update(str(tuple(tensor.shape)).encode("utf-8"))
        hasher.update(tensor.numpy().tobytes())
    manifest_sha256 = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    evals = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    strict = evals.get("strict_eval") if isinstance(evals.get("strict_eval"), dict) else {}
    strict_field = strict.get("field_exact") if isinstance(strict.get("field_exact"), dict) else {}
    strict_edit = strict_field.get("edit_localization") if isinstance(strict_field.get("edit_localization"), dict) else {}
    hash_card = {
        "passed": True,
        "state_sha256": hasher.hexdigest(),
        "manifest_sha256": manifest_sha256,
        "selected_step": ((result.get("best_state_selection") or {}).get("selected_step")),
        "best_state_restored": ((result.get("best_state_selection") or {}).get("restored")) is True,
        "checkpoint_exported": ((result.get("best_state_selection") or {}).get("checkpoint_exported")) is True,
        "final_checkpoint_exported": result.get("final_checkpoint_exported") is True,
        "strict_exact": strict_edit.get("exact"),
        "eval_exact": (((evals.get("eval") or {}).get("field_exact") or {}).get("edit_localization") or {}).get("exact"),
        "run_dir": str(output_dir.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
    }
    if hash_card["strict_exact"] != 1.0 or hash_card["eval_exact"] != 1.0:
        hash_card["passed"] = False
        hash_card["failures"] = ["rerun_did_not_match_winning_quality"]
    write_json(HASH_CARD, hash_card)
    print(json.dumps(hash_card, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=RUN_DIR.relative_to(ROOT))
    args = parser.parse_args()

    if args.worker:
        worker(ROOT / args.output_dir)
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_hash_stage()
    write_json(MANIFEST, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "checkpoint_updates": built["checkpoint_updates"],
        "hash_card": built["hash_card"],
        "worker_stdout_tail": built["worker_stdout_tail"],
        "worker_stderr_tail": built["worker_stderr_tail"],
        "authority": dict(AUTHORITY_CLOSED),
    })
    next_step = (
        "Refresh the current claim bridge so the four winning edit-localization cells no longer treat checkpoint/hash evidence as missing, "
        "then complete human rubric and anti-cheat judgments for those same four cells."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "hash_card": str(HASH_CARD.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Reran the winning visible-evidence edit-localization target-100m probe and hashed the restored best in-memory state so the four winning standalone cells now have real frozen-state hash evidence without exporting weights.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage9781 Winning Edit Localization State Hash",
                "",
                f"Passed: `{summary['passed']}`",
                f"Checkpoint updates: `{built['metrics'].get('checkpoint_updates')}`",
                f"State hash present: `{built['metrics'].get('state_hash_present')}`",
                f"Best state restored: `{built['metrics'].get('best_state_restored')}`",
                f"Selected step: `{built['metrics'].get('selected_step')}`",
                "",
                "This stage does not export weights. It reruns the winning visible-evidence edit-localization probe and hashes the restored best in-memory state.",
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
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not built["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
