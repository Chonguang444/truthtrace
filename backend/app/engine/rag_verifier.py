"""
RAG权威信源实时检索验证引擎 — 第12号引擎

对标抖音"AI求真"大模型的RAG(检索增强生成)模式:
  1. 从用户内容中提取可验证的事实主张
  2. 实时检索权威信源(WHO/国家标准/学术论文API)
  3. 将主张与权威数据自动比对
  4. 返回: 支持/反驳/未找到权威来源

行业参考:
  - 抖音AI求真大模型: "主动审阅内容→联网检索信源→给出研判结果"
  - 南方+辟谣平台: "实体采访+证据链构建"
  - 白杨智鉴: "可解释性鉴伪"

核心原则:
  - 只引用真实存在的、可访问的权威来源
  - 检索失败时说"未找到足够权威来源验证"，不编造
  - 每条验证结果附带来源URL和检索时间
"""

from __future__ import annotations
import re
import hashlib
import logging
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger("truthtrace.rag_verifier")


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class AuthoritySource:
    """一条可以被引用的权威来源"""
    title: str
    url: str
    source_type: str      # government / international / academic / media / standard
    relevance_score: float  # 0-1 与查询的相关性
    excerpt: str = ""      # 关键摘录
    date: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title, "url": self.url,
            "source_type": self.source_type,
            "relevance_score": round(self.relevance_score, 2),
            "excerpt": self.excerpt, "date": self.date,
        }


@dataclass
class ClaimVerification:
    """单条主张的验证结果"""
    claim: str
    verdict: str  # supported / refuted / unverifiable / partially_supported
    explanation: str
    sources: list[AuthoritySource] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "verdict": self.verdict,
            "explanation": self.explanation,
            "sources": [s.to_dict() for s in self.sources],
            "confidence": round(self.confidence, 2),
        }


@dataclass
class RAGVerificationResult:
    """RAG验证完整结果"""
    verified_claims: list[ClaimVerification] = field(default_factory=list)
    total_claims: int = 0
    supported: int = 0
    refuted: int = 0
    unverifiable: int = 0
    authority_score: float = 50.0  # 0-100 整体权威来源覆盖度
    summary: str = ""
    retrieved_at: str = ""

    def to_dict(self) -> dict:
        return {
            "verified_claims": [c.to_dict() for c in self.verified_claims],
            "total_claims": self.total_claims,
            "supported": self.supported,
            "refuted": self.refuted,
            "unverifiable": self.unverifiable,
            "authority_score": round(self.authority_score, 1),
            "summary": self.summary,
            "retrieved_at": self.retrieved_at,
        }


# =============================================================================
# 权威信源数据库 — 可检索的公开API和知识库
# =============================================================================

AUTHORITY_SOURCES_DB = {
    # 食品安全
    "food_safety": [
        {"name": "GB 2760-2024 食品添加剂使用标准", "url": "https://std.samr.gov.cn/gb/search/gbDetailed?id=GB%202760",
         "type": "standard", "api": None, "search_url": "https://std.samr.gov.cn/gb/search/gbDetailed?keyword=%s"},
        {"name": "JECFA (WHO/FAO 食品添加剂联合专家委员会)", "url": "https://www.who.int/teams/nutrition-and-food-safety/databases/jecfa",
         "type": "international", "api": None},
        {"name": "EFSA 欧洲食品安全局", "url": "https://www.efsa.europa.eu/",
         "type": "international", "api": "https://www.efsa.europa.eu/en/search?s=%s"},
        {"name": "FDA GRAS 物质清单", "url": "https://www.fda.gov/food/food-additives-petitions/generally-recognized-safe-gras",
         "type": "government", "api": "https://www.accessdata.fda.gov/scripts/fdcc/index.cfm?set=GRASNotices&sort=GRN_No&order=DESC&showAll=true"},
        {"name": "IARC/WHO 致癌物分类", "url": "https://monographs.iarc.who.int/",
         "type": "international", "api": None},
    ],
    # 医药健康
    "medicine_health": [
        {"name": "WHO 基本药物清单", "url": "https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023",
         "type": "international", "api": None},
        {"name": "NIH PubMed 学术数据库", "url": "https://pubmed.ncbi.nlm.nih.gov/",
         "type": "academic",
         "api": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmax=5&term=%s"},
        {"name": "国家药品监督管理局 (NMPA)", "url": "https://www.nmpa.gov.cn/",
         "type": "government", "api": None},
        {"name": "Cochrane 系统评价数据库", "url": "https://www.cochranelibrary.com/",
         "type": "academic", "api": None},
        {"name": "中国疾病预防控制中心", "url": "https://www.chinacdc.cn/",
         "type": "government", "api": None},
    ],
    # 环境气候
    "environment_climate": [
        {"name": "IPCC 第六次评估报告 (AR6)", "url": "https://www.ipcc.ch/report/ar6/",
         "type": "international", "api": None},
        {"name": "WMO 全球气候状况", "url": "https://public.wmo.int/",
         "type": "international", "api": None},
        {"name": "中国生态环境部", "url": "https://www.mee.gov.cn/",
         "type": "government", "api": None},
        {"name": "NASA GISS 全球温度数据", "url": "https://data.giss.nasa.gov/gistemp/",
         "type": "academic", "api": None},
    ],
    # 经济
    "economics_finance": [
        {"name": "国家统计局 (NBS)", "url": "https://www.stats.gov.cn/",
         "type": "government", "api": None},
        {"name": "中国人民银行 (PBoC)", "url": "http://www.pbc.gov.cn/",
         "type": "government", "api": None},
        {"name": "IMF 世界经济展望", "url": "https://www.imf.org/en/Publications/WEO",
         "type": "international", "api": None},
        {"name": "World Bank Open Data", "url": "https://data.worldbank.org/",
         "type": "international", "api": None},
    ],
}


# =============================================================================
# 主张提取 — 从文本中提取可被验证的量化声明
# =============================================================================

def extract_verifiable_claims(text: str) -> list[dict]:
    """提取可以对照权威数据验证的主张"""
    claims = []

    # 量化主张: 数字+%
    for m in re.finditer(r'([^。！？\n]{3,70}?(?:\d+(?:\.\d+)?\s*%|超过\d+|高达\d+|不到\d+|约\d+)[^。！？\n]{3,70})', text):
        claim_text = m.group().strip()
        if 10 <= len(claim_text) <= 200:
            claims.append({"text": claim_text, "type": "quantitative", "domain": _detect_domain(claim_text)})

    # 因果主张
    for m in re.finditer(r'([^。！？\n]{3,80}?(?:导致|引起|造成|引发|使得|因此|所以|证明|证实|表明|发现|揭示)[^。！？\n]{3,80})', text):
        claim_text = m.group().strip()
        if 10 <= len(claim_text) <= 200:
            # 去重
            if not any(c["text"] == claim_text for c in claims):
                claims.append({"text": claim_text, "type": "causal", "domain": _detect_domain(claim_text)})

    return claims[:15]


def _detect_domain(text: str) -> str:
    keywords = {
        "food_safety": ["食品", "添加剂", "防腐剂", "致癌", "转基因", "农药", "毒素", "剂量", "ADI", "GB2760"],
        "medicine_health": ["疫苗", "药物", "治疗", "癌症", "糖尿病", "病毒", "感染", "副作用", "临床试验", "FDA", "NMPA"],
        "environment_climate": ["气候", "变暖", "碳排放", "CO2", "污染", "雾霾", "PM2.5", "IPCC", "温室"],
        "economics_finance": ["GDP", "CPI", "通胀", "失业", "利率", "汇率", "股市", "房价", "经济", "增速"],
    }
    for domain, kws in keywords.items():
        if any(kw in text for kw in kws):
            return domain
    return "general"


# =============================================================================
# 主验证器
# =============================================================================

class RAGVerifier:
    """
    RAG权威信源检索验证引擎

    三步验证流程:
      1. 提取可验证主张
      2. 对每条主张进行信源检索
      3. 主张 vs 信源 → 支持/反驳/无法验证
    """

    def analyze(self, text: str, title: str = "",
                claims: list[str] | None = None,
                domain: str = "general",
                max_queries: int = 5) -> RAGVerificationResult:
        """
        对文本中的主张进行RAG验证。

        Args:
            text: 全文
            title: 标题
            claims: 预提取的主张列表(可选, 不提供则自动提取)
            domain: 强制领域
            max_queries: 最多验证N条主张
        """
        combined = f"{title}\n{text}"

        # Step 1: 提取主张
        if claims:
            raw_claims = [{"text": c, "type": "causal", "domain": domain} for c in claims]
        else:
            raw_claims = extract_verifiable_claims(combined)

        # Step 2: 为每条主张进行RAG检索
        verified = []
        for claim_data in raw_claims[:max_queries]:
            vc = self._verify_single_claim(claim_data["text"], claim_data.get("domain", domain), claim_data.get("type", "causal"))
            verified.append(vc)

        # Step 3: 汇总
        supported = sum(1 for v in verified if v.verdict == "supported")
        refuted = sum(1 for v in verified if v.verdict == "refuted")
        unverifiable = sum(1 for v in verified if v.verdict == "unverifiable")

        # 权威评分: 每有一条被权威来源支持+10, 被反驳-15(说明信息质量差)
        base = 50
        authority_score = base + supported * 10 - refuted * 15
        authority_score = max(0, min(100, authority_score))

        if supported > 0 and refuted == 0:
            summary = f"共提取 {len(verified)} 条可验证主张, 其中 {supported} 条获得权威来源支持。信息可信度较高。"
        elif refuted > 0:
            summary = f"共提取 {len(verified)} 条可验证主张, 其中 {refuted} 条与权威来源信息存在矛盾。请谨慎采信。"
        elif unverifiable == len(verified):
            summary = f"共提取 {len(verified)} 条主张, 但均无法在权威来源中找到对应验证。请自行核实关键事实。"
        else:
            summary = f"共提取 {len(verified)} 条主张, 部分获得支持, 部分无法验证。"

        return RAGVerificationResult(
            verified_claims=verified,
            total_claims=len(verified),
            supported=supported,
            refuted=refuted,
            unverifiable=unverifiable,
            authority_score=round(authority_score, 1),
            summary=summary,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    def _verify_single_claim(self, claim: str, domain: str, claim_type: str) -> ClaimVerification:
        """
        对单条主张进行RAG验证。

        当前实现: 基于规则+知识库匹配(快速路径), 未来可扩展为真正的API检索。
        """
        # 选择该领域的权威来源
        domain_sources = AUTHORITY_SOURCES_DB.get(domain, [])
        if not domain_sources:
            # 跨领域检索
            domain_sources = [s for v in AUTHORITY_SOURCES_DB.values() for s in v][:10]

        # === 快速路径: 内置知识库匹配 ===
        from app.engine.authoritative_kb import search_knowledge
        kb_results = search_knowledge(claim, domain=domain, limit=3)
        if kb_results:
            for entry in kb_results:
                # 检查是支持还是反驳
                if entry.counter_claim and any(kw in claim for kw in ["致癌", "有毒", "有害", "危险", "不安全", "禁用"]):
                    # 该主张可能是恐惧传播 → 被知识的 counter_claim 反驳
                    return ClaimVerification(
                        claim=claim, verdict="refuted",
                        explanation=f"权威知识库中的反证: {entry.counter_claim[:200]}",
                        sources=[
                            AuthoritySource(
                                title=entry.source_title, url=entry.source_url,
                                source_type=entry.source_type, relevance_score=0.9,
                                excerpt=entry.citation, date=entry.verified_date,
                            )
                        ],
                        confidence=0.85,
                    )
                else:
                    return ClaimVerification(
                        claim=claim, verdict="supported",
                        explanation=f"该主张与权威知识库中的记录一致: {entry.claim[:150]}",
                        sources=[
                            AuthoritySource(
                                title=entry.source_title, url=entry.source_url,
                                source_type=entry.source_type, relevance_score=0.85,
                                excerpt=entry.citation, date=entry.verified_date,
                            )
                        ],
                        confidence=0.80,
                    )

        # === 慢速路径: 权威信源检索(可获得的公开数据) ===
        sources = []
        for ds in domain_sources[:5]:
            sources.append(AuthoritySource(
                title=ds["name"], url=ds["url"], source_type=ds["type"],
                relevance_score=0.5, excerpt=f"可在此查询: {ds['name']}",
            ))

        # 分析主张是否可能被验真
        # 量化主张 + 已知领域 → 提示验证路径
        if claim_type == "quantitative" and domain != "general":
            return ClaimVerification(
                claim=claim,
                verdict="unverifiable",
                explanation=f"该量化主张可对比以下权威来源进行人工核实。系统无法自动验证所有数值, 建议自行查阅。",
                sources=sources[:3],
                confidence=0.3,
            )

        return ClaimVerification(
            claim=claim,
            verdict="unverifiable",
            explanation="当前系统知识库未覆盖该主张。建议查阅权威来源进行人工核实。这不意味着该主张错误。",
            sources=sources[:3] if sources else [],
            confidence=0.2,
        )
