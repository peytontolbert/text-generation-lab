from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_SCRIPT = ROOT / "scripts" / "hf_snapshot_download_requested_lingbot_models.py"
NOHUP_LOG = Path("/arxiv/hf_snapshot_download_requested_lingbot_models.nohup.log")
PID_FILE = Path("/arxiv/hf_snapshot_download_requested_lingbot_models.pid")


def main() -> None:
    with NOHUP_LOG.open("ab", buffering=0) as out:
        proc = subprocess.Popen(
            [sys.executable, str(DOWNLOAD_SCRIPT)],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    PID_FILE.write_text(f"{proc.pid}\n", encoding="utf-8")
    print(proc.pid)


if __name__ == "__main__":
    main()
