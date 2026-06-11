"""
注意力劫持对抗指标

基于B站分析发现: 辟谣视频评论高赞第一经常和辟谣内容无关。
这个模块检测辟谣内容中"娱乐元素 vs 信息元素"的比值，
衡量辟谣信息传递效率。

如果用户只记住了视频中的美女/搞笑/争议，
而没有记住辟谣内容 → 这个辟谣视频是失败的。
"""
import re
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class AttentionMetric:
    """辟谣内容注意力效率评估"""
    # 娱乐信号密度
    entertainment_density: float = 0.0
    entertainment_keywords: list[str] = field(default_factory=list)

    # 信息信号密度
    information_density: float = 0.0
    information_keywords: list[str] = field(default_factory=list)

    # 注意力效率 = 信息密度 / (信息密度 + 娱乐密度)
    attention_efficiency: float = 0.5

    # 评论-主题相关性
    comment_topic_relevance: float = 0.0
    top_comment_distraction_ratio: float = 0.0  # 高赞评论中与主题无关的比例

    # 评估
    risk_level: str = "low"  # low / medium / high — 注意力被劫持的风险
    assessment: str = ""

    def to_dict(self) -> dict:
        return {
            "entertainment_density": round(self.entertainment_density, 2),
            "information_density": round(self.information_density, 2),
            "attention_efficiency": round(self.attention_efficiency, 2),
            "comment_topic_relevance": round(self.comment_topic_relevance, 2),
            "top_comment_distraction_ratio": round(self.top_comment_distraction_ratio, 2),
            "risk_level": self.risk_level,
            "assessment": self.assessment,
        }


# =============================================================================
# 关键词词典
# =============================================================================

ENTERTAINMENT_KEYWORDS = [
    # 视觉注意力劫持
    "美女", "小姐姐", "帅哥", "颜值", "好看", "可爱",
    "身材", "穿搭", "打扮", "妆容", "表情",
    # 情绪/争议劫持
    "笑死", "好笑", "搞笑", "哈哈哈", "离谱",
    "震惊", "无语", "辣眼睛", "恶心", "吓人",
    # 无关互动
    "点赞", "投币", "三连", "关注", "收藏",
    "白嫖", "下次一定",
    # 八卦/梗
    "老婆", "老公", "磕到了", "真香", "蚌埠住了",
    "乐了", "看乐子",
]


def compute_attention_metric(
    content_text: str = "",
    content_title: str = "",
    comments: list[dict] | None = None,
) -> AttentionMetric:
    """
    计算辟谣内容的注意力效率。

    Args:
        content_text: 内容全文 (转录文本或描述)
        content_title: 标题
        comments: 评论列表 [{"content": str, "like": int}, ...]

    Returns:
        AttentionMetric — 包含注意力效率评分
    """
    metric = AttentionMetric()
    combined = f"{content_title}\n{content_text}"

    # === 1. 娱乐信号密度 ===
    ent_count = 0
    for kw in ENTERTAINMENT_KEYWORDS:
        found = combined.count(kw)
        if found > 0:
            ent_count += found
            metric.entertainment_keywords.append(f"{kw}({found})")

    total_chars = max(1, len(combined))
    metric.entertainment_density = ent_count / (total_chars / 100)

    # === 2. 信息信号密度 ===
    info_keywords = [
        "研究", "数据", "证据", "来源", "实验", "证明",
        "结果显示", "发现", "分析", "结论", "报告",
        "统计", "调查", "论文", "标准", "规定",
        "符合", "不符合", "对比", "说明",
    ]
    info_count = 0
    for kw in info_keywords:
        found = combined.count(kw)
        if found > 0:
            info_count += found
            metric.information_keywords.append(f"{kw}({found})")

    metric.information_density = info_count / (total_chars / 100)

    # === 3. 注意力效率 ===
    metric.attention_efficiency = info_count / max(1, info_count + ent_count)

    # === 4. 评论-主题相关性 ===
    comments = comments or []
    if comments and content_title:
        # 提取标题核心词
        title_words = set(re.findall(r'[一-鿿\w]+', content_title))
        # 去除通用停用词
        stopwords = {"的", "是", "了", "在", "和", "就", "都", "也", "但", "而", "及", "或", "这", "那", "着", "过"}

        relevant_count = 0
        top5 = sorted(comments, key=lambda c: c.get("like", 0), reverse=True)[:5]

        for c in top5:
            content = c.get("content", "")
            comment_words = set(re.findall(r'[一-鿿\w]+', content))
            overlap = len(title_words & comment_words - stopwords)
            if overlap >= 2:
                relevant_count += 1

        if top5:
            metric.comment_topic_relevance = relevant_count / len(top5)
            metric.top_comment_distraction_ratio = 1.0 - metric.comment_topic_relevance

    # === 5. 风险评估 ===
    if metric.attention_efficiency < 0.3:
        metric.risk_level = "high"
        metric.assessment = "注意力严重被娱乐元素劫持。辟谣信息可能未被受众接收——建议减少视觉干扰、前3秒直接陈述核心事实。"
    elif metric.attention_efficiency < 0.5:
        metric.risk_level = "medium"
        metric.assessment = "存在一定程度的注意力分散。建议增加信息密度——用屏幕文字同步展示关键数据。"
    else:
        metric.risk_level = "low"
        metric.assessment = "注意力效率良好。信息元素占比充足，受众较大概率接收到辟谣内容。"

    if metric.top_comment_distraction_ratio > 0.6:
        metric.risk_level = "high" if metric.risk_level != "high" else "high"
        metric.assessment += " 高赞评论与辟谣主题无关——受众注意力被娱乐/争议内容劫持。"

    return metric
