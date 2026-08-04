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

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from source_lineage_guard import load_future_eval_identity_denylist


def load_trainer_module():
    spec = importlib.util.spec_from_file_location("recovered_trainer_contract_test", TRAINER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_manifest_with_safe_identity(source: Path, destination: Path) -> Path:
    rows = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for index, row in enumerate(rows):
        row.setdefault("repo_family", "fixture-safe-repo")
        row.setdefault("root_identity", f"fixture-safe-root-{index}")
    destination.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return destination


def write_manifest(path: Path, *, rows: int = 3, bad_loss: bool = False, over_cap: bool = False) -> None:
    payloads = []
    splits = ["train", "eval", "strict_eval"]
    for index in range(rows):
        payloads.append(
            {
                "row_id": f"r{index}",
                "split": splits[index % len(splits)],
                "repo_family": "fixture-safe-repo",
                "root_identity": f"fixture-safe-root-{index}",
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
                "repo_family": "fixture-safe-repo",
                "root_identity": f"fixture-safe-root-{index}",
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



def foundational_cmd(tmp_path: Path, *, contract_only: bool = False) -> list[str]:
    probe_repo = tmp_path / "foundational-repo"
    probe_repo.mkdir(exist_ok=True)
    manifest = (
        ROOT
        / "runs/local/artifacts/stage12687_source_backed_python_foundational_corpus"
        / "private/594cbbdc08af0cc409eceda1/foundational_train_eval_manifest.jsonl"
    )
    command = [
        sys.executable, str(TRAINER), "--repo-root", str(probe_repo),
        "--manifest", str(manifest), "--mode", "foundational_code_ce",
        "--foundational-training-contract", str(ROOT / "configs/training/foundational_code_ce_optimizer_v1.json"),
        "--max-train-rows", "4", "--max-eval-rows", "4", "--max-strict-rows", "0",
        "--max-steps", "1", "--batch-size", "2", "--decoder-ce-weight", "1.0",
        "--structured-aux-weight", "0", "--denoise-weight", "0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export",
        "--skip-final-model-save", "1", "--output-dir", str(probe_repo / "runs" / "foundational"),
        "--run-id", "foundational-integration-test", "--implementation", "transformer",
        "--probe-scale", "tiny_transformer",
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--generation-audit-splits", "eval",
    ]
    command.append("--contract-only" if contract_only else "--execution-authorized-for-recovery-probe")
    return command


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
    for index, row in enumerate(lifted):
        row.setdefault("repo_family", "fixture-safe-repo")
        row.setdefault("root_identity", f"fixture-safe-root-{index}")
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


@pytest.mark.parametrize(
    "bounded_choice_aux_source",
    [
        "encoder_option_retrieval_semantic_candidate_head",
        "encoder_option_retrieval_evidence_role_map",
    ],
)
def test_cli_removes_deterministic_placeholder_bounded_choice_aux_source(
    tmp_path: Path, bounded_choice_aux_source: str
) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    cmd = base_cmd(tmp_path, manifest) + [
        "--contract-only",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "1.0",
        "--bounded-choice-aux-source",
        bounded_choice_aux_source,
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 2
    assert "invalid choice" in result.stderr
    assert bounded_choice_aux_source in result.stderr


def test_contract_accepts_learned_cross_encoder_bounded_choice_aux_source(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest)
    cmd = base_cmd(tmp_path, manifest) + [
        "--contract-only",
        "--decoder-ce-weight",
        "0.0",
        "--bounded-choice-aux-weight",
        "1.0",
        "--bounded-choice-aux-source",
        "encoder_option_cross_encoder",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert result.returncode == 0
    card = json.loads(result.stdout)
    assert card["passed"] is True


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
        "--max-decoder-tokens",
        "128",
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


def test_foundational_mode_rejects_noncanonical_manifest(tmp_path: Path) -> None:
    module = load_trainer_module()
    fake = tmp_path / "foundational.jsonl"
    fake.write_text(
        json.dumps({
            "row_id": "stage12687_fake",
            "split": "train",
            "source_provenance": {"source_stage": "stage12687_source_backed_python_foundational_corpus"},
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(module.ProbeContractError, match="canonical Stage12687 manifest path"):
        module.load_manifest(fake, mode="foundational_code_ce")


def test_foundational_contract_validates_but_execution_remains_blocked(tmp_path: Path) -> None:
    subprocess.run(foundational_cmd(tmp_path, contract_only=True), check=True, text=True, capture_output=True)
    out = tmp_path / "foundational-repo" / "runs" / "foundational"
    contract = json.loads((out / "probe_contract_audit.json").read_text())
    assert contract["passed"] is True
    assert contract["generation_id"] == "594cbbdc08af0cc409eceda1"
    assert contract["split_counts"] == {"train": 16000, "eval": 2000, "strict_eval": 0, "other": 0}
    assert contract["schema_error_count"] == 0
    assert contract["max_untruncated_encoder_tokens"] == 1278
    assert contract["max_untruncated_decoder_tokens"] == 411
    assert contract["decoder_ce_only"] is True
    assert contract["deterministic_choice_features_enabled"] is False
    assert contract["strict_eval_accessible_to_process"] is False
    assert contract["execution_admitted"] is False
    assert contract["production_optimizer_checkpoint_contract_validated"] is True
    assert contract["production_training_contract_sha256"] == "36d64f5e1448cfe8d3f24ffa9087598b74ecb4a83741520c45a65a489d7b6125"
    assert contract["authoritative_training_eligible_rows"] == 0
    assert contract["license_policy"] == "internal_code_user_waiver_2026_08_02"
    assert any("authority remains false" in item for item in contract["execution_blockers"])
    assert all("strict plaintext" not in item for item in contract["execution_blockers"])
    assert all("optimizer/checkpoint" not in item for item in contract["execution_blockers"])
    assert not (out / "execution_result.json").exists()

    denied = subprocess.run(foundational_cmd(tmp_path), text=True, capture_output=True)
    assert denied.returncode != 0
    assert "execution remains admission-blocked" in (denied.stdout + denied.stderr)
    assert not (out / "execution_result.json").exists()


def test_foundational_runtime_wrapper_is_unconditionally_admission_blocked() -> None:
    sys.path.insert(0, str(ROOT / "legacy_src"))
    from agentkernel_lite.training_loop import run_foundational_code_ce

    with pytest.raises(ValueError, match="execution remains admission-blocked"):
        run_foundational_code_ce(max_strict_rows=0, bounded_choice_aux_weight=0.0)


def test_trainer_rejects_stage12686_exact_row_and_lineage_copy(tmp_path: Path) -> None:
    module = load_trainer_module()
    source = ROOT / "runs/local/artifacts/stage12662_structured_repo_state_training_admission_preflight_only/private/structured_repo_state_trainer_manifest.jsonl"
    row = json.loads(next(line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()))
    exact = tmp_path / "exact_quarantined.jsonl"
    exact.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(module.ProbeContractError, match="Stage12686 semantic nonadmission"):
        module.load_manifest(exact)

    row["unrelated_copy_marker"] = True
    copied = tmp_path / "copied_quarantined.jsonl"
    copied.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(module.ProbeContractError, match="Stage12686 semantic nonadmission"):
        module.load_manifest(copied)



def test_trainer_rejects_modified_explicit_stage12680_quarantine_copy(tmp_path: Path) -> None:
    module = load_trainer_module()
    source = ROOT / "runs/local/artifacts/stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only/private/deep_repo_code_knowledge_shortcut_quarantine.jsonl"
    row = next(
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("split") == "train"
    )
    row["unrelated_copy_marker"] = True
    copied = tmp_path / "modified_explicit_quarantine.jsonl"
    copied.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(module.ProbeContractError, match="Stage12686 semantic nonadmission"):
        module.load_manifest(copied)


def test_trainer_rejects_unreleased_stage12687_rows(tmp_path: Path) -> None:
    module = load_trainer_module()
    manifest = tmp_path / "stage12687.jsonl"
    row = {
        "row_id": "stage12687_fixture",
        "split": "train",
        "root_identity": "fixture-safe-root",
        "source_provenance": {"source_stage": "stage12687_source_backed_python_foundational_corpus"},
    }
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(module.ProbeContractError, match="stage12687_release_review_required"):
        module.load_manifest(manifest)


def test_semantic_nonadmission_ledger_tamper_fails_closed(tmp_path: Path) -> None:
    module = load_trainer_module()
    module.SEMANTIC_NONADMISSION_DIR = tmp_path
    module._SEMANTIC_NONADMISSION_HASHES = None
    for name in module.SEMANTIC_NONADMISSION_LEDGER_CONTRACT:
        (tmp_path / name).write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="ledger hash mismatch"):
        module._semantic_nonadmission_hashes()


def test_generation_encoder_row_does_not_mutate_or_supervise_target() -> None:
    sys.path.insert(0, str(ROOT / "legacy_src"))
    from agentkernel_lite.training_loop import _generation_encoder_row

    row = {
        "row_id": "generation-invariant",
        "target": {"decoder_text": "full supervised target"},
        "decoder_text": "direct decoder target",
        "target_text": "direct target text",
        "target_ref": "direct target ref",
        "loss_mask": {"decoder_ce": True},
        "model_input": {"visible": "evidence"},
    }
    before = json.loads(json.dumps(row))
    generation_row = _generation_encoder_row(row)
    assert row == before
    assert generation_row["target"] == {"decoder_text": ""}
    assert generation_row["decoder_text"] == ""
    assert generation_row["target_text"] == ""
    assert generation_row["target_ref"] == ""
    assert generation_row["loss_mask"] == {}
    assert generation_row["model_input"] == row["model_input"]


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
                "repo_family": "fixture-safe-repo",
                "root_identity": f"fixture-safe-root-{index}",
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
    source = ROOT / "runs" / "local" / "artifacts" / "stage9743_multilingual_edit_localization_target_only_package" / "multilingual_edit_localization_target_only.jsonl"
    manifest = copy_manifest_with_safe_identity(source, tmp_path / "target_only.jsonl")
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
    source = ROOT / "runs" / "local" / "artifacts" / "stage9790_edit_localization_opaque_choice_surface" / "edit_localization_opaque_choice_surface.jsonl"
    phase2_source = ROOT / "runs" / "local" / "artifacts" / "stage9813_web_isolated_disambiguator_surface" / "web_isolated_disambiguator_surface.jsonl"
    manifest = copy_manifest_with_safe_identity(source, tmp_path / "phase1.jsonl")
    phase2_manifest = copy_manifest_with_safe_identity(phase2_source, tmp_path / "phase2.jsonl")
    result = subprocess.run(two_phase_structured_cmd(tmp_path, manifest, phase2_manifest) + ["--contract-only"], check=True, text=True, capture_output=True)
    card = json.loads(result.stdout)
    assert card["passed"] is True
    assert card["phase1_mode"] == "edit_localization_probe"
    assert card["phase2_mode"] == "edit_localization_probe"
    assert card["two_phase_in_memory_required"] is True
    assert card["checkpoint_export_allowed_between_phases"] is False


def test_structured_contract_blocks_patch_operator_manifest_without_encoder_visible_evidence(tmp_path: Path) -> None:
    source = ROOT / "runs" / "local" / "artifacts" / "stage9735_multilingual_patch_operator_label_aligned_package" / "multilingual_patch_operator_label_aligned.jsonl"
    manifest = copy_manifest_with_safe_identity(source, tmp_path / "patch_operator.jsonl")
    result = subprocess.run(structured_cmd(tmp_path, manifest, mode="patch_operator_probe") + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    readiness = card["multilingual_surface_readiness"]
    assert readiness["passed"] is False
    assert readiness["failed_bucket_count"] == 12


def test_structured_contract_blocks_verifier_repair_manifest_without_encoder_visible_evidence(tmp_path: Path) -> None:
    source = ROOT / "runs" / "local" / "artifacts" / "stage9738_multilingual_verifier_repair_label_aligned_package" / "multilingual_verifier_repair_label_aligned.jsonl"
    manifest = copy_manifest_with_safe_identity(source, tmp_path / "verifier_repair.jsonl")
    result = subprocess.run(structured_cmd(tmp_path, manifest, mode="verifier_repair_probe") + ["--contract-only"], text=True, capture_output=True)
    assert result.returncode == 1
    card = json.loads(result.stdout)
    assert card["passed"] is False
    readiness = card["multilingual_surface_readiness"]
    assert readiness["passed"] is False
    assert readiness["failed_bucket_count"] == 12


def write_identity_gate_manifest(
    path: Path,
    *,
    split: str,
    repo_family: str | None = "fixture-safe-repo",
    root_identity: object = "fixture-safe-root",
) -> None:
    row: dict[str, object] = {"row_id": path.stem, "split": split}
    if repo_family is not None:
        row["repo_family"] = repo_family
    if root_identity is not None:
        row["root_identity"] = root_identity
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")


def test_denied_unsloth_train_manifest_is_accepted(tmp_path: Path) -> None:
    manifest = tmp_path / "denied_train.jsonl"
    write_identity_gate_manifest(manifest, split="training", repo_family="Unsloth")
    rows = load_trainer_module().load_manifest(manifest)
    assert rows[0]["split"] == "train"
    assert rows[0]["repo_family"] == "Unsloth"


@pytest.mark.parametrize("split", ["validation", "eval", "strict", "sealed", "source-heldout"])
def test_denied_unsloth_heldout_aliases_are_rejected(tmp_path: Path, split: str) -> None:
    manifest = tmp_path / f"denied_{split}.jsonl"
    write_identity_gate_manifest(manifest, split=split, repo_family="UNSLOTH")
    with pytest.raises(ValueError, match="denied future-eval identity"):
        load_trainer_module().load_manifest(manifest)


def test_identityless_heldout_manifest_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "identityless.jsonl"
    write_identity_gate_manifest(
        manifest,
        split="eval",
        repo_family=None,
        root_identity=None,
    )
    with pytest.raises(ValueError, match="no recognized identity"):
        load_trainer_module().load_manifest(manifest)


def test_unknown_explicit_split_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "unknown_split.jsonl"
    write_identity_gate_manifest(manifest, split="test")
    with pytest.raises(ValueError, match="unknown explicit manifest split"):
        load_trainer_module().load_manifest(manifest)


def test_future_eval_denylist_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mandatory future-eval identity denylist missing"):
        load_future_eval_identity_denylist(tmp_path / "missing.json")


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        json.dumps({"schema_version": 1, "record_type": "future_eval_identity_denylist_v1"}),
        json.dumps(
            {
                "schema_version": 1,
                "record_type": "future_eval_identity_denylist_v1",
                "deny": {
                    "repo_family": ["safe"],
                    "source_path": ["/safe"],
                    "root_identity": ["safe-root"],
                    "unknown": ["not-allowed"],
                },
            }
        ),
    ],
)
def test_future_eval_denylist_loader_rejects_malformed_schema(
    tmp_path: Path,
    payload: str,
) -> None:
    denylist = tmp_path / "denylist.json"
    denylist.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        load_future_eval_identity_denylist(denylist)


@pytest.mark.parametrize("phase_name", ["phase2", "phase3"])
def test_denied_phase_manifest_cannot_bypass_load_manifest(
    tmp_path: Path,
    phase_name: str,
) -> None:
    manifest = tmp_path / f"{phase_name}.jsonl"
    write_identity_gate_manifest(
        manifest,
        split="strict_eval",
        repo_family="Unsloth",
    )
    with pytest.raises(ValueError, match="denied future-eval identity"):
        load_trainer_module().load_manifest(manifest)



@pytest.mark.parametrize(
    ("marker", "value"),
    [
        ("source_heldout", True),
        ("strict_eval_eligible", True),
        ("evaluation_allowed", True),
    ],
)
def test_train_split_cannot_override_heldout_boolean_marker(
    tmp_path: Path,
    marker: str,
    value: bool,
) -> None:
    manifest = tmp_path / f"conflict_{marker}.jsonl"
    row = {"row_id": marker, "split": "train", marker: value, "repo_family": "safe"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="train split conflicts with heldout markers"):
        load_trainer_module().load_manifest(manifest)


def test_boolean_only_source_heldout_row_is_not_defaulted_to_train(tmp_path: Path) -> None:
    manifest = tmp_path / "boolean_only.jsonl"
    row = {"row_id": "heldout", "source_heldout": True, "repo_family": "safe", "root_identity": "safe-root"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    rows = load_trainer_module().load_manifest(manifest)
    assert rows[0]["split"] == "strict_eval"


@pytest.mark.parametrize("value", [False, None, "false", 1])
def test_ambiguous_marker_only_row_is_rejected(tmp_path: Path, value: object) -> None:
    manifest = tmp_path / "ambiguous_marker.jsonl"
    row = {"row_id": "ambiguous", "source_heldout": value, "repo_family": "safe"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_trainer_module().load_manifest(manifest)


@pytest.mark.parametrize(
    "identity",
    [
        {"RePoSiToRy": "UNSLOTH"},
        {"SOURCE_REPOSITORY": "/ARXIV/repositories/UNSLOTH"},
        {"Before_Commit": "420799B61EF35D6CFD87C4F4B02C98152FDF6599"},
        {"lineage": {"AFTER": "76A2B9EDF160D68208DC30C02C6523BC6551F950"}},
    ],
)
def test_trainer_rejects_case_variant_repository_and_commit_aliases(
    tmp_path: Path,
    identity: dict[str, object],
) -> None:
    manifest = tmp_path / "case_alias.jsonl"
    row = {"row_id": "denied", "split": "eval", **identity}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="denied future-eval identity"):
        load_trainer_module().load_manifest(manifest)


@pytest.mark.parametrize("split_role", ["heldout", "hidden_final", "sealed", "locked-eval"])
def test_trainer_split_role_heldout_aliases_enforce_identity_gate(
    tmp_path: Path,
    split_role: str,
) -> None:
    manifest = tmp_path / f"split_role_{split_role}.jsonl"
    row = {"row_id": split_role, "split_role": split_role, "repo_family": "UNSLOTH"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="denied future-eval identity"):
        load_trainer_module().load_manifest(manifest)


@pytest.mark.parametrize("split_role", ["train", "training", "train-support", "train_only"])
def test_trainer_split_role_train_aliases_canonicalize(
    tmp_path: Path,
    split_role: str,
) -> None:
    manifest = tmp_path / f"split_role_{split_role}.jsonl"
    row = {"row_id": split_role, "split_role": split_role, "repo_family": "safe"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    rows = load_trainer_module().load_manifest(manifest)
    assert rows[0]["split"] == "train"


def test_trainer_rejects_conflicting_split_role(tmp_path: Path) -> None:
    manifest = tmp_path / "conflicting_split_role.jsonl"
    row = {"row_id": "conflict", "split": "train", "split_role": "hidden_final", "repo_family": "safe"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting explicit manifest splits"):
        load_trainer_module().load_manifest(manifest)


@pytest.mark.parametrize("alias", ["commit", "commit_sha", "commit_hash", "revision"])
def test_trainer_rejects_denied_common_commit_aliases(tmp_path: Path, alias: str) -> None:
    manifest = tmp_path / f"denied_{alias}.jsonl"
    row = {"row_id": alias, "split_role": "sealed", alias.swapcase(): "420799B61EF35D6CFD87C4F4B02C98152FDF6599"}
    manifest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="denied future-eval identity"):
        load_trainer_module().load_manifest(manifest)
