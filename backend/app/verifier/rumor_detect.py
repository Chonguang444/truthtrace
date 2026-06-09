"""
谣言检测器 — 基于传播模式识别谣言特征
"""

from collections import Counter

from loguru import logger


class RumorDetector:
    """
    基于多维特征的谣言检测

    检测维度：
    1. 传播速度异常 — 短时间内爆发式传播
    2. 来源单一 — 缺乏独立来源验证
    3. 情感极化 — 内容引发极端情绪反应
    4. 来源匿名 — 发布者无认证/匿名
    5. 内容模式 — 含常见谣言模板特征
    6. 平台特征 — 特定平台上的异常传播模式
    """

    # 谣言常见模板特征词
    RUMOR_TEMPLATES = [
        "紧急通知", "速看", "刚曝光", "内部消息", "独家揭秘",
        "删前速看", "马上删除", "阅后即焚", "不能说的秘密",
        "惊天", "爆料", "内幕", "黑幕", "真相",
        "千万别", "警惕", "注意了", "所有人注意",
        "央视曝光", "央视报道",
        "扩散", "转给", "求扩散", "急转",
    ]

    # 可疑发布模式
    SUSPICIOUS_PATTERNS = [
        "转发功德", "不转不是",
        "群里都在传", "朋友发给我的",
        "据说", "据传", "网传", "有消息称",
    ]

    async def detect(self, event) -> dict:
        """
        检测事件是否为谣言

        Args:
            event: Event ORM 对象（含 sources 关系）

        Returns:
            {
                "score": 0-100 (谣言指数，越高越可疑),
                "risk_level": "high" | "medium" | "low",
                "flags": 触发的风险标记,
                "analysis": 分析说明
            }
        """
        sources = event.sources if hasattr(event, 'sources') else []
        title = event.title if hasattr(event, 'title') else ""

        flags = []
        risk_score = 0.0

        # 1. 检查标题/内容是否有谣言模板
        template_flags = self._check_templates(title)
        if template_flags:
            flags.extend(template_flags)
            risk_score += len(template_flags) * 8

        # 2. 检查内容是否有谣言模板
        if sources:
            all_content = " ".join([
                s.content or "" for s in sources
                if hasattr(s, 'content') and s.content
            ])
            content_flags = self._check_templates(all_content)
            if content_flags:
                flags.extend(content_flags)
                risk_score += len(content_flags) * 5

        # 3. 来源数量检测
        if len(sources) == 0:
            risk_score += 15
            flags.append({
                "type": "no_sources",
                "description": "没有可验证的数据源",
            })
        elif len(sources) == 1:
            risk_score += 20
            flags.append({
                "type": "single_source",
                "description": "仅有一个来源，缺乏独立验证",
            })
        elif len(sources) < 3:
            risk_score += 8
            flags.append({
                "type": "few_sources",
                "description": f"仅有 {len(sources)} 个来源",
            })

        # 4. 平台多样性检测
        if sources:
            platforms = Counter(
                s.platform.value if hasattr(s.platform, 'value') else "unknown"
                for s in sources
            )
            if len(platforms) == 1 and len(sources) >= 3:
                risk_score += 10
                flags.append({
                    "type": "single_platform",
                    "description": f"所有来源均来自同一平台: {list(platforms.keys())[0]}",
                })

            # 5. 检查匿名/无认证来源
            anonymous_count = sum(
                1 for s in sources
                if not (hasattr(s, 'author') and s.author)
            )
            if anonymous_count > len(sources) * 0.5:
                risk_score += 15
                flags.append({
                    "type": "anonymous_sources",
                    "description": f"{anonymous_count}/{len(sources)} 来源为匿名",
                })

        # 6. 传播速度异常检测
        if sources and len(sources) >= 3:
            speed_flag = self._check_spread_speed(sources)
            if speed_flag:
                flags.append(speed_flag)
                risk_score += 12

        # 7. 情感分析
        if sources:
            sentiment_flag = await self._check_sentiment_polarization(sources)
            if sentiment_flag:
                flags.append(sentiment_flag)
                risk_score += 8

        # 计算风险等级
        risk_score = min(100, risk_score)

        if risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "score": round(risk_score, 1),
            "risk_level": risk_level,
            "flags": flags,
            "analysis": self._generate_analysis(risk_score, risk_level, flags),
        }

    def _check_templates(self, text: str) -> list[dict]:
        """检测谣言模板特征"""
        if not text:
            return []

        flags = []
        for template in self.RUMOR_TEMPLATES:
            if template in text:
                flags.append({
                    "type": "rumor_template",
                    "pattern": template,
                    "description": f"包含可疑模式: 「{template}」",
                })

        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern in text:
                flags.append({
                    "type": "suspicious_pattern",
                    "pattern": pattern,
                    "description": f"包含可疑表述: 「{pattern}」",
                })

        return flags

    def _check_spread_speed(self, sources: list) -> dict | None:
        """
        检测传播速度是否异常

        如果大部分来源集中在很短时间内出现 → 可能是水军/机器转发
        """
        times = []
        for s in sources:
            if hasattr(s, 'published_at') and s.published_at is not None:
                times.append(s.published_at)

        if len(times) < 3:
            return None

        times.sort()
        time_span = (times[-1] - times[0]).total_seconds()

        # 如果 3+ 来源在 1 小时内出现 → 传播异常快
        if time_span <= 3600 and len(times) >= 3:
            return {
                "type": "rapid_spread",
                "description": f"{len(times)} 个来源在 {time_span/3600:.1f} 小时内密集出现",
            }

        # 如果 5+ 来源在 6 小时内出现
        if time_span <= 21600 and len(times) >= 5:
            return {
                "type": "fast_spread",
                "description": f"{len(times)} 个来源在 {time_span/3600:.1f} 小时内出现",
            }

        return None

    async def _check_sentiment_polarization(self, sources: list) -> dict | None:
        """
        检测情感极化

        谣言常常伴随着极端情绪（愤怒/恐惧）
        """
        # 检查是否有大量情感极化词汇
        polarizing_words = {
            "愤怒", "震惊", "恐惧", "害怕", "恶心",
            "令人发指", "触目惊心", "不可思议",
        }

        total_content = ""
        for s in sources:
            if hasattr(s, 'content') and s.content:
                total_content += s.content + " "

        extreme_count = sum(
            1 for word in polarizing_words if word in total_content
        )

        if extreme_count >= 3:
            return {
                "type": "emotional_polarization",
                "description": f"检测到 {extreme_count} 个情感极化词汇",
            }

        return None

    def _generate_analysis(
        self, score: float, risk_level: str, flags: list
    ) -> str:
        """生成分析说明"""
        if risk_level == "high":
            base = "该事件展现出高度谣言特征。"
        elif risk_level == "medium":
            base = "该事件有一定可疑特征，需进一步核实。"
        else:
            base = "未发现明显谣言特征，但仍建议多源验证。"

        reasons = [f["description"] for f in flags[:5]]
        if reasons:
            base += " 检测到：" + "；".join(reasons)

        return base
