"""B站视频音频转录"""
import asyncio, json, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

RESULTS_FILE = 'bilibili_transcriptions.json'

async def main():
    with open('bilibili_full_data.json','r',encoding='utf-8') as f:
        videos = json.load(f)

    from app.crawler.video_transcriber import _extract_bilibili_audio
    import httpx

    # Load existing results
    results = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE,'r',encoding='utf-8') as f:
            results = json.load(f)
    done_bvids = {r['bvid'] for r in results}

    # Load Whisper once
    from faster_whisper import WhisperModel
    model = WhisperModel('tiny', device='cpu', compute_type='int8')

    for i, v in enumerate(videos[:6]):
        bvid = v['bvid']
        if bvid in done_bvids:
            print(f"[{i+1}/6] {bvid} SKIP (already done)")
            continue

        cid = v.get('cid', 0)
        title = v.get('title','')
        n = i+1

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                t0 = time.time()
                wav_path, api_title, err = await _extract_bilibili_audio(client, bvid, cid)
                if err:
                    print(f"[{n}/6] {bvid} AUDIO FAIL: {err}")
                    results.append({'bvid':bvid,'error':err})
                    continue

            segments_list = []
            parts = []
            seg_iter, info = model.transcribe(wav_path, language='zh', beam_size=5, vad_filter=True)
            for seg in seg_iter:
                parts.append(seg.text.strip())
                segments_list.append({'start':round(seg.start,1), 'end':round(seg.end,1), 'text':seg.text.strip()})

            full_text = '\n'.join(parts)
            elapsed = time.time() - t0
            print(f"[{n}/6] {bvid}: {len(full_text)} chars, {info.duration:.0f}s, {elapsed:.1f}s")

            results.append({
                'bvid':bvid,'title':api_title or title,
                'full_text':full_text,'word_count':len(full_text),
                'duration_seconds':info.duration,'language':info.language,
                'segments':segments_list[:50],'method':'whisper-tiny',
            })

            # Save after each success
            with open(RESULTS_FILE,'w',encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            if os.path.exists(wav_path):
                os.unlink(wav_path)

        except Exception as e:
            print(f"[{n}/6] {bvid} ERROR: {type(e).__name__}")
            results.append({'bvid':bvid,'title':title,'error':str(e)[:100]})

    total = sum(r.get('word_count',0) for r in results)
    print(f"Done: {len(results)} videos, {total} chars")

if __name__ == '__main__':
    asyncio.run(main())
