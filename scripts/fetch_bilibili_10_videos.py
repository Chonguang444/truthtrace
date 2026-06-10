"""
用 TruthTrace 已有的 BilibiliCrawler 采集 10 条视频的完整内容：
- 元数据（标题/简介/标签）
- 字幕/CC 文本（视频口语内容）
- 热门评论

输出每个视频的 to_text() 合并文本到 JSON 文件。
"""
import asyncio
import json
import sys
import os

# 添加 backend 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.crawler.video_platforms import BilibiliCrawler

TARGET_VIDEOS = [
    "BV1BzvczMEoz",  # 韩国申遗溯源 - 492万播放
    "BV1HM1yYLEwu",  # 鉴定网络热门营销号谣言 - 124万播放
    "BV1L5411c7TX",  # 溯源的基本思路
    "BV1s6yABZEze",  # 造谣式辟谣的造谣UP
    "BV1J1D8YHEhA",  # 高达谣言辟谣与溯源
    "BV18EER6WEyT",  # 图片溯源-地域黑图片出处
    "BV1na4y1e7NZ",  # 正确辨别网络谣言
    "BV1B7411H72P",  # 八名散布谣言者被依法查处
    "BV1G5EX6JEBz",  # 直升机偷器官辟谣
    "BV1XB4y1F7xu",  # 什么是谣言？
]


async def fetch_all():
    crawler = BilibiliCrawler()
    results = {}

    for bvid in TARGET_VIDEOS:
        url = f"https://www.bilibili.com/video/{bvid}"
        print(f"\n{'='*60}")
        print(f"采集: {bvid}")
        print(f"{'='*60}")

        try:
            info = await crawler.fetch(url)
            if info:
                # 提取字幕行数（视频实际口语内容）
                subtitle_lines = []
                for s in info.subtitles:
                    subtitle_lines.extend([l["content"] for l in s.get("lines", [])])

                results[bvid] = {
                    "title": info.title,
                    "author": info.author_name,
                    "play": info.view_count,
                    "duration": info.duration_seconds,
                    "description": info.description,
                    "tags": info.tags,
                    "subtitle_count": len(info.subtitles),
                    "subtitle_lines": len(subtitle_lines),
                    "subtitle_text": info.subtitle_text,  # 视频口语内容！
                    "comments": [
                        {"author": c["author"], "text": c["text"], "likes": c["likes"]}
                        for c in info.top_comments
                    ],
                    "comments_count": len(info.top_comments),
                    "danmaku_count": info.danmaku_count,
                    "full_text": info.to_text(),  # 合并全文
                }

                print(f"  标题: {info.title[:60]}")
                print(f"  播放: {info.view_count:,}")
                print(f"  字幕轨: {len(info.subtitles)} | 字幕行: {len(subtitle_lines)} | 字幕文本长: {len(info.subtitle_text)}")
                print(f"  评论数: {len(info.top_comments)}/{info.comment_count}")
                if subtitle_lines:
                    print(f"  字幕前3行: {subtitle_lines[:3]}")
            else:
                results[bvid] = {"error": "fetch returned None"}
                print(f"  ❌ 采集失败")

        except Exception as e:
            results[bvid] = {"error": str(e)}
            print(f"  ❌ 异常: {e}")

    # 输出到 JSON
    output_path = os.path.join(os.path.dirname(__file__), "bilibili_10_videos_content.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 汇总
    print(f"\n{'='*60}")
    print(f"采集完成! 输出: {output_path}")
    subtitle_videos = [bvid for bvid, r in results.items() if r.get("subtitle_lines", 0) > 0]
    no_subtitle = [bvid for bvid, r in results.items() if r.get("subtitle_lines", 0) == 0 and "error" not in r]
    errors = [bvid for bvid, r in results.items() if "error" in r]
    print(f"有字幕: {len(subtitle_videos)}个 ({subtitle_videos})")
    print(f"无字幕: {len(no_subtitle)}个 ({no_subtitle})")
    print(f"失败: {len(errors)}个 ({errors})")


if __name__ == "__main__":
    asyncio.run(fetch_all())
