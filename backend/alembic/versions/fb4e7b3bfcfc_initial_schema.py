"""initial_schema

TruthTrace complete database schema — 8 tables, 15+ indexes, 6 enums

Revision ID: fb4e7b3bfcfc
Revises:
Create Date: 2026-06-10 11:35:52
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

# revision identifiers
revision: str = 'fb4e7b3bfcfc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PostgreSQL UUID type that falls back to String for SQLite
def _uuid_type():
    """Return appropriate UUID column type for the backend."""
    # Use sa.Text for dialect-agnostic UUIDs (SQLite doesn't have native UUID)
    return sa.String(36)


def upgrade() -> None:
    # =========================================================================
    # 1. events — 事件主表
    # =========================================================================
    op.create_table(
        'events',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False, index=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('engine_analysis', sa.JSON(), nullable=True,
                  comment='推理引擎全维度分析结果 (distortion/fallacy/statistical/composite/trace/domain/narrative/modality)'),
        sa.Column('status', sa.String(20), nullable=False, server_default='emerging', index=True),
        sa.Column('credibility_score', sa.Float(), nullable=False, server_default='50.0',
                  comment='可信度评分 0-100，50 为中性'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('last_updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    # =========================================================================
    # 2. sources — 信息源/帖子表
    # =========================================================================
    op.create_table(
        'sources',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('event_id', _uuid_type(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('url', sa.String(2048), nullable=False, index=True),
        sa.Column('platform', sa.String(20), nullable=False, index=True),
        sa.Column('author', sa.String(255), nullable=True, index=True),
        sa.Column('author_id', sa.String(255), nullable=True),
        sa.Column('title', sa.String(1000), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False, index=True, comment='SimHash 指纹，用于去重'),
        sa.Column('published_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_original', sa.Boolean(), nullable=False, server_default='0',
                  comment='是否被识别为原始/一手来源'),
        sa.Column('authority_score', sa.Float(), nullable=False, server_default='0.0',
                  comment='来源权威度评分 0-100'),
        sa.Column('engagement_count', sa.JSON(), nullable=True,
                  comment='互动数据: {reposts, likes, comments, views}'),
        sa.Column('meta', sa.JSON(), nullable=True, comment='扩展元数据'),
    )
    # ix_sources_url, ix_sources_platform are auto-created by index=True on Column

    # =========================================================================
    # 3. propagation_edges — 传播关系边
    # =========================================================================
    op.create_table(
        'propagation_edges',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('from_source_id', _uuid_type(), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('to_source_id', _uuid_type(), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('edge_type', sa.String(20), nullable=False),
        sa.Column('propagated_at', sa.DateTime(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0',
                  comment='传播权重，基于互动量等因素计算'),
    )

    # =========================================================================
    # 4. timeline_nodes — 事件时间线节点
    # =========================================================================
    op.create_table(
        'timeline_nodes',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('event_id', _uuid_type(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_id', _uuid_type(), sa.ForeignKey('sources.id', ondelete='SET NULL'), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('description', sa.String(1000), nullable=False),
        sa.Column('significance', sa.Float(), nullable=False, server_default='1.0',
                  comment='节点重要性评分'),
    )

    # =========================================================================
    # 5. rumor_reports — 辟谣报告
    # =========================================================================
    op.create_table(
        'rumor_reports',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('event_id', _uuid_type(), sa.ForeignKey('events.id', ondelete='CASCADE'),
                  nullable=False, unique=True, index=True),
        sa.Column('rumor_claim', sa.Text(), nullable=False, comment='谣言声称的内容'),
        sa.Column('fact_check_result', sa.Text(), nullable=False, comment='事实核查结果'),
        sa.Column('verdict', sa.String(50), nullable=False, index=True,
                  comment='判定: true/false/misleading/unverified'),
        sa.Column('verified_sources', sa.JSON(), nullable=True,
                  comment='验证来源列表: [{url, title, credibility}]'),
        sa.Column('correction', sa.Text(), nullable=True, comment='纠正信息'),
        sa.Column('published_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # =========================================================================
    # 6. users — 用户表
    # =========================================================================
    op.create_table(
        'users',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('display_name', sa.String(128), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
    )
    # ix_users_username, ix_users_email are auto-created by unique=True on Column

    # =========================================================================
    # 7. user_favorites — 用户收藏
    # =========================================================================
    op.create_table(
        'user_favorites',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('user_id', _uuid_type(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_id', _uuid_type(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # =========================================================================
    # 8. user_subscriptions — 用户订阅
    # =========================================================================
    op.create_table(
        'user_subscriptions',
        sa.Column('id', _uuid_type(), primary_key=True),
        sa.Column('user_id', _uuid_type(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_id', _uuid_type(), sa.ForeignKey('events.id', ondelete='CASCADE'),
                  nullable=True, index=True,
                  comment='订阅特定事件，NULL 表示全局订阅'),
        sa.Column('keyword', sa.String(255), nullable=True,
                  comment='订阅关键词，匹配新事件'),
        sa.Column('notify_rumor', sa.Boolean(), nullable=False, server_default='1',
                  comment='辟谣报告更新时通知'),
        sa.Column('notify_propagation', sa.Boolean(), nullable=False, server_default='1',
                  comment='传播链路更新时通知'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # =========================================================================
    # PostgreSQL specific: GIN full-text search indexes
    # SQLite doesn't support GIN, so these are conditional
    # =========================================================================
    # These are created in main.py lifespan for now (database-agnostic)
    # When targeting PostgreSQL, uncomment:
    # op.execute("CREATE INDEX IF NOT EXISTS ix_events_search_tsv ON events "
    #            "USING gin (to_tsvector('simple', coalesce(title, '')) "
    #            "|| to_tsvector('simple', coalesce(summary, '')))")


def downgrade() -> None:
    op.drop_table('user_subscriptions')
    op.drop_table('user_favorites')
    op.drop_table('users')
    op.drop_table('rumor_reports')
    op.drop_table('timeline_nodes')
    op.drop_table('propagation_edges')
    op.drop_table('sources')
    op.drop_table('events')
