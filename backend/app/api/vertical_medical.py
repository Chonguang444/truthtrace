"""
医疗健康垂直方案 API -- 验证医疗声明/搜索知识库/药物查询
基于 WHO/IARC/GB2760/药典/FDA 权威来源
"""

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.auth.jwt import get_current_active_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 医疗知识库 (20+条目, 来自 WHO/IARC/GB2760/FDA/药典)
# =============================================================================

MEDICAL_KB = [
    # --- 致癌物分类 (IARC) ---
    {
        "id": "kb-iarc-001",
        "substance": "阿斯巴甜",
        "en_name": "Aspartame",
        "category": "食品添加剂",
        "iarc_group": "2B",
        "iarc_desc": "可能对人类致癌(证据有限)",
        "adi": "40 mg/kg体重/天 (JECFA)",
        "context": "一个60kg成年人每天需饮用约12-14罐含阿斯巴甜的无糖可乐才可能超过ADI。普通摄入量远低于安全阈值。",
        "sources": ["IARC Monographs Volume 134 (2023)", "JECFA 2023评估报告"],
        "common_myths": ["阿斯巴甜致癌", "无糖饮料不安全"],
    },
    {
        "id": "kb-iarc-002",
        "substance": "加工肉类",
        "en_name": "Processed Meat",
        "category": "食品",
        "iarc_group": "1",
        "iarc_desc": "对人类致癌(证据充分)",
        "context": "IARC 1类致癌物意味着有充分证据表明致癌,但风险取决于摄入量和频率。与吸烟同属1类但风险远低于吸烟(相对风险~1.18 vs ~20)。",
        "sources": ["IARC Monographs Volume 114 (2015)"],
        "common_myths": ["吃培根等于吸烟", "所有肉都致癌"],
    },
    {
        "id": "kb-iarc-003",
        "substance": "红肉",
        "en_name": "Red Meat",
        "category": "食品",
        "iarc_group": "2A",
        "iarc_desc": "很可能对人类致癌",
        "context": "基于有限证据。主要与结直肠癌相关。适度摄入(每周<500g)风险较低。",
        "sources": ["IARC Monographs Volume 114 (2015)"],
        "common_myths": ["吃红肉必得癌"],
    },
    {
        "id": "kb-iarc-004",
        "substance": "酒精饮料",
        "en_name": "Alcoholic Beverages",
        "category": "饮品",
        "iarc_group": "1",
        "iarc_desc": "对人类致癌(证据充分)",
        "context": "与口腔癌、食道癌、肝癌、乳腺癌等多种癌症相关。风险与饮酒量成正比。",
        "sources": ["IARC Monographs Volume 96 (2010)"],
        "common_myths": ["红酒有益健康所以不致癌", "少量饮酒无害"],
    },
    {
        "id": "kb-iarc-005",
        "substance": "手机辐射",
        "en_name": "Radiofrequency Electromagnetic Fields",
        "category": "物理因素",
        "iarc_group": "2B",
        "iarc_desc": "可能对人类致癌(证据有限)",
        "context": "基于有限的流行病学证据。此分类针对手机重度使用者,与5G基站的环境暴露水平完全不同。5G基站辐射属于非电离辐射,能量不足以破坏DNA。",
        "sources": ["IARC Monographs Volume 102 (2013)", "ICNIRP Guidelines (2020)"],
        "common_myths": ["5G致癌", "手机辐射=核辐射"],
    },

    # --- 食品添加剂 (GB2760) ---
    {
        "id": "kb-gb-001",
        "substance": "苯甲酸钠",
        "category": "防腐剂",
        "gb2760_max": "0.2-2.0 g/kg (视食品类别而定)",
        "safety": "在国标限量内安全",
        "context": "广泛使用的食品防腐剂。在允许剂量内使用是安全的。与维生素C在高温酸性条件下反应可能产生微量苯----这在饮料生产中已有控制措施。",
        "sources": ["GB 2760-2014 食品安全国家标准 食品添加剂使用标准"],
    },
    {
        "id": "kb-gb-002",
        "substance": "山梨酸钾",
        "category": "防腐剂",
        "gb2760_max": "0.075-2.0 g/kg",
        "safety": "在国标限量内安全",
        "context": "是目前公认最安全的食品防腐剂之一,毒性仅为苯甲酸钠的1/4。在体内可正常代谢为CO2和水。",
        "sources": ["GB 2760-2014", "WHO Food Additives Series"],
    },
    {
        "id": "kb-gb-003",
        "substance": "味精(谷氨酸钠)",
        "category": "增味剂",
        "gb2760_max": "适量使用",
        "safety": "安全",
        "context": "JECFA设定的ADI为'未规定'(最安全类别)。中餐馆综合征(MSG symptom complex)的早期研究存在方法学缺陷,多项双盲对照研究未证实。",
        "sources": ["JECFA 1988", "FDA GRAS Notice", "GB 2760-2014"],
        "common_myths": ["味精致癌", "味精有毒", "味精导致头痛"],
    },
    {
        "id": "kb-gb-004",
        "substance": "亚硝酸钠",
        "category": "护色剂/防腐剂",
        "gb2760_max": "0.15 g/kg (肉制品)",
        "safety": "在国标限量内安全,但过量有风险",
        "context": "用于肉制品防腐和护色。本身不致癌,但在体内可能与胺类反应生成亚硝胺(致癌物)。这就是为什么国标严格限量且通常与维生素C(阻断亚硝胺生成)同时使用。",
        "sources": ["GB 2760-2014", "IARC Monographs"],
    },

    # --- 疫苗 ---
    {
        "id": "kb-vax-001",
        "substance": "疫苗与自闭症",
        "category": "疫苗安全",
        "verdict": "无关联",
        "context": "1998年Wakefield在《柳叶刀》发表的研究声称MMR疫苗与自闭症有关联----该研究已被撤回,Wakefield被吊销行医执照。此后多项涉及数百万人的大规模研究(如丹麦2002年537,303名儿童研究、2019年丹麦657,461名儿童研究)均未发现任何关联。",
        "sources": ["Taylor et al. (1999) Lancet", "Hviid et al. (2019) Annals of Internal Medicine", "WHO疫苗安全声明"],
        "common_myths": ["疫苗导致自闭症", "疫苗含有汞所以有毒"],
    },
    {
        "id": "kb-vax-002",
        "substance": "疫苗中的铝佐剂",
        "category": "疫苗成分",
        "verdict": "安全",
        "context": "铝佐剂用于增强免疫反应,使用已有70+年历史。疫苗中的铝含量极低(通常<0.85mg/剂),远低于婴儿每日从母乳(0.04mg/L)或配方奶(0.225mg/L)中摄入的量。FDA和WHO均确认铝佐剂安全。",
        "sources": ["FDA Vaccine Ingredients", "WHO Vaccine Safety Basics"],
    },

    # --- 营养素 ---
    {
        "id": "kb-nut-001",
        "substance": "维生素C",
        "category": "维生素",
        "rda": "成人100mg/天(中国DRIs)",
        "upper_limit": "2000mg/天",
        "context": "大量摄入维生素C不能预防或治愈感冒(最多轻微缩短病程)。极端剂量(>2000mg/天)可能导致腹泻、肾结石。诺贝尔奖得主鲍林关于维生素C治癌的主张未获临床证据支持。",
        "sources": ["中国居民膳食营养素参考摄入量(DRIs)", "Cochrane Review on Vitamin C and Common Cold (2013)"],
        "common_myths": ["大量维生素C能治愈感冒"],
    },
    {
        "id": "kb-nut-002",
        "substance": "胶原蛋白口服",
        "category": "保健品",
        "verdict": "证据不充分",
        "context": "口服胶原蛋白在消化系统中会被分解为氨基酸,与其他蛋白质来源无异。虽然一些小规模研究表明可能有轻度改善皮肤水合作用的效果,但多数高质量研究结论不一致。FDA未批准胶原蛋白作为药物。",
        "sources": ["Choi et al. (2019) J Drugs Dermatol", "FDA"],
        "common_myths": ["口服胶原蛋白能美肤", "胶原蛋白肽能直接补充皮肤胶原"],
    },

    # --- 转基因 ---
    {
        "id": "kb-gmo-001",
        "substance": "转基因作物",
        "en_name": "GMO Crops",
        "category": "农业生物技术",
        "verdict": "现有证据不支持转基因食品对人类健康有害的结论",
        "context": "美国国家科学院2016年综合评估: 对900多项研究进行分析后,未发现转基因作物对人类健康有不良影响的可靠证据。美国科学促进会(AAAS)、世界卫生组织、欧洲委员会均得出类似结论。每个转基因品种需经过独立安全评估。",
        "sources": ["NASEM (2016) Genetically Engineered Crops", "WHO FAQ on GM Foods", "European Commission (2010) A Decade of EU-funded GMO Research"],
        "common_myths": ["转基因致癌", "转基因导致不孕", "转基因破坏基因"],
    },

    # --- 常见药物 ---
    {
        "id": "kb-drug-001",
        "substance": "布洛芬",
        "en_name": "Ibuprofen",
        "category": "NSAID止痛药",
        "max_daily": "1200mg(非处方)/3200mg(处方)",
        "contraindications": ["消化性溃疡", "严重肾功能不全", "妊娠晚期"],
        "context": "常用的非甾体抗炎药。空腹服用可能刺激胃黏膜,建议餐后服用。不应与酒精同时大量使用(增加胃出血风险)。",
        "sources": ["中国药典 2020版", "FDA Drug Label"],
    },
    {
        "id": "kb-drug-002",
        "substance": "对乙酰氨基酚",
        "en_name": "Paracetamol/Acetaminophen",
        "category": "解热镇痛药",
        "max_daily": "2000mg(非处方)/4000mg(处方)",
        "contraindications": ["严重肝功能不全", "酒精依赖"],
        "context": "最常见的解热镇痛药之一。过量(>4000mg/天)可导致严重肝损伤。许多复方感冒药含此成分,同时服用多种含对乙酰氨基酚的药品易超量。",
        "sources": ["中国药典 2020版", "FDA Drug Label"],
    },
    {
        "id": "kb-drug-003",
        "substance": "阿莫西林",
        "en_name": "Amoxicillin",
        "category": "抗生素(青霉素类)",
        "contraindications": ["青霉素过敏", "传染性单核细胞增多症"],
        "context": "仅对细菌感染有效,对病毒(如普通感冒、流感)完全无效。滥用抗生素是导致细菌耐药性的主要原因。需医生处方使用。",
        "sources": ["中国药典 2020版", "WHO Model List of Essential Medicines"],
        "common_myths": ["感冒吃阿莫西林好得快"],
    },

    # --- 饮食健康 ---
    {
        "id": "kb-diet-001",
        "substance": "代糖/非营养性甜味剂",
        "category": "食品添加剂",
        "verdict": "在ADI范围内安全",
        "context": "WHO 2023年指南建议不要使用非糖甜味剂来控制体重(基于观察性研究的条件性建议)。注意: 这是关于体重控制的建议,而非安全性警告。JECFA和FDA维持安全性结论。",
        "sources": ["WHO Guideline on Non-Sugar Sweeteners (2023)", "FDA High-Intensity Sweeteners"],
    },
    {
        "id": "kb-diet-002",
        "substance": "反式脂肪酸",
        "category": "营养成分",
        "verdict": "有害健康",
        "context": "工业生产的反式脂肪增加LDL-C、降低HDL-C,增加心血管疾病风险。WHO建议将其摄入量限制在总能量摄入的1%以下。许多国家已禁止或限制使用部分氢化油。",
        "sources": ["WHO REPLACE action package", "FDA Final Determination on PHOs (2015)"],
    },
]


# =============================================================================
# 数据模型
# =============================================================================

class MedicalVerifyRequest(BaseModel):
    claim: str


class DrugCheckRequest(BaseModel):
    drug_name: str


# =============================================================================
# 端点
# =============================================================================

@router.get("/vertical/medical/verify")
async def verify_medical_claim(claim: str = Query(..., min_length=2, description="待验证的医疗健康声明")):
    """验证医疗健康声明"""
    results = []

    for entry in MEDICAL_KB:
        substance = entry.get("substance", "")
        en_name = entry.get("en_name", "")
        common_myths = entry.get("common_myths", [])

        # 多维度匹配
        match_score = 0
        if substance and substance in claim:
            match_score += 5
        if en_name and en_name.lower() in claim.lower():
            match_score += 5
        for myth in common_myths:
            if any(word in claim for word in myth.replace("不", "").replace("导致", "").split()):
                match_score += 3

        if match_score >= 3:
            results.append({
                "matched_entity": substance,
                "category": entry.get("category", ""),
                "verdict": entry.get("verdict", entry.get("iarc_desc", entry.get("safety", "参考知识库"))),
                "context": entry.get("context", ""),
                "sources": entry.get("sources", []),
                "match_confidence": min(match_score / 10, 1.0),
                "common_myths": entry.get("common_myths", []),
            })

    # 按匹配度排序
    results.sort(key=lambda r: r["match_confidence"], reverse=True)

    if not results:
        return {
            "claim": claim,
            "results": [],
            "verdict": "unknown",
            "message": "该声明不在当前知识库覆盖范围内。系统不编造答案----建议查阅WHO/CDC/药监局等权威来源。",
            "uncertainty_note": "医疗健康知识库持续更新中。如涉及个人健康决策,请咨询医生。",
        }

    return {
        "claim": claim,
        "results": results[:5],
        "top_verdict": results[0]["verdict"] if results else "unknown",
        "knowledge_base_version": "2026.06",
        "disclaimer": "本知识库基于公开的权威来源(WHO/IARC/GB2760/药典/FDA)。仅供参考,不构成医疗建议。",
    }


@router.get("/vertical/medical/kb/search")
async def search_medical_kb(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    category: str | None = Query(None, description="分类: 食品添加剂/疫苗安全/维生素/保健品/农业生物技术/..."),
):
    """搜索医疗知识库"""
    results = []
    for entry in MEDICAL_KB:
        text = f"{entry.get('substance', '')} {entry.get('en_name', '')} {entry.get('category', '')} {' '.join(entry.get('common_myths', []))} {entry.get('context', '')}"
        if q.lower() in text.lower():
            if category and category not in entry.get("category", ""):
                continue
            results.append({
                "id": entry["id"],
                "substance": entry.get("substance", ""),
                "category": entry.get("category", ""),
                "verdict": entry.get("verdict", entry.get("iarc_desc", "")),
                "sources": entry.get("sources", []),
            })

    return {
        "query": q,
        "total": len(results),
        "items": results[:20],
        "categories_available": list(set(
            e.get("category", "") for e in MEDICAL_KB
        )),
    }


@router.get("/vertical/medical/drug/check")
async def check_drug(
    drug_name: str = Query(..., min_length=1, description="药物名称(中文或英文)"),
):
    """药物信息查询"""
    drug_entries = [e for e in MEDICAL_KB if e.get("category", "").startswith(("NSAID", "解热", "抗生素"))]

    for entry in drug_entries:
        if (drug_name in entry.get("substance", "")
            or drug_name.lower() in entry.get("en_name", "").lower()):
            return {
                "drug": entry.get("substance", ""),
                "en_name": entry.get("en_name", ""),
                "category": entry.get("category", ""),
                "max_daily": entry.get("max_daily", "请遵医嘱"),
                "contraindications": entry.get("contraindications", []),
                "context": entry.get("context", ""),
                "sources": entry.get("sources", []),
                "warning": "药物信息仅供参考。用药请遵医嘱,不要自行调整剂量。",
            }

    raise HTTPException(404, f"未找到药物 '{drug_name}' 的信息")
