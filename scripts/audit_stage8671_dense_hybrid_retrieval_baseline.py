#!/usr/bin/env python3
from __future__ import annotations
import json, math, re, time
from collections import Counter
from pathlib import Path
from typing import Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
ROOT=Path(__file__).resolve().parents[1]
SPANS=Path('/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl')
OUT_DIR=ROOT/'runs/local/artifacts/stage8671_dense_hybrid_retrieval_baseline'
SUMMARY=ROOT/'runs/summaries/stage8671_dense_hybrid_retrieval_baseline.json'
DOC=ROOT/'docs/DENSE_HYBRID_RETRIEVAL_BASELINE_STAGE8671.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
TOKEN=re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')
STOP={'the','and','for','with','from','import','return','self','class','def','this','that','true','false','none','path','file'}
def toks(s:str)->list[str]: return [t.lower() for t in TOKEN.findall(s or '') if t.lower() not in STOP and len(t)<40]
def load_docs(limit=1000):
 docs=[]
 with SPANS.open() as f:
  for line in f:
   if not line.strip(): continue
   r=json.loads(line); text=r.get('text') or ''; tt=toks(text)
   if len(tt)<8: continue
   q=' '.join([x for x,_ in Counter(tt[:240]).most_common(18)])
   docs.append({'doc_id':r.get('span_id') or '', 'source_id':r.get('source_id') or '', 'corpus':(r.get('meta') or {}).get('corpus',''), 'text':text[:3000], 'query':q, 'tokens':tt})
   if len(docs)>=limit: break
 return docs
class BM25:
 def __init__(self, docs_tokens,k1=1.5,b=.75):
  self.docs=docs_tokens; self.k1=k1; self.b=b; self.n=len(docs_tokens); self.avgdl=sum(len(d) for d in docs_tokens)/max(1,self.n)
  df=Counter()
  for d in docs_tokens: df.update(set(d))
  self.idf={t:math.log(1+(self.n-v+0.5)/(v+0.5)) for t,v in df.items()}; self.tf=[Counter(d) for d in docs_tokens]
 def score(self,q,i):
  dl=len(self.docs[i]); tf=self.tf[i]; s=0.0
  for t in toks(q):
   if t not in self.idf: continue
   f=tf.get(t,0); denom=f+self.k1*(1-self.b+self.b*dl/max(self.avgdl,1e-9)); s+=self.idf[t]*(f*(self.k1+1)/denom) if denom else 0
  return s
 def rank(self,q,k=10):
  scores=[(self.score(q,i),i) for i in range(self.n)]; scores.sort(reverse=True); return scores[:k]
def dense_vectors(docs):
 texts=[d['text'] for d in docs]
 queries=[d['query'] for d in docs]
 backend='tfidf_svd'
 try:
  from sentence_transformers import SentenceTransformer
  model_path='/data/tiny-self-improve/data/models/sentence_transformers/models--sentence-transformers--all-MiniLM-L6-v2'
  if Path(model_path).exists():
   model=SentenceTransformer(model_path, local_files_only=True)
  else:
   model=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', local_files_only=True)
  doc_vec=model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
  qry_vec=model.encode(queries, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
  return np.asarray(doc_vec), np.asarray(qry_vec), 'sentence_transformers_all_minilm_l6_v2_local'
 except Exception as e:
  backend='tfidf_svd_fallback:'+type(e).__name__
  vec=TfidfVectorizer(max_features=12000, ngram_range=(1,2), min_df=1)
  x=vec.fit_transform(texts+queries)
  ncomp=min(256, x.shape[0]-1, x.shape[1]-1)
  svd=TruncatedSVD(n_components=max(2,ncomp), random_state=17)
  z=normalize(svd.fit_transform(x))
  return z[:len(docs)], z[len(docs):], backend
def eval_rank(rank_fn, docs):
 top1=top5=top10=0; rr=0.0
 for i,d in enumerate(docs):
  ids=rank_fn(i,d['query'],10)
  if ids and ids[0]==i: top1+=1
  if i in ids[:5]: top5+=1
  if i in ids[:10]: top10+=1; rr+=1/(ids.index(i)+1)
 n=len(docs); return {'top1':top1/n,'top5':top5/n,'top10':top10/n,'mrr10':rr/n}
def rrf(list_a,list_b,k=60):
 scores={}
 for rank,idx in enumerate(list_a): scores[idx]=scores.get(idx,0)+1/(k+rank+1)
 for rank,idx in enumerate(list_b): scores[idx]=scores.get(idx,0)+1/(k+rank+1)
 return [idx for idx,_ in sorted(scores.items(), key=lambda kv:kv[1], reverse=True)]
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 docs=load_docs(); failures=[]
 bm25=BM25([d['tokens'] for d in docs])
 doc_vec,qry_vec,backend=dense_vectors(docs); sims=qry_vec @ doc_vec.T
 def bm25_rank(i,q,k=10): return [j for _,j in bm25.rank(q,k)]
 def dense_rank(i,q,k=10): return list(np.argsort(-sims[i])[:k])
 def hybrid_rank(i,q,k=10): return rrf(bm25_rank(i,q,20), dense_rank(i,q,20))[:k]
 bm=eval_rank(lambda i,q,k:bm25_rank(i,q,k),docs); de=eval_rank(lambda i,q,k:dense_rank(i,q,k),docs); hy=eval_rank(lambda i,q,k:hybrid_rank(i,q,k),docs)
 if hy['top5'] < bm['top5'] - 0.02: failures.append('hybrid_regresses_bm25_top5')
 if de['top5'] < 0.40: failures.append('dense_top5_too_low')
 samples=[]
 for i,d in enumerate(docs[:8]): samples.append({'query':d['query'],'target':d['doc_id'],'bm25_top':[docs[j]['doc_id'] for j in bm25_rank(i,d['query'],5)],'dense_top':[docs[j]['doc_id'] for j in dense_rank(i,d['query'],5)],'hybrid_top':[docs[j]['doc_id'] for j in hybrid_rank(i,d['query'],5)]})
 card={'stage':8671,'stage_name':'stage8671_dense_hybrid_retrieval_baseline','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'docs':len(docs),'dense_backend':backend,'bm25_top1':bm['top1'],'bm25_top5':bm['top5'],'bm25_mrr10':bm['mrr10'],'dense_top1':de['top1'],'dense_top5':de['top5'],'dense_mrr10':de['mrr10'],'hybrid_rrf_top1':hy['top1'],'hybrid_rrf_top5':hy['top5'],'hybrid_rrf_mrr10':hy['mrr10'],'hybrid_lift_top5_over_bm25':hy['top5']-bm['top5'],'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'samples':samples,'decision':'Dense/hybrid retrieval baseline is available for future candidate retrieval cards.' if not failures else 'Dense/hybrid retrieval baseline failed; use BM25-only until fixed.','next_best_step':'Use BM25+dense+RRF cards when building source-backed graph/symbol rows; add reranker only after locked benchmark pack is versioned.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'dense_hybrid_retrieval_baseline_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8671 Dense Hybrid Retrieval Baseline\n\n'+f"Passed: `{card['passed']}`\n\n- Backend: `{backend}`\n- Docs: `{len(docs)}`\n- BM25 top5: `{bm['top5']:.3f}`\n- Dense top5: `{de['top5']:.3f}`\n- Hybrid RRF top5: `{hy['top5']:.3f}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 print(json.dumps(card,indent=2,sort_keys=True)); raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
