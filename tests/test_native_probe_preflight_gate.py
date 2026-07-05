from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.native_probe_preflight_gate import audit_preflight_rows


def base_row() -> dict[str, object]:
    return {
        "probe_id": "p1",
        "mode": "structured_policy_probe",
        "source_manifest": "runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl",
        "output_dir": "runs/local/probes/p1",
        "max_train_rows": 32,
        "max_eval_rows": 16,
        "max_strict_rows": 16,
        "max_steps": 8,
        "loss_weights": {"decoder_ce_weight": 0.0, "structured_aux_weight": 1.0, "denoise_weight": 0.0},
        "post_run_artifact_gate": {"required": True, "script": "scripts/native_probe_interpretability_artifact_contract.py", "mode": "structured_aux_probe"},
        "cleanup_policy": "safe_cleanup_checkpoints_only",
        "cleanup_forbidden_paths": ["/", "/data", "/arxiv"],
        "authority": {
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
        },
    }


def test_preflight_accepts_closed_tiny_structured_plan(tmp_path: Path) -> None:
    card = audit_preflight_rows([base_row()], repo_root=tmp_path)
    assert card["passed"] is True
    assert card["post_run_artifact_gate_required_rows"] == 1
    assert card["model_execution_authorized_now"] is False


def test_preflight_rejects_missing_artifact_gate(tmp_path: Path) -> None:
    row = base_row()
    row["post_run_artifact_gate"] = {"required": False}
    card = audit_preflight_rows([row], repo_root=tmp_path)
    assert card["passed"] is False
    assert card["missing_gate_rows"] == ["p1"]


def test_preflight_rejects_decoder_weight_for_structured_mode(tmp_path: Path) -> None:
    row = base_row()
    row["loss_weights"] = {"decoder_ce_weight": 1.0, "structured_aux_weight": 1.0, "denoise_weight": 0.0}
    card = audit_preflight_rows([row], repo_root=tmp_path)
    assert card["passed"] is False
    assert card["decoder_open_rows"] == ["p1"]


def test_preflight_rejects_large_caps_and_unsafe_cleanup(tmp_path: Path) -> None:
    row = base_row()
    row["max_train_rows"] = 128
    row["cleanup_policy"] = "freehand_rm"
    row["cleanup_forbidden_paths"] = ["/"]
    card = audit_preflight_rows([row], repo_root=tmp_path)
    assert card["passed"] is False
    assert card["cap_fail_rows"] == ["p1"]
    assert card["unsafe_cleanup_rows"] == ["p1"]


def test_preflight_rejects_output_outside_runs_local(tmp_path: Path) -> None:
    row = base_row()
    row["output_dir"] = "tmp/outside"
    card = audit_preflight_rows([row], repo_root=tmp_path)
    assert card["passed"] is False
    assert card["output_path_fail_rows"] == ["p1"]
