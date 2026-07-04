from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any

FRAME_RE = re.compile(r'File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<function>[^\n]+)')
EXC_RE = re.compile(r'^(?P<type>[A-Za-z_][\w.]*Error|[A-Za-z_][\w.]*Exception|AssertionError|SystemExit|KeyboardInterrupt):?\s*(?P<message>.*)$')
PYTEST_RE = re.compile(r'^(?P<path>[^\s:]+\.py):(?P<line>\d+):\s*(?P<message>.*)$')


@dataclass(frozen=True)
class NormalizedFrame:
    frame_id: str
    path: str
    line: int | None
    function: str | None
    raw: str


@dataclass(frozen=True)
class RuntimeTracePacket:
    trace_id: str
    failure_type: str
    exception_type: str | None
    exception_message: str | None
    frames: list[dict[str, Any]]
    evidence_spans: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _trace_id(text: str, row_id: str) -> str:
    return 'trace_' + sha256((row_id + '\n' + text).encode('utf-8')).hexdigest()[:16]


def classify_failure(exception_type: str | None, text: str) -> str:
    lower = text.lower()
    if exception_type == 'AssertionError' or 'assert' in lower or 'failed' in lower:
        return 'test_assertion_failure'
    if exception_type in {'SyntaxError', 'IndentationError'} or 'syntaxerror' in lower:
        return 'syntax_failure'
    if exception_type in {'ImportError', 'ModuleNotFoundError'} or 'no module named' in lower:
        return 'dependency_import_failure'
    if exception_type in {'NameError', 'AttributeError'}:
        return 'symbol_binding_failure'
    if exception_type in {'TypeError', 'ValueError'}:
        return 'runtime_contract_failure'
    if 'timeout' in lower:
        return 'timeout_failure'
    return 'unknown_runtime_failure' if text.strip() else 'empty_trace'


def normalize_runtime_trace(text: str, *, row_id: str = 'row') -> dict[str, Any]:
    trace = str(text or '')
    frames: list[NormalizedFrame] = []
    exception_type: str | None = None
    exception_message: str | None = None
    lines = trace.splitlines()
    for index, line in enumerate(lines):
        frame_match = FRAME_RE.search(line)
        if frame_match:
            path = frame_match.group('path')
            lineno = int(frame_match.group('line'))
            fn = frame_match.group('function').strip()
            frame_id = 'frame_' + sha256(f'{row_id}:{path}:{lineno}:{fn}:{index}'.encode('utf-8')).hexdigest()[:16]
            frames.append(NormalizedFrame(frame_id, path, lineno, fn, line.strip()))
            continue
        pytest_match = PYTEST_RE.search(line)
        if pytest_match and not frames:
            path = pytest_match.group('path')
            lineno = int(pytest_match.group('line'))
            frame_id = 'frame_' + sha256(f'{row_id}:{path}:{lineno}:pytest:{index}'.encode('utf-8')).hexdigest()[:16]
            frames.append(NormalizedFrame(frame_id, path, lineno, 'pytest', line.strip()))
        exc_match = EXC_RE.match(line.strip())
        if exc_match:
            exception_type = exc_match.group('type')
            exception_message = exc_match.group('message') or None
    evidence_spans = [
        {'kind': 'trace_frame', 'path': frame.path, 'line': frame.line, 'function': frame.function, 'frame_id': frame.frame_id}
        for frame in frames
    ]
    packet = RuntimeTracePacket(
        trace_id=_trace_id(trace, row_id),
        failure_type=classify_failure(exception_type, trace),
        exception_type=exception_type,
        exception_message=exception_message,
        frames=[asdict(frame) for frame in frames],
        evidence_spans=evidence_spans,
        failures=[] if trace.strip() else ['empty_trace'],
    )
    return packet.to_dict()


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Normalize runtime/test stack traces into no-authority verifier evidence packets.')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
    packets = [normalize_runtime_trace(str(row.get('trace') or row.get('log') or row.get('text') or ''), row_id=str(row.get('row_id') or row.get('id') or 'row')) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(packet, sort_keys=True) + '\n' for packet in packets), encoding='utf-8')


if __name__ == '__main__':
    main()
