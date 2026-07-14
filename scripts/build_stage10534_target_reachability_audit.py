#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10534
NAME = "stage10534_target_reachability_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "target_reachability_audit.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

REQUEST_10530 = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe_request/leak_clean_root_based_multitarget_probe_request.json"
REQUEST_10531 = ROOT / "runs/local/artifacts/stage10531_long_target_cap_corrected_probe_request/long_target_cap_corrected_probe_request.json"
TRAIN_MANIFEST = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe_request/leak_clean_root_based_multitarget_probe_manifest.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10528_cleaned_heldout_anticheat_successor/strict_eval_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tokenizer_lengths(rows_path: Path, split_filter: str | None) -> list[dict[str, Any]]:
    script = """
import json, sys
from pathlib import Path
ROOT=Path('/data/agentkernel-seq2seq-text-lab')
sys.path.insert(0, str(ROOT))
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
rows=[json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines() if x.strip()]
split_filter = None if sys.argv[2] == '__ALL__' else sys.argv[2]
tok=AgentKernelBPETokenizer(ROOT/'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json', ROOT/'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json')
out=[]
for r in rows:
    if split_filter is not None and str(r.get('split') or '') != split_filter:
        continue
    text=str(r.get('target_text') or '')
    clean=[i for i in tok.encode(text, max_length=4096) if i not in {tok.pad_id, tok.bos_id, tok.eos_id}]
    out.append({'row_id': str(r.get('row_id') or ''), 'target_subtype': str(r.get('target_subtype') or ''), 'language_family': str(r.get('language_family') or ''), 'token_len': len(clean)})
print(json.dumps(out))
"""
    arg_split = split_filter if split_filter is not None else "__ALL__"
    result = subprocess.run(
        ["conda", "run", "-n", "trellis", "python", "-c", script, str(rows_path), arg_split],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout.strip())


def summarize(length_rows: list[dict[str, Any]], cap: int) -> dict[str, Any]:
    by_subtype: dict[str, list[int]] = defaultdict(list)
    for row in length_rows:
        by_subtype[str(row["target_subtype"])].append(int(row["token_len"]))

    def block(vals: list[int]) -> dict[str, Any]:
        vals = sorted(vals)
        if not vals:
            return {"rows": 0}
        idx = lambda p: vals[min(len(vals) - 1, int((len(vals) - 1) * p))]
        return {
            "rows": len(vals),
            "p50": idx(0.5),
            "p90": idx(0.9),
            "p95": idx(0.95),
            "max": vals[-1],
            "gt_cap": sum(1 for v in vals if v > cap),
        }

    return {key: block(vals) for key, vals in sorted(by_subtype.items())}


def main() -> None:
    request_10530 = load_json(REQUEST_10530)
    request_10531 = load_json(REQUEST_10531)
    strict_lengths = tokenizer_lengths(STRICT_ROWS, None)
    train_lengths = tokenizer_lengths(TRAIN_MANIFEST, "train")

    cap_10530 = int((request_10530.get("command") or [])[((request_10530.get("command") or []).index("--max-decoder-tokens") + 1)] if "--max-decoder-tokens" in (request_10530.get("command") or []) else 256)
    cap_10531 = int((request_10531.get("command") or [])[((request_10531.get("command") or []).index("--max-decoder-tokens") + 1)] if "--max-decoder-tokens" in (request_10531.get("command") or []) else 1024)

    strict_over_10530 = sum(1 for row in strict_lengths if int(row["token_len"]) > cap_10530)
    strict_over_10531 = sum(1 for row in strict_lengths if int(row["token_len"]) > cap_10531)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": strict_over_10531 == 0,
        "claim_scope": [
            "Tokenizer-level target reachability audit for the leak-clean manifest and cleaned strict heldout slice.",
            "Compares the old 256-token decoder cap against the corrected 1024-token cap.",
            "This is a structural audit, not a model-quality result.",
        ],
        "decoder_caps": {
            "stage10530_max_decoder_tokens": cap_10530,
            "stage10531_max_decoder_tokens": cap_10531,
        },
        "strict_reachability": {
            "rows": len(strict_lengths),
            "rows_over_stage10530_cap": strict_over_10530,
            "rows_over_stage10531_cap": strict_over_10531,
            "by_target_subtype": {
                "stage10530_cap": summarize(strict_lengths, cap_10530),
                "stage10531_cap": summarize(strict_lengths, cap_10531),
            },
        },
        "train_reachability": {
            "rows": len(train_lengths),
            "by_target_subtype": {
                "stage10530_cap": summarize(train_lengths, cap_10530),
                "stage10531_cap": summarize(train_lengths, cap_10531),
            },
        },
        "next_best_step": (
            "Use stage10531 rather than stage10530 for any heldout comparison claim, because the corrected decoder cap makes all strict targets reachable. "
            "After the run finishes, execute stage10532 and stage10533."
        ),
    }
    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
