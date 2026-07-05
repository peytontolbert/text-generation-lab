from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_DIM = 32


def _tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_tokens(item))
        return out
    text = str(value).lower()
    token = []
    out = []
    for ch in text:
        if ch.isalnum() or ch in {"_", "-", "."}:
            token.append(ch)
        elif token:
            out.append("".join(token))
            token = []
    if token:
        out.append("".join(token))
    return out


def _feature_tokens(repo: Mapping[str, Any]) -> list[str]:
    fields = [
        "name",
        "description",
        "readme",
        "topics",
        "languages",
        "dependencies",
        "files",
        "symbols",
        "api_surface",
    ]
    tokens: list[str] = []
    for field in fields:
        for token in _tokens(repo.get(field)):
            tokens.append(f"{field}:{token}" if field in {"languages", "dependencies", "topics"} else token)
    return tokens


def hashed_vector(tokens: Iterable[str], *, dim: int = DEFAULT_DIM) -> list[float]:
    vec = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 8) for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def repo_node(repo: Mapping[str, Any], *, dim: int = DEFAULT_DIM) -> dict[str, Any]:
    repo_id = str(repo.get("repo_id") or repo.get("id") or repo.get("name") or "unknown_repo")
    tokens = _feature_tokens(repo)
    vector = hashed_vector(tokens, dim=dim)
    return {
        "repo_id": repo_id,
        "repo_vector": vector,
        "repo_coord3d": vector[:3] if len(vector) >= 3 else vector + [0.0] * (3 - len(vector)),
        "feature_counts": {
            "tokens": len(tokens),
            "languages": len(_tokens(repo.get("languages"))),
            "dependencies": len(_tokens(repo.get("dependencies"))),
            "files": len(_tokens(repo.get("files"))),
            "symbols": len(_tokens(repo.get("symbols"))),
        },
        "lineage": repo.get("lineage", {}),
        "raw_source_included": False,
        "promotion_authority": False,
    }


def build_repository_universe(repos: list[Mapping[str, Any]], *, dim: int = DEFAULT_DIM, k: int = 2) -> dict[str, Any]:
    nodes = [repo_node(repo, dim=dim) for repo in repos]
    edges = []
    for i, src in enumerate(nodes):
        scored = []
        for j, dst in enumerate(nodes):
            if i == j:
                continue
            scored.append((cosine(src["repo_vector"], dst["repo_vector"]), dst["repo_id"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for score, dst_id in scored[: max(0, min(k, len(scored)))]:
            edges.append({
                "src": src["repo_id"],
                "dst": dst_id,
                "edge_type": "repo_knn_similar_to",
                "weight": round(score, 8),
                "promotion_authority": False,
            })
    languages = Counter()
    for repo in repos:
        languages.update(_tokens(repo.get("languages")))
    return {
        "universe_manifest": {
            "repo_count": len(nodes),
            "edge_count": len(edges),
            "vector_dim": dim,
            "knn_k": k,
            "raw_source_included": False,
            "promotion_authority": False,
        },
        "nodes": nodes,
        "edges": edges,
        "metrics": {
            "repo_count": len(nodes),
            "edge_count": len(edges),
            "vector_dim": dim,
            "language_counts": dict(languages),
            "authority_rows": 0,
            "raw_source_rows": 0,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic no-authority repository universe builder.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dim", type=int, default=DEFAULT_DIM)
    parser.add_argument("--k", type=int, default=2)
    args = parser.parse_args()
    card = build_repository_universe(read_jsonl(args.manifest), dim=args.dim, k=args.k)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
