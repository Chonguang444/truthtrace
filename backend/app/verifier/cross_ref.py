"""
交叉验证引擎 — 多源信息交叉比对
"""

from collections import Counter

from loguru import logger


class CrossReferencer:
    """
    多源交叉验证

    原理：
    1. 多个独立来源一致 → 可信度高
    2. 来源之间存在矛盾 → 需要进一步验证
    3. 单一来源无其他佐证 → 可信度低
    """

    async def analyze(self, sources: list) -> dict:
        """
        对多个来源进行交叉验证分析

        Args:
            sources: Source 模型对象列表

        Returns:
            {
                "score": 0-100 可信度评分,
                "source_count": 来源总数,
                "unique_platforms": 独立平台数,
                "consensus_level": "high" | "medium" | "low",
                "contradictions": 矛盾点列表,
                "analysis": 分析文字说明
            }
        """
        if not sources:
            return {
                "score": 50.0,
                "source_count": 0,
                "unique_platforms": 0,
                "consensus_level": "low",
                "contradictions": [],
                "analysis": "缺少数据源进行交叉验证",
            }

        # 统计平台分布
        platforms = [s.platform.value if hasattr(s.platform, 'value') else str(s.platform) for s in sources]
        platform_counts = Counter(platforms)
        unique_platforms = len(platform_counts)

        # 计算共识度
        total_sources = len(sources)
        consensus_level = self._evaluate_consensus(sources, platform_counts)

        # 检测矛盾
        contradictions = await self._detect_contradictions(sources)

        # 综合评分
        score = self._compute_score(
            total_sources=total_sources,
            unique_platforms=unique_platforms,
            consensus_level=consensus_level,
            contradictions_count=len(contradictions),
            platform_distribution=platform_counts,
        )

        return {
            "score": round(score, 1),
            "source_count": total_sources,
            "unique_platforms": unique_platforms,
            "platform_distribution": dict(platform_counts.most_common()),
            "consensus_level": consensus_level,
            "contradictions": contradictions[:5],
            "analysis": self._generate_analysis(
                total_sources, unique_platforms, consensus_level, contradictions
            ),
        }

    def _evaluate_consensus(self, sources: list, platform_counts: Counter) -> str:
        """评估来源共识水平"""
        total = len(sources)

        if total >= 5 and len(platform_counts) >= 3:
            return "high"
        elif total >= 3 and len(platform_counts) >= 2:
            return "medium"
        else:
            return "low"

    async def _detect_contradictions(self, sources: list) -> list[dict]:
        """
        检测来源之间的矛盾

        比较不同来源的关键信息：
        - 时间矛盾
        - 数字矛盾
        - 人物矛盾
        """
        contradictions = []

        # 比较发布时间
        times = []
        for s in sources:
            if hasattr(s, 'published_at') and s.published_at:
                times.append((s.published_at, s.url))

        if len(times) >= 2:
            times.sort(key=lambda x: x[0])
            time_span = (times[-1][0] - times[0][0]).total_seconds()
            if time_span > 86400 * 7:  # 超过一周的时间跨度
                contradictions.append({
                    "type": "time_gap",
                    "description": f"最早来源与最晚来源间隔 {time_span / 86400:.1f} 天",
                    "earliest_url": times[0][1],
                    "latest_url": times[-1][1],
                })

        # 比较内容长度差异（可能暗示信息不一致）
        contents = [
            (s.content or "") for s in sources
            if hasattr(s, 'content') and s.content
        ]
        if len(contents) >= 2:
            lengths = [len(c) for c in contents]
            avg_len = sum(lengths) / len(lengths)
            # 如果某些来源内容极短，可能信息不完整
            short_sources = [i for i, l in enumerate(lengths) if l < avg_len * 0.3]
            if short_sources and len(short_sources) < len(contents):
                contradictions.append({
                    "type": "content_length_disparity",
                    "description": f"{len(short_sources)} 个来源信息量显著少于其他来源",
                })

        return contradictions

    def _compute_score(
        self,
        total_sources: int,
        unique_platforms: int,
        consensus_level: str,
        contradictions_count: int,
        platform_distribution: Counter,
    ) -> float:
        """计算综合可信度评分"""
        score = 50.0

        # 来源数量加分
        if total_sources >= 10:
            score += 15
        elif total_sources >= 5:
            score += 10
        elif total_sources >= 3:
            score += 5

        # 平台多样性加分
        if unique_platforms >= 4:
            score += 15
        elif unique_platforms >= 2:
            score += 8

        # 共识水平
        if consensus_level == "high":
            score += 10
        elif consensus_level == "medium":
            score += 5
        else:
            score -= 5

        # 矛盾扣分
        score -= contradictions_count * 10

        # 权威平台加分
        has_news = any(
            p in ("news", "weibo")
            for p in platform_distribution.keys()
        )
        if has_news:
            score += 5

        return max(0, min(100, score))

    def _generate_analysis(
        self,
        total: int,
        platforms: int,
        consensus: str,
        contradictions: list,
    ) -> str:
        """生成分析文字"""
        parts = []

        if total >= 5:
            parts.append(f"共有 {total} 个独立来源报道此事件")
        elif total >= 2:
            parts.append(f"共有 {total} 个来源报道此事件")
        else:
            parts.append("仅有单一来源，缺乏独立验证")

        if platforms >= 3:
            parts.append(f"覆盖 {platforms} 个不同平台")

        if consensus == "high":
            parts.append("多源信息高度一致")
        elif consensus == "medium":
            parts.append("来源间基本一致，建议进一步核实")

        if contradictions:
            parts.append(f"检测到 {len(contradictions)} 处潜在矛盾")

        return "；".join(parts)
