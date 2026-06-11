"""
回音壁效应检测

基于B站视频2揭示的问题: "新某报可不是什么自媒体，这是正经的事业单位。
于是许多媒体干脆继续据新某报道，形成了原地TP的神奇景象。"

检测: 多个来源引用同一条主张时，是否所有引用链最终指向同一个未经核实的源头。
如果是 → 标记"回音壁效应"，可信度应下调。
"""
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class SourceNode:
    """引用链中的一个来源节点"""
    name: str = ""             # 来源名称
    url: str = ""              # 来源 URL
    source_type: str = ""      # self_media / official / news / academic / unknown
    is_verified: bool = False  # 是否经过核实
    cited_by: list[str] = field(default_factory=list)  # 哪些来源引用了它
    cites: list[str] = field(default_factory=list)      # 它引用了什么


@dataclass
class EchoChamberResult:
    """回音壁检测结果"""
    total_sources: int = 0
    unique_original_sources: int = 0
    echo_chamber_detected: bool = False
    echo_chamber_score: float = 0.0   # 0-100，越高越严重
    root_source: str = ""             # 所有引用最终指向的单一源头
    root_source_type: str = ""        # 该源头的类型
    citation_chain_depth: int = 1     # 引用链深度
    mutual_citation_pairs: list[dict] = field(default_factory=list)  # 互相引用的媒体对
    assessment: str = ""

    def to_dict(self) -> dict:
        return {
            "total_sources": self.total_sources,
            "unique_original_sources": self.unique_original_sources,
            "echo_chamber_detected": self.echo_chamber_detected,
            "echo_chamber_score": round(self.echo_chamber_score, 1),
            "root_source": self.root_source,
            "root_source_type": self.root_source_type,
            "citation_chain_depth": self.citation_chain_depth,
            "mutual_citation_pairs": self.mutual_citation_pairs[:5],
            "assessment": self.assessment,
        }


# =============================================================================
# 检测逻辑
# =============================================================================

def detect_echo_chamber(
    sources: list[dict] | None = None,
    content_text: str = "",
    references: list[str] | None = None,
) -> EchoChamberResult:
    """
    检测信息来源是否形成回音壁效应。

    Args:
        sources: 来源列表 [{"name": str, "url": str, "type": str, "cites": [str]}]
        content_text: 内容文本（用于提取引用模式）
        references: 引用的URL列表

    检测方法:
    1. 统计声称的来源数量 vs 唯一原始来源数量
    2. 检测多源是否指向同一原始出处
    3. 检测互相引用的媒体对
    4. 检测"据XX报道→据XX报道→据XX报道"连锁引用
    """
    result = EchoChamberResult()

    sources = sources or []
    references = references or []
    result.total_sources = len(sources) + len(references)

    if result.total_sources < 2:
        result.assessment = "来源不足，无法判断回音壁效应。"
        return result

    # 1. 分析引用链
    unique_originals = set()
    for s in sources:
        name = s.get("name", "")
        stype = s.get("type", "unknown")
        cites = s.get("cites", [])
        is_original = s.get("is_original", False)

        if is_original or stype in ("government", "academic", "standard", "original_report"):
            unique_originals.add(name)
        elif not cites:
            # 没有引用 → 可能是原始来源
            unique_originals.add(name)

    result.unique_original_sources = len(unique_originals)

    # 2. 检测回音壁: 来源多但原始来源少(或只有1个)
    if result.total_sources >= 3 and result.unique_original_sources <= 1:
        result.echo_chamber_detected = True
        root = list(unique_originals)[0] if unique_originals else "unknown"
        result.root_source = root
        result.root_source_type = "single_point_of_failure"
        result.echo_chamber_score = 80.0

    # 3. 检测文本中的连锁引用模式
    import re as _re
    chain_patterns = [
        r'据(.{2,10})(?:报道|消息|称).{0,30}据(.{2,10})(?:报道|消息|称)',
        r'(?:援引|转引|转自|来源[：:]).{2,20}(?:报道|消息)',
    ]
    chain_count = 0
    for pat in chain_patterns:
        chain_count += len(_re.findall(pat, content_text))

    if chain_count >= 2:
        result.citation_chain_depth = chain_count + 1
        if not result.echo_chamber_detected:
            result.echo_chamber_detected = True
            result.echo_chamber_score = max(result.echo_chamber_score, 60.0)

    # 4. 互相引用对检测
    for i, s1 in enumerate(sources):
        for j, s2 in enumerate(sources):
            if i >= j: continue
            s1_name = s1.get("name", "")
            s2_name = s2.get("name", "")
            s1_cites = s1.get("cites", [])
            s2_cites = s2.get("cites", [])

            # 双向引用
            if s1_name in s2_cites and s2_name in s1_cites:
                result.mutual_citation_pairs.append({
                    "source_a": s1_name[:60], "source_b": s2_name[:60],
                    "pattern": "mutual_citation",
                    "note": "互相引用形成信息闭环",
                })

    # 5. 内容中的"据XX报道"模式提取
    report_pattern = _re.findall(r'据([一-鿿\w]{2,15})(?:报道|消息|称)', content_text)
    if report_pattern:
        counter = defaultdict(int)
        for rp in report_pattern:
            counter[rp] += 1
        # 如果有来源被反复引用 ≥3次
        for src_name, count in counter.items():
            if count >= 3:
                if not result.echo_chamber_detected:
                    result.echo_chamber_detected = True
                if not result.root_source:
                    result.root_source = src_name
                result.echo_chamber_score = min(100, result.echo_chamber_score + count * 10)

    # 6. 生成评估
    if result.echo_chamber_detected:
        result.echo_chamber_score = min(100, result.echo_chamber_score + 20)
        if result.mutual_citation_pairs:
            result.assessment = (
                f"回音壁效应检测阳性 ({result.echo_chamber_score:.0f}/100)。"
                f"{result.total_sources}个来源中仅{result.unique_original_sources}个为原始出处，"
                f"发现{len(result.mutual_citation_pairs)}对相互引用。"
                f"建议核查原始来源「{result.root_source}」是否经过独立验证。"
            )
        else:
            result.assessment = (
                f"回音壁效应检测阳性 ({result.echo_chamber_score:.0f}/100)。"
                f"{result.total_sources}个来源可能指向同一未经核实的原始出处。"
                f"引用链深度{result.citation_chain_depth}层——信息在传播过程中可能被逐层扭曲。"
            )
    elif chain_count:
        result.assessment = f"存在{chain_count}处连锁引用，有一定回音壁风险，但仍在可接受范围。"
    else:
        result.assessment = "未检测到明显的回音壁效应。来源多元化程度正常。"

    return result
