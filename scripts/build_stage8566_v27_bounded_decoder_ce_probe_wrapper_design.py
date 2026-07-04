from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_ARTIFACTS = (
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "cleanup_proof.json",
)


def load_probe_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("probe config must be an object")
    return payload


def build_command(*, repo_root: Path, trainer: Path, manifest: Path, output_dir: Path, run_id: str, config: dict[str, Any]) -> list[str]:
    return [
        "python",
        str(trainer),
        "--repo-root",
        str(repo_root),
        "--manifest",
        str(manifest),
        "--mode",
        str(config.get("mode", "bounded_decoder_ce_probe")),
        "--max-train-rows",
        str(config.get("max_train_rows", 32)),
        "--max-eval-rows",
        str(config.get("max_eval_rows", 16)),
        "--max-strict-rows",
        str(config.get("max_strict_rows", 16)),
        "--max-steps",
        str(config.get("max_steps", 16)),
        "--decoder-ce-weight",
        str(config.get("decoder_ce_weight", 1.0)),
        "--structured-aux-weight",
        str(config.get("structured_aux_weight", 0.0)),
        "--denoise-weight",
        str(config.get("denoise_weight", 0.0)),
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(output_dir),
        "--run-id",
        run_id,
        "--contract-only",
    ]


def build_design(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    config = load_probe_config(args.probe_config)
    trainer = args.trainer
    if not trainer.is_absolute():
        trainer = repo_root / trainer
    manifest = args.manifest
    if not manifest.is_absolute():
        manifest = repo_root / manifest
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    command = build_command(
        repo_root=repo_root,
        trainer=trainer,
        manifest=manifest,
        output_dir=output_dir,
        run_id=args.run_id,
        config=config,
    )
    required_artifacts = config.get("required_artifacts") or list(DEFAULT_REQUIRED_ARTIFACTS)
    return {
        "stage": 8566,
        "stage_name": "stage8566_v27_bounded_decoder_ce_probe_wrapper_design",
        "passed": True,
        "claim_scope": "non_executing_wrapper_design_for_tiny_bounded_decoder_ce_probe",
        "repo_root": str(repo_root),
        "trainer": str(trainer),
        "manifest": str(manifest),
        "output_dir": str(output_dir),
        "run_id": args.run_id,
        "command": command,
        "constraints": {
            "mode": config.get("mode", "bounded_decoder_ce_probe"),
            "max_train_rows": config.get("max_train_rows", 32),
            "max_eval_rows": config.get("max_eval_rows", 16),
            "max_strict_rows": config.get("max_strict_rows", 16),
            "max_steps": config.get("max_steps", 16),
            "decoder_ce_weight": config.get("decoder_ce_weight", 1.0),
            "structured_aux_weight": config.get("structured_aux_weight", 0.0),
            "denoise_weight": config.get("denoise_weight", 0.0),
            "no_final_checkpoint_export": True,
            "contract_only": True,
        },
        "required_artifacts": required_artifacts,
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
        "next_best_step": "audit wrapper design statically before any probe execution",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a non-executing bounded decoder CE probe wrapper design.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--probe-config", type=Path, default=Path("configs/probes/bounded_decoder_ce_probe.json"))
    parser.add_argument("--trainer", type=Path, default=Path("legacy_src/scripts/train_agentkernel_lite_encdec.py"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("runs/local/probes/stage8584_v27_bounded_decoder_ce_tiny_probe_execution"))
    parser.add_argument("--run-id", default="stage8584")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    design = build_design(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(design, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
