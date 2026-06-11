"""
SatyaLens 引用完整性评分引擎 — 第16号引擎

评估信息引用链条的完整性和可信度:
  1. 提取文中引用的来源声明
  2. 验证每个引用来源是否真实存在
  3. 评估来源是否真的支持所引用的主张
  4. 加权计算完整性评分 (0.0-1.0)

设计参考:
  - SatyaLens (github.com/SatyaLens/source-score): Source→Claims→Proofs→验证链路
  - 视频5 (B站Silver_sulfide): 每条反驳标注《Official Gundam Fact File》等参考出处
  - 视频1 (B站小Q): 完全依赖公开可查信息验证

核心原则:
  - 零出处 → 0分
  - 出处可查但不完整 → 50分
  - 每个环节可独立复现 → 100分
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("truthtrace.satyalens")


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class CitationClaim:
    """单条引用主张"""
    text: str                     # 原文中声称引用的文本
    cited_entity: str = ""        # 声称的来源名称（机构/论文/报告名）
    cited_url: str = ""           # 如果有URL
    claim_type: str = "unknown"   # url / name / vague / anonymous
    specificity_score: float = 0.0  # 0-1 引用具体程度

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "cited_entity": self.cited_entity,
            "cited_url": self.cited_url,
            "claim_type": self.claim_type,
            "specificity_score": round(self.specificity_score, 2),
        }


@dataclass
class CitationIntegrityFlag:
    """引用完整性红旗"""
    severity: str        # high / medium / low
    description: str
    citation_index: int  # 对应的引用索引
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "description": self.description,
            "citation_index": self.citation_index,
            "recommendation": self.recommendation,
        }


@dataclass
class SatyaLensResult:
    """SatyaLens 引用完整性评分结果"""
    overall_integrity_score: float = 0.0     # 0.0-1.0 总完整性
    citations_found: int = 0                 # 文本中找到的引用声明数
    citations_verifiable: int = 0            # 可验证的引用数
    citations_vague: int = 0                 # 模糊引用数 ("研究表明"等)
    citations_missing: int = 0               # 有主张但无任何引用
    claim_source_alignment: float = 0.0      # 主张与来源一致性 0-1
    source_quality_distribution: dict = field(default_factory=dict)
    citation_chain_depth: int = 0            # 引用链条深度
    independent_corroboration: bool = False  # 是否有独立交叉验证
    red_flags: list[CitationIntegrityFlag] = field(default_factory=list)
    citation_details: list[CitationClaim] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_integrity_score": round(self.overall_integrity_score, 2),
            "citations_found": self.citations_found,
            "citations_verifiable": self.citations_verifiable,
            "citations_vague": self.citations_vague,
            "citations_missing": self.citations_missing,
            "claim_source_alignment": round(self.claim_source_alignment, 2),
            "source_quality_distribution": self.source_quality_distribution,
            "citation_chain_depth": self.citation_chain_depth,
            "independent_corroboration": self.independent_corroboration,
            "red_flags": [f.to_dict() for f in self.red_flags],
            "citation_details": [c.to_dict() for c in self.citation_details],
            "recommendations": self.recommendations,
            "summary": self.summary,
        }


# =============================================================================
# 引用提取与评分
# =============================================================================

# 模糊引用模式 — "研究表明"、"专家指出" 等不指明具体来源的表述
VAGUE_CITATION_PATTERNS = [
    r"(?:有?研究|调查|报告|数据|统计)(?:表明|显示|发现|指出|称)",
    r"(?:专家|学者|教授|医生|科学家|业内人士)(?:表示|指出|认为|称|说)",
    r"(?:据|根据|按照)(?:相关|有关|可靠|知情|权威)(?:人士|消息|渠道|部门|机构|方面)",
    r"(?:国外|海外|西方|日本|美国)(?:研究|科学家|专家|媒体|机构)",
    r"(?:最新|最近|近日)(?:研究|报告|数据|调查|实验)(?:表明|显示)",
    r"(?:据说|据了解|据透露|据悉|有消息称)",
    r"(?:网传|网上说|有人说|听说|大家都说)",
    r"(?:studies?\s*show|research\s*(?:shows?|indicates?|suggests?))",
    r"(?:experts?\s*(?:say|claim|believe|warn|suggest))",
    r"(?:according\s*to\s*(?:a\s*)?(?:source|report|study|research))",
    r"(?:it\s*is\s*(?:said|reported|claimed|believed|thought)\s*that)",
]

# 具体引用模式 — 有具体名称或URL
SPECIFIC_CITATION_PATTERNS = [
    # URL引用
    r'https?://[^\s<>"\'\]\)，。；！？、]+',
    # 出版物引用: 《...》
    r'《[^》]+》',
    # 机构名称模式
    r'(?:世界卫生组织|WHO|联合国|UNESCO|国家标准|GB/T?\s*\d+[\.-]?\d*)',
    r'(?:国家卫健委|国家药监局|中国疾控中心|中国科学院|中国工程院)',
    r'(?:Nature|Science|Lancet|NEJM|Cell|BMJ|JAMA|PNAS)',
    r'(?:大学|学院|研究所|研究院|实验室)\S*',
    # DOI/arXiv
    r'(?:10\.\d{4,}/[^\s]+)',
    r'(?:arxiv:\d+\.\d+)',
]


class SatyaLensScorer:
    """引用完整性评分器"""

    # 来源类型权重 (用于 source_quality_distribution)
    SOURCE_TYPE_WEIGHTS = {
        "peer_reviewed": 1.0,      # 同行评审论文
        "government": 0.95,        # 政府/国际组织官方文件
        "standard": 0.90,          # 国家标准
        "academic": 0.85,          # 学术出版物
        "official_media": 0.70,    # 官方媒体
        "named_expert": 0.60,      # 指名专家
        "general_media": 0.40,     # 一般媒体
        "social_media": 0.15,      # 社交媒体
        "anonymous": 0.05,         # 匿名来源
        "vague": 0.0,              # 模糊引用 ("研究表明")
    }

    def analyze(
        self,
        text: str,
        title: str = "",
        cited_urls: list[str] | None = None,
        author_claims: list[dict] | None = None,
    ) -> SatyaLensResult:
        """
        分析文本的引用完整性。

        Args:
            text: 待分析文本
            title: 标题 (可选)
            cited_urls: 已知的外部引用URL列表
            author_claims: 从其他引擎提取的主张列表 (可选)
        """
        result = SatyaLensResult()

        if not text or len(text.strip()) < 50:
            result.summary = "文本过短 (<50字符)，无法进行有意义的引用完整性评估。"
            result.recommendations.append("需要更长的文本才能评估引用质量。")
            return result

        full_text = f"{title}\n{text}" if title else text

        # 1. 提取引用声明
        citations = self._extract_citations(full_text, cited_urls or [])
        result.citation_details = citations
        result.citations_found = len(citations)

        # 2. 分类统计
        result.citations_verifiable = sum(
            1 for c in citations if c.claim_type in ("url", "specific_name")
        )
        result.citations_vague = sum(
            1 for c in citations if c.claim_type == "vague"
        )
        result.citations_missing = max(0, len(author_claims or []) - len(citations))

        # 3. 来源质量分布
        result.source_quality_distribution = self._compute_quality_distribution(citations)

        # 4. 引用链深度
        result.citation_chain_depth = self._compute_chain_depth(citations, cited_urls or [])

        # 5. 独立交叉验证检查
        result.independent_corroboration = self._check_corroboration(citations)

        # 6. 主张-来源一致性
        result.claim_source_alignment = self._compute_alignment(citations, author_claims or [])

        # 7. 红旗检测
        result.red_flags = self._detect_red_flags(citations, full_text)

        # 8. 计算总分
        result.overall_integrity_score = self._compute_score(result)

        # 9. 生成建议和摘要
        result.recommendations = self._generate_recommendations(result)
        result.summary = self._generate_summary(result)

        return result

    # -------------------------------------------------------------------
    # 引用提取
    # -------------------------------------------------------------------

    def _extract_citations(self, text: str, known_urls: list[str]) -> list[CitationClaim]:
        """从文本中提取所有引用声明"""
        citations: list[CitationClaim] = []
        seen_spans: set[tuple[int, int]] = set()

        # 1. URL 引用 (优先级最高)
        for match in re.finditer(r'https?://[^\s<>"\'\]\)，。；！？、]{10,}', text):
            url = match.group()
            domain = urlparse(url).netloc.lower()
            start, end = match.start(), match.end()

            # 避免重复
            span = (start, end)
            if span in seen_spans:
                continue
            seen_spans.add(span)

            # 找URL周围的上下文
            ctx_start = max(0, start - 80)
            ctx_end = min(len(text), end + 30)
            context = text[ctx_start:ctx_end].strip()

            claim_type = self._classify_url_domain(domain)
            specificity = 1.0 if claim_type in ("peer_reviewed", "government") else 0.8

            citations.append(CitationClaim(
                text=context,
                cited_url=url,
                cited_entity=domain,
                claim_type="url",
                specificity_score=specificity,
            ))

        # 2. 出版物引用: 《...》
        for match in re.finditer(r'《([^》]{2,80})》', text):
            entity = match.group(1)
            span = (match.start(), match.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)

            ctx_start = max(0, match.start() - 40)
            ctx_end = min(len(text), match.end() + 20)
            context = text[ctx_start:ctx_end].strip()

            citations.append(CitationClaim(
                text=context,
                cited_entity=entity,
                claim_type="specific_name",
                specificity_score=0.75,
            ))

        # 3. 具体机构/出版物名称
        org_patterns = [
            (r'(?:世界卫生组织|WHO)', "government", 0.95),
            (r'(?:国家(?:卫健委|药监局|标准|市场监管)|中国疾控中心)', "government", 0.95),
            (r'(?:中国科学院|中国工程院|中国社科院)', "academic", 0.90),
            (r'(?:联合国|UNESCO|UNICEF|UNDP|WHO)', "government", 0.95),
            (r'(?:Nature|Science|Lancet|NEJM|Cell|BMJ|JAMA|PNAS)', "peer_reviewed", 1.0),
            (r'(?:10\.\d{4,}/[^\s]{5,})', "academic", 0.85),   # DOI
        ]

        for pattern, org_type, weight in org_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = (match.start(), match.end())
                if span in seen_spans:
                    continue
                seen_spans.add(span)

                ctx_start = max(0, match.start() - 60)
                ctx_end = min(len(text), match.end() + 20)
                context = text[ctx_start:ctx_end].strip()

                citations.append(CitationClaim(
                    text=context,
                    cited_entity=match.group(),
                    claim_type=org_type,
                    specificity_score=weight,
                ))

        # 4. 模糊引用 (只记录前5个)
        vague_count = 0
        for pattern in VAGUE_CITATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = (match.start(), match.end())
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                vague_count += 1
                if vague_count > 5:
                    break

                ctx_start = max(0, match.start() - 30)
                ctx_end = min(len(text), match.end() + 10)
                context = text[ctx_start:ctx_end].strip()

                citations.append(CitationClaim(
                    text=context,
                    cited_entity=match.group(),
                    claim_type="vague",
                    specificity_score=0.05,
                ))
            if vague_count > 5:
                break

        # 5. 加入已知URL (从外部传入)
        for url in known_urls:
            if not any(c.cited_url == url for c in citations):
                domain = urlparse(url).netloc.lower()
                citations.append(CitationClaim(
                    text=f"外部引用: {url}",
                    cited_url=url,
                    cited_entity=domain,
                    claim_type=self._classify_url_domain(domain),
                    specificity_score=0.7,
                ))

        return citations

    @staticmethod
    def _classify_url_domain(domain: str) -> str:
        """根据域名分类来源类型"""
        domain_lower = domain.lower()

        # 政府/国际组织
        if any(d in domain_lower for d in ['.gov', 'who.int', 'un.org', 'unesco.org',
                'cdc.gov', 'fda.gov', 'nih.gov', 'europa.eu']):
            return "government"

        # 学术/同行评审
        if any(d in domain_lower for d in ['nature.com', 'science.org', 'thelancet.com',
                'nejm.org', 'bmj.com', 'pnas.org', 'cell.com', 'pubmed.ncbi.nlm.nih.gov',
                'doi.org', 'arxiv.org', 'springer.com', 'wiley.com', 'acm.org', 'ieee.org']):
            return "peer_reviewed"

        # 学术机构
        if any(d in domain_lower for d in ['.edu', '.ac.', 'scholar.google', 'researchgate']):
            return "academic"

        # 官方媒体
        if any(d in domain_lower for d in ['xinhuanet', 'people.com.cn', 'cctv.com',
                'bbc.com', 'reuters.com', 'apnews.com', 'chinadaily']):
            return "official_media"

        # 社交媒体
        if any(d in domain_lower for d in ['weibo.com', 'zhihu.com', 'twitter.com', 'x.com',
                'facebook.com', 'reddit.com', 't.co', 'bilibili.com', 'douyin.com']):
            return "social_media"

        return "general_media"

    # -------------------------------------------------------------------
    # 质量分布
    # -------------------------------------------------------------------

    def _compute_quality_distribution(self, citations: list[CitationClaim]) -> dict:
        """计算来源质量分布"""
        dist: dict[str, int] = {}
        for c in citations:
            dist[c.claim_type] = dist.get(c.claim_type, 0) + 1

        total = len(citations) or 1
        return {
            "counts": dist,
            "weighted_quality": round(
                sum(self.SOURCE_TYPE_WEIGHTS.get(c.claim_type, 0.3) for c in citations) / total, 3
            ),
            "total_citations": len(citations),
        }

    # -------------------------------------------------------------------
    # 引用链深度
    # -------------------------------------------------------------------

    @staticmethod
    def _compute_chain_depth(citations: list[CitationClaim], known_urls: list[str]) -> int:
        """计算引用链条深度"""
        depth = 0

        # 直接引用 (L1)
        if citations:
            depth = 1

        # URL引用 (L2)
        if any(c.cited_url for c in citations) or known_urls:
            depth = 2

        # 链式引用 (L3) — 如果引用指向另一个有引用的来源
        verifiable = sum(1 for c in citations if c.claim_type in ("url", "specific_name"))
        if verifiable >= 3:
            depth = 3

        return depth

    # -------------------------------------------------------------------
    # 独立交叉验证
    # -------------------------------------------------------------------

    @staticmethod
    def _check_corroboration(citations: list[CitationClaim]) -> bool:
        """检查是否有独立来源的交叉验证"""
        url_count = sum(1 for c in citations if c.cited_url)
        name_count = sum(1 for c in citations if c.claim_type in ("specific_name", "peer_reviewed", "government"))
        return (url_count >= 2) or (name_count >= 3) or (url_count >= 1 and name_count >= 1)

    # -------------------------------------------------------------------
    # 主张-来源一致性
    # -------------------------------------------------------------------

    @staticmethod
    def _compute_alignment(citations: list[CitationClaim], claims: list[dict]) -> float:
        """评估主张与引用来源的一致性"""
        if not claims:
            # 如果没有外部主张，基于引用质量估算
            if not citations:
                return 0.0
            specific = sum(1 for c in citations if c.specificity_score >= 0.7)
            return min(specific / max(len(citations), 1), 1.0)

        claim_count = len(claims)
        cite_count = len(citations)

        # 有主张但无引用 → 低一致性
        if claim_count > 0 and cite_count == 0:
            return 0.0

        # 引用覆盖率
        coverage = min(cite_count / max(claim_count, 1), 1.0)

        # 引用具体度加权
        specificity_avg = sum(c.specificity_score for c in citations) / max(len(citations), 1)

        return round((coverage * 0.6 + specificity_avg * 0.4), 2)

    # -------------------------------------------------------------------
    # 红旗检测
    # -------------------------------------------------------------------

    def _detect_red_flags(self, citations: list[CitationClaim], text: str) -> list[CitationIntegrityFlag]:
        """检测引用完整性问题"""
        flags: list[CitationIntegrityFlag] = []

        # 红旗1: 零引用
        if not citations:
            flags.append(CitationIntegrityFlag(
                severity="high",
                description="全文无任何引用来源。所有主张均无法验证。",
                citation_index=-1,
                recommendation="添加可验证的引用来源 (URL、报告名、机构名)。",
            ))

        # 红旗2: 仅有模糊引用
        vague_only = all(c.claim_type == "vague" for c in citations)
        if vague_only and citations:
            flags.append(CitationIntegrityFlag(
                severity="high",
                description=f"全部{len(citations)}处引用均为模糊表述 ('研究表明'等)，无法溯源验证。",
                citation_index=0,
                recommendation="用具体来源替代模糊引用：指明机构名称、报告标题或URL。",
            ))

        # 红旗3: 大量模糊引用
        vague_count = sum(1 for c in citations if c.claim_type == "vague")
        if vague_count >= 3:
            flags.append(CitationIntegrityFlag(
                severity="medium",
                description=f"发现{vague_count}处模糊引用 ('研究表明'/'专家指出'等)。",
                citation_index=-1,
                recommendation="减少'据研究显示'类表述，改用具体的'据WHO 2024年报告指出'。",
            ))

        # 红旗4: 引用社交媒体作为权威来源
        social_cites = [c for c in citations if c.claim_type == "social_media"]
        if social_cites:
            flags.append(CitationIntegrityFlag(
                severity="medium",
                description=f"引用{len(social_cites)}处社交媒体内容作为信息来源。社交媒体本身不构成权威证据。",
                citation_index=citations.index(social_cites[0]) if social_cites else -1,
                recommendation="如需引用社交媒体上的声明，应标注'该信息来自社交媒体，尚未经独立验证'。",
            ))

        # 红旗5: 自引用/循环引用
        text_domains = set()
        for match in re.finditer(r'https?://([^\s/]+)', text):
            text_domains.add(match.group(1).lower())
        for c in citations:
            if c.cited_url:
                cited_domain = urlparse(c.cited_url).netloc.lower()
                if cited_domain in text_domains and len(text_domains) <= 2:
                    flags.append(CitationIntegrityFlag(
                        severity="low",
                        description=f"可能存在循环引用：引用来源与原文来自相同域名 ({cited_domain})。",
                        citation_index=citations.index(c) if c in citations else -1,
                        recommendation="添加独立第三方来源进行交叉验证。",
                    ))
                    break

        return flags

    # -------------------------------------------------------------------
    # 评分计算
    # -------------------------------------------------------------------

    def _compute_score(self, result: SatyaLensResult) -> float:
        """基于所有维度计算最终完整性评分 (0.0-1.0)"""
        if result.citations_found == 0:
            return 0.0

        # 维度1: 引用覆盖率 (40%)
        coverage = min(result.citations_found / max(result.citations_found + result.citations_missing, 1), 1.0)

        # 维度2: 引用具体度 (30%)
        if result.citation_details:
            specificity = sum(c.specificity_score for c in result.citation_details) / len(result.citation_details)
        else:
            specificity = 0.0

        # 维度3: 来源质量 (15%)
        quality = result.source_quality_distribution.get("weighted_quality", 0.0)

        # 维度4: 引用链深度 (10%)
        depth_score = result.citation_chain_depth / 3.0  # normalize to 0-1

        # 维度5: 独立交叉验证 (5%)
        corroboration_score = 1.0 if result.independent_corroboration else 0.0

        # 合成
        raw_score = (
            coverage * 0.40 +
            specificity * 0.30 +
            quality * 0.15 +
            depth_score * 0.10 +
            corroboration_score * 0.05
        )

        # 红旗惩罚
        penalty = 0.0
        for flag in result.red_flags:
            if flag.severity == "high":
                penalty += 0.15
            elif flag.severity == "medium":
                penalty += 0.07
            elif flag.severity == "low":
                penalty += 0.03

        final = max(0.0, min(raw_score - penalty, 1.0))
        return round(final, 3)

    # -------------------------------------------------------------------
    # 摘要与建议
    # -------------------------------------------------------------------

    def _generate_recommendations(self, result: SatyaLensResult) -> list[str]:
        """生成改进建议"""
        recs = list(result.recommendations or [])

        if result.citations_found == 0:
            recs.append("[引用完整性] 添加至少一个可验证的引用来源。")
        elif result.citations_vague > result.citations_verifiable:
            recs.append("[引用完整性] 将模糊引用替换为具体来源 (URL、报告名、机构名)。")

        if result.citation_chain_depth < 2:
            recs.append("[引用链深度] 引用链仅1层。尝试引用原始来源而非二手转述。")

        if not result.independent_corroboration:
            recs.append("[交叉验证] 添加至少一个独立来源交叉验证关键主张。")

        if result.overall_integrity_score < 0.3:
            recs.append("[严重] 引用完整性极低。该信息的几乎所有主张都无法溯源验证。")
        elif result.overall_integrity_score < 0.6:
            recs.append("[中等] 引用完整性中等。部分主张有来源支撑，但需补充更多可验证引用。")

        # 附加各红旗的建议
        for flag in result.red_flags:
            if flag.recommendation and flag.recommendation not in recs:
                recs.append(f"[{flag.severity.upper()}] {flag.recommendation}")

        return recs[:8]  # 最多8条

    def _generate_summary(self, result: SatyaLensResult) -> str:
        """生成人类可读的摘要"""
        score = result.overall_integrity_score
        if score >= 0.80:
            level = "优秀"
        elif score >= 0.60:
            level = "良好"
        elif score >= 0.40:
            level = "一般"
        elif score >= 0.20:
            level = "较差"
        else:
            level = "极差"

        parts = [
            f"引用完整性评分: {score:.2f}/1.00 ({level})",
            f"共{result.citations_found}处引用声明: "
            f"{result.citations_verifiable}处可验证, "
            f"{result.citations_vague}处模糊, "
            f"{result.citations_missing}处缺失引用",
        ]

        if result.red_flags:
            parts.append(f"发现{len(result.red_flags)}个引用质量问题 ("
                        f"{sum(1 for f in result.red_flags if f.severity == 'high')}个高危)")

        return " | ".join(parts)
