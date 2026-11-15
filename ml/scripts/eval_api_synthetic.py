"""Quality of the live API on the synthetic test questions (hybrid mode)."""
import json, math, os, sys, time, uuid, urllib.request
label=sys.argv[1]
qs=[json.loads(l) for l in open("data/eval/synthetic/queries.jsonl",encoding="utf-8")]
rel={}
for l in open("data/eval/synthetic/qrels.jsonl",encoding="utf-8"):
    r=json.loads(l); rel[r["query_id"]]=r["article_id"]
qs=[q for q in qs if q.get("split")=="test"]
ok=set(json.load(open("data/eval/labeling/synthetic_review_summary.json",encoding="utf-8"))["ok_query_ids"])
hit1=mrr=rec=ndcg=0; lat=[]; deg=0; n=0; h_n=h_hit1=h_ndcg=0
for q in qs:
    body=json.dumps({"query":q["text"],"lang":q["lang"],"top_k":10}).encode()
    t=time.time()
    d=json.load(urllib.request.urlopen(urllib.request.Request(os.environ.get("QEVAL_URL","http://localhost:8080")+"/api/v1/search",data=body,headers={"Content-Type":"application/json","X-Session-Id":str(uuid.uuid4())}),timeout=60))
    lat.append((time.time()-t)*1000); n+=1; deg+=bool(d.get("degraded"))
    ids=[r["article"]["article_id"] for r in d["results"]]
    if rel[q["query_id"]] in ids:
        k=ids.index(rel[q["query_id"]])+1; rec+=1; mrr+=1/k; ndcg+=1/math.log2(k+1); hit1+=k==1
        if q["query_id"] in ok: h_hit1+=k==1; h_ndcg+=1/math.log2(k+1)
    h_n+=q["query_id"] in ok
lat.sort()
out={"config":label,"queries":n,"degraded":deg,"hit@1":round(hit1/n,3),"mrr@10":round(mrr/n,3),"ndcg@10":round(ndcg/n,3),"recall@10":round(rec/n,3),"human_ok_n":h_n,"human_ok_hit@1":round(h_hit1/max(h_n,1),3),"human_ok_ndcg@10":round(h_ndcg/max(h_n,1),3),"p50_ms":round(lat[n//2]),"p95_ms":round(lat[int(n*0.95)])}
print(json.dumps(out)); open(sys.argv[2],"a").write(json.dumps(out)+"\n")
