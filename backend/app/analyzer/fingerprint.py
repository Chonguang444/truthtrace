"""
内容指纹 — SimHash + MinHash 支持
用于内容去重和相似度检测
"""

import hashlib
import re
from collections import defaultdict

from loguru import logger


class ContentFingerprinter:
    """
    内容指纹计算器

    提供两种指纹算法：
    1. SimHash — 快速近似去重（适合海量文本）
    2. MinHash — 精确相似度估算（适合短文本比较）
    """

    def __init__(self, simhash_bits: int = 64):
        self.simhash_bits = simhash_bits

    def compute(self, text: str) -> str:
        """
        计算内容的 SimHash 指纹

        Args:
            text: 输入文本

        Returns:
            SimHash 十六进制字符串
        """
        if not text:
            return "0" * (self.simhash_bits // 4)

        # 分词 + 权重
        tokens = self._tokenize(text)
        weights = self._compute_weights(tokens)

        # SimHash 向量累加
        vector = [0] * self.simhash_bits

        for token, weight in weights.items():
            token_hash = int(hashlib.md5(token.encode()).hexdigest(), 16)

            for i in range(self.simhash_bits):
                bit = (token_hash >> i) & 1
                if bit == 1:
                    vector[i] += weight
                else:
                    vector[i] -= weight

        # 压缩为二进制指纹
        fingerprint = 0
        for i in range(self.simhash_bits):
            if vector[i] > 0:
                fingerprint |= (1 << i)

        return hex(fingerprint)[2:].zfill(self.simhash_bits // 4)

    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        计算两个 SimHash 之间的汉明距离

        Args:
            hash1, hash2: SimHash 十六进制字符串

        Returns:
            汉明距离 (0 = 完全相同)
        """
        try:
            int1 = int(hash1, 16)
            int2 = int(hash2, 16)
        except ValueError:
            return self.simhash_bits

        xor = int1 ^ int2
        return xor.bit_count()

    def is_duplicate(self, hash1: str, hash2: str, threshold: int = 3) -> bool:
        """
        判断两段内容是否重复

        SimHash 汉明距离 <= threshold 认为内容相同/高度相似
        经验值: threshold=3 对于 64-bit SimHash 效果良好
        """
        return self.hamming_distance(hash1, hash2) <= threshold

    def compute_shingles(self, text: str, k: int = 5) -> set[int]:
        """
        计算 k-shingles (用于 MinHash)

        Args:
            text: 输入文本
            k: shingle 大小

        Returns:
            shingle 整数哈希集合
        """
        text = self._normalize(text)
        if len(text) < k:
            return set()

        shingles = set()
        for i in range(len(text) - k + 1):
            shingle = text[i:i + k]
            shingles.add(hash(shingle))

        return shingles

    def _tokenize(self, text: str) -> list[str]:
        """中文分词"""
        try:
            import jieba
            tokens = jieba.cut(text)
            return [t.strip() for t in tokens if len(t.strip()) > 1]
        except ImportError:
            # 回退：按字符 n-gram
            text = self._normalize(text)
            return [text[i:i+2] for i in range(len(text)-1)]

    def _compute_weights(self, tokens: list[str]) -> dict[str, int]:
        """计算词频权重"""
        weights: dict[str, int] = defaultdict(int)
        for token in tokens:
            weights[token] += 1
        return dict(weights)

    def _normalize(self, text: str) -> str:
        """文本归一化"""
        # 去标点、空白
        text = re.sub(r'[，。！？、；：""''（）【】《》\s]+', '', text)
        # 去英文标点
        text = re.sub(r'[^一-鿿\w]', '', text)
        return text.lower()
