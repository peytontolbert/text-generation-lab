from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys

import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"


def write_manifest(path: Path, *, rows: int = 3, bad_loss: bool = False, over_cap: bool = False) -> None:
    payloads = []
    splits = ["train", "eval", "strict_eval"]
    for index in range(rows):
        payloads.append(
            {
                "row_id": f"r{index}",
                "split": splits[index % len(splits)],
                "decoder_token_len": 900 if over_cap and index == 0 else 128,
                "target": {"decoder_text": f"Bounded decoder target {index}."},
                "loss_mask": {"build_mode_ce" if bad_loss and index == 0 else "decoder_ce": True},
                "authority": {
                    "model_execution_authorized_next": False,
                    "decoder_ce_training_authorized_next": False,
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
        )
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in payloads) + "\n", encoding="utf-8")



def write_hashlocked_tokenizer_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    tok_json = tmp_path / "tokenizer.json"
    tok_cfg = tmp_path / "tokenizer_config.json"
    hashlock = tmp_path / "tokenizer_hashlock.json"
    tok_json.write_text('{"dummy":"contract-only"}\n', encoding="utf-8")
    tok_cfg.write_text('{"vocab_size":1506,"pad_token_id":0,"bos_token_id":1,"eos_token_id":2}\n', encoding="utf-8")
    hashlock.write_text(
        json.dumps(
            {
                "sha256": {
                    "tokenizer_json": hashlib.sha256(tok_json.read_bytes()).hexdigest(),
                    "tokenizer_config": hashlib.sha256(tok_cfg.read_bytes()).hexdigest(),
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return tok_json, tok_cfg, hashlock

def write_denoise_prefix_manifest(path: Path, *, bad_prefix: bool = False, full_prefix: bool = False) -> None:
    payloads = []
    splits = ["train", "eval", "strict_eval", "train", "eval", "strict_eval"]
    target = "Return the module reference for the bounded repair step."
    prefix = target if full_prefix else ("Select wrong prefix" if bad_prefix else "Return the module reference")
    for index, split in enumerate(splits):
        payloads.append(
            {
                "row_id": f"d{index}",
                "split": split,
                "language_family": "python",
                "target": {"decoder_text": target},
                "corrupted_output": "bad output",
                "model_input": {"copy_prefix_span": prefix},
                "loss_mask": {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False},
                "authority": {
                    "model_execution_authorized_next": False,
                    "decoder_ce_training_authorized_next": False,
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
        )
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in payloads) + "\n", encoding="utf-8")


def denoise_cmd(tmp_path: Path, manifest: Path) -> list[str]:
    probe_repo = tmp_path / "repo"
    probe_repo.mkdir(exist_ok=True)
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(probe_repo),
        "--manifest",
        str(manifest),
        "--mode",
        "denoise_repair_probe",
        "--max-train-rows",
        "2",
        "--max-eval-rows",
        "2",
        "--max-strict-rows",
        "2",
        "--max-steps",
        "1",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "1.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(probe_repo / "runs" / "local" / "probes" / "stage9276"),
        "--run-id",
        "stage9276",
    ]


def base_cmd(tmp_path: Path, manifest: Path) -> list[str]:
    probe_repo = tmp_path / "repo"
    probe_repo.mkdir(exist_ok=True)
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(probe_repo),
        "--manifest",
        str(manifest),
        "--mode",
        "bounded_decoder_ce_probe",
        "--max-train-rows",
        "32",
        "--max-eval-rows",
        "16",
        "--max-strict-rows",
        "16",
        "--max-steps",
        "16",
        "--decoder-ce-weight",
        "1.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--require-counterfactual-obligation-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(probe_repo / "runs" / "local" / "probes" / "stage8584"),
        "--run-id",
        "stage8584",
    ]



def structured_cmd(tmp_path: Path, manifest: Path, *, mode: str) -> list[str]:
    probe_repo = tmp_path / "repo"
    probe_repo.mkdir(exist_ok=True)
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(probe_repo),
        "--manifest",
        str(manifest),
        "--mode",
        mode,
        "--max-train-rows",
        "100",
        "--max-eval-rows",
        "100",
        "--max-strict-rows",
        "100",
        "--max-steps",
        "16",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(probe_repo / "runs" / "local" / "probes" / f"{mode}_contract"),
        "--run-id",
        f"{mode}_contract",
    ]


def two_phase_structured_cmd(tmp_path: Path, manifest: Path, phase2_manifest: Path) -> list[str]:
    probe_repo = tmp_path / "repo"
    probe_repo.mkdir(exist_ok=True)
    return [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(probe_repo),
        "--manifest",
        str(manifest),
        "--phase2-manifest",
        str(phase2_manifest),
        "--mode",
        "two_phase_structured_reconnect_probe",
        "--max-train-rows",
        "20",
        "--max-eval-rows",
        "20",
        "--max-strict-rows",
        "20",
        "--max-steps",
        "16",
        "--phase2-max-train-rows",
        "20",
        "--phase2-max-eval-rows",
        "20",
        "--phase2-max-strict-rows",
        "20",
        "--phase2-max-steps",
        "4",
        "--max-decoder-tokens",
        "4",
        "--phase2-max-decoder-tokens",
        "4",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--restore-best-structured-state",
        "--eval-interval",
        "4",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(probe_repo / "runs" / "local" / "probes" / "two_phase_structured_contract"),
        "--run-id",
        "two_phase_structured_contract",
    ]



def write_clean_visible_evidence_manifest(path: Path) -> None:
    builder = ROOT / "scripts" / "build_stage9771_edit_localization_visible_evidence_lift_package.py"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("stage9771_test_builder", builder)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    rows = module.load_jsonl(module.SOURCE)
    lifted = module.lift_rows(rows)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in lifted), encoding="utf-8")


def test_recovered_trainer_help_exposes_stage8580_flags() -> None:
    result = subprocess.run([sys.executable, str(TRAINER), "--help"], check=True, text=True, capture_output=True)
    for flag in [
        "--manifest",
        "--mode",
        "--decoder-ce-weight",
        "--eos-loss-weight",
        "--denoise-weight",
        "--structured-aux-weight",
        "--max-strict-rows",
        "--require-loss-mask-enforcement-audit",
        "--require-counterfactual-obligation-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "--execution-authorized-for-recovery-probe",
        "--batch-size",
        "--learning-rate",
        "--implementation",
        "--probe-scale",
        "--model-config",
        "--tokenizer-json",
        "--tokenizer-config",
        "--tokenizer-hashlock",
        "--enable-generation-audit",
        "--max-generation-rows",
        "--max-generation-tokens",
        "--generation-prefix-field",
    ]:
        assert flag in result.stdout


def test_contract_only_probe_writes_non_executing_artifacts(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    cmd = base_cmd(tmp_path, manifest) + ["--contract-only"]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["model_execution_attempted"] is False
    out = tmp_path / "repo" / "runs" / "local" / "probes" / "stage8584"
    assert (out / "probe_contract_audit.json").is_file()
    assert (out / "cleanup_dry_run.json").is_file()
    assert (out / "loss_by_step.jsonl").is_file()
    assert not (out / "checkpoints").exists()


def test_trainer_refuses_execution_without_contract_only(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    result = subprocess.run(base_cmd(tmp_path, manifest), text=True, capture_output=True)
    assert result.returncode != 0
    assert "model execution is disabled unless --execution-authorized-for-recovery-probe is present" in result.stderr
    out = tmp_path / "repo" / "runs" / "local" / "probes" / "stage8584"
    assert (out / "probe_contract_audit.json").is_file()
    assert not (out / "loss_by_step.jsonl").exists()
    assert not (out / "cleanup_dry_run.json").exists()


def test_contract_fails_on_unsafe_loss_mask(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, bad_loss=True)
    result = subprocess.run(base_cmd(tmp_path, manifest) + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    assert card["unsafe_loss_rows"] > 0


def test_contract_fails_on_decoder_token_over_cap(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, over_cap=True)
    result = subprocess.run(base_cmd(tmp_path, manifest) + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    assert card["over_cap_rows"] == 1


def test_contract_records_transformer_implementation_without_execution(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    cmd = base_cmd(tmp_path, manifest) + ["--implementation", "transformer", "--contract-only"]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["model_execution_attempted"] is False
    assert card["implementation"] == "transformer"
    assert card["implementation_contract"]["transformer_execution_requires_explicit_authorization"] is True
    assert card["implementation_contract"]["scaffold"] is False




def test_contract_rejects_scaffold_for_recovered_target(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    cmd = base_cmd(tmp_path, manifest) + ["--implementation", "scaffold", "--contract-only"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    assert card["implementation"] == "scaffold"
    assert card["implementation_contract"]["target_implementation_guard"]["allowed_for_recovered_100m_target"] is False
    assert "recovered 100M target requires implementation=transformer" in card["errors"]

def test_tokenizer_contract_records_recovered_bpe_pointer(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    tok_json = ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json"
    pointer = json.loads(tok_json.read_text())
    repo_local = pointer.get("repo_local_paths") or pointer["primary_recovered_paths"]
    cmd = base_cmd(tmp_path, manifest) + [
        "--tokenizer-json",
        str(ROOT / repo_local["tokenizer_json"] if not str(repo_local["tokenizer_json"]).startswith("/") else repo_local["tokenizer_json"]),
        "--tokenizer-config",
        str(ROOT / repo_local["tokenizer_config"] if not str(repo_local["tokenizer_config"]).startswith("/") else repo_local["tokenizer_config"]),
        "--contract-only",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["tokenizer_contract"]["target_100m_vocab_size"] == 1506
    assert card["tokenizer_contract"]["byte_fallback_used_when_unset"] is False

def test_contract_rejects_target_100m_without_model_config(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    cmd = base_cmd(tmp_path, manifest) + ["--probe-scale", "target_100m", "--contract-only"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    assert "--probe-scale target_100m requires --model-config" in card["errors"]


def test_contract_records_recovered_target_100m_model_config_without_execution(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    model_config = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"
    pointer = json.loads((ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json").read_text())
    repo_local = pointer["repo_local_paths"]
    tok_json = ROOT / repo_local["tokenizer_json"]
    tok_cfg = ROOT / repo_local["tokenizer_config"]
    hashlock = ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json"
    cmd = base_cmd(tmp_path, manifest) + [
        "--probe-scale",
        "target_100m",
        "--model-config",
        str(model_config),
        "--tokenizer-json",
        str(tok_json),
        "--tokenizer-config",
        str(tok_cfg),
        "--tokenizer-hashlock",
        str(hashlock),
        "--contract-only",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["model_execution_attempted"] is False
    assert card["probe_scale"] == "target_100m"
    assert card["implementation_contract"]["model_config"] == str(model_config)
    assert card["implementation_contract"]["target_100m_requires_model_config"] is True
    assert card["tokenizer_contract"]["tokenizer_json"] == str(tok_json)
    assert card["tokenizer_contract"]["tokenizer_config"] == str(tok_cfg)
    assert card["tokenizer_contract"]["tokenizer_hashlock"] == str(hashlock)

def test_contract_rejects_target_100m_tokenizer_hash_mismatch(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    model_config = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"
    tok_json, tok_cfg, hashlock = write_hashlocked_tokenizer_files(tmp_path)
    tok_json.write_text('{"changed":"hash-mismatch"}\n', encoding="utf-8")
    cmd = base_cmd(tmp_path, manifest) + [
        "--probe-scale",
        "target_100m",
        "--model-config",
        str(model_config),
        "--tokenizer-json",
        str(tok_json),
        "--tokenizer-config",
        str(tok_cfg),
        "--tokenizer-hashlock",
        str(hashlock),
        "--contract-only",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    assert "tokenizer json sha256 mismatch against hashlock" in card["errors"]


def test_generation_audit_detects_substring_repetition() -> None:
    try:
        import torch  # noqa: F401
    except Exception:
        pytest.skip("torch is required for generation-audit helper import")
    sys.path.insert(0, str(ROOT / "legacy_src"))
    from agentkernel_lite.training_loop import _has_degenerate_repetition

    repeated = "train_refamily_refamily_refamily_refamily_refamily_refamily_refamily"
    assert _has_degenerate_repetition([233, 438, 357, 212, 351, 219, 526, 222, 440] * 4, repeated) is True


def test_authorized_tiny_transformer_generation_audit_writes_quality_cards(tmp_path: Path) -> None:
    try:
        import torch  # noqa: F401
    except Exception:
        pytest.skip("torch is required for authorized generation-audit execution smoke")
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, rows=6)
    cmd = base_cmd(tmp_path, manifest) + [
        "--implementation",
        "transformer",
        "--probe-scale",
        "tiny_transformer",
        "--max-steps",
        "1",
        "--max-generation-rows",
        "2",
        "--max-generation-tokens",
        "8",
        "--enable-generation-audit",
        "--execution-authorized-for-recovery-probe",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    assert '"generation_audit_enabled": true' in result.stdout
    out = tmp_path / "repo" / "runs" / "local" / "probes" / "stage8584"
    sample = json.loads((out / "sample_generation_audit.json").read_text())
    short = json.loads((out / "short_output_probe.json").read_text())
    leak = json.loads((out / "internal_leak_probe.json").read_text())
    repetition = json.loads((out / "repetition_probe.json").read_text())
    eos = json.loads((out / "eos_length_audit.json").read_text())
    loss_rows = [json.loads(line) for line in (out / "loss_by_step.jsonl").read_text().splitlines() if line.strip()]
    assert sample["generated_rows"] == 2
    assert len(sample["samples"]) == 2
    assert "contentful_rate" in sample
    assert short["generated_rows"] == 2
    assert leak["generated_internal_token_rows"] >= 0
    assert repetition["generated_rows"] == 2
    assert eos["eos_loss_weight"] == 1.0
    assert "post_clip_grad_norm" in loss_rows[0]
    assert (out / "generated_repetition_negative_rows.jsonl").is_file()



def test_authorized_tiny_transformer_accepts_eos_loss_weight(tmp_path: Path) -> None:
    try:
        import torch  # noqa: F401
    except Exception:
        pytest.skip("torch is required for authorized stabilization smoke")
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, rows=6)
    cmd = base_cmd(tmp_path, manifest) + [
        "--implementation",
        "transformer",
        "--probe-scale",
        "tiny_transformer",
        "--max-steps",
        "1",
        "--eos-loss-weight",
        "4.0",
        "--execution-authorized-for-recovery-probe",
    ]
    subprocess.run(cmd, check=True, text=True, capture_output=True)
    out = tmp_path / "repo" / "runs" / "local" / "probes" / "stage8584"
    eos = json.loads((out / "eos_length_audit.json").read_text())
    loss_rows = [json.loads(line) for line in (out / "loss_by_step.jsonl").read_text().splitlines() if line.strip()]
    assert eos["eos_loss_weight"] == 4.0
    assert loss_rows[0]["post_clip_grad_norm"] <= loss_rows[0]["pre_clip_grad_norm"]


def test_denoise_contract_accepts_valid_generation_prefix_field(tmp_path: Path) -> None:
    manifest = tmp_path / "denoise.jsonl"
    write_denoise_prefix_manifest(manifest)
    cmd = denoise_cmd(tmp_path, manifest) + [
        "--enable-generation-audit",
        "--generation-prefix-field",
        "model_input.copy_prefix_span",
        "--contract-only",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["generation_prefix_field"] == "model_input.copy_prefix_span"


def test_denoise_contract_rejects_generation_prefix_without_generation_audit(tmp_path: Path) -> None:
    manifest = tmp_path / "denoise.jsonl"
    write_denoise_prefix_manifest(manifest)
    cmd = denoise_cmd(tmp_path, manifest) + [
        "--generation-prefix-field",
        "model_input.copy_prefix_span",
        "--contract-only",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert "--generation-prefix-field requires --enable-generation-audit" in card["errors"]


def test_denoise_contract_rejects_invalid_generation_prefix_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "denoise.jsonl"
    write_denoise_prefix_manifest(manifest, bad_prefix=True)
    cmd = denoise_cmd(tmp_path, manifest) + [
        "--enable-generation-audit",
        "--generation-prefix-field",
        "model_input.copy_prefix_span",
        "--contract-only",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert any(error.startswith("invalid generation prefix rows present") for error in card["errors"])


def test_denoise_contract_rejects_full_target_generation_prefix(tmp_path: Path) -> None:
    manifest = tmp_path / "denoise.jsonl"
    write_denoise_prefix_manifest(manifest, full_prefix=True)
    cmd = denoise_cmd(tmp_path, manifest) + [
        "--enable-generation-audit",
        "--generation-prefix-field",
        "model_input.copy_prefix_span",
        "--contract-only",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert any(error.startswith("invalid generation prefix rows present") for error in card["errors"])


def write_episode_step_manifest(path: Path) -> None:
    authority = {
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "source_emission_authorized": False,
        "body_emission_authorized": False,
        "gemma_execution_authorized_next": False,
        "harness_execution_authorized_next": False,
        "scoring_authorized_next": False,
        "controller_complete_merge_authorized_next": False,
        "promotion_ready": False,
    }
    rows = []
    for index, split in enumerate(["train", "eval", "strict_eval"]):
        rows.append(
            {
                "row_id": f"episode_step_{index}",
                "split": split,
                "transition_schema": "episode_step_suffix_transition_v1",
                "episode_transition": {
                    "state_t": {"active_generation_prefix_span": "Return the module reference"},
                    "action_t": {"action": "REPAIR_SUFFIX_CONTINUATION"},
                    "observation_t": {"boundary_next_token_match": index == 0},
                    "reward_or_verifier": {"reward": 1.0 if index == 0 else 0.0},
                    "state_t_plus_1": {"repair_outcome": "successful_suffix_repair_step" if index == 0 else "residual_suffix_repair_step"},
                },
                "loss_mask": {
                    "decoder_ce": False,
                    "denoise_ce": False,
                    "runtime_reward": False,
                    "episode_repair_outcome_ce": False,
                    "episode_failure_type_ce": False,
                    "episode_boundary_match_ce": False,
                    "episode_target_prefix_match_ce": False,
                    "episode_step_value_mse": False,
                },
                "authority": authority,
            }
        )
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_episode_step_contract_only_accepts_closed_loss_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "episode_steps.jsonl"
    write_episode_step_manifest(manifest)
    probe_repo = tmp_path / "repo"
    probe_repo.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(probe_repo),
        "--manifest",
        str(manifest),
        "--mode",
        "episode_step_denoise_contract_only",
        "--max-train-rows",
        "1",
        "--max-eval-rows",
        "1",
        "--max-strict-rows",
        "1",
        "--max-steps",
        "0",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(probe_repo / "runs" / "local" / "probes" / "stage9450"),
        "--run-id",
        "stage9450",
        "--contract-only",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["mode"] == "episode_step_denoise_contract_only"
    assert card["model_execution_attempted"] is False
    assert card["episode_step_contract_only_probe"] is True
    assert card["unsafe_loss_rows"] == 0
    assert all(value == 0 for value in card["loss_counts"].values())


def test_structured_contract_blocks_target_only_edit_localization_manifest(tmp_path: Path) -> None:
    manifest = ROOT / "runs" / "local" / "artifacts" / "stage9743_multilingual_edit_localization_target_only_package" / "multilingual_edit_localization_target_only.jsonl"
    result = subprocess.run(structured_cmd(tmp_path, manifest, mode="edit_localization_probe") + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    assert "multilingual surface readiness failed" in card["errors"][-1]
    readiness = card["multilingual_surface_readiness"]
    assert readiness["passed"] is False
    assert readiness["failed_bucket_count"] == 12


def test_structured_contract_allows_visible_evidence_edit_localization_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "visible_evidence_manifest.jsonl"
    write_clean_visible_evidence_manifest(manifest)
    result = subprocess.run(structured_cmd(tmp_path, manifest, mode="edit_localization_probe") + ["--contract-only"], check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    readiness = card["multilingual_surface_readiness"]
    assert readiness["passed"] is True
    assert readiness["failed_bucket_count"] == 0


def test_two_phase_structured_contract_allows_same_task_multilingual_then_web_manifest_pair(tmp_path: Path) -> None:
    manifest = ROOT / "runs" / "local" / "artifacts" / "stage9790_edit_localization_opaque_choice_surface" / "edit_localization_opaque_choice_surface.jsonl"
    phase2_manifest = ROOT / "runs" / "local" / "artifacts" / "stage9813_web_isolated_disambiguator_surface" / "web_isolated_disambiguator_surface.jsonl"
    result = subprocess.run(two_phase_structured_cmd(tmp_path, manifest, phase2_manifest) + ["--contract-only"], check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["phase1_mode"] == "edit_localization_probe"
    assert card["phase2_mode"] == "edit_localization_probe"
    assert card["two_phase_in_memory_required"] is True
    assert card["checkpoint_export_allowed_between_phases"] is False


def test_structured_contract_blocks_patch_operator_manifest_without_encoder_visible_evidence(tmp_path: Path) -> None:
    manifest = ROOT / "runs" / "local" / "artifacts" / "stage9735_multilingual_patch_operator_label_aligned_package" / "multilingual_patch_operator_label_aligned.jsonl"
    result = subprocess.run(structured_cmd(tmp_path, manifest, mode="patch_operator_probe") + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    readiness = card["multilingual_surface_readiness"]
    assert readiness["passed"] is False
    assert readiness["failed_bucket_count"] == 12


def test_structured_contract_blocks_verifier_repair_manifest_without_encoder_visible_evidence(tmp_path: Path) -> None:
    manifest = ROOT / "runs" / "local" / "artifacts" / "stage9738_multilingual_verifier_repair_label_aligned_package" / "multilingual_verifier_repair_label_aligned.jsonl"
    result = subprocess.run(structured_cmd(tmp_path, manifest, mode="verifier_repair_probe") + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    readiness = card["multilingual_surface_readiness"]
    assert readiness["passed"] is False
    assert readiness["failed_bucket_count"] == 12

