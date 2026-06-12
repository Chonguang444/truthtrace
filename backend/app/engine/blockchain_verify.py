"""
区块链溯源存证 (Blockchain Trace Verification) — 第39号引擎

非完整区块链 — 基于SHA-256哈希链的防篡改溯源存证
每个溯源结果生成不可篡改的哈希链，分层归因: 直接责任→次级责任
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import hashlib
import json


@dataclass
class TraceBlock:
    block_index: int = 0
    timestamp: str = ""
    event_id: str = ""
    data_hash: str = ""         # 溯源数据的SHA-256
    previous_hash: str = ""     # 前一区块哈希
    block_hash: str = ""        # 本区块哈希
    verification_count: int = 0
    signatures: list[str] = field(default_factory=list)  # 独立验证者签名

    def to_dict(self) -> dict:
        return {
            "block_index": self.block_index,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "data_hash": self.data_hash,
            "previous_hash": self.previous_hash,
            "block_hash": self.block_hash,
            "verification_count": self.verification_count,
        }

    def compute_hash(self) -> str:
        content = f"{self.block_index}{self.timestamp}{self.event_id}{self.data_hash}{self.previous_hash}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class BlockchainVerificationResult:
    chain_name: str = "TruthTrace-Verification-Chain"
    blocks: list[TraceBlock] = field(default_factory=list)
    chain_length: int = 0
    chain_valid: bool = True
    genesis_hash: str = ""
    latest_hash: str = ""
    total_verifications: int = 0
    verification_strength: str = "weak"  # weak/moderate/strong/very_strong
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "chain_name": self.chain_name,
            "blocks": [b.to_dict() for b in self.blocks],
            "chain_length": self.chain_length,
            "chain_valid": self.chain_valid,
            "genesis_hash": self.genesis_hash,
            "latest_hash": self.latest_hash,
            "total_verifications": self.total_verifications,
            "verification_strength": self.verification_strength,
            "summary": self.summary,
        }


@dataclass
class ResponsibilityAttribution:
    """责任归因 (分级归因)"""
    node_id: str = ""
    responsibility_level: str = ""   # direct/primary/secondary/peripheral
    contribution_weight: float = 0.0
    evidence: str = ""
    accountability_score: float = 0.0 # 可追责性 0-1

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "responsibility_level": self.responsibility_level,
            "contribution_weight": round(self.contribution_weight, 2),
            "evidence": self.evidence[:200],
            "accountability_score": round(self.accountability_score, 2),
        }


# =============================================================================
# 区块链溯源引擎
# =============================================================================

class BlockchainVerifier:
    """区块链溯源存证引擎 — SHA-256链式防篡改"""

    @staticmethod
    def hash_analysis_result(analysis_data: dict) -> str:
        """对分析结果生成不可逆哈希"""
        # 排序以确保哈希确定性
        json_str = json.dumps(analysis_data, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    @staticmethod
    def create_block(
        event_id: str,
        data_hash: str,
        previous_block: Optional[TraceBlock] = None,
    ) -> TraceBlock:
        """创建新区块"""
        block = TraceBlock(
            block_index=(previous_block.block_index + 1) if previous_block else 0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id=event_id,
            data_hash=data_hash,
            previous_hash=previous_block.block_hash if previous_block else "0" * 64,
        )
        block.block_hash = block.compute_hash()
        return block

    @staticmethod
    def verify_chain(blocks: list[TraceBlock]) -> bool:
        """验证链完整性"""
        if not blocks:
            return True

        for i in range(1, len(blocks)):
            current = blocks[i]
            previous = blocks[i - 1]

            # 验证前一区块哈希
            if current.previous_hash != previous.block_hash:
                return False

            # 验证当前区块哈希
            if current.compute_hash() != current.block_hash:
                return False

        return True

    @staticmethod
    def create_genesis(event_id: str, analysis_data: dict) -> BlockchainVerificationResult:
        """创建溯源存证的创世区块"""
        data_hash = BlockchainVerifier.hash_analysis_result(analysis_data)

        genesis = TraceBlock(
            block_index=0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id=event_id,
            data_hash=data_hash,
            previous_hash="0" * 64,
        )
        genesis.block_hash = genesis.compute_hash()

        result = BlockchainVerificationResult(
            blocks=[genesis],
            chain_length=1,
            genesis_hash=genesis.block_hash,
            latest_hash=genesis.block_hash,
            total_verifications=1,
            verification_strength="weak",
            summary=f"溯源存证已创建。创世区块: {genesis.block_hash[:16]}...。哈希可公开验证，任何对溯源数据的修改都会改变哈希值。",
        )

        return result

    @staticmethod
    def add_verification(
        chain: BlockchainVerificationResult,
        event_id: str,
        verification_data: dict,
    ) -> BlockchainVerificationResult:
        """添加验证区块"""
        data_hash = BlockchainVerifier.hash_analysis_result(verification_data)
        last_block = chain.blocks[-1] if chain.blocks else None

        new_block = BlockchainVerifier.create_block(event_id, data_hash, last_block)
        chain.blocks.append(new_block)
        chain.chain_length = len(chain.blocks)
        chain.latest_hash = new_block.block_hash
        chain.total_verifications += 1

        # 验证强度
        if chain.total_verifications >= 10:
            chain.verification_strength = "very_strong"
        elif chain.total_verifications >= 5:
            chain.verification_strength = "strong"
        elif chain.total_verifications >= 3:
            chain.verification_strength = "moderate"

        # 链完整性
        chain.chain_valid = BlockchainVerifier.verify_chain(chain.blocks)

        chain.summary = (
            f"溯源存证链: {chain.chain_length}个区块。"
            f"链完整性: {'✅ 有效' if chain.chain_valid else '❌ 已损坏'}。"
            f"验证强度: {chain.verification_strength}。"
            f"最新: {chain.latest_hash[:16]}..."
        )

        return chain

    @staticmethod
    def attribute_responsibility(
        propagation_nodes: list[dict],
        source_node_id: str = "",
    ) -> list[ResponsibilityAttribution]:
        """分级归因: 直接责任→次级责任→外围节点"""
        attributions = []

        # 找到原始来源
        originator = None
        amplifiers = []
        for node in propagation_nodes:
            role = node.get("role", "resharer")
            if role == "originator" or node.get("is_original"):
                originator = node
            elif role in ("amplifier", "resharer"):
                amplifiers.append(node)

        # 原始发布者 → 直接责任
        if originator:
            attributions.append(ResponsibilityAttribution(
                node_id=originator.get("id", source_node_id),
                responsibility_level="direct",
                contribution_weight=1.0,
                evidence="信息原始发布者——对内容真实性负有首要责任",
                accountability_score=0.95,
            ))

        # 放大者 → 次级责任 (权重按粉丝量/传播力递减)
        for i, amp in enumerate(amplifiers[:10]):
            weight = max(0.1, 0.7 - i * 0.06)
            attributions.append(ResponsibilityAttribution(
                node_id=amp.get("id", ""),
                responsibility_level="primary" if weight > 0.4 else "secondary",
                contribution_weight=weight,
                evidence=f"传播放大者——对谣言扩散负有传播责任(权重{weight:.0%})",
                accountability_score=weight * 0.8,
            ))

        return attributions


def create_verification_chain(
    event_id: str = "",
    analysis_data: dict | None = None,
) -> BlockchainVerificationResult:
    """创建溯源存证链 — 便捷函数"""
    return BlockchainVerifier.create_genesis(event_id, analysis_data or {})
