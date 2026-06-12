"""
社区众包验证引擎 (Community Crowd Verification) — 第33号引擎

理论基础:
  - Community Notes (PNAS 2025, Nature Comms 2026): 标注减少46-61%转发
  - 桥接算法 (bridging-based ranking): 选择跨意识形态共识的笔记
  - CANote (arXiv 2026): AI辅助社区笔记写作

核心设计:
  1. 用户提交"证据注记" (Evidence Note): 支持/反对/补充/纠正
  2. 桥接评分 (Bridging Score): 跨立场共识 > 单方观点
  3. 声誉系统: 历史准确度 + 社区反馈 → 用户权重
  4. 共识判定: 多注记 + 高桥接评分 → 发布"社区验证"标签

关键原则(来自Community Notes研究):
  - 速度: AI预填充草稿，加速注记提交 (当前62.9h延迟是核心问题)
  - 覆盖: 鼓励跨语言社区参与
  - 质量: 引用权威来源的注记评分更高
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid
import hashlib
import math


@dataclass
class EvidenceNote:
    """用户提交的证据注记"""
    note_id: str = ""
    event_id: str = ""
    user_id: str = ""
    note_type: str = ""    # support / refute / supplement / correct
    content: str = ""       # 注记内容
    sources: list[str] = field(default_factory=list)  # 引用来源URL
    confidence: float = 0.5  # 提交者自评置信度

    # 桥接评分
    bridging_score: float = 0.0
    helpful_votes: int = 0
    unhelpful_votes: int = 0
    user_reputation: float = 0.5  # 该用户的当前声誉分数

    created_at: str = ""
    status: str = "pending"  # pending / published / rejected

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "event_id": self.event_id,
            "user_id": self.user_id[:8] + "...",  # 匿名化
            "note_type": self.note_type,
            "content": self.content[:300],
            "sources": self.sources[:5],
            "confidence": round(self.confidence, 2),
            "bridging_score": round(self.bridging_score, 3),
            "helpful_votes": self.helpful_votes,
            "unhelpful_votes": self.unhelpful_votes,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class CommunityVerificationResult:
    """社区验证结果"""
    notes: list[EvidenceNote] = field(default_factory=list)
    published_notes: list[EvidenceNote] = field(default_factory=list)
    consensus_verdict: str = "no_consensus"  # supported / refuted / disputed / no_consensus
    consensus_score: float = 0.0
    bridging_quality: float = 0.0
    total_contributors: int = 0
    total_evidence_sources: int = 0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "notes": [n.to_dict() for n in self.published_notes[:10]],
            "consensus_verdict": self.consensus_verdict,
            "consensus_score": round(self.consensus_score, 2),
            "bridging_quality": round(self.bridging_quality, 3),
            "total_contributors": self.total_contributors,
            "total_evidence_sources": self.total_evidence_sources,
            "summary": self.summary,
        }


# =============================================================================
# 桥接评分算法 (Bridging-Based Ranking)
# =============================================================================

class BridgingScorer:
    """
    桥接评分器 — 来自Community Notes研究

    核心思想:
    - 注记不仅由"有多少人觉得有帮助"评分
    - 还由"它是否获得了不同立场用户的共同认可"评分
    - 高桥接 = 跨意识形态共识 = 更可能客观准确
    """

    @staticmethod
    def compute_bridging_score(
        note: EvidenceNote,
        all_notes: list[EvidenceNote],
        user_groups: dict[str, str] | None = None,
    ) -> float:
        """
        计算桥接评分。

        bridge_score = agreement_rate × diversity_factor

        agreement_rate: 在所有注记中, 与该注记观点一致的比例
        diversity_factor: 支持该注记的用户群体的立场多样性
        """
        if not all_notes:
            return 0.0

        # 一致性率
        same_type = [n for n in all_notes if n.note_type == note.note_type]
        agreement_rate = len(same_type) / len(all_notes) if all_notes else 0

        # 多样性因子 (简化版: 有不同note_type的用户都认可 = 高桥接)
        unique_types = set(n.note_type for n in all_notes if n.helpful_votes > n.unhelpful_votes)
        diversity_factor = min(1.0, len(unique_types) / 4) if all_notes else 0

        # 加权: 有帮助票 + 来源引用 + 用户声誉
        helpful_factor = min(1.0, (note.helpful_votes + 1) / max(1, note.helpful_votes + note.unhelpful_votes + 1))
        source_bonus = min(0.2, len(note.sources) * 0.05)

        return (agreement_rate * 0.35 + diversity_factor * 0.25 + helpful_factor * 0.25 + source_bonus) * note.user_reputation

    @staticmethod
    def compute_consensus(notes: list[EvidenceNote]) -> tuple[str, float]:
        """计算社区共识"""
        if not notes:
            return "no_consensus", 0.0

        published = [n for n in notes if n.status == "published"]
        if not published:
            return "no_consensus", 0.0

        # 统计各类型注记的加权桥接评分
        type_scores = {}
        for n in published:
            weight = n.bridging_score * n.user_reputation
            type_scores[n.note_type] = type_scores.get(n.note_type, 0) + weight

        total_weight = sum(type_scores.values()) or 0.001

        support_ratio = type_scores.get("support", 0) / total_weight
        refute_ratio = type_scores.get("refute", 0) / total_weight

        if support_ratio > 0.6:
            return "supported", support_ratio
        elif refute_ratio > 0.6:
            return "refuted", refute_ratio
        elif abs(support_ratio - refute_ratio) < 0.15:
            return "disputed", max(support_ratio, refute_ratio)
        else:
            return "no_consensus", max(support_ratio, refute_ratio)


# =============================================================================
# 声誉系统
# =============================================================================

class ReputationSystem:
    """用户声誉评分"""

    @staticmethod
    def compute_reputation(
        user_notes: list[EvidenceNote],
        total_helpful: int = 0,
        total_notes: int = 0,
    ) -> float:
        """计算用户声誉 (0-1)"""
        if not user_notes:
            return 0.5  # 新人起始分

        # 有帮助的注记比例
        notes_with_feedback = [n for n in user_notes if n.helpful_votes + n.unhelpful_votes > 0]
        if not notes_with_feedback:
            return 0.5

        helpful_ratio = sum(n.helpful_votes for n in notes_with_feedback) / max(1,
            sum(n.helpful_votes + n.unhelpful_votes for n in notes_with_feedback))

        # 发布比例
        publish_ratio = len([n for n in user_notes if n.status == "published"]) / max(1, len(user_notes))

        # 来源引用加分
        source_score = min(1.0, sum(len(n.sources) for n in user_notes) / max(1, len(user_notes) * 2))

        # Bayesian平滑 (避免小样本极端)
        prior = 0.5
        weight = min(1.0, len(notes_with_feedback) / 10)

        return prior * (1 - weight) + (helpful_ratio * 0.5 + publish_ratio * 0.3 + source_score * 0.2) * weight


# =============================================================================
# 社区验证引擎
# =============================================================================

class CommunityVerificationEngine:
    """社区验证引擎 — 众包证据注记 + 桥接共识"""

    # 内存存储 (生产用数据库)
    _notes_store: dict[str, list[EvidenceNote]] = {}

    @classmethod
    def submit_note(
        cls,
        event_id: str,
        user_id: str,
        note_type: str,
        content: str,
        sources: list[str] | None = None,
        confidence: float = 0.5,
        user_reputation: float = 0.5,
    ) -> EvidenceNote:
        """提交证据注记"""
        note = EvidenceNote(
            note_id=str(uuid.uuid4()),
            event_id=event_id,
            user_id=user_id,
            note_type=note_type,
            content=content,
            sources=sources or [],
            confidence=confidence,
            user_reputation=user_reputation,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        if event_id not in cls._notes_store:
            cls._notes_store[event_id] = []
        cls._notes_store[event_id].append(note)

        # 自动发布规则
        if len(content) > 30 and (len(sources) >= 1 if sources else False):
            note.status = "published"
            all_notes = cls._notes_store[event_id]
            note.bridging_score = BridgingScorer.compute_bridging_score(note, all_notes)
        else:
            note.status = "pending"

        return note

    @classmethod
    def get_verification(cls, event_id: str) -> CommunityVerificationResult:
        """获取事件的社区验证结果"""
        notes = cls._notes_store.get(event_id, [])
        result = CommunityVerificationResult(notes=notes)

        published = [n for n in notes if n.status == "published"]
        result.published_notes = published
        result.total_contributors = len(set(n.user_id for n in notes))

        # 统计证据来源
        all_sources = set()
        for n in published:
            all_sources.update(n.sources)
        result.total_evidence_sources = len(all_sources)

        # 桥接质量
        if published:
            avg_bridging = sum(n.bridging_score for n in published) / len(published)
            result.bridging_quality = avg_bridging

        # 共识判定
        verdict, score = BridgingScorer.compute_consensus(published)
        result.consensus_verdict = verdict
        result.consensus_score = score

        result.summary = (
            f"{result.total_contributors}位社区贡献者提交了{len(notes)}条注记"
            f"({len(published)}条已发布)。"
            f"社区共识: {verdict} (评分{score:.0%})。"
        )

        return result

    @classmethod
    def vote_note(cls, note_id: str, event_id: str, is_helpful: bool):
        """为注记投票"""
        notes = cls._notes_store.get(event_id, [])
        for note in notes:
            if note.note_id == note_id:
                if is_helpful:
                    note.helpful_votes += 1
                else:
                    note.unhelpful_votes += 1
                # 重新计算桥接评分
                note.bridging_score = BridgingScorer.compute_bridging_score(note, notes)
                break


def run_community_verification(event_id: str = "") -> CommunityVerificationResult:
    """运行社区验证 — 便捷函数"""
    return CommunityVerificationEngine.get_verification(event_id)
