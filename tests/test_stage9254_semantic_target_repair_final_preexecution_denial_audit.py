from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9254_semantic_target_repair_final_preexecution_denial_audit.py"
    spec = importlib.util.spec_from_file_location("stage9254", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _ticket(tmp_path: Path, manifest_sha: str = "abc"):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"row_id":"r1"}\n', encoding="utf-8")
    return {
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "model_execution_authorized_now": False,
        "decoder_ce_training_authorized_now": False,
        "command_executable_now": False,
        "allowed_operations_now": [],
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "authority": {k: False for k in _load().AUTHORITY_CLOSED},
        "denied_operations_now": sorted(_load().REQUIRED_DENIED),
        "required_limits": dict(_load().REQUIRED_LIMITS),
        "source_manifest_path": str(manifest),
        "source_manifest_sha256": manifest_sha,
        "future_output_dir": "runs/local/artifacts/stage9253_probe/bounded_decoder_probe",
        "requested_stage_name": "stage9253_probe",
        "future_argv": [
            "conda", "run", "-n", "trellis", "python", "legacy_src/scripts/train_agentkernel_lite_encdec.py",
            "--manifest", str(manifest),
            "--mode", "bounded_decoder_ce_probe",
            "--max-train-rows", "32",
            "--max-eval-rows", "16",
            "--max-strict-rows", "16",
            "--max-steps", "16",
            "--max-decoder-tokens", "768",
            "--decoder-ce-weight", "1.0",
            "--structured-aux-weight", "0.0",
            "--denoise-weight", "0.0",
            "--require-loss-mask-enforcement-audit",
            "--no-final-checkpoint-export",
            "--cleanup-checkpoints-after-probe",
            "--skip-final-model-save", "1",
            "--output-dir", "runs/local/artifacts/stage9253_probe/bounded_decoder_probe",
            "--run-id", "stage9253_probe",
            "--batch-size", "2",
            "--max-encoder-tokens", "256",
            "--learning-rate", "5e-5",
            "--implementation", "transformer",
            "--probe-scale", "target_100m",
            "--model-config", "configs/model/agentkernel_100m_seq2seq_recovered_target.json",
            "--tokenizer-json", "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
            "--tokenizer-config", "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
            "--tokenizer-hashlock", "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
            "--enable-generation-audit",
            "--max-generation-rows", "16",
            "--max-generation-tokens", "96",
            "--execution-authorized-for-recovery-probe",
        ],
    }, manifest


def _summaries(manifest_sha: str):
    return {
        "stage9249": {"passed": True, "authority": {}},
        "stage9250": {"passed": True, "authority": {}},
        "stage9251": {"passed": True, "authority": {}, "metrics": {"manifest_sha256": manifest_sha}},
        "stage9252": {"passed": True, "authority": {}},
    }


def _registry():
    return {"metrics": {"latest_stage": 9252, "authority_counts": {k: 0 for k in _load().AUTHORITY_CLOSED}}}


def test_stage9254_audit_accepts_real_denied_review_ready_ticket():
    mod = _load()
    ticket = mod.load_json(mod.TICKET)
    summaries = {name: mod.load_json(path) for name, path in mod.SOURCES.items()}
    registry = {"metrics": {"latest_stage": 9252, "authority_counts": {k: 0 for k in mod.AUTHORITY_CLOSED}}}
    audit = mod.audit_ticket(ticket, summaries, registry)
    assert audit["passed"] is True
    assert audit["current_execution_denied"] is True
    assert audit["future_output_dir_exists"] is False
    assert audit["future_argv_flags_present"] == audit["future_argv_flags_required"]

def test_stage9254_rejects_execution_authorization(tmp_path):
    mod = _load()
    ticket, manifest = _ticket(tmp_path)
    manifest_sha = mod.sha256_file(manifest)
    ticket["source_manifest_sha256"] = manifest_sha
    ticket["execution_authorized_now"] = True
    audit = mod.audit_ticket(ticket, _summaries(manifest_sha), _registry())
    assert audit["passed"] is False
    assert "execution_authorized_now_not_false" in audit["failures"]


def test_stage9254_negative_cases_are_rejected(tmp_path):
    mod = _load()
    ticket, manifest = _ticket(tmp_path)
    manifest_sha = mod.sha256_file(manifest)
    ticket["source_manifest_sha256"] = manifest_sha
    results = mod.negative_cases(ticket, _summaries(manifest_sha), _registry())
    assert len(results) == 10
    assert all(result["rejected"] for result in results)
