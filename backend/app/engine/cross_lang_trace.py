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
        "debunk_suffixes": [" 辟谣", " 真相", " 假的", " 谣言", " 核实", " 求证"],
        "fact_check_sites": [
            "新华社", "人民日报", "央视新闻", "澎湃新闻", "中国食品报融媒体",
            "中国互联网联合辟谣平台", "科学辟谣", "腾讯较真", "上海网络辟谣",
        ],
    },
    "en": {
        "debunk_suffixes": [" debunked", " fact check", " hoax", " debunk", " myth", " truth"],
        "fact_check_sites": [
            "snopes.com", "factcheck.org", "politifact.com", "fullfact.org",
            "reuters.com/fact-check", "apnews.com/hub/ap-fact-check",
            "bbc.com/news/reality_check", "factcheck.afp.com",
        ],
    },
    "ja": {
        "debunk_suffixes": [" デマ", " 嘘", " 検証", " ファクトチェック", " 誤情報", " 真相"],
        "fact_check_sites": [
            "factcheckcenter.jp", "nhk.or.jp", "mainichi.jp",
            "buzzfeed.com/jp/factcheck", "asahi.com",
        ],
    },
    "ko": {
        "debunk_suffixes": [" 루머", " 가짜뉴스", " 팩트체크", " 진실", " 허위", " 검증"],
        "fact_check_sites": [
            "snufactcheck.org", "factcheck.kr", "kbs.co.kr",
            "newstapa.org", "jtbc.co.kr",
        ],
    },
    "fr": {
        "debunk_suffixes": [" debunké", " fact-checking", " intox", " vérification", " désinformation", " rumeur"],
        "fact_check_sites": [
            "factuel.afp.com", "lemonde.fr/les-decodeurs", "liberation.fr/desintox",
            "20minutes.fr/fake-off", "france24.com/fr/info-verifiee",
        ],
    },
    "de": {
        "debunk_suffixes": [" entlarvt", " Faktencheck", " widerlegt", " Desinformation", " Falschmeldung"],
        "fact_check_sites": [
            "correctiv.org", "mimikama.at", "dpa-factchecking.com",
            "br.de/nachrichten/faktencheck", "tagesschau.de/faktenfinder",
        ],
    },
    "es": {
        "debunk_suffixes": [" desmentido", " verificación", " bulo", " desinformación", " fake", " engaño"],
        "fact_check_sites": [
            "maldita.es", "newtral.es", "factual.afp.com",
            "verificat.cat", "chequeado.com",
        ],
    },
    "ar": {
        "debunk_suffixes": [" تكذيب", " تدقيق", " إشاعة", " حقيقة", " تزييف"],
        "fact_check_sites": [
            "factcheckarabia.com", "misbar.com", "fatabyyano.net",
            "verify.com.jo", "aljazeera.net",
        ],
    },
    "ru": {
        "debunk_suffixes": [" разоблачение", " фейк", " проверка", " дезинформация", " опровержение"],
        "fact_check_sites": [
            "provereno.media", "factcheck.kz", "theins.ru",
            "tass.ru/proverka", "stopfake.org",
        ],
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
        "转基因": "GMO", "添加剂": "additive", "副作用": "side effect",
        "激素": "hormone", "抗生素": "antibiotic", "重金属": "heavy metal",
        "农药": "pesticide", "塑料": "plastic", "微塑料": "microplastic",
        "污染": "contamination", "核废水": "nuclear wastewater",
        "地沟油": "gutter oil", "假药": "fake medicine",
        "新冠病毒": "COVID-19", "阴谋论": "conspiracy theory",
        "实验": "experiment", "论文": "paper", "研究": "study",
        "科学家": "scientist", "专家": "expert", "医生": "doctor",
        "法院": "court", "政府": "government", "警察": "police",
        "死亡": "death", "住院": "hospitalization", "爆发": "outbreak",
        "禁止": "banned", "召回": "recall", "警告": "warning",
        "泄露": "leaked", "秘密": "secret", "揭露": "expose",
    },
    "zh→ja": {
        "谣言": "デマ", "溯源": "追跡", "辟谣": "検証",
        "真相": "真実", "虚假": "偽", "事实核查": "ファクトチェック",
        "证据": "証拠", "来源": "出典", "假新闻": "フェイクニュース",
        "致癌": "発がん性", "有毒": "有毒", "疫苗": "ワクチン",
        "食品安全": "食品安全", "辐射": "放射線", "5G": "5G",
        "转基因": "遺伝子組み換え", "添加剂": "添加物",
        "副作用": "副作用", "阴谋论": "陰謀論",
        "核废水": "処理水", "新冠病毒": "新型コロナ",
        "科学家": "科学者", "政府": "政府", "禁止": "禁止",
        "死亡": "死亡", "警告": "警告",
    },
    "zh→ko": {
        "谣言": "루머", "溯源": "추적", "辟谣": "해명",
        "真相": "진실", "虚假": "가짜", "事实核查": "팩트체크",
        "假新闻": "가짜뉴스", "疫苗": "백신", "辐射": "방사선",
        "致癌": "발암", "有毒": "유독", "食品安全": "식품안전",
        "证据": "증거", "来源": "출처", "转基因": "GMO",
        "添加剂": "첨가물", "副作用": "부작용", "阴谋论": "음모론",
        "核废水": "오염수", "新冠病毒": "코로나19",
        "科学家": "과학자", "政府": "정부", "禁止": "금지",
        "死亡": "사망", "实验": "실험", "秘密": "비밀",
    },
    "zh→fr": {
        "谣言": "rumeur", "溯源": "traçage", "辟谣": "démenti",
        "真相": "vérité", "虚假": "faux", "事实核查": "fact-checking",
        "证据": "preuve", "来源": "source", "假新闻": "fausse information",
        "致癌": "cancérigène", "有毒": "toxique", "疫苗": "vaccin",
        "食品安全": "sécurité alimentaire", "辐射": "radiation",
        "新冠病毒": "COVID-19", "阴谋论": "théorie du complot",
        "核废水": "eaux contaminées", "实验": "expérience",
        "科学家": "scientifique", "政府": "gouvernement",
    },
    "zh→de": {
        "谣言": "Gerücht", "溯源": "Rückverfolgung", "辟谣": "Widerlegung",
        "真相": "Wahrheit", "虚假": "Falsch", "事实核查": "Faktencheck",
        "证据": "Beweis", "来源": "Quelle", "假新闻": "Fake News",
        "致癌": "krebserregend", "有毒": "giftig", "疫苗": "Impfstoff",
        "食品安全": "Lebensmittelsicherheit", "辐射": "Strahlung",
        "新冠病毒": "COVID-19", "阴谋论": "Verschwörungstheorie",
        "科学家": "Wissenschaftler", "政府": "Regierung",
    },
    "zh→es": {
        "谣言": "rumor", "溯源": "rastreo", "辟谣": "desmentido",
        "真相": "verdad", "虚假": "falso", "事实核查": "verificación",
        "证据": "evidencia", "来源": "fuente", "假新闻": "noticias falsas",
        "致癌": "cancerígeno", "有毒": "tóxico", "疫苗": "vacuna",
        "食品安全": "seguridad alimentaria", "辐射": "radiación",
        "新冠病毒": "COVID-19", "阴谋论": "teoría de conspiración",
        "科学家": "científico", "政府": "gobierno",
    },
    "zh→ar": {
        "谣言": "إشاعة", "溯源": "تتبع", "辟谣": "تكذيب",
        "真相": "حقيقة", "虚假": "مزيف", "事实核查": "تدقيق",
        "证据": "دليل", "来源": "مصدر", "假新闻": "أخبار كاذبة",
        "疫苗": "لقاح", "食品安全": "سلامة الغذاء",
        "新冠病毒": "كوفيد-19", "阴谋论": "نظرية المؤامرة",
        "科学家": "عالم", "政府": "حكومة",
    },
    "zh→ru": {
        "谣言": "слух", "溯源": "отслеживание", "辟谣": "опровержение",
        "真相": "правда", "虚假": "фейк", "事实核查": "фактчекинг",
        "证据": "доказательство", "来源": "источник", "假新闻": "фейковые новости",
        "致癌": "канцероген", "有毒": "токсичный", "疫苗": "вакцина",
        "食品安全": "безопасность продуктов", "辐射": "радиация",
        "新冠病毒": "COVID-19", "阴谋论": "теория заговора",
        "科学家": "учёный", "政府": "правительство",
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
    query_text: str,
    target_languages: list[str] | None = None,
    source_language: str = "zh",
) -> CrossLangTraceResult:
    """
    为查询文本生成多语言搜索查询。

    Args:
        query_text: 查询文本（任意语言）
        target_languages: 目标语言列表 (默认: ["en", "ja", "ko", "fr", "de"])
        source_language: 源语言 (默认 "zh")

    Returns:
        多语言查询列表 + 外部搜索链接
    """
    target_languages = target_languages or ["en", "ja", "ko", "fr", "de"]
    result = CrossLangTraceResult(
        query=query_text,
        languages_searched=target_languages,
    )

    for lang in target_languages:
        if lang == source_language:
            continue  # Skip same-language search

        mapping_key = f"{source_language}→{lang}"
        term_map = CROSS_LANG_TERMS.get(mapping_key, {})
        templates = CROSS_LANG_SEARCH_TEMPLATES.get(lang, {})

        # Translate core terms
        translated = query_text
        for src_term, lang_term in term_map.items():
            if src_term in query_text:
                translated = translated.replace(src_term, lang_term)

        # Fallback: if no terms translated and source != lang, keep original
        if translated == query_text and source_language != lang:
            # At minimum, append language-appropriate debunk suffixes
            pass

        # Generate search queries with debunk suffixes
        debunk_queries = []
        for suffix in templates.get("debunk_suffixes", []):
            debunk_queries.append(f"{translated}{suffix}")

        # Generate fact-check site search links
        fact_check_urls = []
        for site in templates.get("fact_check_sites", []):
            fact_check_urls.append(f"site:{site} {translated}")

        query_obj = CrossLangQuery(
            original=query_text,
            translated=translated,
            language=lang,
            debunk_queries=debunk_queries,
            fact_check_urls=fact_check_urls,
        )
        result.queries_generated.append(query_obj)

        # Generate external search links
        result.potential_external_sources.extend([
            {
                "language": lang,
                "query": translated,
                "description": f"Search in {lang} sources for '{translated[:80]}'",
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
        # UN / International
        "UNESCO": {"type": "heritage", "website": "https://www.unesco.org"},
        "联合国": {"type": "un", "website": "https://www.un.org"},
        "WHO": {"type": "health", "website": "https://www.who.int"},
        "世界卫生组织": {"type": "health", "website": "https://www.who.int"},
        "WTO": {"type": "trade", "website": "https://www.wto.org"},
        "IMF": {"type": "finance", "website": "https://www.imf.org"},
        "UNICEF": {"type": "children", "website": "https://www.unicef.org"},
        # Health / Science
        "FDA": {"type": "health", "website": "https://www.fda.gov"},
        "CDC": {"type": "health", "website": "https://www.cdc.gov"},
        "NIH": {"type": "research", "website": "https://www.nih.gov"},
        "IARC": {"type": "research", "website": "https://www.iarc.who.int"},
        "EMA": {"type": "health", "website": "https://www.ema.europa.eu"},
        "EFSA": {"type": "food", "website": "https://www.efsa.europa.eu"},
        "NASA": {"type": "science", "website": "https://www.nasa.gov"},
        "CERN": {"type": "science", "website": "https://home.cern"},
        # Journals
        "Nature": {"type": "journal", "website": "https://www.nature.com"},
        "Science": {"type": "journal", "website": "https://www.science.org"},
        "Lancet": {"type": "journal", "website": "https://www.thelancet.com"},
        "柳叶刀": {"type": "journal", "website": "https://www.thelancet.com"},
        "NEJM": {"type": "journal", "website": "https://www.nejm.org"},
        "JAMA": {"type": "journal", "website": "https://jamanetwork.com"},
        "BMJ": {"type": "journal", "website": "https://www.bmj.com"},
        "Cell": {"type": "journal", "website": "https://www.cell.com"},
        "PNAS": {"type": "journal", "website": "https://www.pnas.org"},
        # Regulatory
        "欧盟": {"type": "regulation", "website": "https://europa.eu"},
        "European Commission": {"type": "regulation", "website": "https://ec.europa.eu"},
        "USDA": {"type": "food", "website": "https://www.usda.gov"},
        "EPA": {"type": "env", "website": "https://www.epa.gov"},
        "FCC": {"type": "telecom", "website": "https://www.fcc.gov"},
        # Countries
        "俄罗斯": {"type": "country", "website": ""},
        "美国": {"type": "country", "website": ""},
        "日本": {"type": "country", "website": ""},
        "韩国": {"type": "country", "website": ""},
        "英国": {"type": "country", "website": ""},
        "法国": {"type": "country", "website": ""},
        "德国": {"type": "country", "website": ""},
        "印度": {"type": "country", "website": ""},
        "澳大利亚": {"type": "country", "website": ""},
        "加拿大": {"type": "country", "website": ""},
        "巴西": {"type": "country", "website": ""},
        "乌克兰": {"type": "country", "website": ""},
        # Regions
        "香港": {"type": "region", "website": ""},
        "台湾": {"type": "region", "website": ""},
        "西藏": {"type": "region", "website": ""},
        "新疆": {"type": "region", "website": ""},
        # Government agencies (Japanese/Korean)
        "日本文部科学省": {"type": "gov", "website": ""},
        "厚生労働省": {"type": "gov", "website": ""},
        "食品安全委員会": {"type": "food", "website": ""},
        "식품의약품안전처": {"type": "food", "website": ""},
        "질병관리청": {"type": "health", "website": ""},
        # European
        "BfR": {"type": "risk", "website": "https://www.bfr.bund.de"},
        "ANSES": {"type": "food", "website": "https://www.anses.fr"},
        "RIVM": {"type": "health", "website": "https://www.rivm.nl"},
        # Middle East
        "الجزيرة": {"type": "media", "website": "https://www.aljazeera.net"},
        # Fact-checking orgs
        "Snopes": {"type": "factcheck", "website": "https://www.snopes.com"},
        "PolitiFact": {"type": "factcheck", "website": "https://www.politifact.com"},
    }

    found = []
    langs_needed = set()
    for marker, info in international_markers.items():
        if marker in content_text:
            found.append({"entity": marker, **info})
            if info["type"] in ("country", "heritage", "un", "gov", "regulation"):
                langs_needed.add("en")
            # Asia-Pacific languages
            if marker in ("日本", "日本文部科学省", "厚生労働省", "食品安全委員会"):
                langs_needed.add("ja")
            if marker in ("韩国", "식품의약품안전처", "질병관리청"):
                langs_needed.add("ko")
            # European languages
            if marker in ("法国", "ANSES", "欧盟", "European Commission", "EFSA", "EMA"):
                langs_needed.add("fr")
            if marker in ("德国", "BfR"):
                langs_needed.add("de")
            if marker in ("西班牙",):
                langs_needed.add("es")
            # Russian-speaking entities
            if marker in ("俄罗斯", "乌克兰"):
                langs_needed.add("ru")
            # Arabic-speaking entities
            if marker in ("الجزيرة",):
                langs_needed.add("ar")

    # Cross-language recommendations for markered entities
    langs_recommended = list(langs_needed) if langs_needed else ["en"]

    return {
        "international_entities_found": found[:15],
        "languages_recommended": langs_recommended,
        "recommend_cross_lang_trace": len(found) > 0,
        "cross_lang_queries": (
            generate_cross_lang_queries(content_text[:200], langs_recommended).to_dict()
            if langs_needed else None
        ),
    }


def detect_english_claim(content_text: str) -> dict:
    """
    Detect whether English-language content involves claims that need
    multi-language cross-tracing (reverse of detect_international_claim).

    This is for English-origin rumors that mention Chinese/Japanese/Korean/
    European entities and need to be cross-checked in those languages.
    """
    # English triggers that indicate need for non-English verification
    lang_triggers = {
        "zh": [
            "China", "Chinese", "Beijing", "Shanghai", "Wuhan", "CCP",
            "Tibet", "Xinjiang", "Hong Kong", "Taiwan", "WeChat", "Weibo",
            "Xinhua", "People's Daily", "Global Times",
        ],
        "ja": [
            "Japan", "Japanese", "Tokyo", "Osaka", "Fukushima", "NHK",
            "MEXT", "MHLW", "TEPCO",
        ],
        "ko": [
            "Korea", "Korean", "Seoul", "KCDC", "KDCA",
        ],
        "fr": [
            "France", "French", "Paris", "EU", "European Union",
            "Brussels", "ANSES", "Institut Pasteur",
        ],
        "de": [
            "Germany", "German", "Berlin", "BfR", "Robert Koch",
            "Deutsche Welle",
        ],
        "es": [
            "Spain", "Spanish", "Mexico", "Argentina", "Latin America",
        ],
        "ar": [
            "Arab", "Middle East", "Saudi Arabia", "UAE", "Dubai",
            "Al Jazeera", "Qatar",
        ],
        "ru": [
            "Russia", "Russian", "Moscow", "Kremlin", "Putin",
            "Sputnik", "RT",
        ],
    }

    langs_needed = set()
    found_entities = []

    for lang, triggers in lang_triggers.items():
        for trigger in triggers:
            if trigger.lower() in content_text.lower():
                langs_needed.add(lang)
                found_entities.append({"entity": trigger, "language": lang})

    # Also check for international org markers (from detect_international_claim)
    intl_markers = ["UNESCO", "WHO", "FDA", "CDC", "IARC", "WTO", "IMF"]
    for marker in intl_markers:
        if marker in content_text:
            found_entities.append({"entity": marker, "language": "en"})

    langs_recommended = list(langs_needed) if langs_needed else []

    return {
        "english_entities_found": found_entities[:15],
        "languages_recommended": langs_recommended,
        "recommend_cross_lang_trace": len(langs_needed) > 0,
        "cross_lang_queries": (
            generate_cross_lang_queries(
                content_text[:200], langs_recommended, source_language="en"
            ).to_dict()
            if langs_needed else None
        ),
    }
