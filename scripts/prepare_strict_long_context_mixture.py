from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_long_context_mixture_launcher_v1.json"
DEFAULT_BUNDLE_CARD_PATH = ROOT / "runs" / "local" / "artifacts" / "strict_software_maintainer_training_bundle_v1" / "strict_software_maintainer_training_bundle_card.json"
SURFACE_TO_JSONL_KEY = {
    "full_context_rows": "full_context_rows_jsonl",
    "retrieval_rows": "retrieval_rows_jsonl",
    "memory_rows": "memory_rows_jsonl",
}


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


def _load_config(config_path: Path) -> dict[str, Any]:
    config = _read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"invalid_config:{config_path}")
    return config


def _resolve_dataset_card_path(
    *,
    dataset_card_path: Path | None,
    bundle_card_path: Path | None,
) -> tuple[Path, Path | None]:
    if dataset_card_path is not None:
        resolved_dataset_card_path = dataset_card_path.resolve()
        if not resolved_dataset_card_path.exists():
            raise FileNotFoundError(f"missing_dataset_card:{resolved_dataset_card_path}")
        return resolved_dataset_card_path, bundle_card_path.resolve() if bundle_card_path is not None else None
    if bundle_card_path is None:
        raise ValueError("missing_dataset_card_or_bundle_card")
    resolved_bundle_card_path = bundle_card_path.resolve()
    if not resolved_bundle_card_path.exists():
        raise FileNotFoundError(f"missing_bundle_card:{resolved_bundle_card_path}")
    bundle_card = _read_json(resolved_bundle_card_path)
    resolved_dataset_card_value = str(bundle_card.get("long_context_training_dataset_card_path") or "").strip()
    if not resolved_dataset_card_value:
        raise ValueError(f"missing_long_context_training_dataset_card_path:{resolved_bundle_card_path}")
    resolved_dataset_card_path = Path(resolved_dataset_card_value).resolve()
    if not resolved_dataset_card_path.exists():
        raise FileNotFoundError(f"missing_dataset_card:{resolved_dataset_card_path}")
    return resolved_dataset_card_path, resolved_bundle_card_path


def _surface_parquet_dir(dataset_card: dict[str, Any], surface: str) -> Path | None:
    parquet_summary = dataset_card.get("parquet_summary") or {}
    exports = parquet_summary.get("exports") or {}
    surface_export = exports.get(surface)
    if not isinstance(surface_export, dict):
        return None
    output_dir = str(surface_export.get("output_dir") or "").strip()
    if not output_dir:
        return None
    return Path(output_dir)


def _surface_jsonl_path(dataset_card: dict[str, Any], surface: str) -> Path:
    compiled_outputs = dataset_card.get("compiled_outputs") or {}
    key = SURFACE_TO_JSONL_KEY[surface]
    value = str(compiled_outputs.get(key) or "").strip()
    if not value:
        raise ValueError(f"missing_compiled_output:{surface}:{key}")
    path = Path(value)
    if not path.exists():
        raise FileNotFoundError(f"missing_compiled_output:{path}")
    return path


def build_strict_long_context_mixture_manifest(
    *,
    dataset_card_path: Path | None = None,
    bundle_card_path: Path | None = DEFAULT_BUNDLE_CARD_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path | None = None,
    storage_format: str | None = None,
    surfaces: list[str] | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_config(config_path)
    config_dir = config_path.parent
    defaults = dict(config.get("launcher_defaults") or {})

    dataset_card_path, resolved_bundle_card_path = _resolve_dataset_card_path(
        dataset_card_path=dataset_card_path,
        bundle_card_path=bundle_card_path,
    )
    dataset_card = _read_json(dataset_card_path)
    resolved_output_dir = output_dir or _resolve_path(config_dir, defaults.get("output_dir"))
    if resolved_output_dir is None:
        raise ValueError("missing_output_dir")
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    resolved_storage_format = str(defaults.get("storage_format") or "parquet") if storage_format is None else str(storage_format)
    if resolved_storage_format not in {"jsonl", "parquet"}:
        raise ValueError(f"unsupported_storage_format:{resolved_storage_format}")

    configured_surfaces = defaults.get("surfaces") or []
    requested_surfaces = surfaces or [str(row.get("name") or "") for row in configured_surfaces if isinstance(row, dict)]
    if not requested_surfaces:
        raise ValueError("no_surfaces_requested")

    compile_summary = dataset_card.get("compile_summary") or {}
    train_ready_audit_summary = dataset_card.get("train_ready_audit_summary") or compile_summary.get("train_ready_audit_summary") or {}
    compile_counts = {
        "full_context_rows": int(compile_summary.get("full_context_rows") or 0),
        "retrieval_rows": int(compile_summary.get("retrieval_rows") or 0),
        "memory_rows": int(compile_summary.get("memory_rows") or 0),
    }
    surface_specs = {str(row.get("name") or ""): dict(row) for row in configured_surfaces if isinstance(row, dict)}

    rows: list[dict[str, Any]] = []
    for surface in requested_surfaces:
        if surface not in SURFACE_TO_JSONL_KEY:
            raise ValueError(f"unsupported_surface:{surface}")
        spec = surface_specs.get(surface)
        if spec is None:
            raise ValueError(f"surface_not_configured:{surface}")
        weight = float(spec.get("weight") or 1.0)
        task_family = str(spec.get("task_family") or surface)
        jsonl_path = _surface_jsonl_path(dataset_card, surface)
        parquet_dir = _surface_parquet_dir(dataset_card, surface)
        if resolved_storage_format == "parquet":
            if parquet_dir is None or not parquet_dir.is_dir():
                raise FileNotFoundError(f"missing_surface_parquet:{surface}")
            data_path = parquet_dir.resolve()
        else:
            data_path = jsonl_path.resolve()
        filter_expr = str(spec.get("filter_expr") or "").strip() or None
        manifest_filter_expr = str(spec.get("manifest_filter_expr") or "").strip() or None
        rows.append(
            {
                "row_id": f"strict_longctx_mixture::{surface}",
                "surface": surface,
                "task_family": task_family,
                "storage_format": resolved_storage_format,
                "path": str(data_path),
                "weight": weight,
                "row_count": compile_counts[surface],
                "dataset_card_path": str(dataset_card_path),
                "include_audit_only_direct": bool(dataset_card.get("include_audit_only_direct")),
                "filter_expr": filter_expr,
                "manifest_filter_expr": manifest_filter_expr,
                "state_delta_ready_fraction": float(train_ready_audit_summary.get("avg_state_delta_ready_fraction") or 0.0),
                "evidence_anchor_ready_fraction": float(train_ready_audit_summary.get("avg_evidence_anchor_ready_fraction") or 0.0),
                "min_state_delta_ready_fraction": float(train_ready_audit_summary.get("min_state_delta_ready_fraction") or 0.0),
                "min_evidence_anchor_ready_fraction": float(train_ready_audit_summary.get("min_evidence_anchor_ready_fraction") or 0.0),
            }
        )

    mixture_manifest_path = resolved_output_dir / "strict_long_context_mixture_manifest.jsonl"
    write_jsonl(mixture_manifest_path, rows)
    launcher_card = {
        "config_path": str(config_path),
        "dataset_card_path": str(dataset_card_path),
        "bundle_card_path": str(resolved_bundle_card_path) if resolved_bundle_card_path is not None else None,
        "output_dir": str(resolved_output_dir),
        "storage_format": resolved_storage_format,
        "surfaces": requested_surfaces,
        "mixture_manifest_path": str(mixture_manifest_path),
        "source_dataset_output_dir": dataset_card.get("output_dir"),
        "compile_summary": compile_summary,
        "train_ready_audit_summary": train_ready_audit_summary,
        "rows": rows,
    }
    write_json(resolved_output_dir / "strict_long_context_mixture_launcher_card.json", launcher_card)
    return launcher_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manifest-first mixture launcher for strict long-context training data.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--bundle-card", type=Path, default=DEFAULT_BUNDLE_CARD_PATH)
    parser.add_argument("--dataset-card", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--storage-format", choices=("jsonl", "parquet"))
    parser.add_argument("--surface", action="append", dest="surfaces")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_strict_long_context_mixture_manifest(
        dataset_card_path=args.dataset_card,
        bundle_card_path=args.bundle_card,
        config_path=args.config,
        output_dir=args.output_dir,
        storage_format=args.storage_format,
        surfaces=args.surfaces,
    )


if __name__ == "__main__":
    main()
