from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from compile_long_context_pack_trainer_rows import stream_compile_long_context_pack_trainer_rows
from export_compiled_long_context_shards_to_parquet import export_compiled_long_context_shards_to_parquet
from long_context_common import write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_long_context_training_entrypoint_v1.json"


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


def prepare_strict_long_context_training_dataset(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path | None = None,
    strict_shard_manifest_path: Path | None = None,
    include_audit_only_direct: bool | None = None,
    export_parquet: bool | None = None,
    parquet_output_dir: Path | None = None,
    max_positive_chunks: int | None = None,
    rows_per_shard: int | None = None,
    compression: str | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_entrypoint_config(config_path)
    config_dir = config_path.parent

    dataset_defaults = dict(config.get("dataset_defaults") or {})
    strict_manifest = strict_shard_manifest_path or _resolve_path(config_dir, dataset_defaults.get("strict_shard_manifest"))
    if strict_manifest is None:
        raise ValueError("missing_strict_shard_manifest")
    if not strict_manifest.exists():
        raise FileNotFoundError(f"missing_strict_shard_manifest:{strict_manifest}")

    resolved_output_dir = output_dir or _resolve_path(config_dir, dataset_defaults.get("output_dir"))
    if resolved_output_dir is None:
        raise ValueError("missing_output_dir")

    resolved_include_audit = bool(
        dataset_defaults.get("include_audit_only_direct", False)
        if include_audit_only_direct is None else include_audit_only_direct
    )
    resolved_export_parquet = bool(dataset_defaults.get("export_parquet", True) if export_parquet is None else export_parquet)
    resolved_max_positive_chunks = int(dataset_defaults.get("max_positive_chunks", 8) if max_positive_chunks is None else max_positive_chunks)
    resolved_rows_per_shard = int(dataset_defaults.get("rows_per_shard", 10000) if rows_per_shard is None else rows_per_shard)
    resolved_compression = str(dataset_defaults.get("compression", "zstd") if compression is None else compression)
    resolved_parquet_output_dir = parquet_output_dir or _resolve_path(config_dir, dataset_defaults.get("parquet_output_dir"))
    if resolved_export_parquet and resolved_parquet_output_dir is None:
        resolved_parquet_output_dir = resolved_output_dir / "parquet"

    compile_summary = stream_compile_long_context_pack_trainer_rows(
        strict_shard_manifest_path=strict_manifest,
        include_audit_only_direct=resolved_include_audit,
        output_dir=resolved_output_dir,
        max_positive_chunks=resolved_max_positive_chunks,
    )

    parquet_summary: dict[str, Any] | None = None
    if resolved_export_parquet:
        parquet_summary = export_compiled_long_context_shards_to_parquet(
            compiled_dir=resolved_output_dir,
            output_dir=resolved_parquet_output_dir,
            rows_per_shard=resolved_rows_per_shard,
            compression=resolved_compression,
        )

    dataset_card = {
        "entrypoint_config_path": str(config_path),
        "output_dir": str(resolved_output_dir),
        "strict_shard_manifest_path": str(strict_manifest),
        "include_audit_only_direct": resolved_include_audit,
        "export_parquet": resolved_export_parquet,
        "parquet_output_dir": str(resolved_parquet_output_dir) if resolved_parquet_output_dir is not None else None,
        "compiled_outputs": {
            "full_context_rows_jsonl": str((resolved_output_dir / "full_context_rows.jsonl").resolve()),
            "retrieval_rows_jsonl": str((resolved_output_dir / "retrieval_rows.jsonl").resolve()),
            "memory_rows_jsonl": str((resolved_output_dir / "memory_rows.jsonl").resolve()),
            "compile_card_json": str((resolved_output_dir / "compile_card.json").resolve()),
        },
        "parquet_outputs": (parquet_summary or {}).get("exports") if parquet_summary else None,
        "compile_summary": compile_summary,
        "parquet_summary": parquet_summary,
    }
    write_json(resolved_output_dir / "strict_long_context_training_dataset_card.json", dataset_card)
    return dataset_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a strict long-context training dataset from the accepted shard manifest.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--strict-shard-manifest", type=Path)
    parser.add_argument("--include-audit-only-direct", action="store_true")
    parser.add_argument("--export-parquet", dest="export_parquet", action="store_true")
    parser.add_argument("--no-export-parquet", dest="export_parquet", action="store_false")
    parser.set_defaults(export_parquet=None)
    parser.add_argument("--parquet-output-dir", type=Path)
    parser.add_argument("--max-positive-chunks", type=int)
    parser.add_argument("--rows-per-shard", type=int)
    parser.add_argument("--compression", type=str)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_strict_long_context_training_dataset(
        config_path=args.config,
        output_dir=args.output_dir,
        strict_shard_manifest_path=args.strict_shard_manifest,
        include_audit_only_direct=args.include_audit_only_direct if args.include_audit_only_direct else None,
        export_parquet=args.export_parquet,
        parquet_output_dir=args.parquet_output_dir,
        max_positive_chunks=args.max_positive_chunks,
        rows_per_shard=args.rows_per_shard,
        compression=args.compression,
    )


if __name__ == "__main__":
    main()
