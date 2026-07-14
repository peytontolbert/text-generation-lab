from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json
from prepare_strict_long_context_retrieval_profile_bundle import prepare_strict_long_context_retrieval_profile_bundle

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "software_maintainer" / "strict_long_context_retrieval_training_entrypoint_v1.json"


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


def prepare_strict_long_context_retrieval_training_dataset(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    dataset_card_path: Path | None = None,
    bundle_card_path: Path | None = None,
    mixture_launcher_config_path: Path | None = None,
    output_dir: Path | None = None,
    include_opt_in_profiles: bool | None = None,
    seed: int | None = None,
    max_train_rows: int | None = None,
    max_eval_rows: int | None = None,
    max_strict_rows: int | None = None,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_entrypoint_config(config_path)
    config_dir = config_path.parent

    defaults = dict(config.get("dataset_defaults") or {})
    resolved_dataset_card = dataset_card_path or _resolve_path(config_dir, defaults.get("dataset_card"))
    resolved_bundle_card = bundle_card_path or _resolve_path(config_dir, defaults.get("bundle_card"))
    if resolved_dataset_card is None and resolved_bundle_card is None:
        raise ValueError("missing_dataset_card_or_bundle_card")
    if resolved_dataset_card is not None and not resolved_dataset_card.exists():
        raise FileNotFoundError(f"missing_dataset_card:{resolved_dataset_card}")
    if resolved_bundle_card is not None and not resolved_bundle_card.exists():
        raise FileNotFoundError(f"missing_bundle_card:{resolved_bundle_card}")

    resolved_mixture_launcher_config = mixture_launcher_config_path or _resolve_path(config_dir, defaults.get("mixture_launcher_config"))
    if resolved_mixture_launcher_config is None or not resolved_mixture_launcher_config.exists():
        raise FileNotFoundError(f"missing_mixture_launcher_config:{resolved_mixture_launcher_config}")

    resolved_output_dir = output_dir or _resolve_path(config_dir, defaults.get("output_dir"))
    if resolved_output_dir is None:
        raise ValueError("missing_output_dir")

    resolved_include_opt_in = bool(defaults.get("include_opt_in_profiles", False) if include_opt_in_profiles is None else include_opt_in_profiles)
    resolved_seed = int(defaults.get("seed", 0) if seed is None else seed)

    bundle = prepare_strict_long_context_retrieval_profile_bundle(
        dataset_card_path=resolved_dataset_card,
        bundle_card_path=resolved_bundle_card,
        config_path=resolved_mixture_launcher_config,
        output_dir=resolved_output_dir,
        include_opt_in_profiles=resolved_include_opt_in,
        seed=resolved_seed,
        max_train_rows=max_train_rows,
        max_eval_rows=max_eval_rows,
        max_strict_rows=max_strict_rows,
    )

    dataset_card = {
        "entrypoint_config_path": str(config_path),
        "dataset_card_path": str(resolved_dataset_card) if resolved_dataset_card is not None else None,
        "bundle_card_path": str(resolved_bundle_card) if resolved_bundle_card is not None else None,
        "mixture_launcher_config_path": str(resolved_mixture_launcher_config),
        "output_dir": str(resolved_output_dir),
        "include_opt_in_profiles": resolved_include_opt_in,
        "seed": resolved_seed,
        "profile_bundle_card_path": str((resolved_output_dir / 'strict_long_context_retrieval_profile_bundle_card.json').resolve()),
        "trainer_default_profiles": list(bundle.get("trainer_default_profiles") or []),
        "default_sampled_manifests": dict(bundle.get("default_sampled_manifests") or {}),
        "opt_in_profiles": list(bundle.get("opt_in_profiles") or []),
        "profiles": list(bundle.get("profiles") or []),
    }
    write_json(resolved_output_dir / 'strict_long_context_retrieval_training_dataset_card.json', dataset_card)
    return dataset_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a strict long-context retrieval training dataset bundle from the canonical retrieval profile bundle.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--dataset-card", type=Path)
    parser.add_argument("--bundle-card", type=Path)
    parser.add_argument("--mixture-launcher-config", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--include-opt-in-profiles", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-train-rows", type=int)
    parser.add_argument("--max-eval-rows", type=int)
    parser.add_argument("--max-strict-rows", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepare_strict_long_context_retrieval_training_dataset(
        config_path=args.config,
        dataset_card_path=args.dataset_card,
        bundle_card_path=args.bundle_card,
        mixture_launcher_config_path=args.mixture_launcher_config,
        output_dir=args.output_dir,
        include_opt_in_profiles=args.include_opt_in_profiles if args.include_opt_in_profiles else None,
        seed=args.seed,
        max_train_rows=args.max_train_rows,
        max_eval_rows=args.max_eval_rows,
        max_strict_rows=args.max_strict_rows,
    )


if __name__ == "__main__":
    main()
