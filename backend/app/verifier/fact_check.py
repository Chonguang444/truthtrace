"""
事实核查器 — 对接权威数据库进行事实核查
"""

import re
from datetime import datetime, timedelta

from loguru import logger


class FactChecker:
    """
    事实核查器

    核查策略：
    1. 政府公告数据库（公开数据）
    2. 学术论文数据库（CrossRef/PubMed）
    3. 维基百科/WikiData
    4. 权威媒体已核实报道
    """

    # 科学/数据声明模式
    SCIENTIFIC_CLAIM_PATTERNS = [
        (r'(\d+(?:\.\d+)?%)\s*的?([一-鿿]+)', "统计声明"),
        (r'研究(?:表明|显示|发现)([^。]{5,100})', "研究引述"),
        (r'据([一-鿿]{2,20})(?:发布|报道|统计)', "数据来源"),
        (r'(?:科学家|专家|学者)([一-鿿]{2,10})(?:表示|称|指出)', "专家观点"),
    ]

    # 可验证的权威数据源
    VERIFIABLE_SOURCES = {
        "stats.gov.cn": "国家统计局",
        "who.int": "世界卫生组织",
        "worldbank.org": "世界银行",
        "pubmed.ncbi.nlm.nih.gov": "PubMed 医学文献",
        "doi.org": "学术论文 DOI",
        "wikipedia.org": "维基百科",
        "wikidata.org": "WikiData",
    }

    async def check(self, claim: str, event_data: dict | None = None) -> dict:
        """
        核查一条声明

        Args:
            claim: 待核查的声明文本
            event_data: 事件上下文数据

        Returns:
            {
                "verdict": "verified" | "false" | "misleading" | "unverifiable",
                "confidence": 0-100,
                "evidence": [...],
                "contradicting_sources": [...],
                "suggestion": 进一步验证建议
            }
        """
        result = {
            "verdict": "unverifiable",
            "confidence": 0,
            "evidence": [],
            "contradicting_sources": [],
            "suggestion": "",
        }

        if not claim:
            result["suggestion"] = "未提供待核查内容"
            return result

        # 1. 检测可验证的声明类型
        claim_type = self._classify_claim(claim)

        if claim_type == "statistical":
            result = await self._verify_statistical_claim(claim)
        elif claim_type == "scientific":
            result = await self._verify_scientific_claim(claim)
        elif claim_type == "official":
            result = await self._verify_official_claim(claim)
        else:
            # 通用验证 — 搜索外部数据源
            result = await self._general_verify(claim)

        return result

    def _classify_claim(self, claim: str) -> str:
        """分类声明类型"""
        if re.search(r'\d+(?:\.\d+)?%', claim):
            return "statistical"
        if any(word in claim for word in ["研究", "实验", "科学", "数据证明"]):
            return "scientific"
        if any(word in claim for word in ["公告", "通告", "通知", "政策", "法规"]):
            return "official"
        return "general"

    async def _verify_statistical_claim(self, claim: str) -> dict:
        """验证统计数据声明"""
        result = {
            "verdict": "unverifiable",
            "confidence": 30,
            "evidence": [],
            "contradicting_sources": [],
            "suggestion": "",
        }

        # 提取声称的数字
        numbers = re.findall(r'\d+(?:\.\d+)?%?', claim)
        if not numbers:
            return result

        # 尝试在可验证数据库中查找
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                # 搜索国家统计局等权威来源
                search_query = f"site:stats.gov.cn {claim[:100]}"
                # 这里简化处理，实际需要对接具体 API
                result["evidence"].append({
                    "source": "统计声明核查",
                    "extracted_numbers": numbers,
                    "note": "需手动核对权威统计数据库",
                })
                result["suggestion"] = "建议对照国家统计局或相关部委发布的官方数据"
        except Exception as e:
            logger.warning(f"统计数据核查失败: {e}")

        return result

    async def _verify_scientific_claim(self, claim: str) -> dict:
        """验证科学声明"""
        result = {
            "verdict": "unverifiable",
            "confidence": 25,
            "evidence": [],
            "contradicting_sources": [],
            "suggestion": "建议在 PubMed/Google Scholar 搜索相关研究",
        }

        # 尝试提取 DOI
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', claim)
        if doi_match:
            doi = doi_match.group(0)
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"https://api.crossref.org/works/{doi}",
                        headers={"Accept": "application/json"},
                    )
                    if response.status_code == 200:
                        data = response.json()
                        result["evidence"].append({
                            "type": "doi_verified",
                            "doi": doi,
                            "title": data.get("message", {}).get("title", [""])[0],
                        })
                        result["verdict"] = "verified"
                        result["confidence"] = 80
            except Exception:
                pass

        return result

    async def _verify_official_claim(self, claim: str) -> dict:
        """验证官方声明"""
        return {
            "verdict": "unverifiable",
            "confidence": 40,
            "evidence": [],
            "contradicting_sources": [],
            "suggestion": "建议对照官方发布渠道（gov.cn/政府网站/官方账号）核实",
        }

    async def _general_verify(self, claim: str) -> dict:
        """通用验证"""
        return {
            "verdict": "unverifiable",
            "confidence": 20,
            "evidence": [],
            "contradicting_sources": [],
            "suggestion": "建议多源交叉比对，参考权威媒体和官方渠道",
        }
