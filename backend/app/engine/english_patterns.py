"""
英文信息检测补充模式

TruthTrace 核心引擎的中文正则模式在英文内容上识别能力有限。
本模块提供英文补充模式，各引擎可组合调用。

用法:
    from app.engine.english_patterns import ENGLISH_PATTERNS
    # 附加到原有中文模式后进行匹配
"""

# =============================================================================
# 英文失真检测补充 (7 categories)
# =============================================================================

ENGLISH_DISTORTION_PATTERNS = [
    # 1. Source fabrication — blurry sources
    ("source_fabrication", [
        r'(?i)(?:studies?\s*show|research\s*(?:shows|indicates)|scientists?\s*(?:say|claim|discover))'
            r'(?!.*(?:published in|doi:?|journal of|https?://|according to.{0,40}(?:WHO|CDC|FDA|WHO|UN|NIH)))',
        r'(?i)(?:experts?\s*(?:warn|say|claim)|top\s*doctors?\s*recommend)'
            r'(?!.*(?:MD|PhD|board\s*certified|affiliated\s*with))',
        r'(?i)(?:anonymous\s*(?:source|tip|whistleblower)|sources?\s*(?:close\s*to|familiar\s*with))',
        r'(?i)(?:according\s*to\s*(?:a\s*)?(?:study|research|report))(?!.{0,50}(?:published|journal|link|url))',
    ]),
    # 2. Context stripping — removing critical context
    ("context_stripping", [
        r'(?i)(?:causes?\s*(?:cancer|autism|death|blindness|infertility))'
            r'(?!.{0,40}(?:dose|concentration|exposure|long.?term|established|peer.?reviewed))',
        r'(?i)(?:100%|absolutely|definitely|undeniably|without\s*(?:a\s*)?doubt)\s*(?:safe|dangerous|effective|proven)',
        r'(?i)(?:toxic|poisonous|deadly|lethal)\s*(?:chemical|ingredient|substance|food)'
            r'(?!.{0,40}(?:dose|quantity|concentration|level))',
    ]),
    # 3. Emotional manipulation
    ("emotional_manipulation", [
        r'(?i)(?:share\s*(?:this|before|now)|this\s*(?:will|is\s*going\s*to)\s*shock\s*you)',
        r'(?i)(?:they\s*(?:don\'t|do\s*not)\s*want\s*you\s*to\s*know|the\s*(?:government|media)\s*(?:is|are)\s*hiding)',
        r'(?i)(?:wake\s*up\s*(?:America|people|sheeple)|open\s*your\s*eyes)',
        r'(?i)(?:urgent|breaking|alert|warning).{0,50}(?:must\s*read|share|forward)',
    ]),
    # 4. Authority abuse — fake authority
    ("authority_abuse", [
        r'(?i)(?:Harvard\s*(?:study|researcher|scientist))\s*(?:proves?|shows?|confirms?)'
            r'(?!.{0,50}(?:published|journal|doi|peer.?reviewed))',
        r'(?i)(?:Nobel\s*(?:prize\s*)?(?:winner|laureate)\s*(?:says|claims|proves))',
        r'(?i)(?:according\s*to\s*(?:anonymous\s*)?(?:expert|doctor|scientist|professor))'
            r'(?!.{0,40}(?:university|institute|published|credentials))',
    ]),
    # 5. False equivalence
    ("decontextualization", [
        r'(?i)(?:just\s*as\s*(?:bad|dangerous|deadly|toxic)\s*as)',
        r'(?i)(?:more\s*(?:dangerous|toxic|deadly)\s*than\s*(?:cyanide|arsenic|nuclear))',
        r'(?i)(?:natural\s*=\s*safe|chemical\s*=\s*toxic|synthetic\s*=\s*dangerous)',
    ]),
]

# =============================================================================
# 英文逻辑谬误补充 (12 categories)
# =============================================================================

ENGLISH_FALLACY_PATTERNS = [
    ("false_dichotomy", [
        r'(?i)(?:you.?re?\s*(?:either|with)|if\s*you.?re?\s*not\s*with\s*(?:us|me))',
        r'(?i)(?:it.?s?\s*either.{0,30}or.{0,30}there.?s?\s*no\s*(?:middle|third|alternative))',
    ]),
    ("slippery_slope", [
        r'(?i)(?:if\s*we\s*(?:let|allow|start)\s*(?:this|them).{0,50}(?:next|\s*then).{0,50}(?:eventually|finally|end\s*up))',
        r'(?i)(?:it\s*(?:starts|begins)\s*with.{0,50}(?:ends\s*with|leads\s*to|results\s*in))',
    ]),
    ("hasty_generalization", [
        r'(?i)(?:all\s*(?:of\s*)?(?:the|these|those)|every\s*(?:single\s*)?(?:one|person|case|time))',
        r'(?i)(?:never|always|everyone|nobody|no\s*one)\s*(?:has|does|is|can|will)',
    ]),
    ("straw_man", [
        r'(?i)(?:so\s*(?:you.?re?|you\s*are)\s*saying|so\s*(?:what\s*you|you.?re?)\s*(?:really|basically|essentially)\s*(?:saying|claiming))',
        r'(?i)(?:you\s*(?:just|only)\s*(?:think|believe|care\s*about))',
    ]),
    ("appeal_to_authority", [
        r'(?i)(?:scientists?\s*agree|doctors?\s*confirm|experts?\s*unanimous)'
            r'(?!.{0,60}(?:study|survey|meta.?analysis|systematic\s*review))',
    ]),
    ("red_herring", [
        r'(?i)(?:what\s*about.{0,30}\?|whatabout.{0,30}\?)',
        r'(?i)(?:but\s*(?:what\s*about|you\s*didn.?t?\s*mention))',
    ]),
    ("false_cause", [
        r'(?i)(?:since.{0,50}(?:then|after\s*that|afterwards).{0,50}(?:happened|occurred|started|began))',
    ]),
]

# =============================================================================
# 英文因果指标词
# =============================================================================

ENGLISH_CAUSAL_INDICATORS = [
    # Strong causal
    (r'(.{1,80})\s*(?:causes?|leads?\s*to|results?\s*in|triggers?|induces?)\s*(.{1,80})', "direct_cause", 70),
    (r'(.{1,80})\s*(?:because|due\s*to|as\s*a\s*result\s*of|owing\s*to)\s*(.{1,80})', "direct_cause", 65),
    (r'(.{1,80})\s*(?:therefore|thus|hence|consequently|as\s*a\s*consequence)\s*(.{1,80})', "direct_cause", 60),
    # Contributing
    (r'(.{1,80})\s*(?:contributes?\s*to|promotes?|increases?|enhances?)\s*(.{1,80})', "contributing", 45),
    (r'(.{1,80})\s*(?:is\s*(?:linked|associated|correlated)\s*(?:to|with))\s*(.{1,80})', "corr_as_cause", 30),
    # Conditional
    (r'(?:if|when|should)\s*(.{1,60})\s*(?:then|will|would|may|might)\s*(.{1,60})', "contributing", 35),
]

# =============================================================================
# 英文叙事框架补充
# =============================================================================

ENGLISH_NARRATIVE_PATTERNS = [
    ("conspiracy_theory", [
        r'(?i)(?:deep\s*state|new\s*world\s*order|global\s*elite|cabal|shadow\s*government)',
        r'(?i)(?:they\s*(?:don.?t|do\s*not)\s*want\s*you\s*to\s*know|the\s*truth\s*they.?re?\s*hiding)',
        r'(?i)(?:mainstream\s*media\s*(?:cover.?up|won.?t\s*tell|is\s*lying))',
        r'(?i)(?:orchestrated|engineered|planned|designed)\s*(?:by\s*the\s*(?:government|elites|corporations))',
    ]),
    ("fear_mongering", [
        r'(?i)(?:this\s*(?:will|is\s*going\s*to)\s*(?:destroy|ruin|kill|wipe\s*out))',
        r'(?i)(?:your\s*(?:children|family|health|life)\s*(?:is|are)\s*in\s*(?:danger|jeopardy|risk))',
        r'(?i)(?:it.?s?\s*(?:already\s*)?(?:too\s*late|happening|spreading))',
    ]),
    ("us_vs_them", [
        r'(?i)(?:(?:the|these)\s*(?:elites|globalists|corporations|billionaires)\s*(?:are|want))',
        r'(?i)(?:ordinary\s*(?:people|citizens|Americans|folks)\s*vs?\.?\s*(?:the\s*(?:elite|establishment|system)))',
    ]),
    ("scientism_abuse", [
        r'(?i)(?:quantum.{0,30}(?:healing|energy|consciousness|vibration))',
        r'(?i)(?:science\s*(?:proves|shows|confirms).{0,30}(?:miracle|magical|supernatural))',
        r'(?i)(?:clinically\s*proven|scientifically\s*proven)(?!.{0,60}(?:study|trial|peer.?reviewed))',
    ]),
    ("technophobia", [
        r'(?i)(?:AI\s*(?:will|is\s*going\s*to)\s*(?:take\s*over|destroy|replace|enslave))',
        r'(?i)(?:(?:5G|WiFi|cell\s*(?:phone|tower))\s*(?:radiation|beams|waves)\s*(?:causes?|cooks?|fries?|damages?))',
    ]),
    ("moral_panic", [
        r'(?i)(?:this\s*generation\s*(?:is|has)\s*(?:lost|losing|ruined|destroyed))',
        r'(?i)(?:our\s*(?:children|kids|youth|society)\s*(?:is|are)\s*(?:being|losing|at\s*risk))',
    ]),
]

# =============================================================================
# 英文虚假信息指标词
# =============================================================================

ENGLISH_MISINFO_MARKERS = [
    # Clickbait / engagement bait
    r'(?i)(?:you\s*won.?t?\s*believe|what\s*happens?\s*next|number\s*\d+\s*will\s*shock\s*you)',
    # Anti-establishment
    r'(?i)(?:big\s*(?:pharma|tech|ag|oil|food)\s*(?:doesn.?t|don.?t|is|are)\s*(?:want|hiding|lying))',
    # Miracle cure claims
    r'(?i)(?:miracle\s*cure|cured?\s*(?:overnight|instantly|completely)|secret\s*(?:cure|remedy|formula)\s*(?:they|doctors?)\s*(?:don.?t|won.?t))',
    # Anti-vaccine tropes
    r'(?i)(?:vaccine\s*(?:injuries?|deaths?|shedding)|vaccines?\s*(?:cause|contain|are)\s*(?:autism|mercury|toxins?|poison))',
    # Plandemic/false flag
    r'(?i)(?:(?:plandemic|scamdemic|false\s*flag|hoax))',
    # Censorship claims
    r'(?i)(?:they.?re?\s*(?:censoring|silencing|shadow.?banning|deplatforming)\s*(?:me|us|the\s*truth))',
]

# =============================================================================
# 评分加成
# =============================================================================

def score_english_misinfo(text: str) -> dict:
    """
    对英文文本进行补充评分。
    返回附加风险分数，用于合并到已有的中文引擎评分中。
    """
    import re as _re

    risk_score = 0.0
    matches = []

    for marker in ENGLISH_MISINFO_MARKERS:
        found = _re.findall(marker, text)
        if found:
            risk_score += len(found) * 8
            matches.append({
                "marker": marker[:60],
                "count": len(found),
                "signal": "english_misinfo_marker",
            })

    # Check distortion patterns
    for dist_type, patterns in ENGLISH_DISTORTION_PATTERNS:
        for pat in patterns:
            found = _re.findall(pat, text)
            if found:
                risk_score += len(found) * 10
                matches.append({
                    "type": f"distortion:{dist_type}",
                    "count": len(found),
                    "signal": "english_distortion",
                })
                break  # One match per category

    # Check narrative patterns
    for narr_type, patterns in ENGLISH_NARRATIVE_PATTERNS:
        for pat in patterns:
            found = _re.findall(pat, text)
            if found:
                risk_score += len(found) * 8
                matches.append({
                    "type": f"narrative:{narr_type}",
                    "count": len(found),
                    "signal": "english_narrative",
                })
                break

    return {
        "risk_score": min(100.0, risk_score),
        "matches": matches,
        "match_count": len(matches),
        "language": "en",
    }
