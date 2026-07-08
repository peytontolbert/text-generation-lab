from __future__ import annotations

import hashlib
import json
import subprocess
import sys
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


def test_recovered_trainer_help_exposes_stage8580_flags() -> None:
    result = subprocess.run([sys.executable, str(TRAINER), "--help"], check=True, text=True, capture_output=True)
    for flag in [
        "--manifest",
        "--mode",
        "--decoder-ce-weight",
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

