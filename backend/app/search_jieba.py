"""
Jieba 分词搜索增强 (SQLite 兼容)

在 SQLite 模式下，用 jieba 分词替代 PostgreSQL tsvector，
实现中文分词级别的搜索匹配。

原理:
1. 对查询词进行 jieba 分词
2. 对索引内容(标题/摘要)进行 jieba 分词
3. 将分词结果作为 JSON 关键词存储
4. 搜索时匹配单个分词 token，而非整句模糊匹配

效果对比:
- 旧: ILIKE "%食品安全%" — 只能匹配完整短语
- 新: token "食品" OR token "安全" — 分词后的灵活匹配
"""

import logging

logger = logging.getLogger("truthtrace.search_jieba")

try:
    import jieba
    _JIEBA_OK = True
except ImportError:
    _JIEBA_OK = False
    logger.warning("jieba 未安装，搜索将使用 ILIKE 回退模式")


def tokenize(text: str, max_tokens: int = 15) -> list[str]:
    """Jieba 分词，返回有意义的 token 列表"""
    if not text or not _JIEBA_OK:
        return text.split()[:max_tokens] if text else []

    # 精确模式分词
    tokens = [w.strip() for w in jieba.cut(text) if len(w.strip()) > 1]
    # 过滤停用词
    stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
    tokens = [t for t in tokens if t not in stopwords]

    return tokens[:max_tokens]


def build_search_conditions(query: str, title_col, summary_col, keywords_col) -> list:
    """
    构建基于 jieba 分词的搜索条件 (用于 SQLite)。

    同时保留原始 ILIKE 作为回退，
    确保单字搜索也能工作。
    """
    conditions = []

    # 1. Jieba 分词精确匹配
    tokens = tokenize(query)
    if tokens:
        for token in tokens:
            conditions.append(title_col.ilike(f"%{token}%"))
            conditions.append(summary_col.ilike(f"%{token}%"))
            conditions.append(
                keywords_col.cast(type(keywords_col.type)).ilike(f"%{token}%")
            )

    # 2. 原始 ILIKE 回退 (处理单字、英文、未分词情况)
    conditions.append(title_col.ilike(f"%{query}%"))
    conditions.append(summary_col.ilike(f"%{query}%"))

    return conditions
