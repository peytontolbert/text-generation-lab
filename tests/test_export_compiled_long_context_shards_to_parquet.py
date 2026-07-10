from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_compiled_long_context_shards_to_parquet import export_compiled_long_context_shards_to_parquet  # noqa: E402


def test_export_compiled_long_context_shards_to_parquet_writes_parquet_and_card(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    compiled = tmp_path / "compiled"
    compiled.mkdir()
    (compiled / "compile_card.json").write_text(
        json.dumps({"trainer_rows": 1, "retrieval_rows": 2}, sort_keys=True),
        encoding="utf-8",
    )
    (compiled / "full_context_rows.jsonl").write_text(
        json.dumps(
            {
                "row_id": "full::p1",
                "pack_id": "p1",
                "context_rows": [{"chunk_id": "c1", "path": "src/a.py"}],
                "metadata": {"pack_token_count": 123},
                "target_text": "x",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (compiled / "retrieval_rows.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "row_id": "retrieval::p1::1",
                        "pack_id": "p1",
                        "positive_chunk_ids": ["c1", "c2"],
                        "metadata": {"query_index": 1},
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "row_id": "retrieval::p1::2",
                        "pack_id": "p1",
                        "positive_chunk_ids": ["c2"],
                        "metadata": {"query_index": 2},
                    },
                    sort_keys=True,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (compiled / "memory_rows.jsonl").write_text(
        json.dumps(
            {
                "row_id": "memory::p1",
                "pack_id": "p1",
                "metadata": {"chunk_count": 4},
                "target_text": '{"state_variables":["x"]}',
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = export_compiled_long_context_shards_to_parquet(
        compiled_dir=compiled,
        rows_per_shard=1,
    )

    assert summary["exports"]["full_context_rows"]["row_count"] == 1
    assert summary["exports"]["retrieval_rows"]["shard_count"] == 2
    assert summary["exports"]["memory_rows"]["row_count"] == 1

    import pyarrow.parquet as pq

    full_table = pq.read_table(compiled / "parquet" / "full_context_rows" / "full_context_rows-000000.parquet")
    full_row = full_table.to_pylist()[0]
    assert isinstance(full_row["context_rows"], str)
    assert json.loads(full_row["context_rows"])[0]["chunk_id"] == "c1"
    assert isinstance(full_row["metadata"], str)
    assert json.loads(full_row["metadata"])["pack_token_count"] == 123

    retrieval_table = pq.read_table(compiled / "parquet" / "retrieval_rows" / "retrieval_rows-000000.parquet")
    retrieval_row = retrieval_table.to_pylist()[0]
    assert isinstance(retrieval_row["positive_chunk_ids"], str)
    assert json.loads(retrieval_row["positive_chunk_ids"]) == ["c1", "c2"]

    export_card = json.loads((compiled / "parquet" / "parquet_export_card.json").read_text(encoding="utf-8"))
    assert export_card["compile_card"]["trainer_rows"] == 1
    assert export_card["exports"]["retrieval_rows"]["row_count"] == 2


def test_export_compiled_long_context_shards_to_parquet_requires_all_inputs(tmp_path: Path) -> None:
    compiled = tmp_path / "compiled"
    compiled.mkdir()
    (compiled / "full_context_rows.jsonl").write_text("{}", encoding="utf-8")
    (compiled / "retrieval_rows.jsonl").write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        export_compiled_long_context_shards_to_parquet(compiled_dir=compiled)


def test_export_compiled_long_context_shards_to_parquet_cleans_stale_shards(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    compiled = tmp_path / "compiled"
    compiled.mkdir()
    for name, payload in {
        "full_context_rows.jsonl": {"row_id": "full::p1", "pack_id": "p1", "context_rows": [], "metadata": {}},
        "retrieval_rows.jsonl": {"row_id": "retrieval::p1::1", "pack_id": "p1", "positive_chunk_ids": [], "metadata": {}},
        "memory_rows.jsonl": {"row_id": "memory::p1", "pack_id": "p1", "metadata": {}},
    }.items():
        (compiled / name).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    stale_dir = compiled / "parquet" / "retrieval_rows"
    stale_dir.mkdir(parents=True)
    (stale_dir / "stale.parquet").write_text("stale", encoding="utf-8")

    export_compiled_long_context_shards_to_parquet(compiled_dir=compiled, rows_per_shard=10)

    assert not (stale_dir / "stale.parquet").exists()
    shards = sorted((compiled / "parquet" / "retrieval_rows").glob("*.parquet"))
    assert len(shards) == 1
