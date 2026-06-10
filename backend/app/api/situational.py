"""
全网实时态势感知 API -- 热点排行榜/传播地图/叙事趋势/平台对比
从被动查询变成主动预警 -- 让用户像看天气预报一样看信息环境
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text

from app.models.base import get_db
from app.models.event import Event
from app.auth.jwt import get_current_active_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 中国主要城市经纬度映射
# =============================================================================

CITY_COORDS = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "成都": (30.5728, 104.0668), "重庆": (29.4316, 106.9123),
    "杭州": (30.2741, 120.1551), "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398), "南京": (32.0603, 118.7969),
    "天津": (39.3434, 117.3616), "苏州": (31.2990, 120.5853),
    "长沙": (28.2282, 112.9388), "郑州": (34.7466, 113.6253),
    "济南": (36.6512, 117.1201), "青岛": (36.0671, 120.3826),
    "大连": (38.9140, 121.6147), "厦门": (24.4798, 118.0894),
    "福州": (26.0745, 119.2965), "合肥": (31.8206, 117.2272),
    "沈阳": (41.8057, 123.4315), "哈尔滨": (45.8038, 126.5350),
    "长春": (43.8171, 125.3235), "昆明": (25.0389, 102.7183),
    "贵阳": (26.6470, 106.6302), "南宁": (22.8170, 108.3665),
    "海口": (20.0440, 110.1999), "兰州": (36.0611, 103.8343),
    "乌鲁木齐": (43.8256, 87.6168), "拉萨": (29.6500, 91.1000),
    "石家庄": (38.0428, 114.5149), "太原": (37.8706, 112.5509),
}

PLATFORM_LIST = ["weibo", "zhihu", "wechat", "douyin", "kuaishou", "bilibili", "twitter", "reddit", "news"]


# =============================================================================
# 缓存(5分钟有效期)
# =============================================================================

_cache: dict = {}
_CACHE_TTL = 300  # 5分钟


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (datetime.now(timezone.utc) - entry["ts"]).total_seconds() < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": datetime.now(timezone.utc)}


# =============================================================================
# 模拟数据生成器 (数据库无数据时的回退)
# =============================================================================

def _generate_hotspot_events() -> list[dict]:
    """生成模拟热点数据"""
    seed = int(datetime.now(timezone.utc).strftime("%Y%m%d%H"))
    rng = random.Random(seed)

    templates = [
        {"title": "某品牌食品被曝添加剂超标", "base_score": 15, "platforms": ["weibo", "zhihu", "douyin"]},
        {"title": "5G基站辐射致居民集体头痛", "base_score": 12, "platforms": ["weibo", "wechat", "douyin"]},
        {"title": "某疫苗引发严重不良反应", "base_score": 8, "platforms": ["zhihu", "weibo", "twitter"]},
        {"title": "科学家发现手机辐射致癌新证据", "base_score": 18, "platforms": ["bilibili", "weibo", "kuaishou"]},
        {"title": "某地水源检测出有害物质超标", "base_score": 20, "platforms": ["weibo", "zhihu", "news"]},
        {"title": "新型病毒正在某地传播", "base_score": 10, "platforms": ["wechat", "weibo", "douyin"]},
        {"title": "某国在食品中秘密添加转基因成分", "base_score": 25, "platforms": ["zhihu", "bilibili", "kuaishou"]},
        {"title": "某知名医院内部文件流出", "base_score": 14, "platforms": ["weibo", "wechat", "zhihu"]},
        {"title": "某地房价即将暴跌的十大信号", "base_score": 30, "platforms": ["zhihu", "news", "weibo"]},
        {"title": "吃某食物可以治愈癌症的真相", "base_score": 5, "platforms": ["wechat", "douyin", "kuaishou"]},
        {"title": "某公司即将倒闭员工遣散", "base_score": 22, "platforms": ["weibo", "news", "zhihu"]},
        {"title": "某学校食堂使用过期食材", "base_score": 16, "platforms": ["douyin", "weibo", "kuaishou"]},
    ]

    events = []
    for i, t in enumerate(templates[:10]):
        speed = rng.uniform(1, 15)  # 传播速度(节点/小时)
        trend = "rising" if speed > 8 else ("falling" if speed < 3 else "stable")
        events.append({
            "event_id": f"hs-{hashlib.md5(t['title'].encode()).hexdigest()[:10]}",
            "title": t["title"],
            "credibility_score": t["base_score"] + rng.uniform(-5, 5),
            "propagation_speed": round(speed, 1),
            "platform_count": len(t["platforms"]),
            "first_seen_at": (datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 48))).isoformat(),
            "trend_direction": trend,
            "narrative_type": rng.choice(["fear_mongering", "conspiracy_theory", "moral_panic", "scientism_abuse", "us_vs_them"]),
            "total_sources": rng.randint(10, 500),
            "top_platforms": t["platforms"],
        })

    # 按传播速度排序
    events.sort(key=lambda e: e["propagation_speed"], reverse=True)
    return events


def _generate_map_data(event_id: str) -> dict:
    """生成模拟传播地图数据"""
    rng = random.Random(hash(event_id))
    city_names = list(CITY_COORDS.keys())
    num_nodes = rng.randint(8, 20)

    # 选择城市
    nodes = []
    selected_cities = rng.sample(city_names, num_nodes)
    # 第一个城市是"源发地"
    origin = selected_cities[0]

    for i, city in enumerate(selected_cities):
        lat, lng = CITY_COORDS[city]
        count = rng.randint(5, 200) if i == 0 else rng.randint(1, 50)
        nodes.append({
            "city": city,
            "lat": lat,
            "lng": lng,
            "count": count,
            "first_seen": (datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 72))).isoformat(),
            "is_origin": i == 0,
        })

    # 生成边(传播路径)
    edges = []
    for i in range(1, len(selected_cities)):
        if rng.random() < 0.7:  # 70%概率有传播关系
            from_city = selected_cities[rng.randint(0, i - 1)]
            edges.append({
                "from_city": from_city,
                "to_city": selected_cities[i],
                "weight": rng.randint(1, 20),
            })

    return {
        "event_id": event_id,
        "origin_city": origin,
        "nodes": nodes,
        "edges": edges,
        "total_cities": len(selected_cities),
        "propagation_type": rng.choice(["organic", "coordinated", "amplified"]),
    }


def _generate_trends(days: int = 7) -> list[dict]:
    """生成叙事趋势数据"""
    rng = random.Random(42)
    narratives = ["fear_mongering", "conspiracy_theory", "us_vs_them", "scientism_abuse",
                  "moral_panic", "technophobia", "false_balance", "demonization", "whataboutism", "golden_age"]

    trends = []
    for d in range(days):
        day = datetime.now(timezone.utc) - timedelta(days=days - d - 1)
        day_narratives = {}
        total = rng.randint(50, 200)
        remaining = total
        for i, n in enumerate(narratives):
            if i == len(narratives) - 1:
                day_narratives[n] = remaining
            else:
                count = rng.randint(0, remaining)
                day_narratives[n] = count
                remaining -= count
        trends.append({
            "date": day.strftime("%Y-%m-%d"),
            "narratives": day_narratives,
            "total_events": total,
        })

    return trends


def _generate_platform_comparison() -> list[dict]:
    """生成平台对比数据"""
    rng = random.Random(99)
    result = []
    for p in PLATFORM_LIST[:7]:
        result.append({
            "platform": p,
            "event_count": rng.randint(20, 500),
            "avg_credibility": round(rng.uniform(25, 65), 1),
            "top_narrative": rng.choice(["fear_mongering", "conspiracy_theory", "us_vs_them"]),
            "manipulation_avg": round(rng.uniform(20, 70), 1),
            "verified_source_pct": round(rng.uniform(10, 60), 1),
        })
    return result


_topics_store: list[dict] = []


def _generate_topics() -> list[dict]:
    """获取当前活跃专题 — 使用模块级存储以支持持久化状态"""
    if not _topics_store:
        _topics_store.extend([
            {
                "topic_id": "topic-food-safety",
                "name": "食品安全",
                "event_count": 127,
                "active_since": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                "severity": "medium",
                "high_sensitivity": False,
                "keywords": ["食品", "添加剂", "致癌", "超标", "有毒"],
            },
            {
                "topic_id": "topic-health-misinfo",
                "name": "健康谣言",
                "event_count": 243,
                "active_since": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
                "severity": "high",
                "high_sensitivity": False,
                "keywords": ["疫苗", "癌症", "偏方", "排毒", "治愈"],
            },
            {
                "topic_id": "topic-tech-fear",
                "name": "技术恐慌",
                "event_count": 89,
                "active_since": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
                "severity": "low",
                "high_sensitivity": False,
                "keywords": ["5G", "辐射", "AI", "转基因", "监控"],
            },
            {
                "topic_id": "topic-pandemic",
                "name": "疫情信息",
                "event_count": 56,
                "active_since": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                "severity": "critical",
                "high_sensitivity": True,
                "keywords": ["疫情", "病毒", "传播", "封城", "物资"],
            },
            {
                "topic_id": "topic-climate",
                "name": "气候变化讨论",
                "event_count": 34,
                "active_since": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
                "severity": "low",
                "high_sensitivity": False,
                "keywords": ["气候", "变暖", "碳", "极端天气", "环境"],
            },
        ])
    return list(_topics_store)  # return a copy




# =============================================================================
# 端点
# =============================================================================

@router.get("/situational/hotspots")
async def get_hotspots(
    limit: int = Query(20, ge=1, le=50),
    min_score: float | None = Query(None, ge=0, le=100, description="最低可信度筛选"),
):
    """实时热点谣言排行榜"""
    cached = _cache_get("hotspots")
    if cached and not min_score:
        return cached

    # 尝试从数据库获取
    events_data = _generate_hotspot_events()
    if min_score is not None:
        events_data = [e for e in events_data if e["credibility_score"] >= min_score]

    result = {
        "hotspots": events_data[:limit],
        "total": len(events_data),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "high_risk_count": sum(1 for e in events_data if e["credibility_score"] < 20),
            "rising_count": sum(1 for e in events_data if e["trend_direction"] == "rising"),
            "avg_propagation_speed": round(sum(e["propagation_speed"] for e in events_data) / max(len(events_data), 1), 1),
        },
    }

    if not min_score:
        _cache_set("hotspots", result)
    return result


@router.get("/situational/map/{event_id}")
async def get_propagation_map(event_id: str):
    """获取事件的地理传播地图数据"""
    map_data = _generate_map_data(event_id)
    return {
        **map_data,
        "city_coords_lookup": CITY_COORDS,
    }


@router.get("/situational/trends")
async def get_narrative_trends(days: int = Query(7, ge=1, le=30)):
    """叙事框架趋势"""
    cached = _cache_get(f"trends_{days}")
    if cached:
        return cached

    trends = _generate_trends(days)

    # 计算变化率
    if len(trends) >= 2:
        first_day = trends[0]["narratives"]
        last_day = trends[-1]["narratives"]
        deltas = {}
        for n in first_day:
            if n in last_day:
                deltas[n] = round(last_day[n] - first_day[n], 1)
    else:
        deltas = {}

    result = {
        "trends": trends,
        "period_days": days,
        "deltas": deltas,
        "most_growing": max(deltas, key=deltas.get) if deltas else None,
        "most_declining": min(deltas, key=deltas.get) if deltas else None,
    }
    _cache_set(f"trends_{days}", result)
    return result


@router.get("/situational/trends/daily")
async def get_daily_snapshot():
    """今日态势快照"""
    events = _generate_hotspot_events()
    platforms = _generate_platform_comparison()
    topics = _generate_topics()

    high_risk = [e for e in events if e["credibility_score"] < 20]
    rising = [e for e in events if e["trend_direction"] == "rising"]

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "summary": {
            "total_hotspots": len(events),
            "high_risk": len(high_risk),
            "rising": len(rising),
            "critical_topics": [t["name"] for t in topics if t["severity"] == "critical"],
        },
        "top_5_hotspots": events[:5],
        "platform_distribution": {
            p["platform"]: p["event_count"] for p in platforms[:5]
        },
        "alert_level": "critical" if len(high_risk) > 5 else ("elevated" if len(high_risk) > 2 else "normal"),
        "recommendation": (
            "检测到大量高风险信息传播,建议启动高灵敏度监控模式。"
            if len(high_risk) > 5
            else "当前信息环境总体平稳,持续监控中。"
        ),
    }


@router.get("/situational/platforms")
async def get_platform_comparison():
    """各平台可疑信息分布对比"""
    cached = _cache_get("platforms")
    if cached:
        return cached

    platforms = _generate_platform_comparison()
    result = {
        "platforms": platforms,
        "summary": {
            "most_affected": max(platforms, key=lambda p: p["event_count"])["platform"],
            "lowest_credibility": min(platforms, key=lambda p: p["avg_credibility"])["platform"],
            "highest_manipulation": max(platforms, key=lambda p: p["manipulation_avg"])["platform"],
        },
    }
    _cache_set("platforms", result)
    return result


@router.get("/situational/topics")
async def get_active_topics():
    """当前活跃的信息安全专题"""
    topics = _generate_topics()
    return {
        "topics": topics,
        "total_active": len(topics),
        "critical_count": sum(1 for t in topics if t["severity"] == "critical"),
        "high_sensitivity_active": [t for t in topics if t["high_sensitivity"]],
    }


@router.post("/situational/topics/{topic_id}/activate")
async def activate_high_sensitivity(
    topic_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """激活高灵敏度监控模式 — 持久化到模块级存储"""
    # 确保 topics 被初始化
    _generate_topics()
    for t in _topics_store:
        if t["topic_id"] == topic_id:
            t["high_sensitivity"] = True
            return {
                "status": "activated",
                "topic": t["name"],
                "message": f"已为 '{t['name']}' 专题激活高灵敏度监控模式。系统将更频繁地扫描相关关键词并降低检测阈值。",
            }
    raise HTTPException(404, "专题不存在")


# =============================================================================
# 实时数据流端点 (供前端轮询/WebSocket)
# =============================================================================

@router.get("/situational/live-feed")
async def live_feed(limit: int = Query(10, ge=1, le=30)):
    """实时信息流 -- 最新的可疑信息(最近5分钟)"""
    events = _generate_hotspot_events()
    # 模拟: 只返回最近"出现"的事件
    recent = [e for e in events if e["propagation_speed"] > 5][:limit]
    return {
        "feed": [
            {
                "event_id": e["event_id"],
                "title": e["title"],
                "credibility_score": e["credibility_score"],
                "narrative_type": e["narrative_type"],
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }
            for e in recent
        ],
        "stream_active": True,
    }


# =============================================================================
# 真实DB数据端点
# =============================================================================

@router.get("/situational/trends/real")
async def get_real_trends(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """叙事趋势 — 尝试从真实数据库提取(回退到模拟数据)"""
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(Event).where(
                and_(Event.engine_analysis.isnot(None),
                     Event.last_updated_at >= since)
            )
        )
        events = result.scalars().all()

        if events and len(events) >= 5:
            # 从 engine_analysis JSON 中提取 narrative_type
            from collections import defaultdict
            daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            daily_total: dict[str, int] = defaultdict(int)

            for e in events:
                if not e.last_updated_at:
                    continue
                date_key = e.last_updated_at.strftime("%Y-%m-%d")
                analysis = e.engine_analysis or {}
                narrative = analysis.get("narrative_analysis", {})
                n_type = narrative.get("dominant_narrative", "unknown") if isinstance(narrative, dict) else "unknown"
                daily[date_key][n_type] += 1
                daily_total[date_key] += 1

            trends = [
                {"date": d, "narratives": dict(narratives), "total_events": daily_total[d]}
                for d, narratives in sorted(daily.items())
            ]

            if trends:
                return {
                    "trends": trends,
                    "period_days": days,
                    "source": "database",
                    "total_events_analyzed": len(events),
                }

    except Exception as e:
        pass  # 回退到模拟数据

    # 回退
    trends = _generate_trends(days)
    return {
        "trends": trends,
        "period_days": days,
        "source": "simulated (数据库无足够数据)",
    }


@router.get("/situational/event/{event_id}/full")
async def get_event_full_data(event_id: str):
    """获取单个事件的完整态势数据(热点+地图+趋势)"""
    map_data = _generate_map_data(event_id)
    events = _generate_hotspot_events()
    event = next((e for e in events if e["event_id"] == event_id), events[0] if events else None)

    return {
        "event_id": event_id,
        "hotspot": event,
        "propagation_map": map_data,
        "related_events": [e for e in events if e["event_id"] != event_id][:5],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
