from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from compile_long_context_dataset_admission_manifest import (  # noqa: E402
    EVAL_ONLY,
    PAPER_SUPPORT_ONLY,
    REJECT_GENERIC,
    RETRIEVAL_AUX_ONLY,
    STRICT_TRACE_EPISODE_IMPORT,
    TRACE_SUPPORT_ONLY,
    compile_long_context_dataset_admission_manifest,
)


def _write_parquet(path: Path, rows: list[dict]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, compression='zstd')


def test_compile_long_context_dataset_admission_manifest_routes_known_dataset_shapes(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    open_swe = tmp_path / 'nvidia--Open-SWE-Traces'
    open_swe.mkdir()
    (open_swe / 'README.md').write_text('software maintenance traces with tool use', encoding='utf-8')
    _write_parquet(
        open_swe / 'data' / 'train.parquet',
        [
            {
                'repo': 'org/repo',
                'trajectory': [{'role': 'user', 'content': 'issue'}],
                'model_patch': 'diff --git a/src/a.py b/src/a.py',
                'resolved': 1,
            }
        ],
    )

    fable = tmp_path / 'Crownelius--Complete-FABLE.5-traces-2M'
    fable.mkdir()
    (fable / 'README.md').write_text('agent-traces tool-use claude-code traces', encoding='utf-8')
    _write_parquet(
        fable / 'data' / 'train.parquet',
        [
            {
                'row_hash': 'x',
                'row_json': '{"operation":"enqueue","content":"Create hello.py"}',
                'first_source_dataset': 'foo/bar',
            }
        ],
    )

    papers = tmp_path / 'PeytonT--2m_papers_text'
    papers.mkdir()
    (papers / 'README.md').write_text('arxiv paper abstract methods dataset', encoding='utf-8')
    _write_parquet(papers / 'train.parquet', [{'title': 'paper', 'abstract': 'attention memory retrieval'}])

    swe_atlas = tmp_path / 'ScaleAI--SWE-Atlas-QnA'
    swe_atlas.mkdir()
    (swe_atlas / 'README.md').write_text('rubric evaluation qna', encoding='utf-8')
    (swe_atlas / 'rubric_evaluation_config.yaml').write_text('metric: score\n', encoding='utf-8')

    code_glue = tmp_path / 'google--code_x_glue_tc_nl_code_search_adv'
    code_glue.mkdir()
    (code_glue / 'README.md').write_text('code search retrieval benchmark', encoding='utf-8')

    generic = tmp_path / 'teknium--OpenHermes-2.5'
    generic.mkdir()
    (generic / 'README.md').write_text('assistant responses chat dataset', encoding='utf-8')

    manifest = compile_long_context_dataset_admission_manifest(datasets_root=tmp_path, output_dir=tmp_path / 'out')
    by_name = {row['dataset_name']: row for row in manifest['rows']}

    assert by_name['nvidia--Open-SWE-Traces']['route'] == STRICT_TRACE_EPISODE_IMPORT
    assert by_name['Crownelius--Complete-FABLE.5-traces-2M']['route'] == TRACE_SUPPORT_ONLY
    assert by_name['PeytonT--2m_papers_text']['route'] == PAPER_SUPPORT_ONLY
    assert by_name['ScaleAI--SWE-Atlas-QnA']['route'] == EVAL_ONLY
    assert by_name['google--code_x_glue_tc_nl_code_search_adv']['route'] == RETRIEVAL_AUX_ONLY
    assert by_name['teknium--OpenHermes-2.5']['route'] == REJECT_GENERIC
    assert Path(tmp_path / 'out' / 'long_context_dataset_admission_manifest.json').is_file()


def test_compile_long_context_dataset_admission_manifest_emits_catalog_suggestions_only_for_admissible_routes(tmp_path: Path) -> None:
    if importlib.util.find_spec('pyarrow') is None:
        pytest.skip('pyarrow not installed')

    trace_ds = tmp_path / 'trace-ds'
    trace_ds.mkdir()
    (trace_ds / 'README.md').write_text('agent-traces tool-use traces', encoding='utf-8')
    _write_parquet(trace_ds / 'data' / 'train.parquet', [{'row_json': '{"content":"x"}', 'row_hash': '1'}])

    generic = tmp_path / 'generic-chat'
    generic.mkdir()
    (generic / 'README.md').write_text('assistant responses chat dataset', encoding='utf-8')

    manifest = compile_long_context_dataset_admission_manifest(datasets_root=tmp_path, output_dir=tmp_path / 'out')
    suggestions = {entry['source_id_equals'][0]: entry for entry in manifest['catalog_patch_candidates']}
    assert 'trace-ds' in suggestions
    assert 'generic-chat' not in suggestions
