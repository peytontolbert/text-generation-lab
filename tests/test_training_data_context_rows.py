from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "legacy_src"))

from agentkernel_lite.training_data import (
    AgentKernelBPETokenizer,
    ByteTokenizer,
    MAX_CONTEXT_ROWS_FOR_ENCODER,
    MAX_CONTEXT_TEXT_CHARS,
    _row_text,
    build_batch,
)


def test_row_text_serializes_context_rows_with_roles_in_order() -> None:
    row = {
        "row_id": "r1",
        "language_family": "python",
        "context_rows": [
            {
                "role": "seed_change",
                "source_type": "repo",
                "path": "src/engine.py",
                "token_count": 12,
                "chunk_id": "c1",
                "chunk_ordinal": 0,
                "text": "def run_order(x): return compute_total(x)",
            },
            {
                "role": "verification_constraint",
                "source_type": "test",
                "path": "tests/test_engine.py",
                "token_count": 9,
                "chunk_id": "c2",
                "chunk_ordinal": 1,
                "text": "assert run_order(1) == 2",
            },
        ],
        "target": {"label": "BIND_AVAILABLE"},
    }

    rendered = _row_text(row)

    assert "context.rows.count=2" in rendered
    assert "context.0.role=seed_change" in rendered
    assert "context.0.source_type=repo" in rendered
    assert "context.0.path=src/engine.py" in rendered
    assert "context.0.text=def run_order(x): return compute_total(x)" in rendered
    assert "context.1.role=verification_constraint" in rendered
    assert "context.1.path=tests/test_engine.py" in rendered
    assert rendered.index("context.0.role=seed_change") < rendered.index("context.1.role=verification_constraint")


def test_row_text_bounds_context_rows_and_text() -> None:
    rows = [
        {
            "role": f"role_{index}",
            "source_type": "repo",
            "path": f"src/{index}.py",
            "text": "x" * (MAX_CONTEXT_TEXT_CHARS + 50),
        }
        for index in range(MAX_CONTEXT_ROWS_FOR_ENCODER + 3)
    ]

    rendered = _row_text({"context_rows": rows})

    assert f"context.rows.count={MAX_CONTEXT_ROWS_FOR_ENCODER + 3}" in rendered
    assert f"context.{MAX_CONTEXT_ROWS_FOR_ENCODER - 1}.role=role_{MAX_CONTEXT_ROWS_FOR_ENCODER - 1}" in rendered
    assert f"context.{MAX_CONTEXT_ROWS_FOR_ENCODER}.role=role_{MAX_CONTEXT_ROWS_FOR_ENCODER}" not in rendered
    assert "x" * MAX_CONTEXT_TEXT_CHARS in rendered
    assert "x" * (MAX_CONTEXT_TEXT_CHARS + 1) not in rendered


def test_build_batch_accepts_context_rows() -> None:
    batch = build_batch(
        [
            {
                "row_id": "r1",
                "context_rows": [
                    {"role": "seed_change", "source_type": "repo", "path": "src/a.py", "text": "alpha evidence"}
                ],
                "target": {"label": "KEEP"},
                "loss_mask": {"structured_aux": True},
            }
        ],
        max_encoder_tokens=96,
        max_decoder_tokens=16,
    )

    assert batch.input_ids.shape[0] == 1
    assert batch.loss_mask["structured_aux"].tolist() == [True]
    assert batch.row_ids == ["r1"]


def test_build_batch_accepts_long_context_compiled_rows() -> None:
    batch = build_batch(
        [
            {
                "row_id": "full::pack1",
                "task_type": "full_context_state_reconstruction",
                "prompt_text": "PACK_QUERIES: [1] recover alpha_state",
                "context_rows": [
                    {"role": "repo_evidence", "source_type": "repo", "path": "src/a.py", "text": "alpha_state=True"}
                ],
                "target_text": '{"final_state": {"alpha_state": true}, "state_variable": "alpha_state"}',
            },
            {
                "row_id": "retrieval::pack1::1",
                "task_type": "retrieval_supervision",
                "query_text": "What is the final value of alpha_state?",
                "positive_chunk_ids": ["c1", "c2"],
                "target_text": '{"final_state": {"alpha_state": true}, "state_variable": "alpha_state"}',
            },
            {
                "row_id": "memory::pack1",
                "task_type": "state_summary_compression",
                "input_text": "Summarize persistent working memory.",
                "target_text": '{"state_variables": ["alpha_state"]}',
            },
        ],
        max_encoder_tokens=160,
        max_decoder_tokens=64,
    )

    assert batch.input_ids.shape[0] == 3
    assert batch.decoder_input_ids.shape[0] == 3
    assert batch.row_ids == ["full::pack1", "retrieval::pack1::1", "memory::pack1"]


def test_row_text_excludes_oracle_retrieval_ids() -> None:
    rendered = _row_text(
        {
            "row_id": "retrieval::pack1::1",
            "task_type": "retrieval_supervision",
            "query_text": "What is the final value of alpha_state?",
            "positive_chunk_ids": ["c1", "c2"],
        }
    )

    assert "task_type=retrieval_supervision" in rendered
    assert "query_text=What is the final value of alpha_state?" in rendered
    assert "positive_chunk_ids" not in rendered


def test_encoder_tokens_are_invariant_to_targets_and_opaque_ids() -> None:
    base = {
        "row_id": "row-a",
        "task_type": "retrieval_supervision",
        "query_text": "Which evidence supports alpha?",
        "positive_chunk_ids": ["oracle-a"],
        "context_rows": [
            {"chunk_id": "oracle-a", "role": "repo_evidence", "text": "alpha = enabled"},
        ],
        "target": {"decoder_text": "enabled"},
    }
    mutated = {
        **base,
        "row_id": "row-b",
        "positive_chunk_ids": ["oracle-b"],
        "context_rows": [
            {"chunk_id": "oracle-b", "role": "repo_evidence", "text": "alpha = enabled"},
        ],
        "target": {"decoder_text": "disabled"},
    }

    base_batch = build_batch([base], max_encoder_tokens=128, max_decoder_tokens=16)
    mutated_batch = build_batch([mutated], max_encoder_tokens=128, max_decoder_tokens=16)

    assert base_batch.input_ids.tolist() == mutated_batch.input_ids.tolist()
    assert base_batch.labels.tolist() != mutated_batch.labels.tolist()
    assert "chunk_id" not in _row_text(base)
    assert "oracle-a" not in _row_text(base)


def test_nested_target_aliases_fail_closed() -> None:
    containers = [
        {"input_state": {"gold_label": "LEAK_SENTINEL"}},
        {"model_input": {"expected_output": "LEAK_SENTINEL"}},
        {"query": {"features": {"answer_text": "LEAK_SENTINEL"}}},
        {"graph_input": {"nodes": [{"node_type": "symbol", "features": {"expected_patch": "LEAK_SENTINEL"}}]}},
    ]
    for row in containers:
        try:
            _row_text(row)
        except ValueError as exc:
            assert "forbidden model-visible field" in str(exc)
        else:
            raise AssertionError(f"target alias was serialized: {row}")


def test_overlength_generative_target_fails_closed() -> None:
    row = {
        "row_id": "too-long",
        "input_text": "repair this",
        "target": {"decoder_text": "x" * 40},
        "loss_mask": {"decoder_ce": True},
    }
    try:
        build_batch([row], max_encoder_tokens=32, max_decoder_tokens=8)
    except ValueError as exc:
        assert "too-long" in str(exc)
        assert "max_decoder_tokens=8" in str(exc)
    else:
        raise AssertionError("overlength target was silently truncated")


def test_tokenizers_preserve_eos_when_truncating() -> None:
    byte_tokenizer = ByteTokenizer()
    assert byte_tokenizer.encode("abcdef", max_length=4)[-1] == byte_tokenizer.eos_id

    class FakeEncoding:
        ids = [1, 10, 11, 12, 13, 2]

    class FakeTokenizer:
        def encode(self, text: str, add_special_tokens: bool):
            return FakeEncoding()

    bpe = AgentKernelBPETokenizer.__new__(AgentKernelBPETokenizer)
    bpe._tokenizer = FakeTokenizer()
    bpe.bos_id = 1
    bpe.eos_id = 2
    assert bpe.encode("ignored", max_length=4) == [1, 10, 11, 2]


def test_tokenizers_reject_caps_that_cannot_hold_bos_and_eos() -> None:
    import pytest

    with pytest.raises(ValueError, match="BOS and EOS"):
        ByteTokenizer().encode("x", max_length=1)
