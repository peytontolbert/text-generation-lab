#!/usr/bin/env python3
from __future__ import annotations
import json,math,re,time,hashlib
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
SPANS=Path('/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl')
OUT_DIR=ROOT/'runs/local/artifacts/stage8666_repo_span_bm25_retrieval_baseline'
SUMMARY=ROOT/'runs/summaries/stage8666_repo_span_bm25_retrieval_baseline.json'
DOC=ROOT/'docs/REPO_SPAN_BM25_RETRIEVAL_BASELINE_STAGE8666.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
TOKEN=re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')
STOP={'the','and','for','with','from','import','return','self','class','def','this','that','true','false','none','path','file'}
def toks(s:str)->list[str]: return [t.lower() for t in TOKEN.findall(s or '') if t.lower() not in STOP and len(t)<40]
def load_docs(limit:int=1200):
 docs=[]
 with SPANS.open() as f:
  for line in f:
   if not line.strip(): continue
   r=json.loads(line); text=r.get('text') or ''; sid=r.get('span_id') or ''; src=r.get('source_id') or ''; meta=r.get('meta') or {}; corpus=meta.get('corpus','')
   tt=toks(text)
   if len(tt)<8: continue
   # Query uses code/content tokens, not source_id, to prevent metadata-only from trivially winning.
   q=[]
   for tok,c in Counter(tt[:220]).most_common(16):
    if tok not in q: q.append(tok)
   docs.append({'doc_id':sid,'source_id':src,'corpus':corpus,'text':text[:2000],'query':' '.join(q),'text_tokens':tt,'meta_tokens':toks(' '.join([sid,src,corpus]))})
   if len(docs)>=limit: break
 return docs
class BM25:
 def __init__(self, docs_tokens:list[list[str]], k1=1.5,b=.75):
  self.docs=docs_tokens; self.k1=k1; self.b=b; self.n=len(docs_tokens); self.avgdl=sum(len(d) for d in docs_tokens)/max(1,self.n)
  df=Counter()
  for d in docs_tokens: df.update(set(d))
  self.idf={t:math.log(1+(self.n-v+0.5)/(v+0.5)) for t,v in df.items()}
  self.tf=[Counter(d) for d in docs_tokens]
 def score(self, q:list[str], i:int)->float:
  dl=len(self.docs[i]); tf=self.tf[i]; s=0.0
  for t in q:
   if t not in self.idf: continue
   f=tf.get(t,0); denom=f+self.k1*(1-self.b+self.b*dl/max(1e-9,self.avgdl)); s+=self.idf[t]*(f*(self.k1+1)/denom) if denom else 0
  return s
 def rank(self, query:str, k:int=5):
  q=toks(query); scores=[(self.score(q,i),i) for i in range(self.n)]; scores.sort(reverse=True)
  return scores[:k]
def eval_bm25(model:BM25, docs:list[dict[str,Any]], field:str):
 top1=top5=0; rr=0.0; examples=[]
 for i,d in enumerate(docs):
  ranks=model.rank(d['query'],5); ids=[j for _,j in ranks]
  if ids and ids[0]==i: top1+=1
  if i in ids: top5+=1; rr+=1/(ids.index(i)+1)
  if len(examples)<8: examples.append({'query':d['query'],'target':d['doc_id'],'top_ids':[docs[j]['doc_id'] for j in ids],field+'_top1':ids[0]==i if ids else False})
 n=len(docs); return {'top1_exact':top1/n,'top5_recall':top5/n,'mrr_at5':rr/n,'examples':examples}
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 docs=load_docs()
 failures=[]
 if len(docs)<100: failures.append('too_few_docs')
 text_model=BM25([d['text_tokens'] for d in docs])
 meta_model=BM25([d['meta_tokens'] for d in docs])
 blank_model=BM25([[] for _ in docs])
 text=eval_bm25(text_model,docs,'text')
 meta=eval_bm25(meta_model,docs,'meta')
 blank=eval_bm25(blank_model,docs,'blank')
 if text['top5_recall']<=0.50: failures.append('text_bm25_top5_too_low')
 if meta['top5_recall']>=text['top5_recall']: failures.append('metadata_only_beats_retrieval')
 if blank['top5_recall']>=0.05: failures.append('evidence_removed_does_not_drop')
 card={'stage':8666,'stage_name':'stage8666_repo_span_bm25_retrieval_baseline','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'docs':len(docs),'bm25_top1_exact':text['top1_exact'],'bm25_top5_recall':text['top5_recall'],'bm25_mrr_at5':text['mrr_at5'],'metadata_only_top1_exact':meta['top1_exact'],'metadata_only_top5_recall':meta['top5_recall'],'evidence_removed_top5_recall':blank['top5_recall'],'retrieval_lift_top5_over_metadata':text['top5_recall']-meta['top5_recall'],'retrieval_lift_top5_over_removed':text['top5_recall']-blank['top5_recall'],'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'samples':{'text_examples':text['examples'],'metadata_examples':meta['examples']},'decision':'BM25 text evidence baseline beats metadata-only and evidence-removed baselines.' if not failures else 'Retrieval baseline failed; do not train retrieval-dependent rows.','next_best_step':'Build graph/symbol candidate retrieval cards using this baseline shape, then add dense/rerank once source rows are normalized.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'repo_span_bm25_retrieval_baseline_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 with (OUT_DIR/'retrieval_docs_sample.jsonl').open('w') as f:
  for d in docs[:80]: f.write(json.dumps({k:d[k] for k in ['doc_id','source_id','corpus','query']},sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8666 Repo Span BM25 Retrieval Baseline\n\n'+f"Passed: `{card['passed']}`\n\n- Docs: `{len(docs)}`\n- BM25 top1 exact: `{text['top1_exact']:.3f}`\n- BM25 top5 recall: `{text['top5_recall']:.3f}`\n- Metadata-only top5 recall: `{meta['top5_recall']:.3f}`\n- Evidence-removed top5 recall: `{blank['top5_recall']:.3f}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
