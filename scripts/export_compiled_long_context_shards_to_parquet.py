from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from long_context_common import write_json
from long_context_parquet import shard_path, write_parquet_shard


def _stream_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            yield json.loads(text)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _normalize_value(value) for key, value in row.items()}


def export_jsonl_to_parquet_shards(
    *,
    input_path: Path,
    output_dir: Path,
    prefix: str,
    rows_per_shard: int = 10000,
    compression: str = "zstd",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    shard_index = 0
    total_rows = 0
    shard_rows: list[dict[str, Any]] = []
    shard_counts: list[int] = []

    for row in _stream_jsonl(input_path):
        shard_rows.append(_normalize_row(row))
        if len(shard_rows) >= rows_per_shard:
            write_parquet_shard(
                shard_path(output_dir, prefix, shard_index),
                shard_rows,
                compression=compression,
            )
            shard_counts.append(len(shard_rows))
            total_rows += len(shard_rows)
            shard_rows = []
            shard_index += 1

    if shard_rows:
        write_parquet_shard(
            shard_path(output_dir, prefix, shard_index),
            shard_rows,
            compression=compression,
        )
        shard_counts.append(len(shard_rows))
        total_rows += len(shard_rows)

    return {
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "prefix": prefix,
        "rows_per_shard": int(rows_per_shard),
        "compression": compression,
        "row_count": total_rows,
        "shard_count": len(shard_counts),
        "rows_per_shard_written": shard_counts,
    }


def export_compiled_long_context_shards_to_parquet(
    *,
    compiled_dir: Path,
    output_dir: Path | None = None,
    rows_per_shard: int = 10000,
    compression: str = "zstd",
) -> dict[str, Any]:
    compiled_dir = compiled_dir.resolve()
    destination = (output_dir or (compiled_dir / "parquet")).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    shard_specs = [
        ("full_context_rows", "full_context_rows"),
        ("retrieval_rows", "retrieval_rows"),
        ("memory_rows", "memory_rows"),
    ]

    input_paths = {stem: compiled_dir / f"{stem}.jsonl" for stem, _ in shard_specs}
    missing_inputs = [str(path) for path in input_paths.values() if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing compiled shard inputs: {missing_inputs}")

    for stem, _ in shard_specs:
        shard_output_dir = destination / stem
        if shard_output_dir.exists():
            shutil.rmtree(shard_output_dir)
    export_card_path = destination / "parquet_export_card.json"
    if export_card_path.exists():
        export_card_path.unlink()

    exports: dict[str, Any] = {}
    for stem, prefix in shard_specs:
        exports[stem] = export_jsonl_to_parquet_shards(
            input_path=input_paths[stem],
            output_dir=destination / stem,
            prefix=prefix,
            rows_per_shard=rows_per_shard,
            compression=compression,
        )

    compile_card_path = compiled_dir / "compile_card.json"
    compile_card = json.loads(compile_card_path.read_text(encoding="utf-8")) if compile_card_path.exists() else {}
    summary = {
        "compiled_dir": str(compiled_dir),
        "output_dir": str(destination),
        "rows_per_shard": int(rows_per_shard),
        "compression": compression,
        "compile_card": compile_card,
        "exports": exports,
    }
    write_json(destination / "parquet_export_card.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export compiled long-context training shards from JSONL to Parquet.")
    parser.add_argument("--compiled-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--rows-per-shard", type=int, default=10000)
    parser.add_argument("--compression", type=str, default="zstd")
    args = parser.parse_args()
    export_compiled_long_context_shards_to_parquet(
        compiled_dir=args.compiled_dir,
        output_dir=args.output_dir,
        rows_per_shard=args.rows_per_shard,
        compression=args.compression,
    )


if __name__ == "__main__":
    main()
