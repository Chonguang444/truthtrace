"""
内容去重管理器 — SimHash + 分层哈希 + 时效过期

防止同一谣言以不同形式(不同平台、不同文字表述)被重复分析。
三层去重:
  1. 精确哈希 (SHA256) — 完全相同的文本
  2. SimHash 相似度 — 汉明距离 ≤ 3 的近重复内容
  3. 时效过期 — 超过 72 小时的指纹自动淘汰

集成点:
- BaseCrawler.safe_fetch() 后自动检查
- 追溯任务开始前预检查
- API 接收URL时快速判断是否已分析过
"""

from __future__ import annotations
import hashlib
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

logger = logging.getLogger("truthtrace.dedup")

# =============================================================================
# 配置
# =============================================================================

DEDUP_CONFIG = {
    "simhash_bits": 64,
    "hamming_threshold": 3,        # 汉明距离 <= 3 视为重复
    "fingerprint_ttl": 72 * 3600, # 72小时
    "max_entries": 50_000,         # 最多5万条指纹
    "prune_batch": 5000,           # 每次淘汰5000条
    "min_text_length": 100,        # 少于100字符不计算SimHash
    "min_hash_words": 20,          # 最少20个词才计算
}


@dataclass
class DedupResult:
    """去重检查结果"""
    is_duplicate: bool = False
    match_type: str = ""           # "exact" / "near_duplicate" / "none"
    matched_id: str = ""           # 匹配到的已有内容ID
    hamming_distance: int = -1
    fingerprint: str = ""
    exact_hash: str = ""
    cached_analysis: dict | None = None  # 如果是重复，返回缓存的分析结果


class DedupManager:
    """
    内容去重管理器 — 多层级近似去重。

    使用方式:
        dedup = DedupManager()
        result = dedup.check(title, content)
        if result.is_duplicate:
            return result.cached_analysis  # 跳过分析
        # ... 进行分析 ...
        dedup.store(title, content, analysis_result)
    """

    def __init__(self):
        # 精确哈希 → 条目
        self._exact_hashes: dict[str, dict] = {}
        # SimHash → [(hash, timestamp, entry)]
        self._simhash_index: dict[str, list[tuple[str, float, dict]]] = defaultdict(list)
        self._fingerprinter = None
        self._entry_count = 0

    @property
    def fingerprinter(self):
        """懒加载 SimHash 计算器"""
        if self._fingerprinter is None:
            from app.analyzer.fingerprint import ContentFingerprinter
            self._fingerprinter = ContentFingerprinter(simhash_bits=DEDUP_CONFIG["simhash_bits"])
        return self._fingerprinter

    # ------------------------------------------------------------------
    # 主接口
    # ------------------------------------------------------------------

    def check(self, title: str, content: str) -> DedupResult:
        """
        检查内容是否已存在。

        Args:
            title: 标题
            content: 正文内容

        Returns:
            DedupResult — 去重结果
        """
        # 归一化
        normalized = self._normalize(title, content)
        exact_hash = self._compute_exact_hash(normalized)

        # 第1层: 精确匹配
        if exact_hash in self._exact_hashes:
            entry = self._exact_hashes[exact_hash]
            if not self._is_expired(entry):
                logger.info(f"[去重] 精确匹配: {title[:40]}...")
                return DedupResult(
                    is_duplicate=True,
                    match_type="exact",
                    matched_id=entry.get("id", ""),
                    fingerprint=entry.get("fingerprint", ""),
                    exact_hash=exact_hash,
                    cached_analysis=entry.get("analysis"),
                )

        # 第2层: SimHash 近重复
        if len(normalized) >= DEDUP_CONFIG["min_text_length"]:
            simhash = self.fingerprinter.compute(normalized)

            # 检查所有已存SimHash
            for stored_hash, entries in self._simhash_index.items():
                hd = self.fingerprinter.hamming_distance(simhash, stored_hash)
                if hd <= DEDUP_CONFIG["hamming_threshold"]:
                    for _, _, entry in entries:
                        if not self._is_expired(entry):
                            logger.info(
                                f"[去重] 近重复 (HD={hd}): {title[:40]}..."
                            )
                            return DedupResult(
                                is_duplicate=True,
                                match_type="near_duplicate",
                                matched_id=entry.get("id", ""),
                                hamming_distance=hd,
                                fingerprint=simhash,
                                exact_hash=exact_hash,
                                cached_analysis=entry.get("analysis"),
                            )

        return DedupResult(
            is_duplicate=False,
            match_type="none",
            fingerprint=simhash if len(normalized) >= DEDUP_CONFIG["min_text_length"] else "",
            exact_hash=exact_hash,
        )

    def store(self, title: str, content: str, entry_id: str = "",
              analysis: dict | None = None):
        """
        存储新内容指纹。

        Args:
            title: 标题
            content: 正文内容
            entry_id: 内容标识
            analysis: 可选缓存的完整分析结果
        """
        normalized = self._normalize(title, content)
        exact_hash = self._compute_exact_hash(normalized)
        now = time.time()

        entry = {
            "id": entry_id,
            "title": title[:200],
            "exact_hash": exact_hash,
            "stored_at": now,
            "fingerprint": "",
            "analysis": analysis,
        }

        # 精确哈希存储
        self._exact_hashes[exact_hash] = entry
        self._entry_count += 1

        # SimHash 存储（仅长文本）
        if len(normalized) >= DEDUP_CONFIG["min_text_length"]:
            simhash = self.fingerprinter.compute(normalized)
            entry["fingerprint"] = simhash
            self._simhash_index[simhash].append((exact_hash, now, entry))

        # 内存管理
        self._maybe_prune()

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _normalize(self, title: str, content: str) -> str:
        """文本归一化：标准化空白和去标点"""
        text = f"{title} {content}"[:50_000]
        # 统一空白
        text = re.sub(r'\s+', ' ', text)
        # 去常见噪声
        text = re.sub(r'https?://\S+', ' URL ', text)
        text = re.sub(r'[0-9]{6,}', ' NUM ', text)  # 长数字 → 消除时间戳差异
        return text.lower().strip()

    @staticmethod
    def _compute_exact_hash(text: str) -> str:
        """SHA256 精确哈希"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def _is_expired(self, entry: dict) -> bool:
        """检查条目是否过期"""
        age = time.time() - entry.get("stored_at", 0)
        return age > DEDUP_CONFIG["fingerprint_ttl"]

    def _maybe_prune(self):
        """内存过限时淘汰过期条目"""
        if self._entry_count <= DEDUP_CONFIG["max_entries"]:
            return

        # 删除过期精确哈希
        expired = [h for h, e in self._exact_hashes.items() if self._is_expired(e)]
        for h in expired:
            del self._exact_hashes[h]
            self._entry_count -= 1

        # 删除过期 SimHash 条目
        expired_sh = []
        for sh, entries in self._simhash_index.items():
            entries[:] = [(h, t, e) for h, t, e in entries if not self._is_expired(e)]
            if not entries:
                expired_sh.append(sh)
        for sh in expired_sh:
            del self._simhash_index[sh]

        # 如果还是太多，按时间排序删除最旧的
        if self._entry_count > DEDUP_CONFIG["max_entries"]:
            all_entries = sorted(
                self._exact_hashes.items(),
                key=lambda x: x[1].get("stored_at", 0)
            )
            to_remove = all_entries[:DEDUP_CONFIG["prune_batch"]]
            for h, entry in to_remove:
                sh = entry.get("fingerprint", "")
                if sh and sh in self._simhash_index:
                    self._simhash_index[sh][:] = [
                        (eh, t, e) for eh, t, e in self._simhash_index[sh]
                        if eh != h
                    ]
                    if not self._simhash_index[sh]:
                        del self._simhash_index[sh]
                del self._exact_hashes[h]
                self._entry_count -= 1

            logger.info(f"[去重] 内存淘汰 {len(to_remove)} 条旧指纹")

    def stats(self) -> dict:
        """返回去重统计"""
        return {
            "exact_entries": len(self._exact_hashes),
            "simhash_buckets": len(self._simhash_index),
            "total_entries": self._entry_count,
            "max_entries": DEDUP_CONFIG["max_entries"],
            "config": DEDUP_CONFIG,
        }

    def clear(self):
        """清空所有索引"""
        self._exact_hashes.clear()
        self._simhash_index.clear()
        self._entry_count = 0
        logger.info("[去重] 已清空所有指纹索引")


# =============================================================================
# 全局单例
# =============================================================================

_dedup_manager: DedupManager | None = None


def get_dedup() -> DedupManager:
    """获取全局去重管理器"""
    global _dedup_manager
    if _dedup_manager is None:
        _dedup_manager = DedupManager()
    return _dedup_manager
