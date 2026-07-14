import os
from pathlib import Path

from huggingface_hub import snapshot_download


os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")

BASE = Path("/arxiv/models")

REPOS = """
nvidia/ARDY-Core-RP-20FPS-Horizon40
nvidia/PiD
nvidia/ARDY-G1-RP-25FPS-Horizon52
nvidia/ARDY-G1-RP-25FPS-Horizon8
nvidia/C-RADIOv4-SO400M
nvidia/RADIO
nvidia/C-RADIOv2-VLM-H-RC3
nvidia/bigvgan_v2_44khz_128band_512x
nvidia/parakeet-rnnt-0.6b
nvidia/parakeet-rnnt-1.1b
nvidia/parakeet-ctc-1.1b
nvidia/parakeet-tdt_ctc-110m
nvidia/parakeet-tdt-0.6b-v3
nvidia/parakeet_realtime_eou_120m-v1
nvidia/multitalker-parakeet-streaming-0.6b-v1
nvidia/mel-codec-44khz
nvidia/audio-codec-44khz
nvidia/Llama-3.1-Nemotron-8B-UltraLong-1M-Instruct
nvidia/Llama-3.1-Nemotron-8B-UltraLong-4M-Instruct
nvidia/DAM-3B
nvidia/DAM-3B-Video
nvidia/DAM-3B-Self-Contained
nvidia/Cosmos-Embed1-448p
nvidia/Cosmos-Embed1-448p-anomaly-detection
nvidia/Cosmos-Embed1-224p
nvidia/Audio2Face-3D-v3.0
nvidia/Audio2Emotion-v3.0
nvidia/Audio2Face-3D-v2.3-Mark
nvidia/GEN3C-Cosmos-7B
nvidia/ChronoEdit-14B-Diffusers-Paint-Brush-Lora
nvidia/llama-nemotron-rerank-1b-v2
nvidia/llama-nv-embed-reasoning-3b
nvidia/nemotron-page-elements-v3
nvidia/nemotron-ocr-v2
nvidia/nemotron-speech-streaming-en-0.6b
nvidia/nemotron-3.5-asr-streaming-0.6b
nvidia/parakeet-unified-en-0.6b
nvidia/Cosmos3-Nano
nvidia/Cosmos3-Nano-Policy-DROID
nvidia/Kimodo-SOMA-RP-v1.1
nvidia/Kimodo-SOMA-SEED-v1.1
nvidia/Kimodo-SMPLX-RP-v1
nvidia/TMR-SOMA-RP-v1
nvidia/Kimodo-G1-SEED-v1
nvidia/Kimodo-G1-RP-v1
nvidia/Kimodo-SOMA-SEED-v1.1
nvidia/PixelDiT-1300M-1024px
nvidia/EGM-4B
nvidia/EGM-4B-SFT
nvidia/Lyra-2.0
nvidia/AnyFlow-FAR-Wan2.1-1.3B-Diffusers
nvidia/AnyFlow-Wan2.1-T2V-1.3B-Diffusers
tencent/Hunyuan3D-2mini
tencent/HunyuanWorld-Voyager
tencent/Hunyuan3D-2.1
tencent/Hunyuan3D-Omni
tencent/Hunyuan3D-2mv
tencent/HunyuanVideo-Avatar
tencent/HunyuanVideo-I2V
tencent/HunyuanVideo-PromptRewrite
tencent/HunyuanVideo-1.5
tencent/HunyuanImage-3.0
conradlocke/krea2-identity-edit
OpenMOSS-Team/MOSS-SoundEffect-v2.0
tencent/Youtu-HiChunk
tencent/Youtu-Parsing
tencent/HunyuanVideo-Foley
nvidia/X-Mobility
facebook/sam-3d-objects
ASLP-lab/YingMusic-Singer-Plus
nvidia/music-flamingo-2601-hf
Soul-AILab/SoulX-Singer
meituan-longcat/LongCat-Video-Avatar-1.5
OmerHagage/ltx2-greenscreen-avatar-ic-lora-vertical-v1
tencent/HunyuanVideo-Avatar
huaichang/PersonaLive
nvidia/diar_streaming_sortformer_4spk-v2
robbyant/lingbot-world-v2-14b-causal-fast
tencent/HY-World-2.0
krea/Krea-2-Turbo
Patil/Krea-2-depth-controlnet
tencent/HY-Motion-1.0
Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients
netflix/void-model
facebook/sapiens2-pose-0.4b
Lightricks/LTX-2.3
nvidia/Cosmos-Predict2-2B-Video2World
acvlab/ABot-World-0-5B-LF
robbyant/lingbot-world-v2-14b-causal-fast-diffusers
Quark-Vision/Live-Avatar
facebook/cwm
""".splitlines()

MANUAL_SKIP_REPOS = {
    "tencent/HunyuanVideo-PromptRewrite",
}


def target_for(repo: str) -> Path:
    return BASE / repo.split("/")[-1]


def appears_complete(target: Path) -> bool:
    if not target.exists():
        return False
    cache_dir = target / ".cache" / "huggingface" / "download"
    if cache_dir.exists() and any(cache_dir.rglob("*.incomplete")):
        return False
    return any(
        p.is_file() and ".cache/huggingface/download" not in str(p)
        for p in target.rglob("*")
    )


def main() -> int:
    seen = set()
    failed = []
    skipped = []

    for repo in REPOS:
        repo = repo.strip()
        if not repo or repo in seen:
            continue
        seen.add(repo)

        if repo in MANUAL_SKIP_REPOS:
            print(f"MANUAL_SKIP {repo}", flush=True)
            skipped.append(repo)
            continue

        target = target_for(repo)
        if appears_complete(target):
            print(f"SKIP {repo}: {target}", flush=True)
            skipped.append(repo)
            continue

        print(f"DOWNLOAD {repo} -> {target}", flush=True)
        try:
            path = snapshot_download(
                repo_id=repo,
                local_dir=str(target),
                max_workers=1,
                etag_timeout=60,
            )
            print(f"DONE {repo}: {path}", flush=True)
        except Exception as exc:
            print(f"FAILED {repo}: {type(exc).__name__}: {exc}", flush=True)
            failed.append((repo, type(exc).__name__, str(exc)))

    print("SUMMARY", flush=True)
    print(f"Skipped existing: {len(skipped)}", flush=True)
    print(f"Failed: {len(failed)}", flush=True)
    for repo, exc_type, message in failed:
        print(f"FAILED {repo}: {exc_type}: {message}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
