"""
TruthTrace 推理引擎

核心模块:
- types: 共享数据类型 (失真/谬误/叙事/溯源/判定)
- distortion: 7种信息失真检测
- fallacy: 12种逻辑谬误检测
- trace_depth: 5层溯源分析
- domain_verifier: 6大领域知识验证
- narrative: 8种叙事框架识别
- reasoning: 统一推理管线
"""

from app.engine.types import (
    AnalysisResult, Verdict, Confidence,
    DistortionType, FallacyType, NarrativeType,
    TraceDepth, DomainType,
)
from app.engine.reasoning import run_reasoning_pipeline

__all__ = [
    "AnalysisResult", "Verdict", "Confidence",
    "DistortionType", "FallacyType", "NarrativeType",
    "TraceDepth", "DomainType",
    "run_reasoning_pipeline",
]
