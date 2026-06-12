"""
AI预揭露引擎 (Prebunking Inoculation Engine) — 第29号引擎

理论基础:
  - Inoculation Theory 元分析 (Simchon et al., 2026, 33实验 N=37,075)
  - 12国视频接种验证 (Nature Communications Psychology, 2026)
  - 结构指纹框架 (Germani, Spitale et al., 2026)
  - 逻辑基础型接种 > 技巧型接种 (JESP, 2025)

核心原理:
  在用户接触信息前展示"预揭露提示卡" — 命名操纵手法→解释为何有效→提供检测线索
  不是"这是假的", 而是"这类手法常被用于操纵" → 不触发心理防御

设计参考:
  - Google Jigsaw Prebunking Campaign (12 EU nations, 120M+ YouTube users)
  - Skeptik logical fallacy annotator (ASU)
  - Bad News game (Cambridge Social Decision-Making Lab)
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field

# =============================================================================
# 操纵手法知识库 (Manipulation Technique Knowledge Base)
# =============================================================================

# 每项技术: (名称, 简短描述, 为何有效, 检测线索, 示例)
MANIPULATION_TECHNIQUES = {
    "emotional_manipulation": {
        "name_zh": "情绪操纵",
        "name_en": "Emotional Manipulation",
        "short_desc": "使用强烈情绪(恐惧/愤怒/兴奋)绕过理性思考",
        "why_works": "强烈情绪会降低我们仔细核查事实的意愿和能力。当我们害怕或愤怒时，大脑的杏仁核被激活，前额叶的批判思维被抑制。",
        "detection_clues": [
            "是否包含'震惊'、'愤怒'、'泪目'等强烈情绪词？",
            "是否使用了大量感叹号或全大写？",
            "是否要求你'如果关心家人就转发'？",
        ],
        "example": "这可能是: '太可怕了！这些东西正在毒害你的孩子！转发让更多人看到！'",
        "inoculation_prompt": "⚠️ 这篇内容可能正在使用**情绪操纵**手法。强烈情绪可以绕过我们的批判思维——当你感到强烈的愤怒或恐惧时，请暂停，深呼吸，然后问自己: '这里的事实是什么？有什么证据？'",
    },
    "false_authority": {
        "name_zh": "虚假权威",
        "name_en": "False Authority",
        "short_desc": "引用不存在的'专家'或'研究'来增加可信度",
        "why_works": "我们习惯相信权威。但'哈佛研究证实'不一定真的有哈佛研究。真正的学术研究会明确标注作者、期刊、DOI号。",
        "detection_clues": [
            "提到'科学家'、'专家'、'哈佛研究'却不给出具体人名或论文名？",
            "引用'内部消息'或'据知情人士透露'？",
            "号称'诺贝尔奖得主'但领域完全不相关？",
        ],
        "example": "这可能是: '科学家证实xxx致癌！' 但全文未提及哪位科学家、在哪发表。",
        "inoculation_prompt": "⚠️ 这篇内容可能使用了**虚假权威**手法。'科学家说'≠真的科学家。请检查: 具体是谁说的？在哪里发表的？是否可以独立验证？",
    },
    "context_stripping": {
        "name_zh": "脱离语境/脱离剂量",
        "name_en": "Context Stripping",
        "short_desc": "忽略关键限定条件来歪曲事实",
        "why_works": "当信息被剥离了计量、概率、条件等限定信息时，安全的可以变得'危险'，复杂的可以变得'简单'。剂量决定毒性——氧气浓度过高也会中毒。",
        "detection_clues": [
            "提到'有毒'/'致癌'但不提剂量？",
            "拿实验室极端条件的结果当作日常场景？",
            "忽略'在某些条件下'、'可能'、'相关'等限定词？",
        ],
        "example": "这可能是: '某物质被证实有毒(省略: 在每日摄入超过500g的条件下)'",
        "inoculation_prompt": "⚠️ 这篇内容可能**脱离了关键语境**。'有毒'不等于'在任何剂量下都有毒'。请检查: 剂量是多少？条件是什么？是有害相关性还是因果关系？",
    },
    "false_dichotomy": {
        "name_zh": "虚假二分",
        "name_en": "False Dichotomy",
        "short_desc": "将复杂问题简化为非黑即白的选择",
        "why_works": "我们的认知倾向于简单分类。但大多数现实问题存在于灰色地带。将复杂问题'要么A要么B'的简化可能隐藏了大量中间可能。",
        "detection_clues": [
            "是否只用两个选项框定复杂问题？",
            "是否使用'要么...要么...'、'不是朋友就是敌人'？",
            "是否暗示'不支持A就等于支持B'？",
        ],
        "example": "这可能是: '你要么相信科学，要么相信中医！' (忽略了整合医学等中间地带)",
        "inoculation_prompt": "⚠️ 这篇内容可能在制造**虚假二分**。现实世界很少是非黑即白的。问问自己: 有没有第三种可能？有没有中间方案？",
    },
    "conspiracy_framing": {
        "name_zh": "阴谋论框架",
        "name_en": "Conspiracy Framing",
        "short_desc": "暗示有一个隐藏的恶意团体在操纵一切",
        "why_works": "阴谋论提供了一种'看清真相'的满足感和优越感。当面对复杂或令人不安的事件时，一个简单而'邪恶'的解释令人感到安心——至少有人'负责'。",
        "detection_clues": [
            "是否暗示'他们不想让你知道'？",
            "是否将不相关的多个事件强行链接？",
            "使用'深層政府'、'全球精英'、'影子集团'等词汇？",
        ],
        "example": "这可能是: '医药公司故意隐瞒癌症的治疗方法，因为治疗比治愈更赚钱！'",
        "inoculation_prompt": "⚠️ 这篇内容可能采用了**阴谋论框架**。真正的阴谋很难长期保密——涉及的人越多，秘密越容易泄露。问问自己: 有没有更简单的解释？证据链是否完整？",
    },
    "cherry_picking": {
        "name_zh": "选择性呈现",
        "name_en": "Cherry Picking",
        "short_desc": "只选有利证据，忽略相反证据",
        "why_works": "我们倾向于接受符合已有信念的信息(确认偏误)。当内容只呈现支持某一观点的数据时，我们容易忘记问: '不同意的证据呢？'",
        "detection_clues": [
            "是否只引用单一来源或单一研究？",
            "是否对有争议的话题给出确定的结论？",
            "是否忽略了该领域的主流科学共识？",
        ],
        "example": "这可能是: 引用一篇1980年的孤立研究来'证明'某物质致癌，但忽略了此后40年上百篇研究的安全结论。",
        "inoculation_prompt": "⚠️ 这篇内容可能**选择性呈现**了证据。科学建立在大量研究的**总体趋势**上，不是单一研究。请检查: 其他研究怎么说？主流科学机构的结论是什么？",
    },
    "bandwagon": {
        "name_zh": "从众效应",
        "name_en": "Bandwagon Effect",
        "short_desc": "利用'大家都相信'来推动接受",
        "why_works": "社会从众是人类本能。当看到'80%的人都认为'时，我们的大脑会自动减轻核查的动力——'这么多人信，不可能全错吧？'",
        "detection_clues": [
            "使用'大家都说'、'全网疯传'、'千万人已看'？",
            "给出没有来源的百分比数据？",
            "暗示'不信你就out了'？",
        ],
        "example": "这可能是: '99%的人都不知道这个真相！' (这99%是怎么统计的？)",
        "inoculation_prompt": "⚠️ 这篇内容可能在利用**从众心理**。'大家都信'不等于它就是真的。历史上有无数被大多数人相信但最终被证伪的观点。事实不靠投票决定。",
    },
    "fear_mongering": {
        "name_zh": "制造恐慌",
        "name_en": "Fear Mongering",
        "short_desc": "制造不存在的威胁来驱动行为",
        "why_works": "对危险的警惕是人类生存本能。制造一个'隐形威胁'可以绕过理性分析直接触发行动——'宁可错杀不可放过'。",
        "detection_clues": [
            "宣称一个看不见的威胁正在逼近？",
            "警告'再不行动就晚了'？",
            "将正常现象重新包装成危险信号？",
        ],
        "example": "这可能是: '你的手机正在偷偷发射致癌辐射！睡觉时一定要关机！'",
        "inoculation_prompt": "⚠️ 这篇内容可能试图**制造恐慌**。真正的科学警告会附带明确的证据和风险概率。问问自己: 这个威胁有具体证据吗？风险到底有多大？",
    },
}


@dataclass
class PrebunkingResult:
    """预揭露分析结果"""
    techniques_detected: list[dict] = field(default_factory=list)
    primary_technique: str = ""
    prebunking_card: str = ""
    inoculations: list[str] = field(default_factory=list)
    detection_count: int = 0
    risk_level: str = "low"  # low / medium / high
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "techniques_detected": self.techniques_detected,
            "primary_technique": self.primary_technique,
            "prebunking_card": self.prebunking_card,
            "inoculations": self.inoculations,
            "detection_count": self.detection_count,
            "risk_level": self.risk_level,
            "summary": self.summary,
        }


# =============================================================================
# 检测模式 (基于内容分析，触发操纵手法检测)
# =============================================================================

DETECTION_PATTERNS = {
    "emotional_manipulation": [
        r'(?i)(?:震惊|可怕|恐怖|愤怒|泪目|惊呆|吓死|触目惊心|令人发指)',
        r'(?i)(?:(?:快|赶紧|马上|立即)\s*(?:转发|分享|扩散))',
        r'(?i)(?:你的\s*(?:家人|孩子|父母)\s*(?:正在|会被|已经被))',
        r'(?i)(?:不看\s*(?:后悔|可惜)|看哭了|泪崩)',
        r'(?i)[！!]{2,}',  # 多个感叹号
    ],
    "false_authority": [
        r'(?i)(?:科学家|专家|医生)\s*(?:证实|发现|揭露|表示|承认)',
        r'(?i)(?:哈佛|牛津|剑桥|斯坦福)\s*(?:研究|教授|学者|团队)',
        r'(?i)(?:诺贝尔奖\s*(?:得主|获得者)\s*(?:说|声称|证实))',
        r'(?i)(?:据\s*(?:内部|知情|权威)\s*(?:人士|消息|来源))',
        r'(?i)(?:[一-鿿]{2,6}(?:研究所|研究院|实验室|中心))\s*(?:发布|证实)',
    ],
    "context_stripping": [
        r'(?i)(?:100%|绝对|肯定|必然|毫无疑问)\s*(?:安全|危险|有效|无效)',
        r'(?i)(?:含有|检测到)\s*(?:有毒|致癌|放射性)\s*(?!(?:剂量|浓度|含量|ppm|mg))',
        r'(?i)(?:比砒霜还毒|比氰化物还强)',
        r'(?i)(?:禁止|禁用|召回)\s*[^。]{0,20}(?!(?:原因|条件|前提|范围))',
    ],
    "false_dichotomy": [
        r'(?i)(?:要么.{2,10}要么.{2,10})',
        r'(?i)(?:不是.{2,8}就是.{2,8})',
        r'(?i)(?:只有.{2,10}才能.{2,10})',
        r'(?i)(?:支持.{2,6}等于.{2,6})',
    ],
    "conspiracy_framing": [
        r'(?i)(?:他们.{2,6}不.{2,6}让.{2,4}知道)',
        r'(?i)(?:隐瞒.{1,6}真相|掩盖.{1,6}事实|封锁.{1,6}消息)',
        r'(?i)(?:深[層层]政府|影子政府|全球精英|幕后黑手)',
        r'(?i)(?:资本|利益集团|财团).{2,8}(?:操控|控制|操纵)',
    ],
    "cherry_picking": [
        r'(?i)(?:一篇\s*(?:研究|论文|报道)\s*(?:证实|证明|表明))',
        r'(?i)(?:调查.{2,10}显示.{2,10}证明)',
        r'(?i)(?:唯一的\s*(?:真相|解释|原因))',
    ],
    "bandwagon": [
        r'(?i)(?:\d+[%％]\s*(?:的人|的网友|的家长|的医生))',
        r'(?i)(?:大家\s*(?:都|都在|都在说)|全网\s*(?:都在|疯传|热议))',
        r'(?i)(?:千万\s*(?:人|网友|家庭)\s*(?:已看|已转发|在关注))',
    ],
    "fear_mongering": [
        r'(?i)(?:正在.{2,8}(?:摧毁|破坏|吞噬|威胁))',
        r'(?i)(?:再不看.{2,8}就晚了)',
        r'(?i)(?:你的.{2,8}正在.{2,8}(?:悄悄|偷偷|暗中))',
        r'(?i)(?:下一个.{2,6}(?:就是你|可能就是你|就是你的))',
    ],
}


class PrebunkingDetector:
    """预揭露检测器 — 识别操纵手法并生成接种提示"""

    @staticmethod
    def detect(text: str, title: str = "") -> PrebunkingResult:
        """检测文本中的操纵手法并生成预揭露提示"""
        combined = f"{title}\n{text}" if title else text
        result = PrebunkingResult()

        technique_scores = {}

        for tech_name, patterns in DETECTION_PATTERNS.items():
            tech_info = MANIPULATION_TECHNIQUES.get(tech_name, {})
            match_count = 0
            matched_snippets = []

            for pattern in patterns:
                matches = re.findall(pattern, combined, re.IGNORECASE)
                if matches:
                    match_count += len(matches)
                    for m in matches[:2]:
                        snippet = str(m)[:80] if isinstance(m, str) else str(m)[:80]
                        matched_snippets.append(snippet)

            if match_count > 0:
                # 加权评分: 基础分 + 匹配数 × 权重
                weight = 2.0 if tech_name in ("emotional_manipulation", "fear_mongering") else 1.5
                score = min(1.0, (1 + match_count * 0.3) * weight / 5.0)
                technique_scores[tech_name] = score

                result.techniques_detected.append({
                    "technique": tech_name,
                    "name": tech_info.get("name_zh", tech_name),
                    "match_count": match_count,
                    "confidence": round(score, 2),
                    "snippets": matched_snippets[:3],
                    "short_desc": tech_info.get("short_desc", ""),
                    "detection_clues": tech_info.get("detection_clues", [])[:3],
                })

        result.detection_count = len(result.techniques_detected)

        if result.detection_count == 0:
            result.risk_level = "low"
            result.summary = "未检测到明显的操纵手法。内容可能为中性表达。"
            result.prebunking_card = ""
            return result

        # 按置信度排序，取最高的为主要手法
        result.techniques_detected.sort(key=lambda x: x["confidence"], reverse=True)
        primary = result.techniques_detected[0]
        result.primary_technique = primary["technique"]

        # 风险等级
        if result.detection_count >= 4:
            result.risk_level = "high"
        elif result.detection_count >= 2:
            result.risk_level = "medium"
        else:
            result.risk_level = "low"

        # 生成接种提示 (取前3个手法)
        for tech in result.techniques_detected[:3]:
            info = MANIPULATION_TECHNIQUES.get(tech["technique"], {})
            prompt = info.get("inoculation_prompt", "")
            if prompt:
                result.inoculations.append(prompt)

        # 生成预揭露卡片
        result.prebunking_card = PrebunkingDetector._build_card(result)
        result.summary = f"检测到 {result.detection_count} 种操纵手法: {', '.join(t['name'] for t in result.techniques_detected[:3])}"

        return result

    @staticmethod
    def _build_card(result: PrebunkingResult) -> str:
        """构建预揭露提示卡片文本"""
        if result.detection_count == 0:
            return ""

        techniques = result.techniques_detected
        risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        emoji = risk_emoji.get(result.risk_level, "🟢")

        parts = [
            f"{emoji} **真相核查提示**: 这篇内容可能使用了以下信息操纵手法，请注意保持批判性思维：\n"
        ]

        for i, tech in enumerate(techniques[:3]):
            info = MANIPULATION_TECHNIQUES.get(tech["technique"], {})
            parts.append(
                f"**{i+1}. {tech['name']}** — {tech['short_desc']}\n"
                f"   > {info.get('why_works', '')[:200]}\n"
                f"   > 检测线索: {'; '.join(tech['detection_clues'][:2])}\n"
            )

        parts.append(
            "\n💡 **建议**: 在采信或分享这篇信息前，请: \n"
            "1) 暂停，确认自己的情绪反应是否正在影响判断\n"
            "2) 寻找原始出处和权威来源进行交叉验证\n"
            "3) 问自己: '如果不认同这篇内容的人，会怎么反驳？'\n"
        )

        return "".join(parts)

# =============================================================================
# 便捷函数
# =============================================================================


def run_prebunking_check(text: str, title: str = "") -> PrebunkingResult:
    """运行预揭露检测"""
    return PrebunkingDetector.detect(text, title)
