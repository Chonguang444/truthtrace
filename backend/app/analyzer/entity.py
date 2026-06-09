"""
实体识别器 — 命名实体识别（NER）
支持中文人名、地名、机构名、时间等实体类型
"""

import re
import jieba
import jieba.posseg as pseg
from loguru import logger


class EntityRecognizer:
    """中文命名实体识别"""

    # 实体类型
    PERSON = "PERSON"         # 人物
    ORG = "ORG"              # 组织机构
    LOC = "LOC"              # 地点
    TIME = "TIME"            # 时间
    EVENT = "EVENT"          # 事件
    MISC = "MISC"            # 其他专名

    def __init__(self):
        jieba.initialize()
        # 加载地名词典
        self._load_dictionaries()

    async def extract(self, text: str) -> dict[str, list[str]]:
        """
        从文本中提取命名实体

        Returns:
            {
                "PERSON": ["张三", "李四"],
                "ORG": ["XX公司", "YY部门"],
                "LOC": ["北京", "上海"],
                "TIME": ["2024-01-01", "昨天"],
                "EVENT": ["XX事件"],
                "MISC": [...]
            }
        """
        if not text:
            return {"PERSON": [], "ORG": [], "LOC": [], "TIME": [], "EVENT": [], "MISC": []}

        entities = {
            "PERSON": [],
            "ORG": [],
            "LOC": [],
            "TIME": [],
            "EVENT": [],
            "MISC": [],
        }

        # 使用 jieba 词性标注
        words = pseg.cut(text)

        for word, flag in words:
            word = word.strip()
            if len(word) < 2:
                continue

            # 根据词性分类
            if flag == "nr":  # 人名
                entities[self.PERSON].append(word)
            elif flag == "ns":  # 地名
                entities[self.LOC].append(word)
            elif flag == "nt":  # 机构团体
                entities[self.ORG].append(word)
            elif flag == "t":  # 时间词
                entities[self.TIME].append(word)

        # 使用正则补充时间识别
        time_matches = re.findall(
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?|\d{1,2}月\d{1,2}[日号]|今天|昨天|前天|本周',
            text
        )
        entities[self.TIME].extend(time_matches)

        # 使用正则补充事件识别
        event_matches = re.findall(
            r'[一-鿿]{2,10}(事件|事故|案件|丑闻|危机|灾难|抗议|峰会|大会|发布会)',
            text
        )
        entities[self.EVENT].extend(event_matches)

        # 去重
        for key in entities:
            entities[key] = list(dict.fromkeys(entities[key]))

        return entities

    def _load_dictionaries(self):
        """加载自定义词典"""
        # 添加常见实体词以确保被正确识别
        custom_words = [
            # 机构
            ("国务院", "nt"), ("发改委", "nt"), ("卫健委", "nt"),
            ("教育部", "nt"), ("公安部", "nt"), ("外交部", "nt"),
            # 媒体
            ("新华社", "nt"), ("人民日报", "nt"), ("央视", "nt"),
            ("澎湃新闻", "nt"), ("新京报", "nt"),
            # 平台
            ("微博", "nt"), ("知乎", "nt"), ("抖音", "nt"), ("快手", "nt"),
        ]
        for word, flag in custom_words:
            jieba.add_word(word)
