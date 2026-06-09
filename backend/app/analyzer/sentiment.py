"""
情感分析器 — 检测文本情感倾向
支持正面/负面/中性 + 质疑检测
"""

import re
from collections import Counter

from loguru import logger


class SentimentAnalyzer:
    """中文情感分析器"""

    # 正面情感词
    POSITIVE_WORDS = {
        "好", "棒", "赞", "优秀", "伟大", "成功", "进步", "发展", "改善",
        "支持", "赞同", "认同", "认可", "称赞", "表扬", "感谢", "感动",
        "希望", "期待", "信心", "乐观", "积极", "向上", "美好", "幸福",
        "公平", "正义", "真相", "事实", "科学", "理性", "客观", "专业",
        "权威", "可靠", "可信", "确认", "证实", "属实", "真实", "确实",
    }

    # 负面情感词
    NEGATIVE_WORDS = {
        "差", "烂", "坏", "糟糕", "失败", "倒退", "恶化", "危机", "灾难",
        "反对", "拒绝", "否定", "否认", "批评", "指责", "谴责", "愤怒",
        "失望", "绝望", "悲观", "消极", "黑暗", "腐败", "贪污", "欺骗",
        "谣言", "虚假", "不实", "造谣", "诽谤", "谎言", "骗局", "阴谋",
        "隐瞒", "掩盖", "封锁", "压制", "打压", "攻击", "抹黑", "诋毁",
        "虚假信息", "误导", "歪曲", "断章取义", "双标", "打脸",
    }

    # 质疑/不确定性词
    DOUBT_WORDS = {
        "质疑", "怀疑", "疑问", "疑惑", "存疑", "可疑", "不确定",
        "真的吗", "是不是", "有没有可能", "难道", "不一定", "未必",
        "不确定", "不能确认", "有待证实", "尚无定论", "未经证实",
        "没有证据", "缺乏证据", "网传", "据说", "据称", "传闻",
    }

    def __init__(self):
        # 否定词（翻转情感）
        self.negation_words = {"不", "没", "没有", "未", "无", "非", "别", "莫"}

    async def analyze(self, text: str) -> dict:
        """
        分析文本情感

        Returns:
            {
                "sentiment": "positive" | "negative" | "neutral",
                "score": -1.0 ~ 1.0,
                "is_doubtful": bool,
                "emotion": "anger" | "fear" | "surprise" | "trust" | ...
            }
        """
        if not text:
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "is_doubtful": False,
                "emotion": "neutral",
            }

        # 统计情感词
        pos_count = 0
        neg_count = 0
        doubt_count = 0

        # 分词
        try:
            import jieba
            words = list(jieba.cut(text))
        except ImportError:
            # 回退到字符级匹配
            words = [text[i:i+2] for i in range(len(text)-1)]

        # 否定窗口检测
        negation_active = False
        window_size = 3  # 否定词影响范围

        for i, word in enumerate(words):
            if word in self.negation_words:
                negation_active = True
                continue

            if negation_active and i > window_size:
                negation_active = False

            if word in self.POSITIVE_WORDS:
                if negation_active:
                    neg_count += 1
                else:
                    pos_count += 1
            elif word in self.NEGATIVE_WORDS:
                if negation_active:
                    pos_count += 1
                else:
                    neg_count += 1
            elif word in self.DOUBT_WORDS:
                doubt_count += 1

        # 计算情感分数
        total = pos_count + neg_count
        if total == 0:
            score = 0.0
            sentiment = "neutral"
        else:
            score = (pos_count - neg_count) / max(total, 1)
            if score > 0.1:
                sentiment = "positive"
            elif score < -0.1:
                sentiment = "negative"
            else:
                sentiment = "neutral"

        # 质疑检测
        is_doubtful = doubt_count >= 2 or (doubt_count >= 1 and sentiment == "negative")

        # 情绪检测
        emotion = self._detect_emotion(text)

        return {
            "sentiment": sentiment,
            "score": round(score, 3),
            "is_doubtful": is_doubtful,
            "emotion": emotion,
            "details": {
                "positive_words": pos_count,
                "negative_words": neg_count,
                "doubt_words": doubt_count,
            },
        }

    def _detect_emotion(self, text: str) -> str:
        """检测情绪类别"""
        emotion_words = {
            "anger": {"愤怒", "气愤", "生气", "恼火", "可恨", "可恶", "令人发指"},
            "fear": {"害怕", "恐惧", "担忧", "焦虑", "恐慌", "可怕", "恐怖"},
            "surprise": {"震惊", "惊讶", "意外", "竟然", "居然", "想不到"},
            "trust": {"相信", "信任", "信赖", "可靠", "靠谱", "确定"},
            "sadness": {"悲伤", "难过", "遗憾", "惋惜", "心痛", "哀悼"},
            "disgust": {"恶心", "厌恶", "反感", "讨厌", "令人作呕"},
        }

        scores = {}
        for emotion, words in emotion_words.items():
            count = sum(text.count(w) for w in words)
            scores[emotion] = count

        if max(scores.values(), default=0) == 0:
            return "neutral"

        return max(scores, key=scores.get)
