from __future__ import annotations

import hashlib
import json
import math
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
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".git") for part in path.parts):
            continue
        suffix = path.suffix.lower()
        if suffix in {".py", ".md", ".txt", ".rst", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh"}:
            yield path


def safe_read_text(path: Path, max_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if max_chars is not None:
        return text[:max_chars]
    return text


def source_type_from_path(path: Path, *, source_root: Path) -> str:
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


def choose_distractors(
    chunks: list[dict[str, Any]],
    *,
    exclude_ids: set[str],
    target_tokens: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    pool = [chunk for chunk in chunks if chunk["chunk_id"] not in exclude_ids]
    rng.shuffle(pool)
    total = 0
    out: list[dict[str, Any]] = []
    for chunk in pool:
        out.append(chunk)
        total += int(chunk.get("token_count", 0))
        if total >= target_tokens:
            break
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
