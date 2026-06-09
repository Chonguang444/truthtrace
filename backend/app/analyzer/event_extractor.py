"""
事件提取器 — 从文本中提取 5W1H 事件要素
Who, What, When, Where, Why, How
"""

import re
from datetime import datetime
from collections import Counter

import jieba
import jieba.analyse
from loguru import logger


class EventExtractor:
    """从文本中提取结构化事件信息"""

    # 时间词模式
    TIME_PATTERNS = [
        r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)',
        r'(\d{1,2}月\d{1,2}[日号])',
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
        r'(今天|昨天|前天|本周|上周|本月|上月|今年|去年)',
        r'(\d+小时前|\d+分钟前|\d+天前)',
    ]

    # 地点模式（常见中国地名后缀）
    LOCATION_SUFFIX = r'(省|市|县|区|镇|村|街道|路|广场|大厦|机场|火车站|医院|学校|大学|公司)'

    # 事件触发词
    EVENT_TRIGGERS = {
        '发生', '爆发', '出现', '宣布', '发布', '报道', '曝光', '揭露',
        '证实', '否认', '回应', '通报', '公告', '声明', '举报', '投诉',
        '事故', '事件', '案件', '灾难', '抗议', '示威', '选举', '投票',
        '上市', '收购', '融资', '倒闭', '裁员', '涨价', '降价',
        '感染', '确诊', '死亡', '治愈', '疫苗', '疫情',
        '地震', '洪水', '台风', '火灾', '爆炸', '坠毁', '失踪',
    }

    def __init__(self):
        # 加载 jieba 分词
        jieba.initialize()

    async def extract(self, text: str, title: str | None = None) -> dict:
        """
        从文本提取事件

        Args:
            text: 正文内容
            title: 可选标题

        Returns:
            {
                "title": 事件标题,
                "summary": 事件摘要,
                "when": 发生时间,
                "where": 发生地点,
                "who": 涉及人物/组织,
                "what": 事件内容,
                "why": 原因/背景,
                "keywords": 关键词列表
            }
        """
        if title:
            full_text = f"{title}\n{text}"
        else:
            full_text = text

        if not full_text.strip():
            return {"title": "", "summary": "", "keywords": []}

        # 提取关键词
        keywords = jieba.analyse.extract_tags(full_text, topK=15)

        # 提取时间
        when = self._extract_time(full_text)

        # 提取地点
        where = self._extract_location(full_text)

        # 提取人物/组织
        who = self._extract_entities(full_text)

        # 提取事件摘要
        summary = self._generate_summary(full_text, title)

        # 尝试推断原因
        why = self._extract_reason(full_text)

        return {
            "title": title or self._generate_title(full_text),
            "summary": summary,
            "when": when,
            "where": where,
            "who": who,
            "what": summary,
            "why": why,
            "keywords": keywords,
        }

    def _extract_time(self, text: str) -> str:
        """提取时间信息"""
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    def _extract_location(self, text: str) -> list[str]:
        """提取地点信息"""
        locations = []

        # 匹配含地名后缀的词
        pattern = re.compile(r'[一-鿿]{2,}' + self.LOCATION_SUFFIX)
        matches = pattern.findall(text)

        seen = set()
        for m in matches:
            if m not in seen:
                locations.append(m)
                seen.add(m)

        return locations[:10]

    def _extract_entities(self, text: str) -> list[str]:
        """提取人物/组织实体（简单规则版本）"""
        entities = []

        # 匹配 "XX表示", "XX称", "XX发布" 等发言模式
        speaker_pattern = re.compile(
            r'([一-鿿]{2,8})(表示|称|说|指出|强调|发布|声明|回应|告诉|介绍|透露)'
        )
        matches = speaker_pattern.findall(text)
        for m in matches:
            name = m[0]
            if name not in entities and not self._is_common_word(name):
                entities.append(name)

        # 匹配组织名
        org_pattern = re.compile(
            r'([一-鿿]{2,20}(公司|集团|部门|委员会|中心|机构|组织|协会|基金会|政府|局|厅|处|队|网|报|社|台|大学|学院|医院|银行|保险|证券))'
        )
        org_matches = org_pattern.findall(text)
        for m in org_matches:
            org_name = m[0]
            if org_name not in entities:
                entities.append(org_name)

        return entities[:15]

    def _extract_reason(self, text: str) -> str:
        """提取原因/背景"""
        patterns = [
            r'(原因[是：:]\s*)([^。\n]{5,50})',
            r'(因[为]?\s*)([^，。\n]{5,50})',
            r'(据[悉称了解]\s*[,，]?\s*)([^。\n]{5,100})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(2).strip()
        return ""

    def _generate_title(self, text: str, max_len: int = 100) -> str:
        """从文本生成标题"""
        # 取第一句话作为标题（或前100字）
        first_sentence = re.split(r'[。！？\n]', text.strip())[0]
        if len(first_sentence) > max_len:
            first_sentence = first_sentence[:max_len] + "..."
        return first_sentence.strip()

    def _generate_summary(self, text: str, title: str | None = None) -> str:
        """生成事件摘要"""
        # 使用 TextRank 提取关键句
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if not sentences:
            return text[:500]

        # 找包含事件触发词的句子
        event_sentences = []
        for s in sentences:
            if any(trigger in s for trigger in self.EVENT_TRIGGERS):
                event_sentences.append(s)

        # 取前 3 个关键句作为摘要
        summary_sentences = (event_sentences or sentences)[:3]
        summary = "。".join(summary_sentences)

        if len(summary) > 500:
            summary = summary[:500] + "..."

        return summary

    def _is_common_word(self, word: str) -> bool:
        """判断是否为常见词（非实体）"""
        common_words = {
            "我们", "他们", "你们", "大家", "自己", "什么", "怎么", "为什么",
            "可以", "可能", "应该", "已经", "还是", "这个", "那个", "如果",
            "虽然", "但是", "因为", "所以", "不过", "而且", "然后",
        }
        return word in common_words
