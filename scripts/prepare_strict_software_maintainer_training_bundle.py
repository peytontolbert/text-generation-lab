from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json
from prepare_strict_long_context_retrieval_training_dataset import prepare_strict_long_context_retrieval_training_dataset
from prepare_strict_long_context_training_dataset import prepare_strict_long_context_training_dataset

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_software_maintainer_training_bundle_entrypoint_v1.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(base_dir: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _load_entrypoint_config(config_path: Path) -> dict[str, Any]:
    config = _read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"invalid_config:{config_path}")
    return config


def prepare_strict_software_maintainer_training_bundle(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    long_context_config_path: Path | None = None,
    retrieval_config_path: Path | None = None,
    output_dir: Path | None = None,
    include_audit_only_direct: bool | None = None,
    include_retrieval_opt_in_profiles: bool | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_entrypoint_config(config_path)
    config_dir = config_path.parent

    defaults = dict(config.get("bundle_defaults") or {})
    resolved_long_context_config = long_context_config_path or _resolve_path(config_dir, defaults.get("long_context_config"))
    if resolved_long_context_config is None or not resolved_long_context_config.exists():
        raise FileNotFoundError(f"missing_long_context_config:{resolved_long_context_config}")

    resolved_retrieval_config = retrieval_config_path or _resolve_path(config_dir, defaults.get("retrieval_config"))
    if resolved_retrieval_config is None or not resolved_retrieval_config.exists():
        raise FileNotFoundError(f"missing_retrieval_config:{resolved_retrieval_config}")

    resolved_output_dir = output_dir or _resolve_path(config_dir, defaults.get("output_dir"))
    if resolved_output_dir is None:
        raise ValueError("missing_output_dir")
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    long_context = prepare_strict_long_context_training_dataset(
        config_path=resolved_long_context_config,
        include_audit_only_direct=include_audit_only_direct,
    )
    retrieval = prepare_strict_long_context_retrieval_training_dataset(
        config_path=resolved_retrieval_config,
        include_opt_in_profiles=include_retrieval_opt_in_profiles,
    )

    long_context_dataset_card_path = str((Path(long_context['output_dir']) / 'strict_long_context_training_dataset_card.json').resolve())
    split_pipeline = dict(long_context.get('split_pipeline') or {})
    split_rows_path = ((split_pipeline.get('splits') or {}).get('rows_path'))
    sampled_manifest_path = ((split_pipeline.get('sampled') or {}).get('manifest_path'))
    split_audit_path = ((split_pipeline.get('audit') or {}).get('output_path'))

    bundle = {
        "entrypoint_config_path": str(config_path),
        "output_dir": str(resolved_output_dir),
        "long_context_entrypoint_config_path": str(resolved_long_context_config),
        "retrieval_entrypoint_config_path": str(resolved_retrieval_config),
        "long_context_training_dataset_card_path": long_context_dataset_card_path,
        "retrieval_training_dataset_card_path": str((Path(retrieval['output_dir']) / 'strict_long_context_retrieval_training_dataset_card.json').resolve()),
        "trainer_default_long_context_manifest": long_context_dataset_card_path,
        "trainer_default_long_context_dataset_card": long_context_dataset_card_path,
        "trainer_default_long_context_filtered_shard_manifest": str(long_context.get('strict_shard_manifest_path') or ''),
        "trainer_default_long_context_source_shard_manifest": str(long_context.get('source_strict_shard_manifest_path') or ''),
        "trainer_default_long_context_split_rows": str(split_rows_path or ''),
        "trainer_default_long_context_sampled_manifest": str(sampled_manifest_path or ''),
        "trainer_default_long_context_split_audit": str(split_audit_path or ''),
        "trainer_default_retrieval_manifests": dict(retrieval.get('default_sampled_manifests') or {}),
        "retrieval_trainer_default_profiles": list(retrieval.get('trainer_default_profiles') or []),
        "retrieval_opt_in_profiles": list(retrieval.get('opt_in_profiles') or []),
        "long_context_summary": {
            'compile_summary': long_context.get('compile_summary'),
            'parquet_summary': long_context.get('parquet_summary'),
            'train_ready_audit_summary': long_context.get('train_ready_audit_summary'),
            'shard_filter_summary': long_context.get('shard_filter_summary'),
            'split_pipeline': split_pipeline,
        },
        "retrieval_summary": {
            'trainer_default_profiles': retrieval.get('trainer_default_profiles'),
            'default_sampled_manifests': retrieval.get('default_sampled_manifests'),
            'opt_in_profiles': retrieval.get('opt_in_profiles'),
        },
    }
    write_json(resolved_output_dir / 'strict_software_maintainer_training_bundle_card.json', bundle)
    return bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a top-level software-maintainer training bundle that references both the canonical long-context and retrieval training dataset cards.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--long-context-config", type=Path)
    parser.add_argument("--retrieval-config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--include-audit-only-direct", action="store_true")
    parser.add_argument("--include-retrieval-opt-in-profiles", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_strict_software_maintainer_training_bundle(
        config_path=args.config,
        long_context_config_path=args.long_context_config,
        retrieval_config_path=args.retrieval_config,
        output_dir=args.output_dir,
        include_audit_only_direct=args.include_audit_only_direct if args.include_audit_only_direct else None,
        include_retrieval_opt_in_profiles=args.include_retrieval_opt_in_profiles if args.include_retrieval_opt_in_profiles else None,
    )


if __name__ == "__main__":
    main()
