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
STAGE = 9851
NAME = "stage9851_direct_abstention_counterfactual_exec"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DIRECT_ABSTENTION_COUNTERFACTUAL_EXEC_STAGE9851.md"
AUDIT = OUT_DIR / "direct_abstention_counterfactual_exec_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TMPDIR = Path("/data/tmp")
RUNNER = ROOT / "runs/local/artifacts" / f"{NAME}_runner.py"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_runner() -> None:
    runner_text = """import json\nimport sys\nfrom pathlib import Path\nroot=Path('/data/agentkernel-seq2seq-text-lab')\nlegacy=root/'legacy_src'\nsys.path.insert(0, str(legacy))\nfrom agentkernel_lite.training_loop import run_structured_aux_probe\nrows=[json.loads(line) for line in (root/'runs/local/artifacts/stage9850_abstention_counterfactual_curriculum_manifest/abstention_counterfactual_curriculum_manifest.jsonl').read_text().splitlines() if line.strip()]\nout=root/'runs/local/artifacts/stage9851_direct_abstention_counterfactual_exec'\nres=run_structured_aux_probe(rows=rows, output_dir=out, run_id='stage9851_direct_abstention_counterfactual_exec', mode='edit_localization_probe', max_train_rows=48, max_eval_rows=8, max_strict_rows=8, max_steps=128, batch_size=2, max_encoder_tokens=512, max_decoder_tokens=4, learning_rate=5e-5, implementation='transformer', structured_trainable_profile='full_non_decoder', probe_scale='target_100m', model_config=root/'configs/model/agentkernel_100m_seq2seq_recovered_target.json', tokenizer_json=root/'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json', tokenizer_config=root/'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json')\nprint(json.dumps(res, indent=2, sort_keys=True))\n"""
    RUNNER.write_text(runner_text, encoding="utf-8")


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
    audit = {
        "passed": run.returncode == 0 and bool(result),
        "trainer_returncode": run.returncode,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": run.stderr[-4000:],
        "runtime_executed": result.get("runtime_executed"),
        "eval": result.get("eval"),
        "required_row_artifacts_present": all((RUN_DIR / name).exists() and (RUN_DIR / name).stat().st_size > 0 for name in ["row_field_logits.jsonl", "field_exact_by_cell.json", "structured_confusion_matrix.json", "row_field_losses.jsonl", "row_gradient_norms.jsonl", "row_dynamics_history.jsonl"]),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Compare this abstention-target 100M run against same-surface Gemma on the heldout harder packet to see whether explicit abstention improves the multilingual frontier."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "trainer_returncode": audit["trainer_returncode"], "runtime_executed": audit["runtime_executed"], "required_row_artifacts_present": audit["required_row_artifacts_present"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "runner": str(RUNNER.relative_to(ROOT))},
        "decision": "Executed the abstention-target heldout counterfactual curriculum directly through the structured training loop so the 100M model was trained to abstain on missing-evidence rows before evaluation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9851 Direct Abstention Counterfactual Exec",
        "",
        f"Passed: `{summary['passed']}`",
        f"Runtime executed: `{audit['runtime_executed']}`",
        f"Row artifacts present: `{audit['required_row_artifacts_present']}`",
        "",
        "This stage trains the 100M model on a heldout curriculum that uses an explicit abstention target for missing-evidence rows.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "runtime_executed": audit["runtime_executed"], "required_row_artifacts_present": audit["required_row_artifacts_present"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
