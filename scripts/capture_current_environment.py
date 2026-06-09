#!/usr/bin/env python3
"""Capture source-environment inventory from the legacy agent_kernel_lite repo."""
from __future__ import annotations
import argparse, datetime as _dt, json, os, re, subprocess
from pathlib import Path
PATTERNS = {
    "image": "(image|vision|sana|flux|bitdit|diffusion|coco|imagenet|realcrop|real_crop|teacher_ref|t2i|latent_flow|deartifact|clip|dog_one_seed)",
    "acoustic": "(f5tts|tts|vocos|audio|speech|voice|mel|wav|mp3|acoustic|jarvis|peyton)",
    "text": "(pocketpal|encdec|seq2seq|agentic|intent|retrieval|decoder|controller|ak_token|nvidia|hermes|research_assistant|text|fineweb|causal|agentkernel_lite_100m)"
}
def _rel(root: Path, path: Path) -> str: return str(path.relative_to(root))
def _walk(root: Path, rel_base: str, *, files: bool = True, dirs: bool = False, max_depth: int | None = None) -> list[str]:
    base = root / rel_base
    if not base.exists(): return []
    out=[]
    for dirpath, dirnames, filenames in os.walk(base):
        current = Path(dirpath); depth = len(current.relative_to(base).parts)
        if max_depth is not None and depth >= max_depth: dirnames[:] = []
        if dirs and current != base: out.append(_rel(root, current))
        if files:
            for name in filenames: out.append(_rel(root, current / name))
    return sorted(out)
def _root_files(root: Path) -> list[str]: return sorted(_rel(root, p) for p in root.iterdir() if p.is_file())
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default="/data/agent_kernel_lite")
    parser.add_argument("--lab", choices=sorted(PATTERNS), required=True)
    parser.add_argument("--output", default="manifests/current_environment.json")
    args = parser.parse_args()
    root = Path(args.source_root).resolve(); pattern = re.compile(PATTERNS[args.lab], re.I)
    groups = {
        "root_files": _root_files(root), "scripts": _walk(root, "scripts"), "docs": _walk(root, "docs"), "tests": _walk(root, "tests"),
        "data_files": _walk(root, "data", max_depth=4),
        "checkpoint_dirs": _walk(root, "checkpoints", files=False, dirs=True, max_depth=2),
        "artifact_dirs": _walk(root, "artifacts", files=False, dirs=True, max_depth=2),
        "tmp_files": _walk(root, "tmp", max_depth=2), "logs": _walk(root, "logs", max_depth=3), "examples": _walk(root, "examples", max_depth=3),
        "web_models": _walk(root, "web/models", files=False, dirs=True, max_depth=2), "web_voice": _walk(root, "web/voice", max_depth=4),
        "app_models": _walk(root, "apps/mobile/www/app/models", files=False, dirs=True, max_depth=2), "app_voice": _walk(root, "apps/mobile/www/app/voice", max_depth=4),
        "native_models": _walk(root, "native-models", files=False, dirs=True, max_depth=2), "model_stack": _walk(root, "model-stack", max_depth=4), "wasm": _walk(root, "wasm", max_depth=4),
        "tts_quality_samples": _walk(root, "tts_quality_samples", max_depth=3), "tts_test_outputs": _walk(root, "tts_test_outputs", max_depth=3),
    }
    selected = {key: [item for item in value if pattern.search(item)] for key, value in groups.items()}
    try: git_head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    except Exception: git_head = None
    try: git_status = subprocess.check_output(["git", "-C", str(root), "status", "--short"], text=True).splitlines()
    except Exception: git_status = []
    manifest = {"generated_at": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "source_root": str(root), "source_git_head": git_head, "source_git_status_short": git_status, "lab": args.lab, "selected_counts": {key: len(value) for key, value in selected.items()}, "selected_paths": selected}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(manifest, indent=2) + "\n")
if __name__ == "__main__": main()
