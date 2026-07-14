from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from materialize_trainer_setup import read_jsonl

from assign_strict_long_context_pack_splits import assign_strict_long_context_pack_splits
from audit_strict_long_context_split_quality import audit_strict_long_context_split_quality
from compile_long_context_pack_trainer_rows import stream_compile_long_context_pack_trainer_rows
from export_compiled_long_context_shards_to_parquet import export_compiled_long_context_shards_to_parquet
from long_context_common import write_json
from materialize_strict_long_context_mixture_rows import materialize_strict_long_context_mixture_rows
from prepare_strict_long_context_mixture import build_strict_long_context_mixture_manifest
from sample_strict_long_context_mixture_rows import sample_strict_long_context_mixture_rows


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


def _load_train_ready_audit_summary(*, strict_shard_manifest_path: Path, include_audit_only_direct: bool) -> dict[str, Any] | None:
    manifest = _read_json(strict_shard_manifest_path)
    selected = [dict(row) for row in manifest.get('selected_shards') or [] if isinstance(row, dict)]

    included_shards: list[dict[str, Any]] = []
    pack_rows_all: list[dict[str, Any]] = []
    for shard in selected:
        acceptance_mode = str(shard.get('acceptance_mode') or '')
        if acceptance_mode == 'audit_only_direct' and not include_audit_only_direct:
            continue
        if not bool(shard.get('ready_for_training')):
            continue
        artifacts = dict(shard.get('artifacts') or {})
        pack_audit_path_text = str(artifacts.get('pack_audit_jsonl') or '').strip()
        if not pack_audit_path_text:
            continue
        pack_audit_path = Path(pack_audit_path_text)
        if not pack_audit_path.exists():
            continue
        pack_rows = [dict(row) for row in read_jsonl(pack_audit_path) if isinstance(row, dict)]
        if not pack_rows:
            continue
        pack_rows_all.extend(pack_rows)
        state_delta_values = [float(row.get('state_delta_ready_fraction') or 0.0) for row in pack_rows]
        evidence_anchor_values = [float(row.get('evidence_anchor_ready_fraction') or 0.0) for row in pack_rows]
        included_shards.append({
            'name': str(shard.get('name') or ''),
            'acceptance_mode': acceptance_mode,
            'pack_audit_jsonl': str(pack_audit_path),
            'pack_count': len(pack_rows),
            'accepted_pack_count': sum(1 for row in pack_rows if bool(row.get('accepted'))),
            'avg_state_delta_ready_fraction': (sum(state_delta_values) / len(state_delta_values)) if state_delta_values else 0.0,
            'avg_evidence_anchor_ready_fraction': (sum(evidence_anchor_values) / len(evidence_anchor_values)) if evidence_anchor_values else 0.0,
            'min_state_delta_ready_fraction': min(state_delta_values) if state_delta_values else 0.0,
            'min_evidence_anchor_ready_fraction': min(evidence_anchor_values) if evidence_anchor_values else 0.0,
        })

    if not pack_rows_all:
        return None

    state_delta_values = [float(row.get('state_delta_ready_fraction') or 0.0) for row in pack_rows_all]
    evidence_anchor_values = [float(row.get('evidence_anchor_ready_fraction') or 0.0) for row in pack_rows_all]
    return {
        'included_shard_count': len(included_shards),
        'pack_audit_count': len(pack_rows_all),
        'accepted_pack_count': sum(1 for row in pack_rows_all if bool(row.get('accepted'))),
        'avg_state_delta_ready_fraction': (sum(state_delta_values) / len(state_delta_values)) if state_delta_values else 0.0,
        'avg_evidence_anchor_ready_fraction': (sum(evidence_anchor_values) / len(evidence_anchor_values)) if evidence_anchor_values else 0.0,
        'min_state_delta_ready_fraction': min(state_delta_values) if state_delta_values else 0.0,
        'min_evidence_anchor_ready_fraction': min(evidence_anchor_values) if evidence_anchor_values else 0.0,
        'included_shards': included_shards,
    }


def _filter_strict_shard_manifest(
    *,
    strict_shard_manifest_path: Path,
    include_audit_only_direct: bool,
    output_dir: Path,
    min_state_delta_ready_fraction: float | None,
    min_evidence_anchor_ready_fraction: float | None,
) -> tuple[Path, dict[str, Any] | None]:
    if min_state_delta_ready_fraction is None and min_evidence_anchor_ready_fraction is None:
        return strict_shard_manifest_path, None

    manifest = _read_json(strict_shard_manifest_path)
    selected = [dict(row) for row in manifest.get('selected_shards') or [] if isinstance(row, dict)]
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for shard in selected:
        acceptance_mode = str(shard.get('acceptance_mode') or '')
        if acceptance_mode == 'audit_only_direct' and not include_audit_only_direct:
            included.append(shard)
            continue
        if not bool(shard.get('ready_for_training')):
            included.append(shard)
            continue
        artifacts = dict(shard.get('artifacts') or {})
        pack_audit_path_text = str(artifacts.get('pack_audit_jsonl') or '').strip()
        if not pack_audit_path_text:
            excluded.append({
                'name': str(shard.get('name') or ''),
                'reason': 'missing_pack_audit_jsonl',
            })
            continue
        pack_audit_path = Path(pack_audit_path_text)
        if not pack_audit_path.exists():
            excluded.append({
                'name': str(shard.get('name') or ''),
                'reason': 'missing_pack_audit_file',
                'pack_audit_jsonl': str(pack_audit_path),
            })
            continue
        pack_rows = [dict(row) for row in read_jsonl(pack_audit_path) if isinstance(row, dict)]
        if not pack_rows:
            excluded.append({
                'name': str(shard.get('name') or ''),
                'reason': 'empty_pack_audit_file',
                'pack_audit_jsonl': str(pack_audit_path),
            })
            continue
        shard_min_state_delta = min(float(row.get('state_delta_ready_fraction') or 0.0) for row in pack_rows)
        shard_min_evidence_anchor = min(float(row.get('evidence_anchor_ready_fraction') or 0.0) for row in pack_rows)
        failed_thresholds: list[str] = []
        if min_state_delta_ready_fraction is not None and shard_min_state_delta < float(min_state_delta_ready_fraction):
            failed_thresholds.append('state_delta_ready_fraction')
        if min_evidence_anchor_ready_fraction is not None and shard_min_evidence_anchor < float(min_evidence_anchor_ready_fraction):
            failed_thresholds.append('evidence_anchor_ready_fraction')
        if failed_thresholds:
            excluded.append({
                'name': str(shard.get('name') or ''),
                'reason': 'below_quality_threshold',
                'failed_thresholds': failed_thresholds,
                'min_state_delta_ready_fraction': shard_min_state_delta,
                'min_evidence_anchor_ready_fraction': shard_min_evidence_anchor,
                'pack_audit_jsonl': str(pack_audit_path),
            })
            continue
        included.append(shard)

    if not included:
        raise ValueError('no_shards_meet_train_ready_quality_thresholds')

    filtered_manifest = dict(manifest)
    filtered_manifest['selected_shards'] = included
    filtered_manifest_path = output_dir / 'strict_shard_manifest.filtered_for_train_ready.json'
    write_json(filtered_manifest_path, filtered_manifest)
    summary = {
        'source_strict_shard_manifest_path': str(strict_shard_manifest_path),
        'effective_strict_shard_manifest_path': str(filtered_manifest_path),
        'include_audit_only_direct': bool(include_audit_only_direct),
        'min_state_delta_ready_fraction': min_state_delta_ready_fraction,
        'min_evidence_anchor_ready_fraction': min_evidence_anchor_ready_fraction,
        'included_shard_count': len(included),
        'excluded_shard_count': len(excluded),
        'included_shards': [str(row.get('name') or '') for row in included],
        'excluded_shards': excluded,
    }
    return filtered_manifest_path, summary


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
    prepare_split_pipeline: bool | None = None,
    mixture_output_dir: Path | None = None,
    mixture_rows_output_dir: Path | None = None,
    split_output_dir: Path | None = None,
    sampled_output_dir: Path | None = None,
    split_audit_output_path: Path | None = None,
    min_state_delta_ready_fraction: float | None = None,
    min_evidence_anchor_ready_fraction: float | None = None,
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
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    resolved_include_audit = bool(
        dataset_defaults.get("include_audit_only_direct", False)
        if include_audit_only_direct is None else include_audit_only_direct
    )
    resolved_export_parquet = bool(dataset_defaults.get("export_parquet", True) if export_parquet is None else export_parquet)
    resolved_max_positive_chunks = int(dataset_defaults.get("max_positive_chunks", 8) if max_positive_chunks is None else max_positive_chunks)
    resolved_rows_per_shard = int(dataset_defaults.get("rows_per_shard", 10000) if rows_per_shard is None else rows_per_shard)
    resolved_compression = str(dataset_defaults.get("compression", "zstd") if compression is None else compression)
    resolved_prepare_split_pipeline = bool(dataset_defaults.get("prepare_split_pipeline", False) if prepare_split_pipeline is None else prepare_split_pipeline)
    resolved_min_state_delta_ready_fraction = dataset_defaults.get("min_state_delta_ready_fraction") if min_state_delta_ready_fraction is None else min_state_delta_ready_fraction
    resolved_min_evidence_anchor_ready_fraction = dataset_defaults.get("min_evidence_anchor_ready_fraction") if min_evidence_anchor_ready_fraction is None else min_evidence_anchor_ready_fraction
    resolved_parquet_output_dir = parquet_output_dir or _resolve_path(config_dir, dataset_defaults.get("parquet_output_dir"))
    if resolved_export_parquet and resolved_parquet_output_dir is None:
        resolved_parquet_output_dir = resolved_output_dir / "parquet"

    effective_strict_manifest, shard_filter_summary = _filter_strict_shard_manifest(
        strict_shard_manifest_path=strict_manifest,
        include_audit_only_direct=resolved_include_audit,
        output_dir=resolved_output_dir,
        min_state_delta_ready_fraction=None if resolved_min_state_delta_ready_fraction is None else float(resolved_min_state_delta_ready_fraction),
        min_evidence_anchor_ready_fraction=None if resolved_min_evidence_anchor_ready_fraction is None else float(resolved_min_evidence_anchor_ready_fraction),
    )

    compile_summary = stream_compile_long_context_pack_trainer_rows(
        strict_shard_manifest_path=effective_strict_manifest,
        include_audit_only_direct=resolved_include_audit,
        output_dir=resolved_output_dir,
        max_positive_chunks=resolved_max_positive_chunks,
    )
    train_ready_audit_summary = _load_train_ready_audit_summary(
        strict_shard_manifest_path=effective_strict_manifest,
        include_audit_only_direct=resolved_include_audit,
    )
    if train_ready_audit_summary is not None:
        compile_summary['train_ready_audit_summary'] = train_ready_audit_summary

    parquet_summary: dict[str, Any] | None = None
    if resolved_export_parquet:
        parquet_summary = export_compiled_long_context_shards_to_parquet(
            compiled_dir=resolved_output_dir,
            output_dir=resolved_parquet_output_dir,
            rows_per_shard=resolved_rows_per_shard,
            compression=resolved_compression,
        )

    split_pipeline: dict[str, Any] | None = None
    if resolved_prepare_split_pipeline:
        resolved_mixture_output_dir = mixture_output_dir or _resolve_path(config_dir, dataset_defaults.get("mixture_output_dir"))
        resolved_mixture_rows_output_dir = mixture_rows_output_dir or _resolve_path(config_dir, dataset_defaults.get("mixture_rows_output_dir"))
        resolved_split_output_dir = split_output_dir or _resolve_path(config_dir, dataset_defaults.get("split_output_dir"))
        resolved_sampled_output_dir = sampled_output_dir or _resolve_path(config_dir, dataset_defaults.get("sampled_output_dir"))
        resolved_split_audit_output_path = split_audit_output_path or _resolve_path(config_dir, dataset_defaults.get("split_audit_output_path"))
        if resolved_mixture_output_dir is None or resolved_mixture_rows_output_dir is None or resolved_split_output_dir is None or resolved_sampled_output_dir is None or resolved_split_audit_output_path is None:
            raise ValueError("missing_split_pipeline_output_path")
        if not resolved_export_parquet:
            raise ValueError("split_pipeline_requires_parquet_exports")

        dataset_card_path = resolved_output_dir / "strict_long_context_training_dataset_card.json"
        provisional_dataset_card = {
            "entrypoint_config_path": str(config_path),
            "output_dir": str(resolved_output_dir),
            "strict_shard_manifest_path": str(effective_strict_manifest),
            "source_strict_shard_manifest_path": str(strict_manifest),
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
            "train_ready_audit_summary": train_ready_audit_summary,
            "shard_filter_summary": shard_filter_summary,
        }
        write_json(dataset_card_path, provisional_dataset_card)

        mixture = build_strict_long_context_mixture_manifest(
            dataset_card_path=dataset_card_path,
            bundle_card_path=None,
            output_dir=resolved_mixture_output_dir,
        )
        materialized = materialize_strict_long_context_mixture_rows(
            mixture_manifest_path=Path(mixture["mixture_manifest_path"]),
            output_dir=resolved_mixture_rows_output_dir,
        )
        splits = assign_strict_long_context_pack_splits(
            rows_path=Path(materialized["rows_path"]),
            output_dir=resolved_split_output_dir,
        )
        sampled = sample_strict_long_context_mixture_rows(
            rows_path=Path(splits["rows_path"]),
            output_dir=resolved_sampled_output_dir,
        )
        audit = audit_strict_long_context_split_quality(
            manifest_path=Path(sampled["manifest_path"]),
            output_path=resolved_split_audit_output_path,
        )
        audit_record = {
            **audit,
            "output_path": str(resolved_split_audit_output_path),
        }
        split_pipeline = {
            "mixture": mixture,
            "materialized": materialized,
            "splits": splits,
            "sampled": sampled,
            "audit": audit_record,
        }

    dataset_card = {
        "entrypoint_config_path": str(config_path),
        "output_dir": str(resolved_output_dir),
        "strict_shard_manifest_path": str(effective_strict_manifest),
        "source_strict_shard_manifest_path": str(strict_manifest),
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
        "train_ready_audit_summary": train_ready_audit_summary,
        "shard_filter_summary": shard_filter_summary,
        "split_pipeline": split_pipeline,
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
    parser.add_argument("--prepare-split-pipeline", action="store_true")
    parser.add_argument("--min-state-delta-ready-fraction", type=float)
    parser.add_argument("--min-evidence-anchor-ready-fraction", type=float)
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
        prepare_split_pipeline=args.prepare_split_pipeline if args.prepare_split_pipeline else None,
        min_state_delta_ready_fraction=args.min_state_delta_ready_fraction,
        min_evidence_anchor_ready_fraction=args.min_evidence_anchor_ready_fraction,
    )


if __name__ == "__main__":
    main()
