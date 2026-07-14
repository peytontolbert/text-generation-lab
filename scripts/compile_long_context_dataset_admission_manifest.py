from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASETS_ROOT = Path('/arxiv/datasets')
DEFAULT_OUTPUT_DIR = ROOT / 'runs' / 'local' / 'artifacts' / 'long_context_dataset_admission_manifest_v1'

STRICT_TRACE_EPISODE_IMPORT = 'STRICT_TRACE_EPISODE_IMPORT'
TRACE_SUPPORT_ONLY = 'TRACE_SUPPORT_ONLY'
PAPER_SUPPORT_ONLY = 'PAPER_SUPPORT_ONLY'
RETRIEVAL_AUX_ONLY = 'RETRIEVAL_AUX_ONLY'
EVAL_ONLY = 'EVAL_ONLY'
REJECT_GENERIC = 'REJECT_GENERIC'
REJECT_UNKNOWN = 'REJECT_UNKNOWN'

ROUTE_DESCRIPTIONS = {
    STRICT_TRACE_EPISODE_IMPORT: 'Execution-grounded software-maintenance traces with enough structure for canonical strict episode import.',
    TRACE_SUPPORT_ONLY: 'Agent/tool traces that can supply support chunks or weak trace analogues, but not strict repo-grounded episode rows.',
    PAPER_SUPPORT_ONLY: 'Long-form knowledge support suitable for algorithm grounding or cross-document joins.',
    RETRIEVAL_AUX_ONLY: 'Useful for retrieval/reranker or short-context auxiliary tasks only.',
    EVAL_ONLY: 'Reserved for held-out evaluation or auditing, not training-time augmentation.',
    REJECT_GENERIC: 'Generic instruction/chat/education data not aligned to software-maintainer long-context mining.',
    REJECT_UNKNOWN: 'Unknown schema or insufficient evidence; requires explicit manual review.',
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _read_readme(dataset_root: Path) -> str:
    readme = dataset_root / 'README.md'
    if not readme.is_file():
        return ''
    return readme.read_text(encoding='utf-8', errors='ignore')[:20000]


def _sample_json_row(path: Path) -> dict[str, Any]:
    try:
        if path.suffix == '.gz':
            with gzip.open(path, 'rt', encoding='utf-8') as handle:
                line = next((line.strip() for line in handle if line.strip()), '')
        else:
            line = next((line.strip() for line in path.read_text(encoding='utf-8', errors='ignore').splitlines() if line.strip()), '')
        value = json.loads(line) if line else {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _sample_parquet_row(path: Path) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq
    except Exception:
        return {}
    try:
        parquet = pq.ParquetFile(path)
        if parquet.num_row_groups == 0:
            return {}
        table = parquet.read_row_group(0).slice(0, 1)
        rows = table.to_pylist()
    except Exception:
        return {}
    if not rows or not isinstance(rows[0], dict):
        return {}
    return rows[0]


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _dataset_files(dataset_root: Path) -> dict[str, list[Path]]:
    return {
        'parquet': sorted(dataset_root.rglob('*.parquet')),
        'jsonl': sorted(dataset_root.rglob('*.jsonl')),
        'jsonl_gz': sorted(dataset_root.rglob('*.jsonl.gz')),
        'json': sorted(dataset_root.glob('*.json')),
        'yaml': sorted([*dataset_root.glob('*.yaml'), *dataset_root.glob('*.yml')]),
    }


def _sample_row(files: dict[str, list[Path]]) -> tuple[dict[str, Any], str | None]:
    parquet = _first_existing(files['parquet'])
    if parquet is not None:
        row = _sample_parquet_row(parquet)
        if row:
            return row, str(parquet)
    jsonl_gz = _first_existing(files['jsonl_gz'])
    if jsonl_gz is not None:
        row = _sample_json_row(jsonl_gz)
        if row:
            return row, str(jsonl_gz)
    jsonl = _first_existing(files['jsonl'])
    if jsonl is not None:
        row = _sample_json_row(jsonl)
        if row:
            return row, str(jsonl)
    return {}, None


def _row_keys(row: dict[str, Any]) -> set[str]:
    return {str(key) for key in row.keys()}


def _contains_any(text: str, needles: list[str]) -> bool:
    low = text.lower()
    return any(needle.lower() in low for needle in needles)


def _coarse_route_from_metadata(*, dataset_name: str, readme_text: str, files: dict[str, list[Path]]) -> tuple[str | None, list[str]]:
    lowered_name = dataset_name.lower()
    reasons: list[str] = []
    if _contains_any(lowered_name, ['open-swe']):
        reasons.append('metadata_marks_open_swe_trace_surface')
        return STRICT_TRACE_EPISODE_IMPORT, reasons
    if _contains_any(lowered_name, ['fable', 'mythos']):
        reasons.append('metadata_marks_agent_trace_support_surface')
        return TRACE_SUPPORT_ONLY, reasons
    if _contains_any(lowered_name, ['cuda-engineer']) or _contains_any(readme_text, ['cuda engineer', 'cuda debugging', 'runtime debugging']):
        reasons.append('metadata_marks_runtime_trace_support_surface')
        return TRACE_SUPPORT_ONLY, reasons
    if _contains_any(lowered_name, ['swe-atlas', 'atlas']) or _contains_any(readme_text, ['rubric', 'qna', 'evaluation']) or files['yaml']:
        reasons.append('metadata_marks_eval_or_rubric_surface')
        return EVAL_ONLY, reasons
    if _contains_any(lowered_name, ['code_x_glue', 'codeglue', 'ms_marco']) or _contains_any(readme_text, ['code search', 'retrieval', 'ranking', 'clone detection', 'defect detection', 'code refinement']):
        reasons.append('metadata_marks_retrieval_or_short_context_aux_surface')
        return RETRIEVAL_AUX_ONLY, reasons
    if _contains_any(lowered_name, ['papers', 'paper_instructions']) or (_contains_any(readme_text, ['arxiv', 'paper', 'abstract']) and bool(files['parquet']) and not _contains_any(lowered_name, ['open-swe', 'fable', 'cuda-engineer', 'code_x_glue', 'atlas'])):
        reasons.append('metadata_marks_paper_support_surface')
        return PAPER_SUPPORT_ONLY, reasons
    if _contains_any(lowered_name, ['education', 'dialog', 'banking', 'mmlu', 'openhermes', 'chat']) or _contains_any(readme_text, ['dialog', 'education', 'assistant responses', 'qa benchmark', 'multiple choice']):
        reasons.append('metadata_marks_generic_instruction_dialog_or_benchmark_surface')
        return REJECT_GENERIC, reasons
    return None, reasons


def _needs_sample_row(*, dataset_name: str, readme_text: str, files: dict[str, list[Path]]) -> bool:
    lowered_name = dataset_name.lower()
    if _contains_any(lowered_name, ['open-swe', 'fable', 'papers', 'cuda-engineer']):
        return True
    if _contains_any(readme_text, ['agent-traces', 'tool-use', 'claude-code', 'traces', 'arxiv', 'paper', 'abstract', 'methods', 'cuda', 'runtime', 'debugging']):
        return True
    return bool(files['parquet']) and len(files['parquet']) <= 4


def _infer_route(*, dataset_name: str, readme_text: str, row: dict[str, Any], files: dict[str, list[Path]]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    row_keys = _row_keys(row)
    lowered_name = dataset_name.lower()

    if {'trajectory', 'model_patch', 'resolved', 'repo'} <= row_keys:
        reasons.append('row_keys_match_open_swe_like_trace')
        return STRICT_TRACE_EPISODE_IMPORT, reasons

    row_json = str(row.get('row_json') or '')
    if 'open-swe' in lowered_name or 'swe traces' in readme_text.lower():
        reasons.append('dataset_name_or_readme_marks_swe_trace')
        return STRICT_TRACE_EPISODE_IMPORT, reasons

    if 'row_json' in row_keys and _contains_any(readme_text, ['agent-traces', 'tool-use', 'claude-code', 'traces']):
        reasons.append('row_json_trace_wrapper_with_agent_trace_readme')
        return TRACE_SUPPORT_ONLY, reasons

    if _contains_any(lowered_name, ['papers']) or _contains_any(readme_text, ['arxiv', 'paper', 'abstract', 'methods']) and files['parquet']:
        reasons.append('paper_like_dataset_surface')
        return PAPER_SUPPORT_ONLY, reasons

    if _contains_any(lowered_name, ['swe-atlas', 'atlas']) or _contains_any(readme_text, ['rubric', 'qna', 'evaluation']) or files['yaml']:
        reasons.append('eval_or_rubric_surface')
        return EVAL_ONLY, reasons

    if _contains_any(lowered_name, ['code_x_glue', 'codeglue', 'ms_marco']) or _contains_any(readme_text, ['code search', 'retrieval', 'ranking', 'clone detection', 'defect detection', 'code refinement']):
        reasons.append('retrieval_or_short_context_aux_surface')
        return RETRIEVAL_AUX_ONLY, reasons

    if _contains_any(lowered_name, ['cuda-engineer']) or _contains_any(readme_text, ['cuda', 'runtime', 'trace', 'debugging']) and files['parquet']:
        reasons.append('runtime_trace_support_surface')
        return TRACE_SUPPORT_ONLY, reasons

    if _contains_any(lowered_name, ['education', 'dialog', 'banking', 'mmlu', 'openhermes', 'chat']) or _contains_any(readme_text, ['dialog', 'education', 'assistant responses', 'qa benchmark', 'multiple choice']):
        reasons.append('generic_instruction_dialog_or_benchmark_surface')
        return REJECT_GENERIC, reasons

    if row_keys:
        reasons.append('unrecognized_row_schema_keys')
    else:
        reasons.append('no_sample_row_schema')
    return REJECT_UNKNOWN, reasons


def _catalog_suggestion(dataset_name: str, route: str) -> dict[str, Any] | None:
    if route == STRICT_TRACE_EPISODE_IMPORT:
        return {
            'allow_augmentation': True,
            'name': dataset_name.replace('--', '_').lower(),
            'provenance_tier': 'execution_grounded_trace_support',
            'quality_tier': 'high',
            'role_override': 'trace_analogue',
            'source_id_equals': [dataset_name],
            'source_type': 'dataset',
        }
    if route == TRACE_SUPPORT_ONLY:
        return {
            'allow_augmentation': True,
            'name': dataset_name.replace('--', '_').lower(),
            'provenance_tier': 'execution_grounded_trace_support',
            'quality_tier': 'medium',
            'role_override': 'trace_analogue',
            'source_id_equals': [dataset_name],
            'source_type': 'dataset',
        }
    if route == PAPER_SUPPORT_ONLY:
        return {
            'allow_augmentation': True,
            'name': dataset_name.replace('--', '_').lower(),
            'provenance_tier': 'pure_grounded_paper_support',
            'quality_tier': 'high',
            'role_override': 'algorithm_grounding',
            'source_id_equals': [dataset_name],
            'source_type': 'dataset',
        }
    if route == EVAL_ONLY:
        return {
            'allow_augmentation': False,
            'name': dataset_name.replace('--', '_').lower(),
            'provenance_tier': 'heldout_eval_only',
            'quality_tier': 'heldout_only',
            'source_id_equals': [dataset_name],
            'source_type': 'dataset',
        }
    if route == RETRIEVAL_AUX_ONLY:
        return {
            'allow_augmentation': False,
            'name': dataset_name.replace('--', '_').lower(),
            'provenance_tier': 'retrieval_aux_only',
            'quality_tier': 'auxiliary_only',
            'source_id_equals': [dataset_name],
            'source_type': 'dataset',
        }
    return None


def analyze_dataset_root(dataset_root: Path) -> dict[str, Any]:
    dataset_name = dataset_root.name
    files = _dataset_files(dataset_root)
    readme_text = _read_readme(dataset_root)
    coarse_route, coarse_reasons = _coarse_route_from_metadata(dataset_name=dataset_name, readme_text=readme_text, files=files)
    row: dict[str, Any] = {}
    sampled_path: str | None = None
    if coarse_route is None and _needs_sample_row(dataset_name=dataset_name, readme_text=readme_text, files=files):
        row, sampled_path = _sample_row(files)
    route, reasons = (coarse_route, coarse_reasons) if coarse_route is not None else _infer_route(dataset_name=dataset_name, readme_text=readme_text, row=row, files=files)
    return {
        'dataset_name': dataset_name,
        'path': str(dataset_root),
        'route': route,
        'route_description': ROUTE_DESCRIPTIONS[route],
        'reasons': reasons,
        'sampled_schema_path': sampled_path,
        'sampled_row_keys': sorted(_row_keys(row)),
        'file_counts': {
            'parquet': len(files['parquet']),
            'jsonl': len(files['jsonl']),
            'jsonl_gz': len(files['jsonl_gz']),
            'json': len(files['json']),
            'yaml': len(files['yaml']),
        },
        'catalog_suggestion': _catalog_suggestion(dataset_name, route),
    }


def compile_long_context_dataset_admission_manifest(*, datasets_root: Path = DEFAULT_DATASETS_ROOT, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    dataset_dirs = sorted(path for path in datasets_root.iterdir() if path.is_dir())
    rows = [analyze_dataset_root(path) for path in dataset_dirs]
    route_counts = Counter(str(row['route']) for row in rows)
    admitted_catalog_entries = [row['catalog_suggestion'] for row in rows if isinstance(row.get('catalog_suggestion'), dict)]
    manifest = {
        'schema_version': 'long_context_dataset_admission_manifest_v1',
        'datasets_root': str(datasets_root),
        'dataset_count': len(rows),
        'route_counts': dict(sorted(route_counts.items())),
        'rows': rows,
        'catalog_patch_candidates': admitted_catalog_entries,
        'recommended_next_steps': [
            'Implement strict episode adapters only for datasets routed to STRICT_TRACE_EPISODE_IMPORT.',
            'Admit TRACE_SUPPORT_ONLY and PAPER_SUPPORT_ONLY datasets through the curated source catalog for augmentation only.',
            'Keep EVAL_ONLY and RETRIEVAL_AUX_ONLY datasets out of strict episode mining unless a dedicated downstream builder consumes them.',
            'Reject or manually review REJECT_GENERIC and REJECT_UNKNOWN datasets before any training-path admission.',
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / 'long_context_dataset_admission_manifest.json', manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description='Compile a route-assigned admission manifest for long-context dataset mining.')
    parser.add_argument('--datasets-root', type=Path, default=DEFAULT_DATASETS_ROOT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    compile_long_context_dataset_admission_manifest(datasets_root=args.datasets_root, output_dir=args.output_dir)


if __name__ == '__main__':
    main()
