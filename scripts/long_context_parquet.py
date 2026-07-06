from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

def write_parquet_shard(path: Path, rows: list[dict[str, Any]], *, compression: str = "zstd") -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression=compression)


def shard_path(directory: Path, prefix: str, shard_index: int) -> Path:
    return directory / f"{prefix}-{shard_index:06d}.parquet"
