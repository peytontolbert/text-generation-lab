from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / 'configs' / 'software_maintainer' / 'strict_long_context_retrieval_mixture_launcher_v1.json'
DEFAULT_BUNDLE_CARD_PATH = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_software_maintainer_training_bundle_v1' / 'strict_software_maintainer_training_bundle_card.json'
SURFACE_KEYS = {
    'retriever_rows': 'retriever_rows_path',
    'reranker_pairwise_rows': 'reranker_pairwise_rows_path',
    'reranker_listwise_rows': 'reranker_listwise_rows_path',
    'retriever_curriculum_rows': 'retriever_curriculum_rows_path',
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


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
        raise ValueError(f'invalid_config:{config_path}')
    return config


def _resolve_retrieval_surface_dataset_card(path: Path) -> Path:
    resolved_path = path.resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f'missing_dataset_card:{resolved_path}')
    card = _read_json(resolved_path)
    if any(key in card for key in SURFACE_KEYS.values()):
        return resolved_path
    nested_dataset_card_value = str(card.get('dataset_card_path') or '').strip()
    if not nested_dataset_card_value:
        raise ValueError(f'missing_retrieval_surface_dataset_card:{resolved_path}')
    nested_dataset_card_path = Path(nested_dataset_card_value).resolve()
    if not nested_dataset_card_path.exists():
        raise FileNotFoundError(f'missing_dataset_card:{nested_dataset_card_path}')
    nested_card = _read_json(nested_dataset_card_path)
    if not any(key in nested_card for key in SURFACE_KEYS.values()):
        raise ValueError(f'invalid_retrieval_surface_dataset_card:{nested_dataset_card_path}')
    return nested_dataset_card_path


def _resolve_dataset_card_path(
    *,
    dataset_card_path: Path | None,
    bundle_card_path: Path | None,
) -> tuple[Path, Path | None]:
    if dataset_card_path is not None:
        resolved_dataset_card_path = _resolve_retrieval_surface_dataset_card(dataset_card_path)
        return resolved_dataset_card_path, bundle_card_path.resolve() if bundle_card_path is not None else None
    if bundle_card_path is None:
        raise ValueError('missing_dataset_card_or_bundle_card')
    resolved_bundle_card_path = bundle_card_path.resolve()
    if not resolved_bundle_card_path.exists():
        raise FileNotFoundError(f'missing_bundle_card:{resolved_bundle_card_path}')
    bundle_card = _read_json(resolved_bundle_card_path)
    resolved_dataset_card_value = str(bundle_card.get('retrieval_training_dataset_card_path') or '').strip()
    if not resolved_dataset_card_value:
        raise ValueError(f'missing_retrieval_training_dataset_card_path:{resolved_bundle_card_path}')
    resolved_dataset_card_path = _resolve_retrieval_surface_dataset_card(Path(resolved_dataset_card_value))
    return resolved_dataset_card_path, resolved_bundle_card_path


def _surface_path(card: dict[str, Any], surface: str) -> Path:
    key = SURFACE_KEYS[surface]
    value = str(card.get(key) or '').strip()
    if not value:
        raise ValueError(f'missing_surface_path:{surface}:{key}')
    path = Path(value)
    if not path.exists():
        raise FileNotFoundError(f'missing_surface_path:{path}')
    return path


def _surface_row_count(card: dict[str, Any], surface: str) -> int:
    if surface == 'retriever_rows':
        return int(((card.get('retriever_summary') or {}).get('retriever_row_count')) or 0)
    if surface == 'reranker_pairwise_rows':
        return int(((card.get('reranker_summary') or {}).get('pairwise_row_count')) or 0)
    if surface == 'reranker_listwise_rows':
        return int(((card.get('listwise_summary') or {}).get('listwise_row_count')) or 0)
    if surface == 'retriever_curriculum_rows':
        return int(((card.get('curriculum_summary') or {}).get('curriculum_row_count')) or 0)
    raise ValueError(f'unsupported_surface:{surface}')


def build_strict_long_context_retrieval_mixture_manifest(
    *,
    dataset_card_path: Path | None = None,
    bundle_card_path: Path | None = DEFAULT_BUNDLE_CARD_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_config(config_path)
    config_dir = config_path.parent
    defaults = dict(config.get('launcher_defaults') or {})
    profiles = {str(row.get('name') or ''): dict(row) for row in (config.get('profiles') or []) if isinstance(row, dict)}

    dataset_card_path, resolved_bundle_card_path = _resolve_dataset_card_path(
        dataset_card_path=dataset_card_path,
        bundle_card_path=bundle_card_path,
    )
    dataset_card = _read_json(dataset_card_path)
    resolved_output_dir = output_dir or _resolve_path(config_dir, defaults.get('output_dir'))
    if resolved_output_dir is None:
        raise ValueError('missing_output_dir')
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    resolved_profile = str(profile or defaults.get('profile') or '').strip()
    if not resolved_profile:
        raise ValueError('missing_profile')
    profile_spec = profiles.get(resolved_profile)
    if profile_spec is None:
        raise ValueError(f'unknown_profile:{resolved_profile}')

    rows: list[dict[str, Any]] = []
    for surface_spec in profile_spec.get('surfaces') or []:
        if not isinstance(surface_spec, dict):
            continue
        surface = str(surface_spec.get('name') or '').strip()
        if surface not in SURFACE_KEYS:
            raise ValueError(f'unsupported_surface:{surface}')
        weight = float(surface_spec.get('weight') or 1.0)
        task_family = str(surface_spec.get('task_family') or surface).strip()
        data_path = _surface_path(dataset_card, surface)
        row_count = _surface_row_count(dataset_card, surface)
        filter_expr = str(surface_spec.get('filter_expr') or '').strip() or None
        rows.append({
            'row_id': f'strict_longctx_retrieval_mixture::{resolved_profile}::{surface}',
            'surface': surface,
            'task_family': task_family,
            'storage_format': 'jsonl',
            'path': str(data_path.resolve()),
            'weight': weight,
            'row_count': row_count,
            'dataset_card_path': str(dataset_card_path),
            'profile': resolved_profile,
            'filter_expr': filter_expr,
        })

    manifest_path = resolved_output_dir / 'strict_long_context_retrieval_mixture_manifest.jsonl'
    write_jsonl(manifest_path, rows)
    launcher_card = {
        'config_path': str(config_path),
        'dataset_card_path': str(dataset_card_path),
        'bundle_card_path': str(resolved_bundle_card_path) if resolved_bundle_card_path is not None else None,
        'output_dir': str(resolved_output_dir),
        'profile': resolved_profile,
        'profile_description': str(profile_spec.get('description') or ''),
        'mixture_manifest_path': str(manifest_path),
        'rows': rows,
    }
    write_json(resolved_output_dir / 'strict_long_context_retrieval_mixture_launcher_card.json', launcher_card)
    return launcher_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build retrieval-side mixture manifests for strict long-context retriever and reranker datasets.')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--bundle-card', type=Path, default=DEFAULT_BUNDLE_CARD_PATH)
    parser.add_argument('--dataset-card', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--profile', type=str)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_strict_long_context_retrieval_mixture_manifest(
        dataset_card_path=args.dataset_card,
        bundle_card_path=args.bundle_card,
        config_path=args.config,
        output_dir=args.output_dir,
        profile=args.profile,
    )


if __name__ == '__main__':
    main()
