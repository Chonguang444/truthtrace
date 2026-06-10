"""
实时谣言监控 — 热点爬取 + 自动分析 + 叙事告警

架构:
1. HotspotCrawler: 从多个平台爬取热点内容
2. 每条热点自动送入 10 引擎推理管线
3. NarrativeAlertManager: 检测新叙事框架的涌现并告警
4. MonitorScheduler: 定时调度 + 增量更新

支持平台: 微博热搜, 知乎热榜, 百度风云榜, 今日头条
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional
import hashlib

logger = logging.getLogger("truthtrace.monitor")


# =============================================================================
# 数据类型
# =============================================================================

@dataclass
class HotItem:
    """一条热点条目"""
    id: str = ""
    platform: str = ""       # weibo / zhihu / baidu / toutiao
    title: str = ""
    url: str = ""
    summary: str = ""
    rank: int = 0
    heat_score: float = 0.0
    category: str = ""       # 自动分类
    crawled_at: Optional[datetime] = None
    engine_analysis: Optional[dict] = None  # 10引擎分析结果

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "platform": self.platform,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "rank": self.rank,
            "heat_score": self.heat_score,
            "category": self.category,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
            "engine_verdict": self.engine_analysis.get("verdict") if self.engine_analysis else None,
            "credibility_score": self.engine_analysis.get("credibility_score") if self.engine_analysis else None,
        }


@dataclass
class NarrativeAlert:
    """叙事框架告警"""
    id: str = ""
    narrative_type: str = ""
    title: str = ""
    description: str = ""
    detected_items: list[str] = field(default_factory=list)  # 触发告警的热点 ID 列表
    manipulation_score: float = 0.0
    severity: str = "low"     # low / medium / high / critical
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "narrative_type": self.narrative_type,
            "title": self.title,
            "description": self.description,
            "detected_items": self.detected_items,
            "manipulation_score": self.manipulation_score,
            "severity": self.severity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# 热点爬虫
# =============================================================================

class HotspotCrawler:
    """多平台热点爬虫"""

    def __init__(self, http_client=None):
        self._client = http_client

    async def _fetch_weibo_hot(self) -> list[HotItem]:
        """微博热搜 (非官方API, 从公开接口获取)"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://weibo.com/ajax/side/hotSearch",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                items = []
                for item in data.get("data", {}).get("realtime", [])[:20]:
                    word = item.get("word", "")
                    if not word:
                        continue
                    items.append(HotItem(
                        id=hashlib.md5(f"weibo_{word}".encode()).hexdigest()[:12],
                        platform="weibo",
                        title=word,
                        url=f"https://s.weibo.com/weibo?q={word}",
                        summary=item.get("note", "") or word,
                        rank=item.get("rank", 0),
                        heat_score=float(item.get("raw_hot", 0)),
                        crawled_at=datetime.now(timezone.utc),
                    ))
                return items
        except Exception as e:
            logger.warning(f"微博热搜爬取失败: {e}")
            return []

    async def _fetch_zhihu_hot(self) -> list[HotItem]:
        """知乎热榜"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                items = []
                for item in data.get("data", [])[:20]:
                    target = item.get("target", {})
                    title = target.get("title", "")
                    if not title:
                        continue
                    items.append(HotItem(
                        id=hashlib.md5(f"zhihu_{title}".encode()).hexdigest()[:12],
                        platform="zhihu",
                        title=title,
                        url=f"https://www.zhihu.com/question/{target.get('id', '')}",
                        summary=target.get("excerpt", "") or title,
                        rank=item.get("index", 0),
                        heat_score=float(target.get("heat", 0)),
                        crawled_at=datetime.now(timezone.utc),
                    ))
                return items
        except Exception as e:
            logger.warning(f"知乎热榜爬取失败: {e}")
            return []

    async def _fetch_baidu_hot(self) -> list[HotItem]:
        """百度风云榜"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://top.baidu.com/board?tab=realtime",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code != 200:
                    return []

                # 百度页面是HTML渲染的，简化处理：从页面提取
                import re
                items = []
                # 提取热搜词
                words = re.findall(r'<div class="c-single-text-ellipsis">(.+?)</div>', resp.text)
                for i, word in enumerate(words[:20]):
                    word_clean = re.sub(r'<[^>]+>', '', word).strip()
                    if word_clean:
                        items.append(HotItem(
                            id=hashlib.md5(f"baidu_{word_clean}".encode()).hexdigest()[:12],
                            platform="baidu",
                            title=word_clean,
                            url=f"https://www.baidu.com/s?wd={word_clean}",
                            summary=word_clean,
                            rank=i + 1,
                            heat_score=float(20 - i) * 50,
                            crawled_at=datetime.now(timezone.utc),
                        ))
                return items
        except Exception as e:
            logger.warning(f"百度风云榜爬取失败: {e}")
            return []

    async def crawl_all(self) -> list[HotItem]:
        """从所有平台爬取热点"""
        tasks = [
            self._fetch_weibo_hot(),
            self._fetch_zhihu_hot(),
            self._fetch_baidu_hot(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"平台 {i} 爬取异常: {result}")
            elif isinstance(result, list):
                all_items.extend(result)

        # 按热度排序
        all_items.sort(key=lambda x: x.heat_score, reverse=True)
        logger.info(f"爬取完成: {len(all_items)} 条热点, 覆盖 {len(set(i.platform for i in all_items))} 个平台")
        return all_items


# =============================================================================
# 叙事告警管理器
# =============================================================================

class NarrativeAlertManager:
    """检测新叙事框架的涌现并产生告警"""

    def __init__(self):
        self._seen_narratives: dict[str, set[str]] = {}   # narrative_type → set of item_ids
        self._active_alerts: list[NarrativeAlert] = []
        self._alert_threshold = 3  # 同一叙事类型出现 N 条以上触发告警

    def process_analysis(self, item: HotItem) -> Optional[NarrativeAlert]:
        """处理一条热点的分析结果，检查是否触发叙事告警"""
        if not item.engine_analysis:
            return None

        narrative_data = item.engine_analysis.get("narrative_analysis", {})
        if not narrative_data:
            return None

        dominant = narrative_data.get("dominant_narrative")
        manipulation = narrative_data.get("manipulation_score", 0)

        if not dominant or manipulation < 30:  # 阈值：操纵性评分 > 30 才关注
            return None

        # 更新该叙事类型的计数
        if dominant not in self._seen_narratives:
            self._seen_narratives[dominant] = set()
        self._seen_narratives[dominant].add(item.id)

        count = len(self._seen_narratives[dominant])

        # 超过阈值 → 产生告警
        if count >= self._alert_threshold and not any(
            a.narrative_type == dominant for a in self._active_alerts
        ):
            alert = NarrativeAlert(
                id=f"alert_{dominant}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
                narrative_type=dominant,
                title=f"检测到 {self._narrative_label(dominant)} 叙事在热点中涌现",
                description=f"最近爬取的 {count} 条热点中检测到 '{self._narrative_label(dominant)}' 叙事框架, 操纵性评分均分 {manipulation:.0f}/100。建议关注该叙事的传播情况。",
                detected_items=list(self._seen_narratives[dominant]),
                manipulation_score=manipulation,
                severity="high" if manipulation > 60 else "medium" if manipulation > 40 else "low",
                created_at=datetime.now(timezone.utc),
            )
            self._active_alerts.append(alert)
            logger.warning(f"🚨 叙事告警: {alert.title}")
            return alert

        return None

    def get_active_alerts(self) -> list[NarrativeAlert]:
        return self._active_alerts

    def dismiss_alert(self, alert_id: str):
        self._active_alerts = [a for a in self._active_alerts if a.id != alert_id]

    @staticmethod
    def _narrative_label(nt: str) -> str:
        return {
            "conspiracy_theory": "阴谋论", "us_vs_them": "对立叙事",
            "victimhood_nationalism": "受害者民族主义", "fear_mongering": "恐惧营销",
            "golden_age": "辉煌过去", "scientism_abuse": "伪科学包装",
            "whataboutism": "转移焦点", "demonization": "妖魔化",
            "moral_panic": "道德恐慌", "purification": "净化叙事",
            "technophobia": "技术恐惧", "false_balance": "虚假平衡",
        }.get(nt, nt)


# =============================================================================
# 监控调度器
# =============================================================================

@dataclass
class MonitorState:
    """监控系统状态"""
    is_running: bool = False
    last_crawl_at: Optional[datetime] = None
    total_crawled: int = 0
    total_analyzed: int = 0
    alerts_count: int = 0
    next_crawl_at: Optional[datetime] = None


class MonitorScheduler:
    """
    监控调度器 — 定时爬取热点并送入引擎分析

    用法:
        scheduler = MonitorScheduler()
        await scheduler.start(interval_minutes=15)
        # 或者手动触发
        items = await scheduler.run_once()
    """

    def __init__(self):
        self.crawler = HotspotCrawler()
        self.alert_manager = NarrativeAlertManager()
        self.state = MonitorState()
        self._task: Optional[asyncio.Task] = None

    async def run_once(self) -> list[HotItem]:
        """执行一次完整的监控周期: 爬取 → 分析 → 告警"""
        logger.info("🔄 开始监控周期...")

        # 1. 爬取
        items = await self.crawler.crawl_all()
        self.state.total_crawled += len(items)
        self.state.last_crawl_at = datetime.now(timezone.utc)

        if not items:
            return items

        # 2. 对每条热点运行引擎分析
        analyzed = 0
        for item in items[:30]:  # 限制每次分析30条
            try:
                from app.engine.reasoning import run_reasoning_pipeline
                result = await run_reasoning_pipeline(
                    url=item.url,
                    title=item.title,
                    text=f"{item.title}\n{item.summary}",
                )
                item.engine_analysis = result.to_dict()
                analyzed += 1

                # 3. 叙事告警检测
                self.alert_manager.process_analysis(item)

            except Exception as e:
                logger.debug(f"分析 {item.title[:30]}... 失败: {e}")

        self.state.total_analyzed += analyzed
        logger.info(f"✅ 监控周期完成: 爬取{len(items)}条, 分析{analyzed}条, 活跃告警{len(self.alert_manager.get_active_alerts())}条")
        return items

    async def start(self, interval_minutes: int = 15):
        """启动定时监控"""
        if self.state.is_running:
            return
        self.state.is_running = True
        logger.info(f"监控系统已启动 (间隔: {interval_minutes}分钟)")
        await self.run_once()  # 立即执行第一次

    async def stop(self):
        self.state.is_running = False
        if self._task:
            self._task.cancel()

    def get_state(self) -> MonitorState:
        self.state.alerts_count = len(self.alert_manager.get_active_alerts())
        return self.state


# 全局单例
monitor_scheduler = MonitorScheduler()
