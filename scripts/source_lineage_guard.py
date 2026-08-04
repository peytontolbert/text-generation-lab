from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
DEFAULT_FUTURE_EVAL_IDENTITY_DENYLIST = ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json"

IDENTITY_TYPES = ("repo_family", "source_path", "root_identity")
REPO_IDENTITY_KEYS = frozenset(
    (
        "repo_family",
        "repository_family",
        "canonical_repo",
        "canonical_repository",
        "repo_name",
        "repository_name",
    )
)
REPO_IDENTITY_PLURAL_KEYS = frozenset(("repo_families", "repository_families"))
SOURCE_IDENTITY_KEYS = frozenset(
    (
        "source_path",
        "canonical_source_path",
        "repo_path",
        "repository_path",
        "source_repository_path",
        "source_checkout_path",
    )
)
SOURCE_IDENTITY_PLURAL_KEYS = frozenset(
    ("source_paths", "repo_paths", "repository_paths", "source_repository_paths")
)
REPOSITORY_ALIAS_KEYS = frozenset(("repo", "repository", "source_repo", "source_repository"))
ROOT_IDENTITY_KEYS = frozenset(
    (
        "root_id",
        "root_key",
        "root_identity",
        "root_lineage_key",
        "stage12105_root_key",
        "source_root",
        "repository_root",
    )
)
ROOT_IDENTITY_PLURAL_KEYS = frozenset(
    (
        "root_ids",
        "root_keys",
        "root_identities",
        "root_lineage_keys",
        "source_roots",
        "repository_roots",
    )
)
ROOT_IDENTITY_SUFFIXES = (
    "_root_id",
    "_root_key",
    "_root_identity",
    "_root_lineage_key",
    "_source_root",
    "_repository_root",
)
ROOT_IDENTITY_PLURAL_SUFFIXES = (
    "_root_ids",
    "_root_keys",
    "_root_identities",
    "_root_lineage_keys",
    "_source_roots",
    "_repository_roots",
)
TRAIN_SPLIT_ALIASES = frozenset(
    ("train", "training", "train_support", "train-support", "train_only", "train-only")
)
EVAL_SPLIT_ALIASES = frozenset(("eval", "evaluation", "validation", "valid", "val"))
STRICT_SPLIT_ALIASES = frozenset(
    (
        "strict",
        "strict_eval",
        "strict-eval",
        "sealed",
        "heldout",
        "holdout",
        "hidden_final",
        "hidden-final",
        "locked_eval",
        "locked-eval",
        "source-heldout",
        "source_heldout",
    )
)
STRICT_HELDOUT_MARKERS = frozenset(
    (
        "source_heldout",
        "source_heldout_admissible",
        "strict_eval",
        "strict_eval_eligible",
        "strict_eval_allowed",
        "strict_eval_authority",
        "locked_eval",
        "locked_eval_source",
        "hidden_final",
        "hidden_final_source",
    )
)
EVAL_HELDOUT_MARKERS = frozenset(
    (
        "eval_eligible",
        "evaluation_eligible",
        "eval_allowed",
        "evaluation_allowed",
        "eval_authority",
        "evaluation_authority",
    )
)
COMMIT_IDENTITY_KEYS = frozenset(
    (
        "before_commit",
        "after_commit",
        "base_commit",
        "target_commit",
        "before_commit_sha",
        "after_commit_sha",
        "base_commit_sha",
        "target_commit_sha",
        "commit",
        "commit_sha",
        "commit_hash",
        "revision",
    )
)
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class IdentityExtraction:
    identities: dict[str, frozenset[str]]
    malformed_paths: tuple[str, ...]

    @property
    def has_identity(self) -> bool:
        return any(self.identities.values())


def canonicalize_manifest_split(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid explicit manifest split: {value!r}")
    normalized = value.strip().lower()
    if normalized in TRAIN_SPLIT_ALIASES:
        return "train"
    if normalized in EVAL_SPLIT_ALIASES:
        return "eval"
    if normalized in STRICT_SPLIT_ALIASES:
        return "strict_eval"
    raise ValueError(f"unknown explicit manifest split: {value!r}")


def canonicalize_row_split(row: dict[str, Any]) -> str:
    explicit = [(key, row[key]) for key in ("split", "package_split", "split_role") if key in row]
    canonical = [(key, canonicalize_manifest_split(value)) for key, value in explicit]
    if canonical and len({value for _, value in canonical}) != 1:
        raise ValueError(f"conflicting explicit manifest splits: {explicit!r}")
    marker_values: dict[str, list[tuple[str, bool]]] = {"strict_eval": [], "eval": []}
    seen: set[int] = set()

    def visit(value: Any, path: str) -> None:
        if isinstance(value, (dict, list, tuple)):
            marker = id(value)
            if marker in seen:
                return
            seen.add(marker)
        if isinstance(value, dict):
            for raw_key, child in value.items():
                key = str(raw_key).strip().casefold().replace("-", "_")
                child_path = f"{path}.{raw_key}" if path else str(raw_key)
                marker_kind = None
                marker_suffixes = ("eligible", "eligibility", "allowed", "authority", "admissible")
                if (
                    key in STRICT_HELDOUT_MARKERS
                    or key.endswith("_source_heldout")
                    or (key.startswith(("strict_", "strict_eval_", "source_heldout_")) and key.endswith(marker_suffixes))
                ):
                    marker_kind = "strict_eval"
                elif key in EVAL_HELDOUT_MARKERS or (
                    key.startswith(("eval_", "evaluation_")) and key.endswith(marker_suffixes)
                ):
                    marker_kind = "eval"
                if marker_kind is not None:
                    if type(child) is not bool:
                        raise ValueError(f"ambiguous heldout marker {child_path}: {child!r}")
                    marker_values[marker_kind].append((child_path, child))
                visit(child, child_path)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(row, "")
    for marker_kind, values in marker_values.items():
        observed = {value for _, value in values}
        if len(observed) > 1:
            raise ValueError(f"conflicting {marker_kind} heldout markers: {values!r}")

    strict_true = any(value for _, value in marker_values["strict_eval"])
    eval_true = any(value for _, value in marker_values["eval"])
    if canonical:
        split = canonical[0][1]
        if split == "train" and (strict_true or eval_true):
            raise ValueError(f"train split conflicts with heldout markers: {marker_values!r}")
        if strict_true:
            return "strict_eval"
        if eval_true and split == "strict_eval":
            return "strict_eval"
        return "eval" if eval_true else split
    if strict_true:
        return "strict_eval"
    if eval_true:
        return "eval"
    if any(marker_values.values()):
        raise ValueError(f"heldout-marker-only row has no authoritative split: {marker_values!r}")
    return "train"


def _identity_types_for_key(key: str, value: Any) -> tuple[str, ...]:
    key = key.strip().casefold()
    if key in REPOSITORY_ALIAS_KEYS or (key == "source" and isinstance(value, str)):
        return ("repo_family", "source_path")
    if (
        key in REPO_IDENTITY_KEYS
        or key in REPO_IDENTITY_PLURAL_KEYS
        or key.endswith("_repo_family")
        or key.endswith("_repo_families")
    ):
        return ("repo_family",)
    if (
        key in SOURCE_IDENTITY_KEYS
        or key in SOURCE_IDENTITY_PLURAL_KEYS
        or key.endswith("_source_path")
        or key.endswith("_source_paths")
    ):
        return ("source_path",)
    if (
        key in ROOT_IDENTITY_KEYS
        or key in ROOT_IDENTITY_PLURAL_KEYS
        or key.endswith(ROOT_IDENTITY_SUFFIXES)
        or key.endswith(ROOT_IDENTITY_PLURAL_SUFFIXES)
        or key in COMMIT_IDENTITY_KEYS
        or key.endswith(("_before_commit", "_after_commit", "_base_commit", "_target_commit"))
        or (key in {"before", "after"} and isinstance(value, str) and COMMIT_RE.fullmatch(value.strip()))
    ):
        return ("root_identity",)
    return ()


def _normalize_identity(identity_type: str, value: str) -> str:
    normalized = re.sub(r"/+", "/", value.strip().casefold().replace("\\", "/"))
    if identity_type == "source_path":
        return posixpath.normpath(normalized)
    if identity_type == "root_identity":
        return normalized
    normalized = normalized.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4].rstrip("/")
    return normalized


def extract_future_eval_identities(value: Any, _seen: set[int] | None = None) -> IdentityExtraction:
    """Recursively extract typed future-eval identities and report malformed aliases."""
    found: dict[str, set[str]] = {identity_type: set() for identity_type in IDENTITY_TYPES}
    malformed: list[str] = []
    seen = _seen if _seen is not None else set()

    def collect(identity_type: str, child: Any, path: str) -> None:
        if isinstance(child, str):
            if child.strip():
                found[identity_type].add(_normalize_identity(identity_type, child))
            else:
                malformed.append(path)
            return
        if isinstance(child, (list, tuple)):
            if not child:
                malformed.append(path)
            for index, item in enumerate(child):
                item_path = f"{path}[{index}]"
                if isinstance(item, str) and item.strip():
                    found[identity_type].add(_normalize_identity(identity_type, item))
                else:
                    malformed.append(item_path)
            return
        malformed.append(path)

    def visit(child: Any, path: str) -> None:
        if isinstance(child, (dict, list, tuple)):
            marker = id(child)
            if marker in seen:
                return
            seen.add(marker)
        if isinstance(child, dict):
            for raw_key, nested in child.items():
                key = str(raw_key)
                nested_path = f"{path}.{key}" if path else key
                identity_types = _identity_types_for_key(key, nested)
                for identity_type in identity_types:
                    collect(identity_type, nested, nested_path)
                visit(nested, nested_path)
        elif isinstance(child, (list, tuple)):
            for index, nested in enumerate(child):
                visit(nested, f"{path}[{index}]")

    visit(value, "")
    return IdentityExtraction(
        identities={key: frozenset(values) for key, values in found.items()},
        malformed_paths=tuple(sorted(set(malformed))),
    )


def load_future_eval_identity_denylist(
    path: Path = DEFAULT_FUTURE_EVAL_IDENTITY_DENYLIST,
) -> dict[str, frozenset[str]]:
    if not path.is_file():
        raise ValueError(f"mandatory future-eval identity denylist missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed future-eval identity denylist: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"future-eval identity denylist must be an object: {path}")
    expected_top_level = {"schema_version", "record_type", "deny"}
    if set(data) != expected_top_level:
        raise ValueError(f"future-eval identity denylist schema mismatch: {path}")
    if data.get("schema_version") != 1 or data.get("record_type") != "future_eval_identity_denylist_v1":
        raise ValueError(f"future-eval identity denylist schema mismatch: {path}")
    deny = data.get("deny")
    if not isinstance(deny, dict) or set(deny) != set(IDENTITY_TYPES):
        raise ValueError(f"future-eval identity denylist has missing or unknown buckets: {path}")
    loaded: dict[str, frozenset[str]] = {}
    for identity_type in IDENTITY_TYPES:
        values = deny[identity_type]
        if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError(f"invalid future-eval identity denylist bucket {identity_type}: {path}")
        normalized = [_normalize_identity(identity_type, item) for item in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"duplicate future-eval identity denylist value in {identity_type}: {path}")
        loaded[identity_type] = frozenset(normalized)
    return loaded


def assert_future_eval_identity_allowed(
    row: dict[str, Any],
    split: str,
    denylist: dict[str, frozenset[str]],
) -> None:
    if split not in {"eval", "strict_eval"}:
        return
    extraction = extract_future_eval_identities(row)
    row_id = row.get("row_id") or row.get("id") or "<unknown>"
    if extraction.malformed_paths:
        raise ValueError(
            f"heldout row {row_id} has malformed recognized identities: {list(extraction.malformed_paths)}"
        )
    if not extraction.has_identity:
        raise ValueError(f"heldout row {row_id} has no recognized identity")
    denied = {
        identity_type: sorted(values & denylist[identity_type])
        for identity_type, values in extraction.identities.items()
        if values & denylist[identity_type]
    }
    if denied:
        raise ValueError(f"heldout row {row_id} uses denied future-eval identity: {denied}")


def load_source_registry(path: Path = DEFAULT_LINEAGE) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError(f"missing records in {path}")
    return {str(record["source_id"]): record for record in records if isinstance(record, dict) and record.get("source_id")}


def locked_source_ids(registry: dict[str, dict[str, Any]]) -> set[str]:
    return {source_id for source_id, record in registry.items() if record.get("locked_eval") or record.get("hidden_final")}


def train_eligible_source_ids(registry: dict[str, dict[str, Any]]) -> set[str]:
    return {source_id for source_id, record in registry.items() if record.get("train_eligible") is True and not record.get("locked_eval") and not record.get("hidden_final")}


def source_ids_from_value(value: Any, _seen: set[int] | None = None) -> set[str]:
    """Extract source identities recursively without treating hashes as IDs."""
    seen = _seen if _seen is not None else set()
    if isinstance(value, (dict, list, tuple)):
        marker = id(value)
        if marker in seen:
            return set()
        seen.add(marker)
    found: set[str] = set()
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key == "source_id" or key.endswith("_source_id"):
                if isinstance(child, str) and child:
                    found.add(child)
                else:
                    found.update(source_ids_from_value(child, seen))
                continue
            if key == "source_ids":
                if isinstance(child, str) and child:
                    found.add(child)
                elif isinstance(child, (list, tuple)):
                    found.update(item for item in child if isinstance(item, str) and item)
                    for item in child:
                        if not isinstance(item, str):
                            found.update(source_ids_from_value(item, seen))
                else:
                    found.update(source_ids_from_value(child, seen))
                continue
            found.update(source_ids_from_value(child, seen))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(source_ids_from_value(child, seen))
    return found


def source_ids_from_row(row: dict[str, Any]) -> set[str]:
    return source_ids_from_value(row)


def evaluate_row_source_lineage(row: dict[str, Any], registry: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = registry or load_source_registry()
    ids = source_ids_from_row(row)
    unknown = sorted(source_id for source_id in ids if source_id not in registry)
    locked = sorted(source_id for source_id in ids if registry.get(source_id, {}).get("locked_eval") or registry.get(source_id, {}).get("hidden_final"))
    ineligible = sorted(
        source_id
        for source_id in ids
        if source_id in registry and registry[source_id].get("train_eligible") is not True
    )
    train_eligible = bool(ids) and not unknown and not locked and not ineligible
    return {
        "row_id": row.get("row_id") or row.get("id") or "",
        "source_ids": sorted(ids),
        "unknown_source_ids": unknown,
        "locked_source_ids": locked,
        "train_ineligible_source_ids": ineligible,
        "train_eligible_lineage": train_eligible,
        "blocked_training_reason": (
            "unknown_source_id" if unknown else "locked_eval_source" if locked else "train_ineligible_source" if ineligible else None
        ),
    }


def assert_row_train_source_allowed(row: dict[str, Any], registry: dict[str, dict[str, Any]] | None = None) -> None:
    result = evaluate_row_source_lineage(row, registry)
    if not result["train_eligible_lineage"]:
        raise ValueError(f"row source lineage not train-eligible: {result}")
