#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9855
NAME = "stage9855_direct_multisurface_abstention_honesty_exec"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PATCH_RUN_DIR = OUT_DIR / "patch_operator_abstention_honesty_exec"
VERIFIER_RUN_DIR = OUT_DIR / "verifier_repair_abstention_honesty_exec"
AUDIT = OUT_DIR / "direct_multisurface_abstention_honesty_exec.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DIRECT_MULTISURFACE_ABSTENTION_HONESTY_EXEC_STAGE9855.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TMPDIR = Path("/data/tmp")
RUNNER = ROOT / "runs/local/artifacts" / f"{NAME}_runner.py"
PATCH_MANIFEST = ROOT / "runs/local/artifacts/stage9854_multisurface_abstention_honesty_manifests/multilingual_patch_operator_abstention_honesty.jsonl"
VERIFIER_MANIFEST = ROOT / "runs/local/artifacts/stage9854_multisurface_abstention_honesty_manifests/multilingual_verifier_repair_abstention_honesty.jsonl"
REQUIRED = [
    "row_field_logits.jsonl",
    "field_exact_by_cell.json",
    "structured_confusion_matrix.json",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "row_dynamics_history.jsonl",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def build_runner() -> None:
    runner_text = """import json\nimport sys\nfrom pathlib import Path\nroot=Path('/data/agentkernel-seq2seq-text-lab')\nlegacy=root/'legacy_src'\nsys.path.insert(0, str(legacy))\nfrom agentkernel_lite.training_loop import run_structured_aux_probe\nconfigs=[\n    {\n        'name':'patch_operator',\n        'manifest':root/'runs/local/artifacts/stage9854_multisurface_abstention_honesty_manifests/multilingual_patch_operator_abstention_honesty.jsonl',\n        'output_dir':root/'runs/local/artifacts/stage9855_direct_multisurface_abstention_honesty_exec/patch_operator_abstention_honesty_exec',\n        'run_id':'stage9855_patch_operator_abstention_honesty_exec',\n        'mode':'patch_operator_probe',\n        'max_train_rows':48,\n        'max_eval_rows':48,\n        'max_strict_rows':48,\n    },\n    {\n        'name':'verifier_repair',\n        'manifest':root/'runs/local/artifacts/stage9854_multisurface_abstention_honesty_manifests/multilingual_verifier_repair_abstention_honesty.jsonl',\n        'output_dir':root/'runs/local/artifacts/stage9855_direct_multisurface_abstention_honesty_exec/verifier_repair_abstention_honesty_exec',\n        'run_id':'stage9855_verifier_repair_abstention_honesty_exec',\n        'mode':'verifier_repair_probe',\n        'max_train_rows':36,\n        'max_eval_rows':36,\n        'max_strict_rows':36,\n    },\n]\nout={}\nfor cfg in configs:\n    rows=[json.loads(line) for line in cfg['manifest'].read_text().splitlines() if line.strip()]\n    res=run_structured_aux_probe(rows=rows, output_dir=cfg['output_dir'], run_id=cfg['run_id'], mode=cfg['mode'], max_train_rows=cfg['max_train_rows'], max_eval_rows=cfg['max_eval_rows'], max_strict_rows=cfg['max_strict_rows'], max_steps=128, batch_size=2, max_encoder_tokens=512, max_decoder_tokens=4, learning_rate=5e-5, implementation='transformer', structured_trainable_profile='full_non_decoder', probe_scale='target_100m', model_config=root/'configs/model/agentkernel_100m_seq2seq_recovered_target.json', tokenizer_json=root/'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json', tokenizer_config=root/'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json')\n    out[cfg['name']]=res\nprint(json.dumps(out, indent=2, sort_keys=True))\n"""
    RUNNER.write_text(runner_text, encoding="utf-8")


def _field_exact(result: dict[str, Any], split: str, field: str) -> float | None:
    evals = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    split_card = evals.get(split) if isinstance(evals.get(split), dict) else {}
    field_card = split_card.get("field_exact") if isinstance(split_card.get("field_exact"), dict) else {}
    metrics = field_card.get(field) if isinstance(field_card.get(field), dict) else {}
    value = metrics.get("exact")
    return None if value is None else float(value)


def _surface_audit(result: dict[str, Any], run_dir: Path, field: str) -> dict[str, Any]:
    return {
        "trainer_returncode": 0,
        "runtime_executed": result.get("runtime_executed"),
        "required_row_artifacts_present": all((run_dir / name).exists() and (run_dir / name).stat().st_size > 0 for name in REQUIRED),
        "eval_exact": _field_exact(result, "eval", field),
        "strict_exact": _field_exact(result, "strict_eval", field),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    build_runner()
    env = {"TMPDIR": str(TMPDIR), "TEMP": str(TMPDIR), "TMP": str(TMPDIR)}
    command = ["conda", "run", "-n", "trellis", "python", str(RUNNER)]
    run = subprocess.run(command, cwd=ROOT, env={**os.environ, **env}, text=True, capture_output=True, check=False)
    stdout = run.stdout.strip()
    result = json.loads(stdout) if stdout else {}
    patch = result.get("patch_operator") if isinstance(result.get("patch_operator"), dict) else {}
    verifier = result.get("verifier_repair") if isinstance(result.get("verifier_repair"), dict) else {}
    patch_audit = _surface_audit(patch, PATCH_RUN_DIR, "patch_operator")
    verifier_audit = _surface_audit(verifier, VERIFIER_RUN_DIR, "verifier_repair")
    passed = (
        run.returncode == 0
        and bool(result)
        and patch_audit["runtime_executed"] is True
        and verifier_audit["runtime_executed"] is True
        and patch_audit["required_row_artifacts_present"] is True
        and verifier_audit["required_row_artifacts_present"] is True
    )
    audit = {
        "passed": passed,
        "trainer_returncode": run.returncode,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": run.stderr[-4000:],
        "patch_operator": patch_audit,
        "verifier_repair": verifier_audit,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If the 100M model learns these abstention honesty packets cleanly, add same-surface Gemma comparisons before deciding whether these rebuilt hard surfaces are ready to re-enter the multilingual v2.7 scoreboard."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "trainer_returncode": run.returncode,
            "patch_eval_exact": patch_audit["eval_exact"],
            "patch_strict_exact": patch_audit["strict_exact"],
            "verifier_eval_exact": verifier_audit["eval_exact"],
            "verifier_strict_exact": verifier_audit["strict_exact"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "patch_run_dir": str(PATCH_RUN_DIR.relative_to(ROOT)),
            "verifier_run_dir": str(VERIFIER_RUN_DIR.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "runner": str(RUNNER.relative_to(ROOT)),
        },
        "decision": "Executed the patch-operator and verifier-repair abstention honesty manifests directly through the 100M structured loop to verify whether the model can learn the explicit abstention target on the rebuilt hard surfaces.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9855 Direct Multisurface Abstention Honesty Exec",
                "",
                f"Passed: `{summary['passed']}`",
                f"Patch eval/strict exact: `{patch_audit['eval_exact']}` / `{patch_audit['strict_exact']}`",
                f"Verifier eval/strict exact: `{verifier_audit['eval_exact']}` / `{verifier_audit['strict_exact']}`",
                "",
                "This stage checks whether the 100M model can reliably learn the explicit abstention target on the rebuilt patch-operator and verifier-repair surfaces.",
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
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "patch_eval_exact": patch_audit["eval_exact"],
                "patch_strict_exact": patch_audit["strict_exact"],
                "verifier_eval_exact": verifier_audit["eval_exact"],
                "verifier_strict_exact": verifier_audit["strict_exact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
