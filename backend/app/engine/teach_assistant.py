"""
AI事实核查教学助手 (AI Fact-Check Teaching Assistant) — 第37号引擎

理论:
  - 主动开放思维(AOT)培养 (JESP, 2025)
  - VerifactzGPT 5维度验证矩阵
  - Skeptik 分层干预设计

教学模式:
  Level 1: 引导式 — AI引导用户逐步验证主张
  Level 2: 教练式 — AI指出遗漏，用户自行查找
  Level 3: 自主式 — 用户独立完成，AI仅打分反馈
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Optional


class TeachingLevel(str, Enum):
    GUIDED = "guided"       # AI引导
    COACHED = "coached"     # AI教练
    AUTONOMOUS = "autonomous"  # 用户自主


@dataclass
class VerificationStep:
    """验证步骤"""
    step_number: int = 0
    dimension: str = ""     # source/facts/context/intent/media
    question: str = ""
    hint: str = ""
    example_answer: str = ""
    user_answer: str = ""
    score: float = 0.0      # AI评分 0-1

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


@dataclass
class TeachResult:
    """教学结果"""
    claim: str = ""
    level: str = "guided"
    steps: list[VerificationStep] = field(default_factory=list)
    total_score: float = 0.0
    skills_assessed: dict = field(default_factory=dict)
    feedback: str = ""
    certificate_level: str = ""  # beginner/intermediate/advanced/master

    def to_dict(self) -> dict:
        return {
            "claim": self.claim[:200],
            "level": self.level,
            "steps": [s.to_dict() for s in self.steps],
            "total_score": round(self.total_score, 2),
            "skills_assessed": self.skills_assessed,
            "feedback": self.feedback,
            "certificate_level": self.certificate_level,
        }


# 5维度验证矩阵
VERIFICATION_MATRIX = {
    "source": {
        "name": "来源验证",
        "icon": "🔍",
        "questions": [
            "这个信息是谁发布的？是个人还是机构？",
            "发布者在这个话题上是否有专业背景？",
            "你能找到发布者的其他作品来判断其一贯风格吗？",
        ],
        "hints": "检查发布者主页、历史记录、认证状态",
        "skill": "source_evaluation",
    },
    "facts": {
        "name": "事实核查",
        "icon": "📊",
        "questions": [
            "文中提到的数据/研究有来源引用吗？",
            "搜索一下，是否有其他独立来源确认了同样的信息？",
            "数据是否是最近更新的？还是引用的旧数据？",
        ],
        "hints": "使用搜索引擎或专业数据库交叉验证关键数据",
        "skill": "fact_verification",
    },
    "context": {
        "name": "语境审查",
        "icon": "🌐",
        "questions": [
            "这段信息是否脱离了原始语境？",
            "查找原文/原视频的完整版本",
            "该信息发布的时间和地点背景是什么？",
        ],
        "hints": "许多谣言通过剪辑/截图脱离语境来歪曲意思",
        "skill": "contextual_analysis",
    },
    "intent": {
        "name": "意图判断",
        "icon": "🎯",
        "questions": [
            "发布者为什么发这个？想要你做什么？",
            "这个内容是否试图激发强烈情绪(愤怒/恐惧)？",
            "是否隐藏了商业链接或引导你购买产品？",
        ],
        "hints": "情绪操纵和商业动机是虚假信息的常见特征",
        "skill": "intent_detection",
    },
    "media": {
        "name": "图像/视频验证",
        "icon": "📷",
        "questions": [
            "图片/视频是否有编辑痕迹？",
            "用反向图片搜索查找这张图是否在其他地方出现过",
            "视频的拍摄时间和地点是否与声称一致？",
        ],
        "hints": "Google Images/Tineye反向搜索；检查图片元数据",
        "skill": "media_verification",
    },
}


class FactCheckTeacher:
    """事实核查教学助手"""

    @staticmethod
    def generate_lesson(
        claim: str = "",
        level: TeachingLevel = TeachingLevel.GUIDED,
        user_answers: dict[str, str] | None = None,
    ) -> TeachResult:
        """生成教学课程"""
        result = TeachResult(claim=claim, level=level.value)
        user_answers = user_answers or {}

        step_num = 0
        for dim_key, dim_info in VERIFICATION_MATRIX.items():
            for i, question in enumerate(dim_info["questions"]):
                step_num += 1
                step = VerificationStep(
                    step_number=step_num,
                    dimension=f"{dim_info['icon']} {dim_info['name']}",
                    question=question,
                    hint=dim_info["hints"] if i == 0 else "",
                    example_answer="",
                )

                # 用户答案评分
                answer_key = f"{dim_key}_{i}"
                if answer_key in user_answers and user_answers[answer_key]:
                    step.user_answer = user_answers[answer_key][:200]
                    # 简单评分: 长度+来源引用+具体性
                    score = 0.3
                    if len(user_answers[answer_key]) > 30:
                        score += 0.2
                    if any(w in user_answers[answer_key].lower() for w in ["http", "来源", "source", "who", "官方"]):
                        score += 0.3
                    if len(user_answers[answer_key]) > 100:
                        score += 0.2
                    step.score = min(1.0, score)

                result.steps.append(step)

        # 总评分
        scores = [s.score for s in result.steps if s.score > 0]
        if scores:
            result.total_score = sum(scores) / len(scores)
        else:
            result.total_score = 0.0

        # 技能评估
        result.skills_assessed = {}
        for dim_key, dim_info in VERIFICATION_MATRIX.items():
            dim_scores = [s.score for s in result.steps if dim_key in s.dimension.lower() and s.score > 0]
            result.skills_assessed[dim_info["skill"]] = round(sum(dim_scores) / len(dim_scores), 2) if dim_scores else 0.0

        # 证书等级
        if result.total_score >= 0.8:
            result.certificate_level = "master"
            result.feedback = "🏆 优秀! 你已经掌握了事实核查的核心技能，可以独立辨别信息真伪。建议你帮助身边的人也学会这些方法。"
        elif result.total_score >= 0.6:
            result.certificate_level = "advanced"
            result.feedback = "👍 不错! 你已经有较强的事实核查能力。在'来源验证'和'语境审查'方面还可以再深入一些。"
        elif result.total_score >= 0.4:
            result.certificate_level = "intermediate"
            result.feedback = "📚 继续加油! 你已经掌握了基础方法。建议多练习'意图判断'——这是许多人容易忽略的关键环节。"
        else:
            result.certificate_level = "beginner"
            result.feedback = "🌱 起步很好! 事实核查是一项可以学习的技能。每当你看到一条让你情绪激动的信息时，记得先暂停，深呼吸，然后问自己这5个问题。"

        return result

    @staticmethod
    def generate_prompt(claim: str) -> str:
        """生成引导式提问"""
        prompt = "🔍 让我们一起来验证这条信息:\n\n"
        prompt += f"> \"{claim[:150]}\"\n\n"
        prompt += "请按以下步骤思考：\n\n"

        for i, (dim_key, dim_info) in enumerate(VERIFICATION_MATRIX.items(), 1):
            prompt += f"**第{i}步: {dim_info['icon']} {dim_info['name']}**\n"
            prompt += f"{dim_info['questions'][0]}\n"
            prompt += f"💡 提示: {dim_info['hints']}\n\n"

        prompt += "---\n"
        prompt += "现在，你已经有了一套系统的方法。让我们一起验证第一条信息吧！"

        return prompt


def generate_teaching_lesson(
    claim: str = "",
    level: str = "guided",
    user_answers: dict[str, str] | None = None,
) -> TeachResult:
    """生成教学课程 — 便捷函数"""
    return FactCheckTeacher.generate_lesson(
        claim=claim,
        level=TeachingLevel(level),
        user_answers=user_answers,
    )
