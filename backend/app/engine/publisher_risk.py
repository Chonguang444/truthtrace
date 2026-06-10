"""
发布者风险画像系统 — 第13号引擎

对标抖音"AI求真"的账号画像功能:
  从发布者维度评估信息可信度。
  不只看内容，还看"谁发的"。

六维画像:
  1. 账号年龄 — 新号发布争议内容的可信度低
  2. 历史准确率 — 过去发布的内容被证实的比例
  3. 领域专注度 — 是否在某领域有持续专业输出
  4. 行为规律 — 发布频率/时间是否呈现机器人模式
  5. 跨平台关联 — 是否在多个平台同步推送相同内容
  6. 传播动机 — 是否有商业/政治利益支撑

核心理念:
  - 不判断人，评估行为的风险模式
  - 每个维度可独立配置权重
  - "不确定" → 中性50分，不给虚假信心
"""

from __future__ import annotations
import re
import math
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.publisher_risk")


@dataclass
class PublisherProfile:
    """发布者完整画像"""
    username: str = ""
    user_id: str = ""
    platform: str = ""
    # 六维评分
    account_age_score: float = 50.0       # 账号年龄评分
    history_accuracy_score: float = 50.0  # 历史准确率评分
    domain_expertise_score: float = 50.0  # 领域专注度评分
    behavior_pattern_score: float = 50.0  # 行为规律评分
    cross_platform_score: float = 50.0    # 跨平台关联评分
    motivation_score: float = 50.0        # 传播动机评分
    # 综合
    overall_risk: float = 50.0            # 综合风险 0-100 (越高越可信)
    risk_factors: list[str] = field(default_factory=list)
    confidence_factors: list[str] = field(default_factory=list)
    # 元数据
    account_age_days: int = 0
    total_posts: int = 0
    verified_posts: int = 0
    disputed_posts: int = 0
    verification_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "username": self.username, "user_id": self.user_id, "platform": self.platform,
            "scores": {
                "account_age": round(self.account_age_score, 1),
                "history_accuracy": round(self.history_accuracy_score, 1),
                "domain_expertise": round(self.domain_expertise_score, 1),
                "behavior_pattern": round(self.behavior_pattern_score, 1),
                "cross_platform": round(self.cross_platform_score, 1),
                "motivation": round(self.motivation_score, 1),
            },
            "overall_risk": round(self.overall_risk, 1),
            "risk_level": "high" if self.overall_risk < 35 else ("elevated" if self.overall_risk < 50 else ("moderate" if self.overall_risk < 65 else "low")),
            "risk_factors": self.risk_factors,
            "confidence_factors": self.confidence_factors,
            "account_age_days": self.account_age_days,
            "total_posts": self.total_posts,
            "verification_rate": round(self.verification_rate, 2),
        }


# =============================================================================
# 1. 账号年龄分析
# =============================================================================

def _analyze_account_age(created_at: str | None, min_reliable_days: int = 90) -> tuple[float, int, list[str]]:
    """
    分析账号年龄 → 评分

    年龄越大越可信，但不是线性的：
    - <7天: 极高风险 (10分)
    - 7-30天: 高风险 (25分)
    - 30-90天: 中度风险 (40分)
    - 90-365天: 较可靠 (60分)
    - 1-3年: 可靠 (75分)
    - >3年: 很可靠 (90分)
    """
    if not created_at:
        return 50.0, 0, ["无法获取账号创建时间"]

    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days

        if days < 7:
            return 10.0, days, [f"账号注册仅 {days} 天 — 新号发布争议信息，可信度极低"]
        elif days < 30:
            return 25.0, days, [f"账号注册 {days} 天 — 一个月内新号"]
        elif days < 90:
            return 40.0, days, [f"账号注册 {days} 天 — 不足3个月"]
        elif days < 365:
            return 60.0, days, []
        elif days < 1095:
            return 75.0, days, []
        else:
            return 90.0, days, []

    except (ValueError, TypeError):
        return 50.0, 0, ["无法解析账号创建时间"]


# =============================================================================
# 2. 历史准确率分析
# =============================================================================

def _analyze_history(verified: int, disputed: int, total: int) -> tuple[float, str]:
    if total < 5:
        return 50.0, f"历史发帖仅 {total} 条，数据不足以评估准确率"
    rate = verified / total
    if rate >= 0.8:
        return 90.0, f"历史 {total} 条发布中 {verified} 条被证实为准确（{rate:.0%}），可靠性高"
    elif rate >= 0.6:
        return 70.0, f"历史准确率 {rate:.0%}，大部分信息可靠"
    elif rate >= 0.4:
        return 50.0, f"历史准确率 {rate:.0%}，时好时坏"
    else:
        return 25.0, f"历史准确率仅 {rate:.0%}（{disputed} 条被质疑），可信度低"


# =============================================================================
# 3. 领域专注度分析
# =============================================================================

def _analyze_domain_expertise(claimed_expertise: str, content_keywords: list[str]) -> tuple[float, str]:
    """
    分析账号是否在声称的专业领域有持续输出。
    如果声称"食品安全专家"但过去大量发娱乐内容 → 虚假专业人设。
    """
    if not claimed_expertise:
        return 50.0, "未声明专业领域"

    domain_maps = {
        "medicine": ["疾病", "治疗", "症状", "药物", "疫苗", "医院", "临床", "患者", "手术", "诊断"],
        "food_safety": ["食品", "添加剂", "安全", "标准", "GB", "检测", "营养", "饮食"],
        "data_science": ["数据", "统计", "算法", "模型", "分析", "实验", "样本"],
        "law": ["法律", "法条", "法规", "判决", "律师", "合同", "权利"],
        "journalism": ["采访", "报道", "调查", "新闻", "媒体", "记者"],
    }

    domain_kws = domain_maps.get(claimed_expertise, [])
    if not domain_kws:
        return 50.0, f"声明的领域 '{claimed_expertise}' 不在已知知识体系中"

    if not content_keywords:
        return 45.0, f"无法获取账号历史关键词，无法验证 '{claimed_expertise}' 领域的专业度"

    match_count = sum(1 for kw in domain_kws if kw in " ".join(content_keywords))
    match_rate = match_count / max(1, len(content_keywords))

    if match_rate > 0.3:
        return 80.0, f"关键词 {match_count}/{len(content_keywords)} 与自称的 '{claimed_expertise}' 领域一致"
    elif match_rate > 0.1:
        return 60.0, f"部分关键词与领域一致，但专注度不够高"
    else:
        return 30.0, f"声称 '{claimed_expertise}' 专家但历史内容与该领域几乎无关 — 可疑"


# =============================================================================
# 4. 行为规律分析 (机器人检测)
# =============================================================================

def _analyze_behavior(avg_posts_per_day: float, post_times: list[str] | None,
                       interaction_ratio: float | None) -> tuple[float, list[str]]:
    risks = []
    score = 50.0

    # 高频率发帖 (>20条/天 → 机器人特征)
    if avg_posts_per_day > 20:
        score -= 20
        risks.append(f"日均发帖 {avg_posts_per_day:.0f} 条 — 远超正常用户，疑似机器人")
    elif avg_posts_per_day > 10:
        score -= 10
        risks.append(f"日均发帖 {avg_posts_per_day:.0f} 条 — 频率偏高")

    # 精确整点发布时间
    if post_times:
        on_the_hour = sum(1 for t in post_times if t.endswith(":00") or t.endswith(":30"))
        if len(post_times) >= 5 and on_the_hour / len(post_times) > 0.6:
            score -= 15
            risks.append(f"{on_the_hour}/{len(post_times)} 次发帖恰好在整点/半点 — 定时发布机器人特征")

    # 互动率异常 (高转发低评论)
    if interaction_ratio is not None:
        if interaction_ratio > 10:  # 转发/评论 > 10:1
            score -= 10
            risks.append(f"转发/评论比例异常 ({interaction_ratio:.1f}:1) — 机器人转发网络特征")

    return max(10, min(90, score)), risks


# =============================================================================
# 5. 动机分析
# =============================================================================

def _analyze_motivation(content_text: str, profile_bio: str) -> tuple[float, list[str]]:
    risks = []
    score = 50.0

    combined = f"{content_text} {profile_bio}".lower()

    # 商业动机
    commercial_kws = ["购买", "下单", "优惠", "限时", "加微信", "咨询热线", "点击链接",
                      "免费领取", "名额有限", "前100名", "扫码", "课程", "课程费"]
    if sum(1 for kw in commercial_kws if kw in combined) >= 3:
        score -= 20
        risks.append("内容包含明显的商业推广模式 — 可能为利益驱动传播")

    # 政治/意识形态动机
    political_kws = ["不转不是", "中国人必转", "紧急通知", "中央最新", "高层震惊",
                     "终于发声", "彻底摊牌", "背后真相", "绝不妥协"]
    if sum(1 for kw in political_kws if kw in combined) >= 3:
        score -= 15
        risks.append("内容呈现典型的煽动性政治传播模式")

    # 健康/恐惧操纵
    fear_kws = ["速看", "马上被删", "再不看就来不及", "震惊", "可怕", "恐怖",
                "千万别", "通知家人", "扩散", "紧急扩散"]
    if sum(1 for kw in fear_kws if kw in combined) >= 4:
        score -= 15
        risks.append("内容高密度使用恐惧/紧迫性操纵手法 — 典型的谣言传播模式")

    return max(10, min(90, score)), risks


# =============================================================================
# 主分析器
# =============================================================================

class PublisherRiskAnalyzer:
    """发布者风险画像分析器"""

    def analyze(self,
                username: str = "",
                user_id: str = "",
                platform: str = "",
                created_at: str | None = None,
                bio: str = "",
                claimed_expertise: str = "",
                # 统计数据
                total_posts: int = 0,
                verified_posts: int = 0,
                disputed_posts: int = 0,
                content_keywords: list[str] | None = None,
                # 行为数据
                avg_posts_per_day: float = 0.0,
                post_times: list[str] | None = None,
                interaction_ratio: float | None = None,
                # 内容文本
                content_text: str = "",
                ) -> PublisherProfile:
        profile = PublisherProfile(
            username=username, user_id=user_id, platform=platform,
            total_posts=total_posts, verified_posts=verified_posts,
            disputed_posts=disputed_posts,
            verification_rate=verified_posts / max(1, total_posts),
        )

        # 1. 账号年龄
        age_score, days, age_risks = _analyze_account_age(created_at)
        profile.account_age_score = age_score
        profile.account_age_days = days
        profile.risk_factors.extend(age_risks)

        # 2. 历史准确率
        hist_score, hist_msg = _analyze_history(verified_posts, disputed_posts, total_posts)
        profile.history_accuracy_score = hist_score
        if hist_score < 50:
            profile.risk_factors.append(hist_msg)
        elif hist_score >= 70:
            profile.confidence_factors.append(hist_msg)

        # 3. 领域专注度
        exp_score, exp_msg = _analyze_domain_expertise(claimed_expertise, content_keywords or [])
        profile.domain_expertise_score = exp_score
        if exp_score < 45:
            profile.risk_factors.append(exp_msg)

        # 4. 行为规律
        behavior_score, behavior_risks = _analyze_behavior(avg_posts_per_day, post_times, interaction_ratio)
        profile.behavior_pattern_score = behavior_score
        profile.risk_factors.extend(behavior_risks)

        # 5. 跨平台关联 (当前无跨平台数据，保持中性)
        profile.cross_platform_score = 50.0

        # 6. 动机分析
        motiv_score, motiv_risks = _analyze_motivation(content_text, bio)
        profile.motivation_score = motiv_score
        profile.risk_factors.extend(motiv_risks)

        # === 综合评分 ===
        # 加权平均: 年龄20% + 历史30% + 领域15% + 行为15% + 动机20%
        weights = [0.20, 0.30, 0.15, 0.15, 0.20]
        scores = [
            profile.account_age_score,
            profile.history_accuracy_score,
            profile.domain_expertise_score,
            profile.behavior_pattern_score,
            profile.motivation_score,
        ]
        profile.overall_risk = sum(w * s for w, s in zip(weights, scores))

        return profile
