from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts" / "training_runtime_contract.py"
AUDIT = ROOT / "scripts" / "audit_training_runtime_contract.py"
TELEMETRY = ROOT / "scripts" / "training_telemetry.py"
TRAINER = ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"


def test_training_runtime_contract_and_audit(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    contract = tmp_path / "contract.json"
    audit = tmp_path / "audit.json"
    plan.write_text(json.dumps({"plan_name": "p", "mode": "bounded_decoder_ce_probe"}), encoding="utf-8")
    subprocess.run([sys.executable, str(RUNTIME), "--training-plan", str(plan), "--output", str(contract)], check=True, text=True, capture_output=True)
    subprocess.run([sys.executable, str(AUDIT), str(contract), "--output", str(audit)], check=True, text=True, capture_output=True)
    card = json.loads(audit.read_text())
    assert card["passed"] is True
    assert card["gates"]["required_components_present"] is True
    assert card["gates"]["checkpoint_export_forbidden"] is True


def test_training_telemetry_emits_required_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "probe"
    subprocess.run(
        [sys.executable, str(TELEMETRY), "--output-dir", str(out), "--run-id", "r", "--mode", "bounded_decoder_ce_probe"],
        check=True,
        text=True,
        capture_output=True,
    )
    for name in [
        "loss_by_step.jsonl",
        "eval_loss_by_checkpoint.jsonl",
        "row_field_logits.jsonl",
        "row_field_losses.jsonl",
        "row_token_loss.jsonl",
        "eos_length_audit.json",
        "short_output_probe.json",
        "repetition_probe.json",
        "internal_leak_probe.json",
        "sample_generation_audit.json",
        "module_delta_norms.json",
        "failure_bucket_card.json",
        "cleanup_proof.json",
    ]:
        assert (out / name).is_file()

def test_trainer_uses_safe_cleanup_only() -> None:
    trainer = TRAINER.read_text(encoding="utf-8")
    assert "from safe_cleanup import safe_cleanup_checkpoints" in trainer
    assert "safe_cleanup_checkpoints(" in trainer
    assert "shutil.rmtree" not in trainer
    assert ".unlink(" not in trainer

