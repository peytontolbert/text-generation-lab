from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from loss_mask_card import normalize_loss_mask, read_jsonl, validate_loss_mask_row
from safe_paths import UnsafePathError, assert_no_destructive_command_tokens
from stage_summary_schema import AUTHORITY_KEYS, normalize_authority

REQUIRED_FLAGS = [
    "--repo-root",
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--decoder-ce-weight",
    "--structured-aux-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "--output-dir",
]
REQUIRED_ARTIFACTS = [
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
]
FORBIDDEN_COMMAND_TOKENS = [
    "--run-runtime",
    "--run-gemma",
    "--run-harness",
    "--hidden-scoring",
    "--save-final-checkpoint", "1",
    "--export-browser-bitnet", "1",
]


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"not object: {path}")
    return value


def split_of(row: dict[str, Any]) -> str:
    value = str(row.get("split") or row.get("package_split") or "train")
    return "strict_eval" if value == "strict" else value


def audit_manifest(rows: list[dict[str, Any]], *, max_train: int, max_eval: int, max_strict: int, max_decoder_tokens: int) -> dict[str, Any]:
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0, "other": 0}
    unsafe_loss = []
    authority_rows = []
    over_cap = []
    for i, row in enumerate(rows):
        rid = str(row.get("row_id") or f"row_{i}")
        split = split_of(row)
        split_counts[split if split in split_counts else "other"] += 1
        mask = normalize_loss_mask(row)
        enabled = [k for k, v in mask.items() if v]
        if enabled != ["decoder_ce"]:
            unsafe_loss.append({"row_id": rid, "enabled": enabled})
        mask_errors = validate_loss_mask_row(row, allow_decoder_ce=True, allow_denoise=False, allow_runtime=False)
        if mask_errors:
            unsafe_loss.append({"row_id": rid, "errors": mask_errors})
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else row
        if any(bool(authority.get(k, False)) for k in AUTHORITY_KEYS):
            authority_rows.append(rid)
        token_len = row.get("decoder_token_len") or row.get("target_token_len") or 0
        try:
            token_len_i = int(token_len)
        except Exception:
            token_len_i = 999999
        if token_len_i > max_decoder_tokens:
            over_cap.append(rid)
    errors = []
    if split_counts["train"] > max_train:
        errors.append("train cap exceeded")
    if split_counts["eval"] > max_eval:
        errors.append("eval cap exceeded")
    if split_counts["strict_eval"] > max_strict:
        errors.append("strict cap exceeded")
    if split_counts["other"]:
        errors.append("unexpected split rows")
    if unsafe_loss:
        errors.append("unsafe loss rows")
    if authority_rows:
        errors.append("authority rows")
    if over_cap:
        errors.append("over cap rows")
    return {
        "rows": len(rows),
        "split_counts": split_counts,
        "unsafe_loss_rows": len(unsafe_loss),
        "authority_rows": len(authority_rows),
        "over_cap_rows": len(over_cap),
        "errors": errors,
        "passed": not errors and bool(rows),
    }


def audit(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    gates: dict[str, bool] = {}
    repo = args.repo_root.resolve()
    trainer = (repo / args.trainer).resolve() if not args.trainer.is_absolute() else args.trainer.resolve()
    manifest = (repo / args.manifest).resolve() if not args.manifest.is_absolute() else args.manifest.resolve()
    wrapper = (repo / args.wrapper_design).resolve() if not args.wrapper_design.is_absolute() else args.wrapper_design.resolve()
    output_dir = (repo / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()

    gates["trainer_exists"] = trainer.is_file()
    gates["manifest_exists"] = manifest.is_file()
    gates["wrapper_design_exists"] = wrapper.is_file()
    gates["output_dir_under_repo_root"] = is_relative_to(output_dir, repo)
    if not gates["trainer_exists"]:
        errors.append(f"trainer missing: {trainer}")
    if not gates["manifest_exists"]:
        errors.append(f"manifest missing: {manifest}")
    if not gates["wrapper_design_exists"]:
        errors.append(f"wrapper design missing: {wrapper}")
    if not gates["output_dir_under_repo_root"]:
        errors.append("output dir is not under repo root")

    help_missing: list[str] = []
    if trainer.is_file():
        result = subprocess.run([sys.executable, str(trainer), "--help"], text=True, capture_output=True, check=False)
        help_text = result.stdout + result.stderr
        help_missing = [flag for flag in REQUIRED_FLAGS if flag not in help_text]
        gates["trainer_help_only_train_entrypoint"] = result.returncode == 0 and not help_missing
        if help_missing:
            errors.append(f"trainer help missing flags: {help_missing}")
    else:
        gates["trainer_help_only_train_entrypoint"] = False

    wrapper_payload: dict[str, Any] = {}
    command: list[str] = []
    if wrapper.is_file():
        wrapper_payload = load_json(wrapper)
        command = [str(x) for x in wrapper_payload.get("command", [])]
        missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in command]
        gates["wrapper_command_has_required_flags"] = not missing_flags
        if missing_flags:
            errors.append(f"wrapper missing flags: {missing_flags}")
        gates["wrapper_command_contract_only"] = "--contract-only" in command
        if "--contract-only" not in command:
            errors.append("wrapper command is not contract-only")
        gates["wrapper_authority_closed"] = not any(normalize_authority(wrapper_payload).values())
        if not gates["wrapper_authority_closed"]:
            errors.append("wrapper authority open")
        try:
            assert_no_destructive_command_tokens(command)
            gates["wrapper_destructive_tokens_absent"] = True
        except UnsafePathError as exc:
            gates["wrapper_destructive_tokens_absent"] = False
            errors.append(str(exc))
        forbidden_pair = " ".join(command)
        forbidden_present = [tok for tok in ["--run-runtime", "--run-gemma", "--run-harness", "--hidden-scoring"] if tok in command]
        if "--save-final-checkpoint 1" in forbidden_pair or "--export-browser-bitnet 1" in forbidden_pair:
            forbidden_present.append("checkpoint_or_browser_export_enabled")
        gates["forbidden_execution_flags_absent"] = not forbidden_present
        if forbidden_present:
            errors.append(f"forbidden execution flags: {forbidden_present}")
        required_artifacts = wrapper_payload.get("required_artifacts", [])
        missing_artifacts = [a for a in REQUIRED_ARTIFACTS if a not in required_artifacts]
        gates["required_telemetry_declared"] = not missing_artifacts
        if missing_artifacts:
            errors.append(f"required artifacts missing from wrapper design: {missing_artifacts}")

    manifest_card = {"passed": False, "rows": 0}
    if manifest.is_file():
        manifest_card = audit_manifest(
            read_jsonl(manifest),
            max_train=args.max_train_rows,
            max_eval=args.max_eval_rows,
            max_strict=args.max_strict_rows,
            max_decoder_tokens=args.max_decoder_tokens,
        )
        gates["manifest_loss_mask_passed"] = manifest_card["passed"]
        if not manifest_card["passed"]:
            errors.append(f"manifest audit failed: {manifest_card['errors']}")

    auth = {key: False for key in AUTHORITY_KEYS}
    return {
        "stage": 8583,
        "stage_name": "stage8583_v27_bounded_decoder_ce_patched_final_pre_execution_audit",
        "passed": not errors,
        "claim_scope": "final_pre_execution_audit_rebuilt_non_executing",
        "repo_root": str(repo),
        "trainer": str(trainer),
        "manifest": str(manifest),
        "wrapper_design": str(wrapper),
        "output_dir": str(output_dir),
        "gates": gates,
        "errors": errors,
        "manifest_card": manifest_card,
        "trainer_help_missing_flags": help_missing,
        "model_execution_attempted": False,
        "actual_execution_authorized_next": False,
        "authority": auth,
        "next_best_step": "only after this audit passes should real tiny execution implementation be rebuilt and separately authorized",
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Final pre-execution audit for bounded decoder CE probe, non-executing.")
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--trainer", type=Path, default=Path("legacy_src/scripts/train_agentkernel_lite_encdec.py"))
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--wrapper-design", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("runs/local/probes/stage8584_v27_bounded_decoder_ce_tiny_probe_execution"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-train-rows", type=int, default=32)
    p.add_argument("--max-eval-rows", type=int, default=16)
    p.add_argument("--max-strict-rows", type=int, default=16)
    p.add_argument("--max-decoder-tokens", type=int, default=768)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    card = audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
