#!/usr/bin/env python3
"""No-train overlap audit for Stage11718 sentencepiece C++ smoke packet."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_source_heldout_smoke_packet.json'
ROWS = ROOT / 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_smoke_rows.jsonl'
OUT_DIR = ROOT / 'runs/local/artifacts/stage11719_sentencepiece_cpp_no_train_overlap_audit'
SUMMARY = ROOT / 'runs/summaries/stage11719_sentencepiece_cpp_no_train_overlap_audit.json'
TRAIN_MARKERS = ('train', 'support', 'training', 'probe_request', 'finetune')
IGNORE = ('stage11718_sentencepiece_cpp_source_heldout_smoke_packet', 'stage11719_sentencepiece_cpp_no_train_overlap_audit')


def read_json(path: Path) -> dict[str, Any]:
    return json.load(open(path))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in open(path) if line.strip()]


def trainish_files() -> list[Path]:
    files=[]
    for p in ROOT.glob('runs/local/artifacts/**/*.jsonl'):
        s=str(p).lower()
        if any(i in s for i in IGNORE):
            continue
        if any(m in s for m in TRAIN_MARKERS):
            files.append(p)
    return sorted(files)


def rg_files(patterns: list[str]) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pat = OUT_DIR / 'sentencepiece_overlap_patterns.txt'
    pat.write_text('\n'.join(patterns)+'\n')
    proc = subprocess.run(['rg','-l','-F','-f',str(pat),'runs/local/artifacts','-g','*.jsonl'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode not in (0,1):
        raise RuntimeError(proc.stderr)
    return [ROOT / line for line in proc.stdout.splitlines() if line.strip()]


def classify(path: Path, line: str, row: dict[str, Any] | None) -> str:
    s=str(path).lower()
    if row:
        split=str(row.get('split','')).lower(); split_role=str(row.get('split_role','')).lower()
        if row.get('train_support_only') is True or split in {'train','train_support','support'} or split_role in {'train','train_support','support'}:
            return 'train_like_field'
        if split in {'strict_eval','validation','eval','heldout'} or split_role in {'strict_eval','validation','eval','heldout'}:
            return 'nontrain_like_field'
    if any(m in s for m in TRAIN_MARKERS):
        return 'train_like_path'
    return 'unknown_context'


def main() -> None:
    packet=read_json(PACKET); rows=read_rows(ROWS)
    OUT_DIR.mkdir(parents=True, exist_ok=True); SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    root_id=packet['root_id']; snapshot=packet['source_snapshot_id']
    source_paths=sorted({o['value'] for r in rows for o in r.get('opaque_options',[]) if isinstance(o.get('value'),str) and o['value'].startswith('src/')})
    # Strong identifiers and repo/source path strings. Repo-level hits are warnings; exact new root hits are blockers if train-like.
    patterns=[root_id, snapshot]
    candidate_files=rg_files(patterns)
    hits=[]; counts=Counter(); exact_new_root_train_hits=[]; repo_train_hits=[]; source_path_train_hits=[]
    for path in candidate_files:
        try: fh=open(path, encoding='utf-8', errors='replace')
        except OSError: continue
        with fh:
            for line_no,line in enumerate(fh,1):
                matched=[p for p in patterns if p in line]
                if not matched: continue
                try: row=json.loads(line)
                except Exception: row=None
                kind=classify(path,line,row); counts[kind]+=1
                hit={'path':str(path.relative_to(ROOT)),'line_no':line_no,'hit_kind':kind,'matched':matched[:8]}
                if row:
                    hit.update({'row_id':row.get('row_id'),'root_id':row.get('root_id'),'source_root_id':row.get('source_root_id'),'split':row.get('split'),'split_role':row.get('split_role'),'train_support_only':row.get('train_support_only')})
                hits.append(hit)
                if kind.startswith('train'):
                    if root_id in matched or snapshot in matched:
                        exact_new_root_train_hits.append(hit)
                    if 'sentencepiece' in matched:
                        repo_train_hits.append(hit)
                    if any(m in source_paths for m in matched):
                        source_path_train_hits.append(hit)
    status='pass_no_exact_new_root_train_overlap'
    blockers=[]; warnings=[]
    if exact_new_root_train_hits:
        status='reject_exact_new_root_train_overlap'
        blockers.append('exact_new_root_or_snapshot_seen_in_train_support')
    artifact={
        'stage':11719,
        'stage_name':'sentencepiece_cpp_no_train_overlap_audit',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'decision':status,
        'passed':not blockers,
        'root_id':root_id,
        'source_snapshot_id':snapshot,
        'patterns_checked':patterns,
        'warning_patterns_deferred': ['sentencepiece'] + source_paths,
        'candidate_files_from_rg':len(candidate_files),
        'hit_counts':dict(counts),
        'exact_new_root_train_hits':len(exact_new_root_train_hits),
        'repo_train_hits':len(repo_train_hits),
        'source_path_train_hits':len(source_path_train_hits),
        'blockers':blockers,
        'warnings':warnings,
        'claim_boundary':[
            'Passing this audit only proves the new Stage11718 root/snapshot was not found in train/support artifacts.',
            'Repo-family/source-path warning scans are deferred to avoid noisy broad-string hits; this stage checks exact new root and source snapshot blockers.',
            'Admission still requires Stage11714-style row preflight and explicit source_heldout_admissible derivation.'
        ],
        'outputs':{
            'artifact':'runs/local/artifacts/stage11719_sentencepiece_cpp_no_train_overlap_audit/sentencepiece_cpp_no_train_overlap_audit.json',
            'hits_jsonl':'runs/local/artifacts/stage11719_sentencepiece_cpp_no_train_overlap_audit/sentencepiece_cpp_overlap_hits.jsonl',
            'summary':'runs/summaries/stage11719_sentencepiece_cpp_no_train_overlap_audit.json'
        }
    }
    (OUT_DIR/'sentencepiece_cpp_no_train_overlap_audit.json').write_text(json.dumps(artifact,indent=2,sort_keys=True)+'\n')
    with (OUT_DIR/'sentencepiece_cpp_overlap_hits.jsonl').open('w') as fh:
        for h in hits:
            fh.write(json.dumps(h,sort_keys=True)+'\n')
    shutil.copyfile(OUT_DIR/'sentencepiece_cpp_no_train_overlap_audit.json', SUMMARY)
    print(json.dumps({'artifact':str(OUT_DIR/'sentencepiece_cpp_no_train_overlap_audit.json'),'summary':str(SUMMARY),'passed':artifact['passed'],'decision':status,'warnings':warnings},indent=2))


if __name__=='__main__': main()
