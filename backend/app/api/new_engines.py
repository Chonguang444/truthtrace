"""
新引擎 API 端点 — 预揭露/可信度/知识图谱/个性化辟谣/社区验证/深度伪造/信息污染/教学助手/叙事战场
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import Optional

router = APIRouter()


# =============================================================================
# 请求模型
# =============================================================================

class PrebunkingRequest(BaseModel):
    text: str = ""
    title: str = ""

    @field_validator("text")
    @classmethod
    def text_required(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError("文本至少需要10个字符")
        return v


class KGReasoningRequest(BaseModel):
    text: str = ""
    title: str = ""
    claims: list[str] = []


class PersonalizedDebunkingRequest(BaseModel):
    rumor: str = ""
    verified_facts: list[str] = []
    sources: list[str] = []
    query: str = ""
    persona: Optional[dict] = None


class CommunityNoteRequest(BaseModel):
    event_id: str = ""
    note_type: str = "supplement"  # support/refute/supplement/correct
    content: str = ""
    sources: list[str] = []
    confidence: float = 0.5


class DeepfakeCheckRequest(BaseModel):
    text: str = ""
    has_image: bool = False
    has_video: bool = False
    has_audio: bool = False
    file_info: Optional[dict] = None


class TeachingRequest(BaseModel):
    claim: str = ""
    level: str = "guided"
    user_answers: Optional[dict[str, str]] = None


# =============================================================================
# P0: 预揭露
# =============================================================================

@router.post("/prebunking/check")
async def check_prebunking(req: PrebunkingRequest):
    """检测操纵手法并生成预揭露提示"""
    from app.engine.prebunking import run_prebunking_check
    result = run_prebunking_check(text=req.text, title=req.title)
    return result.to_dict()


# =============================================================================
# P0: 溯源可信度指数
# =============================================================================

@router.get("/credibility-index/{event_id}")
async def get_credibility_index(event_id: str):
    """获取事件的溯源可信度指数"""
    from app.engine.credibility_index import compute_credibility_index
    # 从数据库获取节点和边 (简化版)
    result = compute_credibility_index(nodes=[{"id": event_id, "url": f"https://truthtrace.app/events/{event_id}"}])
    return result.to_dict()


# =============================================================================
# P1: 知识图谱推理
# =============================================================================

@router.post("/kg-reasoning")
async def kg_reasoning(req: KGReasoningRequest):
    """知识图谱增强推理"""
    from app.engine.kg_reasoning import run_kg_reasoning
    result = run_kg_reasoning(text=req.text, claims=req.claims, title=req.title)
    return result.to_dict()


# =============================================================================
# P1: 个性化辟谣
# =============================================================================

@router.post("/personalized-debunking")
async def personalized_debunking(req: PersonalizedDebunkingRequest):
    """生成个性化辟谣文本"""
    from app.engine.personalized_debunking import generate_personalized_debunking
    result = generate_personalized_debunking(
        rumor=req.rumor, verified_facts=req.verified_facts,
        sources=req.sources, query=req.query, persona=req.persona,
    )
    return result.to_dict()


# =============================================================================
# P1: 社区验证
# =============================================================================

@router.post("/community/notes")
async def submit_community_note(req: CommunityNoteRequest):
    """提交社区证据注记"""
    from app.engine.community_verify import CommunityVerificationEngine
    note = CommunityVerificationEngine.submit_note(
        event_id=req.event_id, user_id="anonymous",
        note_type=req.note_type, content=req.content,
        sources=req.sources, confidence=req.confidence,
    )
    return note.to_dict()


@router.get("/community/verification/{event_id}")
async def get_community_verification(event_id: str):
    """获取社区验证结果"""
    from app.engine.community_verify import run_community_verification
    result = run_community_verification(event_id=event_id)
    return result.to_dict()


@router.post("/community/notes/{note_id}/vote")
async def vote_community_note(note_id: str, event_id: str = Query(...), helpful: bool = Query(True)):
    """为社区注记投票"""
    from app.engine.community_verify import CommunityVerificationEngine
    CommunityVerificationEngine.vote_note(note_id=note_id, event_id=event_id, is_helpful=helpful)
    return {"status": "voted", "note_id": note_id, "helpful": helpful}


# =============================================================================
# P1: 深度伪造检测
# =============================================================================

@router.post("/deepfake/check")
async def check_deepfake(req: DeepfakeCheckRequest):
    """多模态深度伪造检测"""
    from app.engine.deepfake_detector import run_deepfake_check
    result = run_deepfake_check(
        text=req.text, file_info=req.file_info,
        has_image=req.has_image, has_video=req.has_video,
        has_audio=req.has_audio,
    )
    return result.to_dict()


# =============================================================================
# P2: 信息污染指数
# =============================================================================

@router.get("/pollution-index")
async def get_pollution_index():
    """获取实时信息污染指数 (AQI式公共产品)"""
    from app.engine.pollution_index import compute_pollution_index
    result = compute_pollution_index()
    return result.to_dict()


# =============================================================================
# P2: AI事实核查教学
# =============================================================================

@router.post("/teach/lesson")
async def create_teaching_lesson(req: TeachingRequest):
    """生成AI事实核查教学课程"""
    from app.engine.teach_assistant import generate_teaching_lesson
    result = generate_teaching_lesson(
        claim=req.claim, level=req.level,
        user_answers=req.user_answers,
    )
    return result.to_dict()


@router.get("/teach/prompt")
async def get_teaching_prompt(claim: str = Query(...)):
    """获取引导式验证提示"""
    from app.engine.teach_assistant import FactCheckTeacher
    prompt = FactCheckTeacher.generate_prompt(claim)
    return {"prompt": prompt}


# =============================================================================
# P2: 叙事战场
# =============================================================================

@router.get("/narrative-battlefield/{event_id}")
async def get_narrative_battlefield(
    event_id: str,
    text: str = Query(""),
    title: str = Query(""),
):
    """获取事件的叙事战场分析"""
    from app.engine.narrative_battlefield import analyze_narrative_battlefield
    result = analyze_narrative_battlefield(text=text, title=title)
    return result.to_dict()


# =============================================================================
# P2: 区块链存证
# =============================================================================

@router.post("/blockchain/verify")
async def create_blockchain_verification(
    event_id: str = Query(...),
):
    """创建溯源存证的上链记录"""
    from app.engine.blockchain_verify import create_verification_chain
    result = create_verification_chain(event_id=event_id)
    return result.to_dict()
