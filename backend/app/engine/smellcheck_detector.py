"""
smellcheck AI 文本静态指纹检测引擎 — 第19号引擎

通过 8 类静态指纹检测 AI 生成文本的表面特征，零依赖纯 Python。

设计参考:
  - smellcheck (github.com/fbuchinger/smellcheck): zero ML, 4 pluggable detectors
  - 检测 AI 文本的 "指纹"：排版怪异、Unicode 模式、热词密度、不自然词汇

检测类别:
  1. Unicode 同形字 — 西里尔 'а' vs 拉丁 'a' 等混淆字符
  2. 零宽字符 — U+200B/U+200C/U+200D/U+FEFF 隐藏字符
  3. AI 热词密度 — "delve","tapestry","值得注意的是" 等
  4. 引号风格不一致 — 弯引号 vs 直引号混用
  5. 破折号一致性 — em dash / en dash / 连字符混用
  6. 空白异常 — 双空格、制表符-空格混用
  7. 控制字符 — 不可打印字符
  8. RTL 覆盖攻击 — 方向控制字符 (bidi attacks)

核心原则:
  - 这些是"指纹"而非"判决"
  - 人类也可能产生某些指纹 (如排版软件)
  - 多个指纹同时出现 → 信号更强
"""

from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class SmellcheckFlag:
    """单条指纹标记"""
    category: str           # 检测类别
    severity: str           # high / medium / low
    description: str
    location_hint: str = "" # 位置提示 (字符偏移)
    count: int = 0

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "location_hint": self.location_hint,
            "count": self.count,
        }


@dataclass
class SmellcheckResult:
    """smellcheck 完整检测结果"""
    flags: list[SmellcheckFlag] = field(default_factory=list)
    total_flags: int = 0
    high_severity_count: int = 0
    anomaly_score: float = 0.0        # 0-100 异常评分
    categories_triggered: int = 0     # 触发了几个类别
    max_categories: int = 8
    text_length: int = 0
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "flags": [f.to_dict() for f in self.flags],
            "total_flags": self.total_flags,
            "high_severity_count": self.high_severity_count,
            "anomaly_score": round(self.anomaly_score, 1),
            "categories_triggered": self.categories_triggered,
            "max_categories": self.max_categories,
            "text_length": self.text_length,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


# =============================================================================
# 检测数据
# =============================================================================

# 1. Unicode 同形字/混淆字符映射
HOMOGLYPH_MAP = {
    # 西里尔 → 拉丁
    'а': 'a',   # Cyrillic 'а'
    'е': 'e',   # Cyrillic 'е'
    'о': 'o',   # Cyrillic 'о'
    'р': 'p',   # Cyrillic 'р'
    'с': 'c',   # Cyrillic 'с'
    'у': 'y',   # Cyrillic 'у'
    'х': 'x',   # Cyrillic 'х'
    'ѕ': 's',   # Cyrillic 'ѕ'
    'Ѕ': 'S',   # Cyrillic 'Ѕ'
    'Α': 'A',   # Greek 'Α'
    'Ε': 'E',   # Greek 'Ε'
    'Ν': 'N',   # Greek 'Ν'
    'Ο': 'O',   # Greek 'Ο'
    'Ρ': 'P',   # Greek 'Ρ'
    'Υ': 'Y',   # Greek 'Υ'
    'Β': 'B',   # Greek 'Β'
    'Η': 'H',   # Greek 'Η'
    'Ι': 'I',   # Greek 'Ι'
    'Κ': 'K',   # Greek 'Κ'
    'Μ': 'M',   # Greek 'Μ'
    'Τ': 'T',   # Greek 'Τ'
    'Χ': 'X',   # Greek 'Χ'
    'Σ': 'Z',   # Greek 'Ζ'  (not exactly Z but confusable)
}

# 2. 零宽字符
ZERO_WIDTH_CHARS = {
    '​': 'ZERO WIDTH SPACE',
    '‌': 'ZERO WIDTH NON-JOINER',
    '‍': 'ZERO WIDTH JOINER',
    '﻿': 'ZERO WIDTH NO-BREAK SPACE (BOM)',
    '⁠': 'WORD JOINER',
    '‎': 'LEFT-TO-RIGHT MARK',
    '‏': 'RIGHT-TO-LEFT MARK',
}

# 3. AI 热词 (中英文)
AI_BUZZWORDS = {
    "en": [
        "delve", "tapestry", "moreover", "furthermore",
        "additionally", "notably", "crucial", "vital",
        "paramount", "underscores", "embodiment",
        "testament", "realm", "landscape", "ecosystem",
        "actionable", "synergistic", "holistic",
        "pivotal", "robust", "comprehensive",
        "in today's rapidly evolving", "it is worth noting",
    ],
    "zh": [
        "值得注意的是", "毋庸置疑", "众所周知",
        "随着社会的不断发展", "在当今这个时代",
        "究其根本", "由此可见", "综上所述",
        "具有重要的现实意义", "无论从哪个角度看",
        "不可否认", "显而易见", "从某种意义上说",
        "狠狠地", "绝绝子", "yyds",  # AI 学网络用语也容易过火
    ],
}

# 4. 引号风格检测
SMART_QUOTES = {
    '“': '"',  # LEFT DOUBLE QUOTATION MARK
    '”': '"',  # RIGHT DOUBLE QUOTATION MARK
    '‘': "'",  # LEFT SINGLE QUOTATION MARK
    '’': "'",  # RIGHT SINGLE QUOTATION MARK
    '«': '"',  # LEFT-POINTING DOUBLE ANGLE («)
    '»': '"',  # RIGHT-POINTING DOUBLE ANGLE (»)
}

# 5. 破折号类型
DASH_TYPES = {
    '—': 'EM DASH (—)',
    '–': 'EN DASH (–)',
    '―': 'HORIZONTAL BAR (―)',
    '−': 'MINUS SIGN (−)',
    '-': 'HYPHEN-MINUS (-)',
    '－': 'FULLWIDTH HYPHEN-MINUS (－)',
}

# 8. RTL/bidi 攻击字符
RTL_OVERRIDE_CHARS = {
    '‪': 'LEFT-TO-RIGHT EMBEDDING',
    '‫': 'RIGHT-TO-LEFT EMBEDDING',
    '‬': 'POP DIRECTIONAL FORMATTING',
    '‭': 'LEFT-TO-RIGHT OVERRIDE',
    '‮': 'RIGHT-TO-LEFT OVERRIDE',
    '⁦': 'LEFT-TO-RIGHT ISOLATE',
    '⁧': 'RIGHT-TO-LEFT ISOLATE',
    '⁨': 'FIRST STRONG ISOLATE',
    '⁩': 'POP DIRECTIONAL ISOLATE',
}


class SmellcheckDetector:
    """
    smellcheck 静态 AI 指纹检测器 — 8 个类别。
    纯 Python，零外部依赖，零 ML。
    """

    def analyze(self, text: str, title: str = "") -> SmellcheckResult:
        """运行全部 8 个指纹类别检测"""
        result = SmellcheckResult(text_length=len(text))

        if len(text.strip()) < 20:
            result.summary = "文本过短 (<20字符)，指纹检测不可靠。"
            return result

        full_text = f"{title}\n{text}" if title else text
        flags: list[SmellcheckFlag] = []

        # C1: Unicode 同形字
        f1 = self._detect_homoglyphs(full_text)
        if f1:
            flags.append(f1)

        # C2: 零宽字符
        f2 = self._detect_zero_width(full_text)
        if f2:
            flags.append(f2)

        # C3: AI 热词密度
        f3 = self._detect_buzzwords(full_text)
        if f3:
            flags.append(f3)

        # C4: 引号风格不一致
        f4 = self._detect_quote_inconsistency(full_text)
        if f4:
            flags.append(f4)

        # C5: 破折号一致性
        f5 = self._detect_dash_inconsistency(full_text)
        if f5:
            flags.append(f5)

        # C6: 空白异常
        f6 = self._detect_whitespace_anomalies(full_text)
        if f6:
            flags.append(f6)

        # C7: 控制字符
        f7 = self._detect_control_chars(full_text)
        if f7:
            flags.append(f7)

        # C8: RTL 覆盖攻击
        f8 = self._detect_rtl_override(full_text)
        if f8:
            flags.append(f8)

        result.flags = flags
        result.total_flags = len(flags)
        result.high_severity_count = sum(1 for f in flags if f.severity == "high")
        result.categories_triggered = len({f.category for f in flags})

        # 异常评分 (0-100)
        severity_weights = {"high": 25, "medium": 12, "low": 5}
        raw_score = sum(severity_weights.get(f.severity, 5) for f in flags)
        result.anomaly_score = min(raw_score, 100.0)

        # 摘要与建议
        result.summary = self._build_summary(result)
        result.recommendations = self._build_recommendations(result)

        return result

    # ===================================================================
    # C1: Unicode 同形字检测
    # ===================================================================

    def _detect_homoglyphs(self, text: str) -> SmellcheckFlag | None:
        """检测使用非标准 Unicode 字符伪装的文本"""
        found: dict[str, list[int]] = {}

        for i, ch in enumerate(text):
            if ch in HOMOGLYPH_MAP:
                normal = HOMOGLYPH_MAP[ch]
                ch_name = unicodedata.name(ch, f'U+{ord(ch):04X}')
                key = f"'{ch}' (U+{ord(ch):04X}, {ch_name}) → 伪装的 '{normal}'"
                if key not in found:
                    found[key] = []
                found[key].append(i)

        if not found:
            return None

        total_count = sum(len(positions) for positions in found.values())
        examples = list(found.keys())[:3]
        positions = list(found.values())[0][:5] if found.values() else []

        severity = "high" if total_count >= 3 else "medium"

        return SmellcheckFlag(
            category="Unicode同形字",
            severity=severity,
            description=f"检测到 {total_count} 个同形字/混淆字符: {'; '.join(examples)}。"
                       f"这些字符看起来像普通拉丁字母但实际上是其他 Unicode 块的字符。",
            location_hint=f"位置: {positions}" if positions else "",
            count=total_count,
        )

    # ===================================================================
    # C2: 零宽字符
    # ===================================================================

    def _detect_zero_width(self, text: str) -> SmellcheckFlag | None:
        """检测零宽/不可见字符"""
        found: dict[str, int] = {}

        for ch in text:
            if ch in ZERO_WIDTH_CHARS:
                name = f"U+{ord(ch):04X} ({ZERO_WIDTH_CHARS[ch]})"
                found[name] = found.get(name, 0) + 1

        if not found:
            return None

        total = sum(found.values())
        examples = [f"{name}: {c}" for name, c in list(found.items())[:3]]

        severity = "high" if total >= 5 else "medium"

        return SmellcheckFlag(
            category="零宽字符",
            severity=severity,
            description=f"检测到 {total} 个零宽/不可见字符: {'; '.join(examples)}。"
                       f"这些字符可能来自富文本编辑器的复制粘贴或批量文本生成。",
            count=total,
        )

    # ===================================================================
    # C3: AI 热词密度
    # ===================================================================

    def _detect_buzzwords(self, text: str) -> SmellcheckFlag | None:
        """检测 AI 生成文本的高频热词"""
        text_lower = text.lower()
        found_buzzwords: dict[str, int] = {}

        for lang, words in AI_BUZZWORDS.items():
            for word in words:
                count = len(re.findall(re.escape(word), text_lower))
                if count > 0:
                    key = f"'{word}'" + ("[EN]" if lang == "en" else "[ZH]")
                    found_buzzwords[key] = count

        if not found_buzzwords:
            return None

        total = sum(found_buzzwords.values())
        top = sorted(found_buzzwords.items(), key=lambda x: x[1], reverse=True)[:5]
        top_str = "; ".join(f"{w}×{c}" for w, c in top)

        # 严重程度: 按总词数/文本长度
        text_words = len(re.findall(r'\w+', text))
        density = total / max(text_words, 1)
        severity = "high" if density > 0.03 else ("medium" if density > 0.015 else "low")

        return SmellcheckFlag(
            category="AI热词密度",
            severity=severity,
            description=f"检测到 {total} 个 AI 高频热词 (密度 {density:.2%}): {top_str}。"
                       f"这些词汇在 AI 生成文本中出现频率异常高。",
            count=total,
        )

    # ===================================================================
    # C4: 引号风格不一致
    # ===================================================================

    def _detect_quote_inconsistency(self, text: str) -> SmellcheckFlag | None:
        """检测引号风格混用 (弯引号 vs 直引号)"""
        smart_count = 0
        straight_count = 0
        quote_types: dict[str, int] = {}

        for ch in text:
            if ch in SMART_QUOTES:
                smart_count += 1
                name = unicodedata.name(ch, f'U+{ord(ch):04X}')
                quote_types[name] = quote_types.get(name, 0) + 1
            elif ch in ('"', "'"):
                straight_count += 1

        # 仅当两者都出现时才标记
        if smart_count == 0 or straight_count == 0:
            return None

        # 多风格混用
        if len(quote_types) >= 2 and straight_count > 0:
            return SmellcheckFlag(
                category="引␣风格混用",
                severity="low",
                description=f"检测到 {len(quote_types)} 种弯引号 + {straight_count} 处直引号混用。"
                           f"这可能来自AI模型从不同来源拼接内容。",
                count=smart_count + straight_count,
            )

        return None

    # ===================================================================
    # C5: 破折号一致性
    # ===================================================================

    def _detect_dash_inconsistency(self, text: str) -> SmellcheckFlag | None:
        """检测多种破折号/连字符混用"""
        dash_counts: dict[str, int] = {}

        for ch in text:
            if ch in DASH_TYPES:
                name = DASH_TYPES[ch]
                dash_counts[name] = dash_counts.get(name, 0) + 1

        dash_types_used = len(dash_counts)

        if dash_types_used < 2:
            return None

        # 3种以上 → 异常
        severity = "medium" if dash_types_used >= 3 else "low"
        examples = [f"{name}: {c}" for name, c in list(dash_counts.items())[:4]]

        return SmellcheckFlag(
            category="破折号一致性",
            severity=severity,
            description=f"检测到 {dash_types_used} 种不同破折号/连字符混用: {'; '.join(examples)}。"
                       f"人类通常只使用1-2种。AI生成文本可能混用多种。",
            count=sum(dash_counts.values()),
        )

    # ===================================================================
    # C6: 空白异常
    # ===================================================================

    def _detect_whitespace_anomalies(self, text: str) -> SmellcheckFlag | None:
        """检测空白字符异常"""
        anomalies: list[str] = []

        # 双空格
        double_spaces = len(re.findall(r'  +', text))
        if double_spaces > 2:
            anomalies.append(f"{double_spaces} 处连续空格")

        # 制表符-空格混用
        has_tabs = '\t' in text
        has_spaces_for_indent = bool(re.search(r'(?:\n|^)  +', text))
        if has_tabs and has_spaces_for_indent:
            anomalies.append("制表符与空格缩进混用")

        # 行尾空格
        trailing = len(re.findall(r' +\n', text))
        if trailing > 2:
            anomalies.append(f"{trailing} 处行尾空格")

        # 全角/半角空格混用
        has_fullwidth = '　' in text
        has_regular = ' ' in text
        if has_fullwidth and has_regular:
            anomalies.append("全角空格(U+3000)与半角空格混用")

        if not anomalies:
            return None

        severity = "low"
        if len(anomalies) >= 3:
            severity = "medium"

        return SmellcheckFlag(
            category="空白异常",
            severity=severity,
            description=f"空白字符异常: {'; '.join(anomalies)}。"
                       f"这在AI生成或自动化内容中更常见。",
            count=len(anomalies),
        )

    # ===================================================================
    # C7: 控制字符
    # ===================================================================

    def _detect_control_chars(self, text: str) -> SmellcheckFlag | None:
        """检测不可打印控制字符 (排除常见空白)"""
        control_chars: dict[str, int] = {}

        for ch in text:
            cp = ord(ch)
            # 检查控制字符 (排除 \t \n \r)
            if ch not in ('\t', '\n', '\r') and (
                (0 <= cp <= 31) or (127 <= cp <= 159)
            ):
                name = f"U+{cp:04X}"
                control_chars[name] = control_chars.get(name, 0) + 1

        if not control_chars:
            return None

        total = sum(control_chars.values())
        examples = [f"{name}×{c}" for name, c in list(control_chars.items())[:3]]

        severity = "high" if total >= 3 else "medium"

        return SmellcheckFlag(
            category="控制字符",
            severity=severity,
            description=f"检测到 {total} 个不可打印控制字符: {'; '.join(examples)}。"
                       f"这些控制字符来自非标准文本处理流程。",
            count=total,
        )

    # ===================================================================
    # C8: RTL/bidi 覆盖攻击
    # ===================================================================

    def _detect_rtl_override(self, text: str) -> SmellcheckFlag | None:
        """检测 RTL/bidi 方向控制字符 (可能的安全风险)"""
        found: dict[str, int] = {}

        for ch in text:
            if ch in RTL_OVERRIDE_CHARS:
                name = f"U+{ord(ch):04X} ({RTL_OVERRIDE_CHARS[ch]})"
                found[name] = found.get(name, 0) + 1

        if not found:
            return None

        total = sum(found.values())
        examples = [f"{name}: {c}" for name, c in list(found.items())[:3]]

        return SmellcheckFlag(
            category="RTL覆盖字符",
            severity="high",
            description=f"检测到 {total} 个 Unicode 方向控制字符: {'; '.join(examples)}。"
                       f"⚠ 这些字符可用于 bidi 攻击，改变文本视觉呈现顺序。",
            count=total,
        )

    # ===================================================================
    # 摘要与建议
    # ===================================================================

    @staticmethod
    def _build_summary(result: SmellcheckResult) -> str:
        """生成摘要"""
        if result.total_flags == 0:
            return "未检测到 AI 文本静态指纹。文本在字符层面表现自然。"

        parts = [
            f"检测到 {result.total_flags} 个静态指纹异常 ({result.categories_triggered}/8 类别触发)",
        ]

        if result.high_severity_count > 0:
            parts.append(f"{result.high_severity_count} 个高危标记")

        parts.append(f"综合异常评分: {result.anomaly_score:.0f}/100")

        return " | ".join(parts)

    @staticmethod
    def _build_recommendations(result: SmellcheckResult) -> list[str]:
        """生成建议"""
        recs: list[str] = []
        if result.total_flags == 0:
            return recs

        if result.high_severity_count > 0:
            recs.append("[高危] 存在高风险AI指纹。建议人工核查内容来源。")

        high_flags = [f for f in result.flags if f.severity == "high"]
        for f in high_flags[:3]:
            recs.append(f"[{f.category}] {f.description[:120]}")

        if result.anomaly_score > 50:
            recs.append("[综合] 多个指纹异常高度提示文本可能由 AI 自动生成。这仅是信号，需要结合内容分析。")
        elif result.anomaly_score > 25:
            recs.append("[综合] 存在一定程度的静态指纹异常。建议配合 lmscan 统计特征进行交叉验证。")

        return recs
