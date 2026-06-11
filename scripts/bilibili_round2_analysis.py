"""B站第二轮深度分析 — 谣言/溯源/网络信息"""
import asyncio, httpx, json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# ====== Step 1: Search ======
async def search(kw):
    from app.crawler.video_platforms import BilibiliCrawler
    c = BilibiliCrawler()
    async with httpx.AsyncClient(timeout=30) as cl:
        await c._fetch_wbi_keys(cl)
    params = c._wbi_sign({'search_type':'video','keyword':kw,'order':'click','duration':0,'page':1})
    async with httpx.AsyncClient(timeout=30) as cl:
        r = await cl.get('https://api.bilibili.com/x/web-interface/wbi/search/type',params=params,
            headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'})
    results = r.json().get('data',{}).get('result') or []
    return [{'bvid':v.get('bvid',''),'title':v.get('title','').replace('<em class="keyword">','').replace('</em>',''),
             'author':v.get('author',''),'play':v.get('play',0),'duration':v.get('duration',''),
             'description':v.get('description',''),'tag':v.get('tag','')} for v in results]

# ====== Step 2: Metadata + Comments ======
async def get_full(bvid):
    async with httpx.AsyncClient(timeout=20) as c:
        hdrs = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer':f'https://www.bilibili.com/video/{bvid}','Origin':'https://www.bilibili.com'}
        r = await c.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',headers=hdrs)
        if r.json().get('code')!=0: return None
        dd = r.json()['data']
        aid = dd.get('aid')
        info = {'bvid':bvid,'aid':aid,'title':dd.get('title',''),'desc':dd.get('desc',''),
            'duration':dd.get('duration',0),'owner':dd.get('owner',{}).get('name',''),
            'stat':dd.get('stat',{}),'cid':(dd.get('pages',[{}])[0] or {}).get('cid',0)}
        # comments - try multiple endpoints (P1 fix for API changes)
        replies = []
        for ep in [f'/x/v2/reply?type=1&oid={aid}&pn=1&ps=40&sort=1',
                   f'/x/v2/reply/main?type=1&oid={aid}&ps=40&sort=1',
                   f'/x/v2/reply/wbi/main?type=1&oid={aid}&mode=3&ps=40']:
            r2 = await c.get(f'https://api.bilibili.com{ep}', headers=hdrs)
            d2 = r2.json()
            if d2.get('code') == 0:
                rps = d2.get('data',{}).get('replies') or []
                if rps:
                    replies = rps
                    break
        info['comments'] = [{'content':rp.get('content',{}).get('message',''),'like':rp.get('like',0),
            'member':rp.get('member',{}).get('uname','')} for rp in replies]
        return info

# ====== Step 3: Transcribe ======
async def transcribe_one(bvid, cid, model):
    from app.crawler.video_transcriber import _extract_bilibili_audio
    async with httpx.AsyncClient(timeout=120) as c:
        wav_path, title, err = await _extract_bilibili_audio(c, bvid, cid)
        if err: return {'bvid':bvid,'error':err}
    segs, parts = [], []
    seg_iter, info = model.transcribe(wav_path, language='zh', beam_size=5, vad_filter=True)
    for seg in seg_iter:
        parts.append(seg.text.strip())
        segs.append({'start':round(seg.start,1),'end':round(seg.end,1),'text':seg.text.strip()})
    import os; os.unlink(wav_path)
    return {'bvid':bvid,'title':title,'full_text':'\n'.join(parts),'word_count':len('\n'.join(parts)),
            'duration_seconds':info.duration,'language':info.language,'segments':segs[:50]}

# ====== Step 4: 23-engine analysis ======
async def analyze(title, text, url):
    from app.engine.reasoning import run_reasoning_pipeline
    r = await run_reasoning_pipeline(url=url, title=title, text=text[:8000])
    return r.to_dict()

# ====== Main ======
async def main():
    print("="*50)
    print("B站 Round 2 — 谣言/溯源/网络信息 深度分析")
    print("="*50)

    # 1. Search
    keywords = ['谣言 溯源', '网络信息 真假', '谣言 传播', '辟谣 真相', '信息 可信度']
    all_v = []; seen = set()
    for kw in keywords:
        vs = await search(kw)
        for v in vs:
            if v['bvid'] not in seen:
                seen.add(v['bvid']); all_v.append(v)
    all_v.sort(key=lambda v:v['play'], reverse=True)
    top = all_v[:8]
    print(f"[1/4] Search: {len(all_v)} unique, analyzing TOP {len(top)}")

    # 2. Metadata + comments
    full_data = []
    for v in top:
        info = await get_full(v['bvid'])
        if info: full_data.append(info)
    tc = sum(len(f.get('comments',[])) for f in full_data)
    print(f"[2/4] Metadata+Comments: {len(full_data)} videos, {tc} comments")

    # 3. Transcribe
    print("[3/4] Transcribing audio (Whisper tiny)...")
    from faster_whisper import WhisperModel
    model = WhisperModel('tiny', device='cpu', compute_type='int8')
    transcripts = []
    for i,f in enumerate(full_data):
        print(f"  [{i+1}/{len(full_data)}] {f['bvid']}...", end=' ', flush=True)
        t0 = time.time()
        tx = await transcribe_one(f['bvid'], f['cid'], model)
        if 'error' in tx:
            print(f"SKIP: {tx['error']}")
            tx['full_text'] = f.get('desc','') or f['title']
            tx['word_count'] = len(tx['full_text'])
        else:
            print(f"{tx['word_count']} chars in {time.time()-t0:.1f}s")
        transcripts.append(tx)

    # 4. Engine analysis
    print("[4/4] 23-engine analysis...")
    analyses = []
    for i,(f,tx) in enumerate(zip(full_data, transcripts)):
        text = tx.get('full_text','') or f.get('desc','') or f['title']
        print(f"  [{i+1}/{len(full_data)}] {f['bvid']} ({len(text)} chars)...", end=' ', flush=True)
        t0 = time.time()
        a = await analyze(f['title'], text, f"https://www.bilibili.com/video/{f['bvid']}")
        print(f"{a.get('credibility_score',50):.0f}/{a.get('verdict','?')} ({time.time()-t0:.1f}s)")
        a['_transcript_chars'] = tx.get('word_count',0)
        a['_is_debunking'] = a.get('is_debunking', False)
        a['_debunk_adjustment'] = a.get('debunking_adjustment', 0)
        analyses.append(a)

    # Save all
    with open('bilibili_round2_full.json','w',encoding='utf-8') as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)
    with open('bilibili_round2_transcripts.json','w',encoding='utf-8') as f:
        json.dump(transcripts, f, ensure_ascii=False, indent=2)
    with open('bilibili_round2_analyses.json','w',encoding='utf-8') as f:
        json.dump(analyses, f, ensure_ascii=False, indent=2)

    scores_str = ', '.join(str(round(a.get('credibility_score',50))) for a in analyses)
    print(f'\nDone: {len(full_data)} videos, {sum(t.get("word_count",0) for t in transcripts)} transcribed chars')
    print(f'Scores: {scores_str}')

if __name__ == '__main__':
    asyncio.run(main())
