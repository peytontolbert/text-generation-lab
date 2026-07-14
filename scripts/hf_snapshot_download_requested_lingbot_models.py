from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import snapshot_download


MODELS = [
    "robbyant/lingbot-world-v2-14b-causal-fast",
    "robbyant/lingbot-video-rewriter-lora",
    "robbyant/lingbot-video-dense-1.3b",
    "robbyant/lingbot-va-base",
    "robbyant/lingbot-world-base-act-preview",
    "nvidia/DAM-3B-Video",
    "tencent/Hunyuan3D-2",
]

TARGET_ROOT = Path("/arxiv/models")
LOG = Path("/arxiv/hf_snapshot_download_requested_lingbot_models.log")


def log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    line = f"{ts} {message}"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{line}\n")
    print(line, flush=True)


def main() -> None:
    log("QUEUE_START")
    failures: list[tuple[str, str]] = []

    for repo_id in MODELS:
        target = TARGET_ROOT / repo_id
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            log(f"START repo_type=model repo_id={repo_id} target={target}")
            path = snapshot_download(
                repo_id=repo_id,
                repo_type="model",
                local_dir=str(target),
                max_workers=8,
            )
            log(f"DONE repo_type=model repo_id={repo_id} path={path}")
        except Exception as exc:
            log(f"ERROR repo_type=model repo_id={repo_id} error={type(exc).__name__}: {exc}")
            failures.append((repo_id, repr(exc)))

    log(f"QUEUE_DONE failures={len(failures)}")
    for repo_id, err in failures:
        log(f"FAILED repo_id={repo_id} err={err}")


if __name__ == "__main__":
    main()
