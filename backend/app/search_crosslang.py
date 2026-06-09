"""
跨语言搜索支持 — 中文/英文双向检索

原理: 关键词 JSON 字段 (events.keywords) 同时存储中英文标签，
搜索时中英文查询词都会被匹配。
"""

# 中英文关键词对照表 (核心领域高频词汇)
# 当事件被索引时，自动补充另一语言的对应词
CROSSLANG_MAP = {
    # 食品安全
    "致癌": "carcinogenic",
    "有毒": "toxic",
    "添加剂": "food additive",
    "食品安全": "food safety",
    "防腐剂": "preservative",
    "甜味剂": "sweetener",
    "阿斯巴甜": "aspartame",
    "转基因": "GMO",
    "农药": "pesticide",
    "蔬菜": "vegetable",
    "水果": "fruit",
    "肉类": "meat",
    "牛奶": "milk",
    "食品": "food",
    # 医疗
    "疫苗": "vaccine",
    "癌症": "cancer",
    "药": "drug",
    "副作用": "side effect",
    "临床试验": "clinical trial",
    # 经济
    "经济": "economy",
    "房价": "housing price",
    "股市": "stock market",
    "GDP": "GDP",
    "通胀": "inflation",
    "就业": "employment",
    # 环境
    "污染": "pollution",
    "气候": "climate",
    "碳排放": "carbon emission",
    "核废水": "nuclear wastewater",
    # 技术
    "人工智能": "AI",
    "5G": "5G",
    "芯片": "chip",
    # 社会
    "谣言": "rumor",
    "辟谣": "debunk",
    "恐慌": "panic",
    "虚假": "fake",
}


def expand_query_crosslang(query: str) -> str:
    """
    将中文查询词扩展为也包含英文对应词，反之亦然。
    例如: "cancer" → "cancer 癌症 致癌"
    """
    expanded = {query.lower()}

    for zh, en in CROSSLANG_MAP.items():
        if query.lower() in (zh.lower(), en.lower()):
            expanded.add(zh.lower())
            expanded.add(en.lower())

    return " ".join(expanded)


def enrich_keywords_crosslang(keywords: list[str]) -> list[str]:
    """
    为已有关键词列表补充跨语言对应词。
    例如: ["致癌", "添加剂"] → ["致癌", "添加剂", "carcinogenic", "food additive"]
    """
    enriched = list(keywords)
    for kw in keywords:
        for zh, en in CROSSLANG_MAP.items():
            if kw == zh and en not in enriched:
                enriched.append(en)
            elif kw == en and zh not in enriched:
                enriched.append(zh)
    return enriched
