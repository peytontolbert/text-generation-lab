from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_open_swe_traces_episodes import import_open_swe_traces_episodes  # noqa: E402


def _write_parquet(path: Path, rows: list[dict]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def test_import_open_swe_traces_episodes_emits_canonical_trace_backed_episode(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    parquet_path = tmp_path / "train-00000.parquet"
    _write_parquet(
        parquet_path,
        [
            {
                "instance_id": "attrs-770",
                "repo": "python-attrs/attrs",
                "license": "MIT",
                "language": "python",
                "trajectory_id": "traj-1",
                "resolved": 1,
                "metadata": {"category": "bug-fix", "num_modified_files": 1, "num_modified_lines": 8},
                "model_patch": "\n".join(
                    [
                        "diff --git a/src/attr/_make.py b/src/attr/_make.py",
                        "--- a/src/attr/_make.py",
                        "+++ b/src/attr/_make.py",
                        "@@",
                        "+import types",
                        "-    type_ = type(name, bases, body)",
                        "+    type_ = types.new_class(name, bases, {}, lambda ns: ns.update(body))",
                    ]
                ),
                "trajectory": [
                    {
                        "role": "user",
                        "content": "\n".join(
                            [
                                "<uploaded_files>",
                                "/workspace/python-attrs__attrs__1.0",
                                "</uploaded_files>",
                                "Consider the following issue description:",
                                "<issue_description>",
                                "attr.make_class does not work with Python>=3.7 and fails with `TypeError` in `make_class`.",
                                "</issue_description>",
                            ]
                        ),
                        "tool_calls": [],
                    },
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "str_replace_editor", "arguments": json.dumps({"command": "view", "path": "/workspace/python-attrs__attrs__1.0/src/attr/_make.py"})}}
                        ],
                    },
                    {
                        "role": "tool",
                        "content": "Here's the result of running `cat -n` on /workspace/python-attrs__attrs__1.0/src/attr/_make.py:\n2887 def make_class(name, attrs, bases=(object,), **attributes_arguments):\n2920     type_ = type(name, bases, body)\n",
                        "tool_calls": [],
                    },
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "execute_bash", "arguments": json.dumps({"command": "pytest tests/test_make.py::TestMakeClass::test_make_class_ordered -q"})}}
                        ],
                    },
                    {
                        "role": "tool",
                        "content": "tests/test_make.py::TestMakeClass::test_make_class_ordered PASSED\n================= 1 passed in 0.22s =================",
                        "tool_calls": [],
                    },
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "execute_bash", "arguments": json.dumps({"command": "python reproduce.py"})}}
                        ],
                    },
                    {
                        "role": "tool",
                        "content": "ERROR: type() doesn't support MRO entry resolution; use types.new_class()\nTraceback (most recent call last):\nTypeError: type() doesn't support MRO entry resolution; use types.new_class()\n",
                        "tool_calls": [],
                    },
                ],
            }
        ],
    )

    output_path = tmp_path / "episodes.jsonl"
    summary = import_open_swe_traces_episodes(
        input_glob=str(parquet_path),
        output_path=output_path,
        dataset_name="nvidia--Open-SWE-Traces",
    )

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert summary["imported_rows"] == 1
    assert len(rows) == 1
    row = rows[0]
    assert row["seed_type"] == "open_swe_trace_episode"
    assert row["repo_id"] == "python-attrs/attrs"
    assert row["seed_paths"] == ["src/attr/_make.py"]
    assert row["selected_tests"] == ["tests/test_make.py::TestMakeClass::test_make_class_ordered"]
    assert row["source_metadata"]["route"] == "PATCH_PLUS_VERIFY"
    assert row["target"]["state_after"]["execution_route"] == "PATCH_PLUS_VERIFY"
    assert "TypeError" in row["source_metadata"]["trace_exception_types"]
    roles = {context_row["role"] for context_row in row["context_rows"]}
    assert "seed_change" in roles
    assert "verification_constraint" in roles


def test_import_open_swe_traces_episodes_skips_trace_without_verification_targets(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        pytest.skip("pyarrow not installed")

    parquet_path = tmp_path / "train-00001.parquet"
    _write_parquet(
        parquet_path,
        [
            {
                "instance_id": "weak-1",
                "repo": "example/repo",
                "license": "MIT",
                "language": "python",
                "trajectory_id": "traj-weak",
                "resolved": 1,
                "metadata": {"category": "bug-fix", "num_modified_files": 1, "num_modified_lines": 2},
                "model_patch": "\n".join(
                    [
                        "diff --git a/src/main.py b/src/main.py",
                        "--- a/src/main.py",
                        "+++ b/src/main.py",
                        "@@",
                        "-    return False",
                        "+    return True",
                    ]
                ),
                "trajectory": [
                    {
                        "role": "user",
                        "content": "<issue_description>Fix the boolean return.</issue_description>",
                        "tool_calls": [],
                    },
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "str_replace_editor", "arguments": json.dumps({"command": "view", "path": "/workspace/example/src/main.py"})}}
                        ],
                    },
                    {
                        "role": "tool",
                        "content": "def run():\n    return False\n",
                        "tool_calls": [],
                    },
                ],
            }
        ],
    )

    with pytest.raises(ValueError, match="no_open_swe_trace_episodes_imported"):
        import_open_swe_traces_episodes(input_glob=str(parquet_path), output_path=tmp_path / "episodes.jsonl")
