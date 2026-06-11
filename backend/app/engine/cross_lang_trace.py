"""
多语言溯源引擎

基于B站视频2/3/5揭示的缺口: 许多谣言涉及跨国信息(UNESCO/乌克兰/俄罗斯)，
单语言搜索无法验证。

自动将查询翻译为目标语言，在多个语言的源中并行搜索。
"""
import re
from dataclasses import dataclass, field


# =============================================================================
# 多语言搜索模板
# =============================================================================

CROSS_LANG_SEARCH_TEMPLATES = {
    "zh": {
        "debunk_suffixes": [" 辟谣", " 真相", " 假的", " 谣言"],
        "fact_check_sites": ["新华社", "人民日报", "央视新闻", "澎湃新闻", "中国食品报融媒体"],
    },
    "en": {
        "debunk_suffixes": [" debunked", " fact check", " hoax", " debunk", " myth", " truth"],
        "fact_check_sites": ["snopes.com", "factcheck.org", "politifact.com", "fullfact.org", "reuters.com/fact-check"],
    },
    "ja": {
        "debunk_suffixes": [" デマ", " 嘘", " 検証", " ファクトチェック"],
        "fact_check_sites": ["factcheckcenter.jp", "nhk.or.jp", "mainichi.jp"],
    },
    "ko": {
        "debunk_suffixes": [" 루머", " 가짜뉴스", " 팩트체크", " 진실"],
        "fact_check_sites": ["snufactcheck.org", "factcheck.kr", "kbs.co.kr"],
    },
}


# =============================================================================
# 查询翻译 (简化版 — 基于常见术语映射)
# =============================================================================

CROSS_LANG_TERMS = {
    "zh→en": {
        "谣言": "rumor", "溯源": "trace", "辟谣": "debunk",
        "真相": "truth", "虚假": "fake", "事实核查": "fact check",
        "证据": "evidence", "来源": "source", "假新闻": "fake news",
        "致癌": "cancer", "有毒": "toxic", "疫苗": "vaccine",
        "食品安全": "food safety", "辐射": "radiation", "5G": "5G",
    },
    "zh→ja": {
        "谣言": "デマ", "溯源": "追跡", "辟谣": "検証",
        "真相": "真実", "虚假": "偽", "事实核查": "ファクトチェック",
        "证据": "証拠", "来源": "出典", "假新闻": "フェイクニュース",
    },
    "zh→ko": {
        "谣言": "루머", "溯源": "추적", "辟谣": "해명",
        "真相": "진실", "虚假": "가짜", "事实核查": "팩트체크",
        "假新闻": "가짜뉴스", "疫苗": "백신", "辐射": "방사선",
    },
}


@dataclass
class CrossLangQuery:
    original: str = ""
    translated: str = ""
    language: str = ""
    debunk_queries: list[str] = field(default_factory=list)
    fact_check_urls: list[str] = field(default_factory=list)


@dataclass
class CrossLangTraceResult:
    query: str = ""
    languages_searched: list[str] = field(default_factory=list)
    queries_generated: list[CrossLangQuery] = field(default_factory=list)
    potential_external_sources: list[dict] = field(default_factory=list)
    search_links: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "languages_searched": self.languages_searched,
            "queries_generated": len(self.queries_generated),
            "potential_external_sources": self.potential_external_sources[:10],
            "search_links": self.search_links[:10],
        }


def generate_cross_lang_queries(
    query_zh: str,
    target_languages: list[str] | None = None,
) -> CrossLangTraceResult:
    """
    为中文查询生成多语言搜索查询。

    Args:
        query_zh: 中文查询文本
        target_languages: 目标语言列表 (默认: ["en", "ja", "ko"])

    Returns:
        多语言查询列表 + 外部搜索链接
    """
    target_languages = target_languages or ["en", "ja", "ko"]
    result = CrossLangTraceResult(
        query=query_zh,
        languages_searched=target_languages,
    )

    for lang in target_languages:
        mapping_key = f"zh→{lang}"
        term_map = CROSS_LANG_TERMS.get(mapping_key, {})
        templates = CROSS_LANG_SEARCH_TEMPLATES.get(lang, {})

        # 翻译核心术语
        translated = query_zh
        for zh_term, lang_term in term_map.items():
            if zh_term in query_zh:
                translated = translated.replace(zh_term, lang_term)

        # 生成搜索查询
        debunk_queries = []
        for suffix in templates.get("debunk_suffixes", []):
            debunk_queries.append(f"{translated}{suffix}")

        # 生成事实核查网站搜索链接
        fact_check_urls = []
        for site in templates.get("fact_check_sites", []):
            fact_check_urls.append(f"site:{site} {translated}")

        query_obj = CrossLangQuery(
            original=query_zh,
            translated=translated,
            language=lang,
            debunk_queries=debunk_queries,
            fact_check_urls=fact_check_urls,
        )
        result.queries_generated.append(query_obj)

        # 生成外部搜索链接
        result.potential_external_sources.extend([
            {
                "language": lang,
                "query": translated,
                "description": f"在{lang}语言源中搜索'{translated}'",
            }
        ])
        for site_url in fact_check_urls:
            result.search_links.append({
                "language": lang,
                "google_search": f"https://www.google.com/search?q={site_url}",
                "description": f"{lang}: {site_url}",
            })

    return result


def detect_international_claim(content_text: str) -> dict:
    """检测文本是否涉及需要跨国溯源的主张"""
    international_markers = {
        "UNESCO": {"type": "heritage", "website": "https://www.unesco.org"},
        "联合国": {"type": "un", "website": "https://www.un.org"},
        "WHO": {"type": "health", "website": "https://www.who.int"},
        "世界卫生组织": {"type": "health", "website": "https://www.who.int"},
        "FDA": {"type": "health", "website": "https://www.fda.gov"},
        "欧盟": {"type": "regulation", "website": "https://europa.eu"},
        "俄罗斯": {"type": "country", "website": ""},
        "美国": {"type": "country", "website": ""},
        "日本": {"type": "country", "website": ""},
        "韩国": {"type": "country", "website": ""},
        "IARC": {"type": "research", "website": "https://www.iarc.who.int"},
        "Nature": {"type": "journal", "website": "https://www.nature.com"},
        "Science": {"type": "journal", "website": "https://www.science.org"},
        "Lancet": {"type": "journal", "website": "https://www.thelancet.com"},
        "柳叶刀": {"type": "journal", "website": "https://www.thelancet.com"},
        "乌克兰": {"type": "country", "website": ""},
        "香港": {"type": "region", "website": ""},
        "台湾": {"type": "region", "website": ""},
        "日本文部科学省": {"type": "gov", "website": ""},
    }

    found = []
    langs_needed = set()
    for marker, info in international_markers.items():
        if marker in content_text:
            found.append({"entity": marker, **info})
            if info["type"] in ("country", "heritage", "un", "gov"):
                langs_needed.add("en")
            if marker in ("日本", "日本文部科学省"):
                langs_needed.add("ja")
            if marker in ("韩国",):
                langs_needed.add("ko")

    return {
        "international_entities_found": found[:10],
        "languages_recommended": list(langs_needed) if langs_needed else ["en"],
        "recommend_cross_lang_trace": len(found) > 0,
        "cross_lang_queries": (
            generate_cross_lang_queries(content_text[:200], list(langs_needed)).to_dict()
            if langs_needed else None
        ),
    }
