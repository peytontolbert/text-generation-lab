from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json
from materialize_strict_long_context_retrieval_mixture_rows import materialize_strict_long_context_retrieval_mixture_rows
from prepare_strict_long_context_retrieval_mixture import build_strict_long_context_retrieval_mixture_manifest
from sample_strict_long_context_retrieval_mixture_rows import sample_strict_long_context_retrieval_mixture_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / 'configs' / 'software_maintainer' / 'strict_long_context_retrieval_mixture_launcher_v1.json'
DEFAULT_BUNDLE_CARD = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_software_maintainer_training_bundle_v1' / 'strict_software_maintainer_training_bundle_card.json'
DEFAULT_OUTPUT_DIR = ROOT / 'runs' / 'local' / 'artifacts' / 'strict_long_context_retrieval_mixture_v1'


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def prepare_strict_long_context_retrieval_profile_bundle(
    *,
    dataset_card_path: Path | None = None,
    bundle_card_path: Path | None = DEFAULT_BUNDLE_CARD,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    include_opt_in_profiles: bool = False,
    profiles: list[str] | None = None,
    seed: int = 0,
    max_train_rows: int | None = None,
    max_eval_rows: int | None = None,
    max_strict_rows: int | None = None,
) -> dict[str, Any]:
    config = _read_json(config_path.resolve())
    defaults = dict(config.get('launcher_defaults') or {})
    default_train_profiles = [str(item) for item in defaults.get('default_train_profiles') or [] if str(item)]
    opt_in_profiles = [str(item) for item in defaults.get('opt_in_profiles') or [] if str(item)]
    selected_profiles = list(profiles or default_train_profiles)
    if include_opt_in_profiles:
        for item in opt_in_profiles:
            if item not in selected_profiles:
                selected_profiles.append(item)
    if not selected_profiles:
        raise ValueError('no_profiles_selected')

    output_dir.mkdir(parents=True, exist_ok=True)
    profile_cards: list[dict[str, Any]] = []
    default_sampled_manifests: dict[str, str] = {}
    for profile in selected_profiles:
        profile_dir = output_dir / profile
        launcher_card = build_strict_long_context_retrieval_mixture_manifest(
            dataset_card_path=dataset_card_path,
            bundle_card_path=bundle_card_path,
            config_path=config_path,
            output_dir=profile_dir,
            profile=profile,
        )
        materialized = materialize_strict_long_context_retrieval_mixture_rows(
            mixture_manifest_path=Path(launcher_card['mixture_manifest_path']),
            output_dir=profile_dir / 'materialized',
        )
        sampled = sample_strict_long_context_retrieval_mixture_rows(
            rows_path=Path(materialized['rows_path']),
            output_dir=profile_dir / 'sampled',
            seed=seed,
            max_train_rows=max_train_rows,
            max_eval_rows=max_eval_rows,
            max_strict_rows=max_strict_rows,
        )
        default_sampled_manifests[profile] = sampled['manifest_path']
        profile_cards.append({
            'profile': profile,
            'launcher_card_path': str((profile_dir / 'strict_long_context_retrieval_mixture_launcher_card.json').resolve()),
            'materialized_card_path': str((profile_dir / 'materialized' / 'strict_long_context_retrieval_mixture_rows_card.json').resolve()),
            'sampled_card_path': str((profile_dir / 'sampled' / 'strict_long_context_retrieval_sampled_manifest_card.json').resolve()),
            'sampled_manifest_path': sampled['manifest_path'],
            'row_count': int(sampled['row_count']),
        })

    bundle = {
        'config_path': str(config_path.resolve()),
        'dataset_card_path': str(dataset_card_path.resolve()) if dataset_card_path is not None else None,
        'bundle_card_path': str(bundle_card_path.resolve()) if bundle_card_path is not None else None,
        'output_dir': str(output_dir.resolve()),
        'default_train_profiles': default_train_profiles,
        'opt_in_profiles': opt_in_profiles,
        'selected_profiles': selected_profiles,
        'default_sampled_manifests': {k: str(v) for k, v in default_sampled_manifests.items()},
        'profiles': profile_cards,
        'trainer_default_profiles': [profile for profile in selected_profiles if profile in default_train_profiles],
    }
    write_json(output_dir / 'strict_long_context_retrieval_profile_bundle_card.json', bundle)
    return bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build, materialize, and sample provenance-aware strict long-context retrieval profile manifests.')
    parser.add_argument('--dataset-card', type=Path)
    parser.add_argument('--bundle-card', type=Path, default=DEFAULT_BUNDLE_CARD)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument('--include-opt-in-profiles', action='store_true')
    parser.add_argument('--profiles', nargs='*')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--max-train-rows', type=int)
    parser.add_argument('--max-eval-rows', type=int)
    parser.add_argument('--max-strict-rows', type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_strict_long_context_retrieval_profile_bundle(
        dataset_card_path=args.dataset_card,
        bundle_card_path=args.bundle_card,
        config_path=args.config,
        output_dir=args.output_dir,
        include_opt_in_profiles=args.include_opt_in_profiles,
        profiles=args.profiles,
        seed=args.seed,
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_strict_rows=args.max_strict_rows,
    )


if __name__ == '__main__':
    main()
