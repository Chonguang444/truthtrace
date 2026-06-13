"""
TruthTrace 核心数据模型
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid as SA_Uuid
import enum

from app.models.base import Base


class EventStatus(str, enum.Enum):
    EMERGING = "emerging"    # 初现端倪
    ACTIVE = "active"        # 热议中
    RESOLVED = "resolved"    # 已有定论


class EdgeType(str, enum.Enum):
    REPOST = "repost"        # 直接转发
    QUOTE = "quote"          # 引用/评论
    REFERENCE = "reference"  # 参考/提及


class Platform(str, enum.Enum):
    WEIBO = "weibo"
    ZHIHU = "zhihu"
    WECHAT = "wechat"
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"
    GENERAL = "general"
    UNKNOWN = "unknown"


class Event(Base):
    """事件主表"""
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    engine_analysis: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="推理引擎全维度分析结果 (distortion/fallacy/statistical/composite/trace/domain/narrative/modality)"
    )

    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus), default=EventStatus.EMERGING, index=True
    )
    credibility_score: Mapped[float] = mapped_column(
        Float, default=50.0,
        comment="可信度评分 0-100，50 为中性"
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # 关系
    sources: Mapped[list["Source"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    timeline_nodes: Mapped[list["TimelineNode"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    rumor_report: Mapped[Optional["RumorReport"]] = relationship(
        back_populates="event", uselist=False, cascade="all, delete-orphan"
    )

    # GIN 索引通过 main.py lifespan 创建 (复合表达式不支持 ORM 声明)

    def __repr__(self):
        return f"<Event {self.title[:30]}>"


class Source(Base):
    """信息源/帖子表"""
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("events.id", ondelete="CASCADE"),
        index=True
    )

    url: Mapped[str] = mapped_column(String(2048), index=True)
    platform: Mapped[Platform] = mapped_column(SAEnum(Platform), index=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    author_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True,
        comment="SimHash 指纹，用于去重")

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 溯源字段
    is_original: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="是否被识别为原始/一手来源"
    )
    authority_score: Mapped[float] = mapped_column(
        Float, default=0.0,
        comment="来源权威度评分 0-100"
    )

    # 互动数据
    engagement_count: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="互动数据: {reposts, likes, comments, views}"
    )

    # 元数据
    meta: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="扩展元数据"
    )

    # 关系
    event: Mapped["Event"] = relationship(back_populates="sources")
    outgoing_edges: Mapped[list["PropagationEdge"]] = relationship(
        back_populates="from_source",
        foreign_keys="PropagationEdge.from_source_id",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["PropagationEdge"]] = relationship(
        back_populates="to_source",
        foreign_keys="PropagationEdge.to_source_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Source {self.platform.value}:{self.author}>"


class PropagationEdge(Base):
    """传播关系边"""
    __tablename__ = "propagation_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    from_source_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    to_source_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )

    edge_type: Mapped[EdgeType] = mapped_column(SAEnum(EdgeType))
    propagated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    weight: Mapped[float] = mapped_column(
        Float, default=1.0,
        comment="传播权重，基于互动量等因素计算"
    )

    # 关系
    from_source: Mapped["Source"] = relationship(
        back_populates="outgoing_edges", foreign_keys=[from_source_id]
    )
    to_source: Mapped["Source"] = relationship(
        back_populates="incoming_edges", foreign_keys=[to_source_id]
    )

    def __repr__(self):
        return f"<Edge {self.edge_type.value}>"


class TimelineNode(Base):
    """事件时间线节点"""
    __tablename__ = "timeline_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("events.id", ondelete="CASCADE"),
        index=True
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SA_Uuid, ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    description: Mapped[str] = mapped_column(String(1000))
    significance: Mapped[float] = mapped_column(
        Float, default=1.0,
        comment="节点重要性评分"
    )

    # 关系
    event: Mapped["Event"] = relationship(back_populates="timeline_nodes")

    def __repr__(self):
        return f"<TimelineNode {self.description[:30]}>"


class RumorReport(Base):
    """辟谣报告"""
    __tablename__ = "rumor_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("events.id", ondelete="CASCADE"),
        unique=True, index=True
    )

    rumor_claim: Mapped[str] = mapped_column(
        Text, comment="谣言声称的内容"
    )
    fact_check_result: Mapped[str] = mapped_column(
        Text, comment="事实核查结果"
    )
    verdict: Mapped[str] = mapped_column(
        String(50), index=True,
        comment="判定: true/false/misleading/unverified"
    )
    verified_sources: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True,
        comment="验证来源列表: [{url, title, credibility}]"
    )
    correction: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="纠正信息"
    )

    published_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # 关系
    event: Mapped["Event"] = relationship(back_populates="rumor_report")

    def __repr__(self):
        return f"<RumorReport verdict={self.verdict}>"
