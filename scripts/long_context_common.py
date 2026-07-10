from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")
COMPOUND_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[_-][A-Za-z0-9]+)+|[A-Z]?[a-z0-9]+(?:[A-Z][a-z0-9]+)+")
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "your", "have", "will", "would",
    "about", "their", "there", "which", "when", "where", "while", "using", "used", "than", "then",
    "what", "only", "because", "been", "being", "were", "they", "them", "across", "are", "can",
    "our", "not", "such", "all", "set", "has", "these", "between", "let", "each", "two", "three",
    "four", "five", "more", "most", "other", "some", "many", "into", "also", "than", "over", "under",
}
GENERIC_CORPUS_TERMS = {
    "paper", "papers", "section", "source", "text", "system", "systems", "data", "value", "based",
    "method", "methods", "analysis", "standard", "time", "path", "file", "model", "models", "result",
    "results", "approach", "approaches", "framework", "storage", "market", "technology", "frequency",
}
STRUCTURED_NOISE_TERMS = {
    "timestamp", "payload", "response_item", "turn_id", "session_meta", "event_msg", "call_id", "tool_call",
    "message", "messages", "content", "input_text", "output_text", "jsonl", "null", "true", "false",
    "type", "types", "role", "roles", "phase", "model_provider", "cli_version", "source_id", "doc_id",
    "paper_chunk", "pdf_path", "pdfs", "meta", "arxiv", "domains", "workspace", "user", "assistant",
    "developer", "commentary", "final", "reasoning", "token_count", "cached_input_tokens", "output_tokens",
    "used_percent", "window_minutes", "resets_at", "skills", "skill", "codex", "app", "apps", "html",
    "const", "var", "function", "functions", "files", "metadata", "name", "title", "work", "code",
    "cli", "tool", "tools", "repo", "repos", "prompt", "prompts", "agent", "agents",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def approx_tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text or "")


def approx_token_count(text: str) -> int:
    return len(approx_tokenize(text))


def iter_text_files(root: Path) -> Iterator[Path]:
    allowed_suffixes = {".py", ".md", ".txt", ".rst", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh"}
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirname for dirname in dirnames if not dirname.startswith('.git'))
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            if any(part.startswith('.git') for part in path.parts):
                continue
            suffix = path.suffix.lower()
            if suffix in allowed_suffixes:
                yield path


def safe_read_text(path: Path, max_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if max_chars is not None:
        return text[:max_chars]
    return text


def source_type_from_path(path: Path, *, source_root: Path, declared_type: str | None = None) -> str:
    if declared_type in {"paper", "repo", "dataset"}:
        return declared_type
    if source_root.name == "repositories":
        return "repo"
    if source_root.name == "datasets":
        return "dataset"
    if "papers" in source_root.parts:
        return "paper"
    return "document"


def source_id_from_path(path: Path, *, source_root: Path) -> str:
    rel = path.relative_to(source_root)
    if not rel.parts:
        return source_root.name
    return rel.parts[0]


def modality_from_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh"}:
        return "code"
    if suffix in {".json", ".jsonl", ".yaml", ".yml", ".toml", ".cfg", ".ini"}:
        return "structured_text"
    return "text"


def language_from_suffix(path: Path) -> str | None:
    mapping = {
        ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
        ".java": "java", ".go": "go", ".rs": "rust", ".c": "c", ".cc": "cpp", ".cpp": "cpp",
        ".h": "c", ".hpp": "cpp", ".sh": "shell",
    }
    return mapping.get(path.suffix.lower())


def stable_id(prefix: str, *parts: str) -> str:
    base = "_".join(slugify(part) for part in parts if part)
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{base}_{digest}" if base else f"{prefix}_{digest}"


def slugify(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_").lower()
    return value[:80] if value else "x"


def chunk_text(text: str, *, max_tokens: int) -> list[str]:
    lines = text.splitlines() or [text]
    out: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in lines:
        line_tokens = approx_token_count(line)
        if current and current_tokens + line_tokens > max_tokens:
            out.append("\n".join(current).strip())
            current = []
            current_tokens = 0
        if line_tokens > max_tokens and not current:
            tokens = approx_tokenize(line)
            for start in range(0, len(tokens), max_tokens):
                out.append(" ".join(tokens[start : start + max_tokens]))
            continue
        current.append(line)
        current_tokens += line_tokens
    if current:
        out.append("\n".join(current).strip())
    return [chunk for chunk in out if chunk]


def should_keep_term(term: str, *, source_type: str | None = None, modality: str | None = None) -> bool:
    lower = term.lower().strip()
    if len(lower) < 3:
        return False
    if lower in STOPWORDS or lower in GENERIC_CORPUS_TERMS:
        return False
    if lower in STRUCTURED_NOISE_TERMS:
        return False
    if lower.isdigit():
        return False
    if lower.startswith(("call_", "turn_", "msg_", "tok_", "chunk_")):
        return False
    if lower.endswith(("_id", "_ids", "_json", "_jsonl", "_count", "_tokens")):
        return False
    if source_type == "dataset" or modality == "structured_text":
        if lower in {"input", "output", "command", "commands", "args", "argument", "arguments", "session", "sessions", "tool", "tools", "status", "system", "chat", "instruction", "instructions"}:
            return False
    return True


def extract_terms(text: str, *, max_terms: int = 32, source_type: str | None = None, modality: str | None = None) -> list[str]:
    counts: Counter[str] = Counter()
    for token in WORD_RE.findall(text or ""):
        lower = token.lower()
        if not should_keep_term(lower, source_type=source_type, modality=modality):
            continue
        counts[lower] += 1
    return [term for term, _ in counts.most_common(max_terms)]


def _split_camel(token: str) -> list[str]:
    return [part for part in re.findall(r'[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|$)', token) if part]


def normalize_compound_term(token: str) -> str | None:
    raw = str(token or '').strip()
    if not raw:
        return None
    if '_' in raw or '-' in raw:
        pieces = re.split(r'[_-]+', raw)
    else:
        pieces = _split_camel(raw)
    normalized_parts = []
    for piece in pieces:
        lower = piece.lower().strip()
        if len(lower) < 3:
            continue
        if not should_keep_term(lower):
            continue
        normalized_parts.append(lower)
    if len(normalized_parts) < 2:
        return None
    compound = '_'.join(normalized_parts)
    if not should_keep_term(compound, source_type=None, modality=None):
        return None
    return compound


def extract_compound_terms(text: str, *, max_terms: int = 16, source_type: str | None = None, modality: str | None = None) -> list[str]:
    counts: Counter[str] = Counter()
    for token in COMPOUND_RE.findall(text or ''):
        normalized = normalize_compound_term(token)
        if not normalized:
            continue
        if not should_keep_term(normalized, source_type=source_type, modality=modality):
            continue
        counts[normalized] += 1
    return [term for term, _ in counts.most_common(max_terms)]


def lexical_overlap_score(a: str, b: str) -> float:
    ta = set(extract_terms(a, max_terms=128))
    tb = set(extract_terms(b, max_terms=128))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _normalized_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./').lower()

def _path_suffix_candidates(path: str) -> set[str]:
    parts = [part for part in _normalized_path(path).split('/') if part]
    out: set[str] = set()
    if len(parts) >= 1:
        out.add(parts[-1])
    if len(parts) >= 2:
        out.add('/'.join(parts[-2:]))
    if len(parts) >= 3:
        out.add('/'.join(parts[-3:]))
    return out

def _chunk_path(chunk: Mapping[str, Any]) -> str:
    metadata_json = chunk.get('metadata_json')
    metadata = {}
    if isinstance(metadata_json, str) and metadata_json.strip():
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
    return str(chunk.get('path') or metadata.get('path') or '')

def _chunk_filter_terms(chunk: Mapping[str, Any]) -> tuple[set[str], set[str], str]:
    source_type = str(chunk.get('source_type') or '') or None
    modality = str(chunk.get('modality') or '') or None
    path_value = _chunk_path(chunk)
    text_value = str(chunk.get('text') or '')
    sample = f"{path_value}\n{text_value[:4000]}"
    terms = set(extract_terms(sample, max_terms=128, source_type=source_type, modality=modality))
    compounds = set(extract_compound_terms(sample, max_terms=64, source_type=source_type, modality=modality))
    return terms, compounds, path_value

def choose_distractors(
    chunks: list[dict[str, Any]],
    *,
    exclude_ids: set[str],
    target_tokens: int,
    rng: random.Random,
    forbidden_terms: set[str] | None = None,
    forbidden_compounds: set[str] | None = None,
    forbidden_exact_paths: set[str] | None = None,
    forbidden_path_suffixes: set[str] | None = None,
    forbidden_repo_source_ids: set[str] | None = None,
    anchor_text: str = '',
    max_anchor_overlap: float = 0.02,
) -> list[dict[str, Any]]:
    forbidden_terms = {str(term).lower() for term in (forbidden_terms or set()) if str(term).strip()}
    forbidden_compounds = {str(term).lower() for term in (forbidden_compounds or set()) if str(term).strip()}
    forbidden_exact_paths = {_normalized_path(path_value) for path_value in (forbidden_exact_paths or set()) if str(path_value).strip()}
    forbidden_path_suffixes = {str(item).lower() for item in (forbidden_path_suffixes or set()) if str(item).strip()}
    forbidden_repo_source_ids = {str(item) for item in (forbidden_repo_source_ids or set()) if str(item).strip()}

    pool = [chunk for chunk in chunks if str(chunk.get('chunk_id') or '') not in exclude_ids]
    rng.shuffle(pool)
    total = 0
    out: list[dict[str, Any]] = []
    for chunk in pool:
        source_type = str(chunk.get('source_type') or '')
        source_id = str(chunk.get('source_id') or '')
        if source_type == 'repo' and source_id and source_id in forbidden_repo_source_ids:
            continue
        terms, compounds, raw_path = _chunk_filter_terms(chunk)
        norm_path = _normalized_path(raw_path)
        if norm_path and norm_path in forbidden_exact_paths:
            continue
        if forbidden_path_suffixes and _path_suffix_candidates(norm_path) & forbidden_path_suffixes:
            continue
        if forbidden_terms and terms & forbidden_terms:
            continue
        if forbidden_compounds and compounds & forbidden_compounds:
            continue
        if anchor_text:
            overlap = lexical_overlap_score(anchor_text, f"{raw_path}\n{str(chunk.get('text') or '')[:4000]}")
            if overlap > max_anchor_overlap:
                continue
        out.append(chunk)
        total += int(chunk.get('token_count') or 0)
        if total >= target_tokens:
            break
    if total < target_tokens:
        raise ValueError(f'insufficient_clean_distractors:{total}:{target_tokens}')
    return out

def infer_entity_type(name: str, source_types: Iterable[str]) -> str:
    joined = " ".join(source_types)
    lower = name.lower()
    if any(tag in lower for tag in {"error", "failure", "exception", "regression"}):
        return "failure_type"
    if lower in {"benchmark", "benchmarks", "mmlu", "swebench", "swe"}:
        return "benchmark_term"
    if "repo" in joined:
        return "symbol_or_repo_term"
    if "paper" in joined:
        return "paper_term"
    return "term"


def bool_flip(value: Any) -> bool:
    return not bool(value)


def pick_query_text(program: Mapping[str, Any]) -> str:
    state_vars = program.get("state_variables", [])
    if not state_vars:
        return "What is the final state after all evidence?"
    first = state_vars[0]["name"]
    return f"What is the final value of `{first}` after reconciling all evidence?"


def mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / max(1, len(vals))


def source_mix(chunks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for chunk in chunks:
        counts[str(chunk.get("source_type") or "unknown")] += 1
    return dict(sorted(counts.items()))
