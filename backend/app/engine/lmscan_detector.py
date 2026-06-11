"""
lmscan AI 文本统计特征检测引擎 — 第18号引擎

基于12种统计特征检测 AI 生成文本，零依赖纯 Python 实现。

设计参考:
  - lmscan (github.com/stef41/lmscan): zero-dependency, offline, LLM fingerprinting
  - DetectZoo (arXiv 2606.04205): 61 detectors, multi-modal unified toolkit
  - DivEye (IBM, TMLR 2026): surprisal-based detection, 33.2% better than zero-shot

检测特征:
  1. Token 重复率 — AI 生成文本有更高的 token 重复率
  2. 滑动窗口熵 — 困惑度代理，AI 文本熵更均匀
  3. Burstiness — 稀有词聚集度，人类写作更"bursty"
  4. 句长均匀度 — AI 句长变异系数更低
  5. 标点模式熵 — AI 标点使用模式更规整
  6. 词汇丰富度 (TTR) — 独特词/总词数比，AI 更低
  7. 短语重复指数 — N-gram 重复度
  8. 句法模板检测 — 高频句式模板
  9. 文本结构分数 — 标准"总-分-总"过度模式
  10. 过渡词密度 — "furthermore","however"等过度使用
  11. 代词/回指一致性 — AI 的指代更"完美"
  12. 组合指纹哈希 — 向量距离评分

核心原则:
  - 所有信号都是"线索"而非"判定"
  - 短文本 (<100字) 结果不可靠
  - 多个检测器一致时信号更强
"""

from __future__ import annotations
import re
import math
import statistics
import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class LmscanFeature:
    """单个统计特征的检测结果"""
    name: str
    value: float           # 原始值
    score: float           # 归一化 AI 概率 0-1
    threshold: float       # 判定阈值
    flagged: bool = False
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "score": round(self.score, 2),
            "threshold": self.threshold,
            "flagged": self.flagged,
            "detail": self.detail,
        }


@dataclass
class LmscanResult:
    """lmscan 完整检测结果"""
    features: list[LmscanFeature] = field(default_factory=list)
    ai_probability: float = 0.0       # 综合 AI 概率 0-1
    feature_count_flagged: int = 0
    confidence: str = "low"           # low / moderate / high
    text_length: int = 0
    model_fingerprint: str = ""       # 可能的 LLM 指纹 (gpt / claude / llama / human / unknown)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "features": [f.to_dict() for f in self.features],
            "ai_probability": round(self.ai_probability, 2),
            "feature_count_flagged": self.feature_count_flagged,
            "confidence": self.confidence,
            "text_length": self.text_length,
            "model_fingerprint": self.model_fingerprint,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


# =============================================================================
# AI 模型语言指纹
# =============================================================================

# 各模型的特征词
MODEL_FINGERPRINTS = {
    "gpt": [
        "delve", "tapestry", "moreover", "furthermore", "additionally",
        "it is worth noting that", "in conclusion", "in summary",
        "a testament to", "underscores", "shed light on",
        "值得注意的是", "综上所述", "总的来说", "毋庸置疑",
    ],
    "claude": [
        "certainly", "absolutely", "I appreciate", "great question",
        "I understand", "based on the", "here's", "let me",
        "certainly", "absolutely",
    ],
    "gemini": [
        "as an AI", "I cannot", "based on my knowledge",
        "it's important to note", "keep in mind",
    ],
    "llama": [
        "however", "therefore", "consequently", "in other words",
        "to put it simply", "this means that",
    ],
}

# 过渡词（AI 高密度特征）
TRANSITION_WORDS = {
    "en": [
        "however", "therefore", "consequently", "moreover", "furthermore",
        "nevertheless", "nonetheless", "accordingly", "hence", "thus",
        "additionally", "specifically", "alternatively", "meanwhile",
        "subsequently", "ultimately", "in addition", "in contrast",
        "on the other hand", "as a result", "for instance",
    ],
    "zh": [
        "然而", "因此", "此外", "而且", "不过",
        "但是", "所以", "另外", "与此同时", "最后",
        "首先", "其次", "第三", "综上所述", "换句话说",
        "也就是说", "值得注意的是", "需要强调的是",
    ],
}

# 标准文本结构模板 (AI 高频特征)
STRUCTURE_PATTERNS = [
    r"(?:首先|第一|其一)[\s\S]{10,80}(?:其次|第二|其二|另外)",
    r"(?:总之|综上所述|总的来说|最后)[\s\S]{0,60}(?:我们希望|我们应该|需要)",
    r"^(?:本文|本报告|这篇文章).{0,30}(?:探|分析|研究|介绍|讨论)",
    r"(?:is\s+a\s+complex\s+(?:and\s+)?multifaceted)",
    r"(?:plays?\s+a?\s*(?:crucial|vital|essential|important|significant)\s+role)",
    r"(?:it\s+is\s+(?:important|crucial|essential|vital)\s+to)",
]


class LmscanDetector:
    """
    lmscan AI 文本统计特征检测器 — 12 个维度。
    纯 Python，零外部依赖。
    """

    def analyze(self, text: str, title: str = "") -> LmscanResult:
        """运行全部 12 个特征检测"""
        result = LmscanResult(text_length=len(text))

        if len(text.strip()) < 50:
            result.summary = "文本过短 (<50字符)，统计特征不可靠。不进行 AI 检测。"
            result.recommendations.append("需要至少50个字符才能进行有意义的统计分析。")
            result.confidence = "low"
            return result

        # 预处理
        cleaned = self._preprocess(text)
        sentences = self._split_sentences(cleaned)
        words = self._tokenize(cleaned)

        # 运行 12 个特征
        features: list[LmscanFeature] = []

        # F1: Token 重复率
        f1 = self._feature_token_repetition(words)
        features.append(f1)

        # F2: 滑动窗口熵
        f2 = self._feature_sliding_entropy(words)
        features.append(f2)

        # F3: Burstiness
        f3 = self._feature_burstiness(words)
        features.append(f3)

        # F4: 句长均匀度
        f4 = self._feature_sentence_uniformity(sentences)
        features.append(f4)

        # F5: 标点模式熵
        f5 = self._feature_punctuation_entropy(text)
        features.append(f5)

        # F6: 词汇丰富度 TTR
        f6 = self._feature_ttr(words)
        features.append(f6)

        # F7: 短语重复指数
        f7 = self._feature_phrase_repetition(words)
        features.append(f7)

        # F8: 句法模板检测
        f8 = self._feature_syntax_templates(text)
        features.append(f8)

        # F9: 文本结构分数
        f9 = self._feature_structure_score(text)
        features.append(f9)

        # F10: 过渡词密度
        f10 = self._feature_transition_density(text)
        features.append(f10)

        # F11: 代词一致性
        f11 = self._feature_pronoun_consistency(text)
        features.append(f11)

        # F12: 组合指纹
        f12 = self._feature_fingerprint_hash(features)
        features.append(f12)

        result.features = features
        result.feature_count_flagged = sum(1 for f in features if f.flagged)

        # 综合评分
        flagged_scores = [f.score for f in features if f.flagged]
        if flagged_scores:
            result.ai_probability = sum(flagged_scores) / max(len(flagged_scores), 1)
        else:
            result.ai_probability = sum(f.score * 0.5 for f in features[:6]) / 6

        # 置信度
        if result.feature_count_flagged >= 6:
            result.confidence = "high"
        elif result.feature_count_flagged >= 3:
            result.confidence = "moderate"
        else:
            result.confidence = "low"

        # 模型指纹
        result.model_fingerprint = self._fingerprint_model(text)

        # 摘要
        result.summary = self._build_summary(result)

        return result

    # ===================================================================
    # 特征实现
    # ===================================================================

    @staticmethod
    def _feature_token_repetition(words: list[str]) -> LmscanFeature:
        """F1: Token (词) 重复率 — AI 文本重复率更高"""
        if len(words) < 10:
            return LmscanFeature(name="词重复率", value=0, score=0, threshold=0.30)

        unique = set(words)
        # 计算重复词占比
        word_counts = Counter(words)
        repeated = sum(1 for w, c in word_counts.items() if c > 1)
        repetition_rate = repeated / max(len(unique), 1)

        # 阈值: >0.25 可能 AI
        flagged = repetition_rate > 0.30
        score = min(repetition_rate / 0.50, 1.0)

        return LmscanFeature(
            name="词重复率",
            value=repetition_rate,
            score=score,
            threshold=0.30,
            flagged=flagged,
            detail=f"重复词占比 {repetition_rate:.1%}, 阈值 30%",
        )

    @staticmethod
    def _feature_sliding_entropy(words: list[str], window: int = 15) -> LmscanFeature:
        """F2: 滑动窗口熵 — AI 文本熵更均匀 (困惑度代理)"""
        if len(words) < window * 2:
            return LmscanFeature(name="滑动窗口熵", value=0, score=0, threshold=0.60)

        word_freq = Counter(words)
        total = len(words)

        entropies = []
        for i in range(0, len(words) - window, max(1, window // 3)):
            window_words = words[i:i + window]
            wf = Counter(window_words)
            entropy = sum(
                -(c / window) * math.log2(c / window)
                for c in wf.values() if c > 0
            )
            entropies.append(entropy)

        if len(entropies) < 2:
            return LmscanFeature(name="滑动窗口熵", value=0, score=0, threshold=0.60)

        # 熵的变异系数 — AI 更低 (更均匀)
        mean_e = statistics.mean(entropies)
        std_e = statistics.stdev(entropies) if len(entropies) > 1 else 0
        cv = std_e / max(mean_e, 0.01)

        # 阈值: 变异系数 < 0.15 可能 AI
        flagged = cv < 0.18
        score = max(0, min(1 - cv / 0.40, 1.0))

        return LmscanFeature(
            name="滑动窗口熵变异",
            value=cv,
            score=score,
            threshold=0.18,
            flagged=flagged,
            detail=f"熵变异系数 {cv:.3f} (越低越像AI), 均值熵 {mean_e:.2f}",
        )

    @staticmethod
    def _feature_burstiness(words: list[str]) -> LmscanFeature:
        """F3: Burstiness — 稀有词聚集度。人类写作更 'bursty'"""
        if len(words) < 30:
            return LmscanFeature(name="Burstiness", value=0, score=0, threshold=0.65)

        word_freq = Counter(words)
        total = len(words)

        # 找"稀有词" (频率 <= 2)
        rare_words = {w for w, c in word_freq.items() if c <= 2 and len(w) > 2}

        # 计算稀有词的分布方差
        rare_positions = []
        for i, w in enumerate(words):
            if w in rare_words:
                rare_positions.append(i)

        if len(rare_positions) < 3:
            return LmscanFeature(name="Burstiness", value=1.0, score=0.8, threshold=0.65,
                                flagged=True, detail="稀有词太少 — AI 文本特征")

        # 相邻稀有词间距的标准差
        gaps = [rare_positions[i + 1] - rare_positions[i] for i in range(len(rare_positions) - 1)]
        mean_gap = statistics.mean(gaps)
        std_gap = statistics.stdev(gaps) if len(gaps) > 1 else 0

        # burstiness = std/mean — 越高越 "人类"
        burstiness = std_gap / max(mean_gap, 1)
        burstiness_normalized = min(burstiness / 2.0, 1.0)

        # 阈值: burstiness < 0.5 → 太均匀 → 可能是 AI
        flagged = burstiness_normalized < 0.30
        score = 1.0 - burstiness_normalized

        return LmscanFeature(
            name="Burstiness",
            value=burstiness_normalized,
            score=score,
            threshold=0.30,
            flagged=flagged,
            detail=f"Burstiness {burstiness_normalized:.3f} (越高越像人), {len(rare_positions)}个稀有词",
        )

    @staticmethod
    def _feature_sentence_uniformity(sentences: list[str]) -> LmscanFeature:
        """F4: 句长均匀度 — AI 句长变异系数更低"""
        if len(sentences) < 5:
            return LmscanFeature(name="句长均匀度", value=0, score=0, threshold=0.25)

        lengths = [len(s) for s in sentences if len(s.strip()) > 2]
        if len(lengths) < 5:
            return LmscanFeature(name="句长均匀度", value=0, score=0, threshold=0.25)

        mean_l = statistics.mean(lengths)
        std_l = statistics.stdev(lengths) if len(lengths) > 1 else 0
        cv = std_l / max(mean_l, 1)

        # 阈值: CV < 0.30 → 太均匀 → AI
        flagged = cv < 0.30
        score = max(0, min(1 - cv / 0.60, 1.0))

        return LmscanFeature(
            name="句长均匀度",
            value=cv,
            score=score,
            threshold=0.30,
            flagged=flagged,
            detail=f"句长 CV={cv:.3f}, 平均{mean_l:.0f}字, {len(lengths)}句",
        )

    @staticmethod
    def _feature_punctuation_entropy(text: str) -> LmscanFeature:
        """F5: 标点模式熵 — AI 标点更规整"""
        punct_chars = r'[，,。！!？?；;：:、""''「」『』【】《》（()）—….,!?;:"\'()]'
        puncts = re.findall(punct_chars, text)

        if len(puncts) < 10:
            return LmscanFeature(name="标点模式熵", value=0, score=0, threshold=0.85)

        punct_freq = Counter(puncts)
        total = len(puncts)

        # Shannon 熵
        entropy = sum(
            -(c / total) * math.log2(c / total)
            for c in punct_freq.values() if c > 0
        )

        # 中文文本标点熵通常在 1.5-3.5。AI 倾向于更低的熵 (重复使用少数标点)
        entropy_norm = entropy / 3.5  # 归一化

        # 阈值: 标点熵 < 0.5 (归一化后) → 模式太简单 → AI
        flagged = entropy_norm < 0.55
        score = 1.0 - min(entropy_norm, 1.0)

        return LmscanFeature(
            name="标点模式熵",
            value=entropy,
            score=score,
            threshold=1.92,
            flagged=flagged,
            detail=f"标点熵 {entropy:.2f} (归一化 {entropy_norm:.2f}), {len(punct_freq)}种标点, {total}次",
        )

    @staticmethod
    def _feature_ttr(words: list[str]) -> LmscanFeature:
        """F6: 词汇丰富度 Type-Token Ratio — AI 更低"""
        if len(words) < 20:
            return LmscanFeature(name="词汇丰富度", value=0, score=0, threshold=0.55)

        # 分段 TTR (避免长度影响)
        segment_size = 30
        ttrs = []
        for i in range(0, len(words), segment_size):
            seg = words[i:i + segment_size]
            if len(seg) >= 10:
                ttrs.append(len(set(seg)) / len(seg))

        if not ttrs:
            return LmscanFeature(name="词汇丰富度", value=0, score=0, threshold=0.55)

        avg_ttr = statistics.mean(ttrs)

        # 阈值: TTR < 0.55 → 词汇可能贫乏
        flagged = avg_ttr < 0.55
        score = max(0, min(1 - avg_ttr / 0.80, 1.0))

        return LmscanFeature(
            name="词汇丰富度 (TTR)",
            value=avg_ttr,
            score=score,
            threshold=0.55,
            flagged=flagged,
            detail=f"分段TTR均值 {avg_ttr:.3f} ({len(ttrs)}段), 总词数 {len(words)}",
        )

    @staticmethod
    def _feature_phrase_repetition(words: list[str]) -> LmscanFeature:
        """F7: 短语重复指数 — Bigram/Trigram 重复"""
        if len(words) < 20:
            return LmscanFeature(name="短语重复", value=0, score=0, threshold=0.10)

        def get_ngrams(n: int) -> Counter:
            grams = []
            for i in range(len(words) - n + 1):
                grams.append("_".join(words[i:i + n]))
            return Counter(grams)

        bigrams = get_ngrams(2)
        trigrams = get_ngrams(3)

        # 重复率
        bigram_repeat = sum(1 for c in bigrams.values() if c > 1) / max(len(bigrams), 1)
        trigram_repeat = sum(1 for c in trigrams.values() if c > 1) / max(len(trigrams), 1)
        avg_repeat = (bigram_repeat + trigram_repeat) / 2

        # 阈值: 重复率 > 0.10
        flagged = avg_repeat > 0.10
        score = min(avg_repeat / 0.25, 1.0)

        return LmscanFeature(
            name="短语重复指数",
            value=avg_repeat,
            score=score,
            threshold=0.10,
            flagged=flagged,
            detail=f"Bigram {bigram_repeat:.3f} | Trigram {trigram_repeat:.3f} | 总{len(words)}词",
        )

    @staticmethod
    def _feature_syntax_templates(text: str) -> LmscanFeature:
        """F8: 句法模板检测 — AI 高频句式模式"""
        templates = [
            (r'(?:不仅|不但)\S{0,20}(?:而且|还|也)', "递进结构"),
            (r'(?:虽然|尽管)\S{0,20}(?:但是|但|然而)', "转折结构"),
            (r'(?:因为|由于)\S{0,20}(?:所以|因此|因而)', "因果结构"),
            (r'(?:一方面)\S{0,20}(?:另一方面)', "对比结构"),
            (r'not\s+only.{0,40}but\s+also', "not only...but also"),
            (r'(?:in\s+conclusion|to\s+sum\s+up|in\s+summary)', "结论模板"),
            (r'(?:it\s+should\s+be\s+noted|it\s+is\s+worth\s+(?:noting|mentioning))', "强调模板"),
        ]

        match_count = 0
        total_chars = len(text)
        for pattern, _ in templates:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            match_count += matches

        # 每千字模板密度
        density = (match_count / max(total_chars, 1)) * 1000

        # 阈值: density > 2.5
        flagged = density > 2.5
        score = min(density / 6.0, 1.0)

        return LmscanFeature(
            name="句法模板密度",
            value=density,
            score=score,
            threshold=2.5,
            flagged=flagged,
            detail=f"每千字 {density:.1f} 个模板匹配, 共 {match_count} 处",
        )

    @staticmethod
    def _feature_structure_score(text: str) -> LmscanFeature:
        """F9: 文本结构分数 — "总-分-总"过度规整模式"""
        structure_indicators = {
            "opening": [
                "随着", "近年来", "在当今", "目前", "当前",
                "in today's", "in recent years", "nowadays",
                "随着社会的发展", "随着科技的进步",
            ],
            "transition": [
                "首先", "其次", "第三", "第一", "第二",
                "first", "second", "third", "firstly", "secondly",
            ],
            "closing": [
                "总之", "综上所述", "最后", "总而言之",
                "in conclusion", "to sum up", "in summary",
                "因此我们应该", "所以我们需要",
            ],
        }

        scores = {}
        for section, patterns in structure_indicators.items():
            count = sum(1 for p in patterns if p.lower() in text.lower())
            scores[section] = min(count, 3)  # cap at 3

        # 全部分都存在 → 高度结构化 → AI
        total = sum(scores.values())
        structure_score = total / 9.0  # max 9

        flagged = structure_score > 0.40
        score_value = structure_score

        return LmscanFeature(
            name="文本结构分数",
            value=structure_score,
            score=score_value,
            threshold=0.40,
            flagged=flagged,
            detail=f"开头{sum(1 for p in structure_indicators['opening'] if p in text)} / "
                    f"过渡{sum(1 for p in structure_indicators['transition'] if p in text)} / "
                    f"结尾{sum(1 for p in structure_indicators['closing'] if p in text)}",
        )

    @staticmethod
    def _feature_transition_density(text: str) -> LmscanFeature:
        """F10: 过渡词密度 — AI 过度使用 'however', 'furthermore' 等"""
        total_words = len(re.findall(r'\w+', text))
        if total_words < 20:
            return LmscanFeature(name="过渡词密度", value=0, score=0, threshold=0.05)

        # 检测中英文过渡词
        all_transitions = TRANSITION_WORDS["en"] + TRANSITION_WORDS["zh"]
        transition_count = 0
        for tw in all_transitions:
            transition_count += len(re.findall(re.escape(tw), text, re.IGNORECASE))

        density = transition_count / max(total_words, 1)

        # 阈值: 过渡词超过 5%
        flagged = density > 0.05
        score = min(density / 0.10, 1.0)

        return LmscanFeature(
            name="过渡词密度",
            value=density,
            score=score,
            threshold=0.05,
            flagged=flagged,
            detail=f"{density:.2%} ({transition_count}/{total_words}词), 阈值 5%",
        )

    @staticmethod
    def _feature_pronoun_consistency(text: str) -> LmscanFeature:
        """F11: 代词/回指一致性 — AI 的指代过于完美"""
        # 人类写作中代词使用有自然的多样性 (你/您/他/她/它 混用)
        # AI 倾向于高度一致性
        zh_pronouns = re.findall(r'(?:他|她|它|你|您|我|我们|他们|她们|它们)', text)
        en_pronouns = re.findall(r'\b(?:he|she|it|they|we|you|I|him|her|them|us|me)\b',
                                 text, re.IGNORECASE)

        all_pronouns = zh_pronouns + en_pronouns
        if len(all_pronouns) < 5:
            return LmscanFeature(name="代词一致性", value=0, score=0, threshold=0.80)

        pronoun_freq = Counter(p.lower() for p in all_pronouns)
        total = len(all_pronouns)

        # 归一化成 "主导代词" 的浓度
        dominant_ratio = max(pronoun_freq.values()) / max(total, 1)

        # 阈值: >0.80 → 代词太一致 → 可能 AI
        flagged = dominant_ratio > 0.80
        score = min(dominant_ratio / 0.95, 1.0)

        return LmscanFeature(
            name="代词一致性",
            value=dominant_ratio,
            score=score,
            threshold=0.80,
            flagged=flagged,
            detail=f"主导代词占比 {dominant_ratio:.1%}, {total}个人称代词, "
                    f"{len(pronoun_freq)}种代词",
        )

    @staticmethod
    def _feature_fingerprint_hash(features: list[LmscanFeature]) -> LmscanFeature:
        """F12: 组合指纹哈希 — 基于前11个特征的加权向量距离"""
        if len(features) < 11:
            return LmscanFeature(name="组合指纹", value=0, score=0, threshold=0.50)

        # 各特征权重
        weights = [1.2, 1.0, 1.3, 0.8, 0.7, 1.0, 1.1, 0.8, 0.6, 0.9, 0.8]

        scores = [f.score for f in features[:11]]
        weighted = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        # 生成指纹哈希
        hash_input = ",".join(f"{f.value:.4f}" for f in features[:11])
        fp_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]

        flagged = weighted > 0.50

        return LmscanFeature(
            name="组合指纹",
            value=weighted,
            score=weighted,
            threshold=0.50,
            flagged=flagged,
            detail=f"加权综合 {weighted:.2f} | 指纹 {fp_hash}",
        )

    # ===================================================================
    # 模型指纹识别
    # ===================================================================

    @staticmethod
    def _fingerprint_model(text: str) -> str:
        """尝试识别特定的 AI 模型指纹"""
        text_lower = text.lower()
        scores: dict[str, int] = {}

        for model, phrases in MODEL_FINGERPRINTS.items():
            score = sum(1 for p in phrases if p.lower() in text_lower)
            scores[model] = score

        max_score = max(scores.values()) if scores else 0
        if max_score >= 4:
            for model, score in scores.items():
                if score == max_score:
                    return model

        if max_score >= 2:
            return "unknown"

        return "likely_human"

    # ===================================================================
    # 工具方法
    # ===================================================================

    @staticmethod
    def _preprocess(text: str) -> str:
        """预处理文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除 URL
        text = re.sub(r'https?://\S+', '', text)
        return text.strip()

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """分句"""
        return re.split(r'[。！？!?\n；;]+', text)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词 (中英文混合)"""
        # 提取中文字符和英文单词
        chinese_chars = re.findall(r'[一-鿿]', text)
        english_words = re.findall(r'[a-zA-Z]+', text)

        # 中文按单字处理，英文按单词
        tokens = chinese_chars + english_words
        return tokens

    @staticmethod
    def _build_summary(result: LmscanResult) -> str:
        """生成摘要"""
        prob = result.ai_probability
        if prob >= 0.70:
            verdict = "高概率AI生成"
        elif prob >= 0.40:
            verdict = "中等概率AI生成/辅助"
        elif prob >= 0.20:
            verdict = "低概率AI参与"
        else:
            verdict = "很可能是人类写作"

        parts = [
            f"AI 概率: {prob:.0%} — {verdict}",
            f"{result.feature_count_flagged}/12 特征触发",
            f"置信度: {result.confidence}",
        ]

        if result.model_fingerprint not in ("likely_human", "unknown"):
            parts.append(f"模型指纹: {result.model_fingerprint}")

        if result.text_length < 200:
            parts.append("[注意] 短文本检测不可靠")

        return " | ".join(parts)
