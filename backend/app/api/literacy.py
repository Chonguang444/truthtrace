"""
信息素养学院 API -- 挑战赛/案例图书馆/认证系统
把10引擎检测能力转化为教育产品
"""

import uuid
import random
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.base import get_db
from app.models.event import Event
from app.auth.jwt import get_current_active_user, get_current_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 数据模型
# =============================================================================

class ChallengeQuestion(BaseModel):
    id: str
    text: str  # 可疑文本片段
    options: list[str]  # 4个谬误类型选项
    correct_type: str  # 正确答案 (仅后端使用，不返回客户端)
    explanation: str   # 解释为什么 (仅后端使用，不返回客户端)


class PublicChallengeQuestion(BaseModel):
    """返回给客户端的题目 — 不含答案"""
    id: str
    text: str
    options: list[str]

class ChallengeResponse(BaseModel):
    challenge_id: str
    title: str
    description: str
    questions: list[PublicChallengeQuestion]  # 不含答案
    difficulty: str  # beginner/intermediate/advanced
    created_at: str

class AnswerSubmission(BaseModel):
    question_id: str
    selected_type: str

class ChallengeSubmitRequest(BaseModel):
    challenge_id: str
    answers: list[AnswerSubmission]

class ChallengeResult(BaseModel):
    challenge_id: str
    score: int
    total: int
    percentage: float
    results: list[dict]  # [{question_id, correct, correct_type, explanation}]
    earned_xp: int
    message: str

class CaseLibraryItem(BaseModel):
    id: str
    title: str
    summary: str
    category: str  # distortion/fallacy/narrative/statistical
    sub_type: str  # 具体类型如 false_cause
    annotated_text: str  # 标注后的文本
    credibility_score: float
    source_url: str
    created_at: str

class CertificationExamRequest(BaseModel):
    answers: list[AnswerSubmission]

# =============================================================================
# 预置挑战题库 -- 基于真实谣言模式
# =============================================================================

CHALLENGE_POOL = [
    {
        "id": "c001",
        "text": "自从5G基站建在小区旁边后,很多居民反映头痛失眠。所以5G基站的辐射导致健康问题。",
        "options": ["滑坡论证", "虚假因果", "诉诸权威", "稻草人谬误"],
        "correct": "虚假因果",
        "explanation": "将时间先后关系当作因果关系。头痛失眠和5G基站同时发生不等于基站是原因----需要排除其他因素(如心理暗示、季节性变化)并查阅辐射安全标准。"
    },
    {
        "id": "c002",
        "text": "据最新研究表明,市面上90%的食品含有致癌物质。科学家们发现这些添加剂长期食用会导致严重健康问题。",
        "options": ["来源伪造/模糊引用", "以偏概全", "滑坡论证", "红鲱鱼"],
        "correct": "来源伪造/模糊引用",
        "explanation": "'据最新研究''科学家们发现'但未给出任何具体研究名称、发表期刊或链接。这是典型的模糊权威引用----让人感觉有科学依据但无法查证。"
    },
    {
        "id": "c003",
        "text": "你要么支持这个政策,要么就是反对国家发展。不支持的人不是真正的中国人。",
        "options": ["虚假二分", "诉诸情感", "类比滥用", "窃取论题"],
        "correct": "虚假二分",
        "explanation": "将复杂问题简化为两个极端选项,排除了中间立场和其他可能性。同时对不认同者进行道德绑架。"
    },
    {
        "id": "c004",
        "text": "这个保健品是纯天然植物提取的,所以绝对安全无害,适合所有人长期服用。",
        "options": ["概念偷换(天然=安全)", "以偏概全", "诉诸传统", "虚假权威"],
        "correct": "概念偷换(天然=安全)",
        "explanation": "'天然'不等于'安全'----毒蘑菇也是天然的。安全性需要通过临床试验验证,与是否为天然来源无关。"
    },
    {
        "id": "c005",
        "text": "速看!马上被删!某食品公司内部文件曝光,触目惊心!赶快转发给你的家人朋友,不然就来不及了!",
        "options": ["情感操纵(紧迫性)", "权威绑架", "语境剥离", "错误引用"],
        "correct": "情感操纵(紧迫性)",
        "explanation": "使用'速看''马上被删''来不及了'等紧迫性词汇催促用户不加思考地转发。这是典型的情感操纵手法----利用恐慌绕过理性判断。"
    },
    {
        "id": "c006",
        "text": "如果允许这种添加剂使用,那么明天就会有更多有害添加剂获批,食品安全标准会一步步降低,最终我们吃的东西全是毒药。",
        "options": ["滑坡论证", "诉诸情感", "虚假因果", "稻草人谬误"],
        "correct": "滑坡论证",
        "explanation": "假设第一步必然导致一系列越来越糟的后果,没有提供任何中间环节的证据。每种添加剂都有独立的审批流程和安全评估。"
    },
    {
        "id": "c007",
        "text": "幕后的势力在刻意隐瞒真相!这一切都是被精心策划好的,内部知情人士透露了惊人内幕。",
        "options": ["阴谋论叙事", "以偏概全", "诉诸无知", "红鲱鱼"],
        "correct": "阴谋论叙事",
        "explanation": "暗示存在一个秘密的、有组织的势力在操控一切。使用'幕后势力''精心策划''内部知情人士'等模糊词汇,无法验证且天然免疫反驳。"
    },
    {
        "id": "c008",
        "text": "国外发达国家都没有这个问题。我们中国却有。外国全部都不存在食品安全问题。",
        "options": ["以偏概全", "错误的类比", "虚假二分", "诉诸传统"],
        "correct": "以偏概全",
        "explanation": "将'部分国外发达国家在某个方面的表现'过度泛化为'所有外国都没有任何问题'。事实上各国都有自己的食品安全挑战。"
    },
    {
        "id": "c009",
        "text": "那你怎么不说美国的问题呢？美国的食品安全问题更严重,先把本国的问题管好再说吧。",
        "options": ["红鲱鱼(转移话题)", "稻草人谬误", "诉诸人身", "虚假二分"],
        "correct": "红鲱鱼(转移话题)",
        "explanation": "典型的'那XX又怎么说'(Whataboutism)----不回应原论点,转而指向其他问题来转移注意力。这是一种回避核心讨论的策略。"
    },
    {
        "id": "c010",
        "text": "量子能量排毒疗法,诺贝尔奖得主推荐,能清除体内毒素,调节酸碱体质。",
        "options": ["伪科学包装", "诉诸权威", "情感操纵", "语境剥离"],
        "correct": "伪科学包装",
        "explanation": "使用'量子能量''排毒''酸碱体质'等听起来科学但实际无根据的术语包装非科学概念。'酸碱体质'理论已被科学界否定,诺贝尔奖得主推荐也无法查证。"
    },
    {
        "id": "c011",
        "text": "据统计,高达78.5%的消费者不知道他们每天食用的食品中含有有害添加剂。",
        "options": ["统计滥用(数据来源不透明)", "以偏概全", "虚假因果", "滑坡论证"],
        "correct": "统计滥用(数据来源不透明)",
        "explanation": "给出精确数字(78.5%)但不说统计来源、样本量和调查方法。'有害添加剂'也未定义----合法使用的食品添加剂不等于'有害'。"
    },
    {
        "id": "c012",
        "text": "在小鼠实验中,极高剂量的该物质可能导致肝损伤。所以这物质对人体绝对有害,应该全面禁止。",
        "options": ["模态漂移(推测→确定)", "虚假因果", "以偏概全", "诉诸情感"],
        "correct": "模态漂移(推测→确定)",
        "explanation": "从小鼠实验的'可能'跳跃到'绝对有害',忽略了剂量差异(极高剂量≠日常摄入量)、物种差异(小鼠≠人类)和实验条件限制。"
    },
    {
        "id": "c013",
        "text": "以前多好啊,老祖宗的智慧都被现在这些人抛弃了。过去从来不会出现这种食品安全问题!",
        "options": ["辉煌过去叙事", "诉诸传统谬误", "确认偏误", "滑坡论证"],
        "correct": "辉煌过去叙事",
        "explanation": "将过去浪漫化为'黄金时代',忽略历史上同样存在的食品安全问题。这是一种记忆偏差----过去并非没有问题,只是缺乏记录和监督。"
    },
    {
        "id": "c014",
        "text": "现在的年轻人整天刷短视频,这一代都废了。短视频正在毁掉我们的下一代,如果不加管控,整个民族都会被毁掉。",
        "options": ["道德恐慌叙事", "以偏概全", "滑坡论证", "虚假因果"],
        "correct": "道德恐慌叙事",
        "explanation": "典型的道德恐慌----将某种新兴行为(刷短视频)夸大为对整个世代乃至民族的威胁。缺乏'刷短视频'与'被毁掉'之间的因果证据。"
    },
    {
        "id": "c015",
        "text": "这些转基因食品就是现代版的弗兰肯斯坦怪物!我们根本不知道它们会对人体造成什么长期影响!",
        "options": ["技术恐惧叙事", "诉诸无知", "滑坡论证", "情感操纵"],
        "correct": "技术恐惧叙事",
        "explanation": "用'弗兰肯斯坦怪物'等恐怖意象激发对技术的不理性恐惧。'不知道长期影响'不等于'一定有危害'----诉诸无知谬误。转基因食品经过严格安全评估。"
    },
]

# 案例图书馆数据
CASE_LIBRARY = [
    {
        "id": "case001",
        "title": "5G基站致癌 谣言分析",
        "summary": "2024年广泛传播的5G健康恐慌谣言，使用了虚假因果和技术恐惧双重操纵手法",
        "category": "fallacy",
        "sub_type": "false_cause",
        "annotated_text": "虚假因果: 自从小区旁边建了5G基站后居民反映头痛失眠 -> 将时间先后误当作因果关系。 技术恐惧: 5G辐射会对人体造成不可逆的危害 -> 忽略辐射类型区别和国际安全标准。",
        "credibility_score": 12.0,
        "source_url": "https://example.com/5g-rumor",
        "created_at": "2024-03-15T08:00:00"
    },
    {
        "id": "case002",
        "title": "食品添加剂全都有毒 论调解剖",
        "summary": "以天然=安全、化学=有毒为核心的长期传播谬误",
        "category": "fallacy",
        "sub_type": "equivocation",
        "annotated_text": "概念偷换: 纯天然的就是好的，化学合成的就是有毒的 -> 天然不等于安全(毒蘑菇天然)，化学不等于有害(水是化学物质H2O)。 语境剥离: XX物质被证实致癌 -> 脱离剂量谈毒性。",
        "credibility_score": 18.0,
        "source_url": "https://example.com/additive-fear",
        "created_at": "2024-05-20T10:00:00"
    },
    {
        "id": "case003",
        "title": "疫苗导致自闭症 谬误链分析",
        "summary": "经典的反疫苗叙事，包含虚假因果、权威绑架和选择性报告",
        "category": "distortion",
        "sub_type": "authority_abuse",
        "annotated_text": "虚假因果: 接种疫苗后孩子出现自闭症 -> 时间相关不等于因果。权威绑架: 有研究表明 -> 引用的1998年Wakefield研究已被撤回。选择性报告: 只报道个别案例。",
        "credibility_score": 8.0,
        "source_url": "https://example.com/vaccine-myth",
        "created_at": "2024-01-10T12:00:00"
    },
    {
        "id": "case004",
        "title": "某饮料含有毒物质 语境剥离案例",
        "summary": "脱离剂量和使用条件谈毒性的典型案例",
        "category": "statistical",
        "sub_type": "relative_without_absolute",
        "annotated_text": "统计滥用: 该物质致癌风险增加50% -> 不报绝对风险。语境剥离: 含有的物质在高温下会产生有害物 -> 省略了产生条件。",
        "credibility_score": 22.0,
        "source_url": "https://example.com/drink-scare",
        "created_at": "2024-06-05T14:00:00"
    },
    {
        "id": "case005",
        "title": "气候变化是骗局 叙事框架拆解",
        "summary": "包含虚假平衡、阴谋论叙事和选择性报告的复合型谣言",
        "category": "narrative",
        "sub_type": "false_balance",
        "annotated_text": "虚假平衡: 将97%科学共识与3%少数意见等权呈现。阴谋论: 科学家在夸大其词以获取经费。选择性报告: 混淆天气与气候。",
        "credibility_score": 15.0,
        "source_url": "https://example.com/climate-denial",
        "created_at": "2024-04-22T09:00:00"
    },
    {
        "id": "case006",
        "title": "不转不是中国人 情感道德绑架分析",
        "summary": "典型的民族情绪操纵+情感勒索传播模式",
        "category": "distortion",
        "sub_type": "emotional_manipulation",
        "annotated_text": "情感操纵: 不转不是中国人 -> 将爱国情感与信息传播绑定。语境剥离: 原始信息在传播中被剥离上下文。",
        "credibility_score": 5.0,
        "source_url": "https://example.com/patriotism-coercion",
        "created_at": "2024-02-14T16:00:00"
    }
]

# 认证考试题库(高级) -- 独立于日常挑战题，防止提前泄题
CERTIFICATION_POOL = [
    {
        "id": "cert016",
        "text": "关于气候变化,一方面有些人认为这是人类活动导致的,另一方面也有人认为这是自然周期。这个问题还存在很大争议。",
        "options": ["虚假平衡", "以偏概全", "诉诸权威", "滑坡论证"],
        "correct": "虚假平衡",
        "explanation": "将97%的科学共识与少数异议同等权重呈现----这是典型的虚假平衡。科学共识的权重不应与少数观点等同。"
    },
    {
        "id": "cert017",
        "text": "不吹不黑,客观地说,现在的食品安全状况比以前差太多了。以前的食品没有这么多添加剂。",
        "options": ["模态漂移(客观伪装主观)", "虚假因果", "以偏概全", "诉诸传统"],
        "correct": "模态漂移(客观伪装主观)",
        "explanation": "'不吹不黑''客观地说'这类词汇看似中立客观,但后面跟着的是主观判断。这是主观判断包装为客观事实的典型案例。"
    },
    {
        "id": "cert018",
        "text": "该产品经国际认证,获FDA认可,某著名医院专家推荐。",
        "options": ["权威绑架(模糊/虚假背书)", "以偏概全", "情感操纵", "统计滥用"],
        "correct": "权威绑架(模糊/虚假背书)",
        "explanation": "'国际认证'是哪个组织？'FDA认可'可通过FDA官网验证吗？'某著名医院专家'是谁？模糊的权威背书无法验证,很可能是虚假的。"
    },
    {
        "id": "cert019",
        "text": "那些支持添加剂安全的人,说白了就是想让大家把化学品当饭吃而已。",
        "options": ["稻草人谬误", "滑坡论证", "诉诸人身", "虚假二分"],
        "correct": "稻草人谬误",
        "explanation": "将支持方的观点(添加剂在安全剂量内可使用)歪曲为极端版本(让大家把化学品当饭吃),然后攻击这个被歪曲的观点。这是经典的稻草人谬误。"
    },
    {
        "id": "cert020",
        "text": "人工智能最终会统治世界并毁灭人类。马斯克和霍金早就警告过我们。",
        "options": ["技术恐惧+诉诸权威", "滑坡论证", "以偏概全", "阴谋论"],
        "correct": "技术恐惧+诉诸权威",
        "explanation": "将知名人物的警告(可能是特定语境下的)作为绝对真理引用,同时激发对技术的非理性恐惧。霍金和马斯克的言论也需要放在原始语境中理解。"
    },
    {
        "id": "cert021",
        "text": "我们从小吃这个长大,从来没人得癌症。所以现在说这个致癌完全是瞎说。",
        "options": ["诉诸个人经验+幸存者偏差", "诉诸传统", "虚假因果", "以偏概全"],
        "correct": "诉诸个人经验+幸存者偏差",
        "explanation": "个人经验不等于统计证据。没有观察到不等于不存在——需要对照研究和流行病学数据。这是典型的幸存者偏差。"
    },
    {
        "id": "cert022",
        "text": "这个药的副作用包括头痛和恶心。这个药太危险了,坚决不能吃。",
        "options": ["语境剥离(忽略获益风险比)", "滑坡论证", "虚假因果", "诉诸情感"],
        "correct": "语境剥离(忽略获益风险比)",
        "explanation": "所有药物都有副作用,列出副作用不等于药危险。需要评估获益是否大于风险。阿司匹林也有副作用,但不是'不能吃'。"
    },
    {
        "id": "cert023",
        "text": "中国癌症发病率逐年上升,都是因为食品添加剂和环境污染。",
        "options": ["多因一果简化", "虚假因果", "诉诸情感", "滑坡论证"],
        "correct": "多因一果简化",
        "explanation": "癌症发病率上升有多种原因:人口老龄化(最大因素)、筛查技术进步检出更多早期病例、生活方式变化等。不能简单归因为单一因素。"
    },
    {
        "id": "cert024",
        "text": "某地发生食品安全事件后,媒体开始密集报道类似事件。可见食品安全在恶化。",
        "options": ["可得性启发(媒体放大效应)", "虚假因果", "滑坡论证", "以偏概全"],
        "correct": "可得性启发(媒体放大效应)",
        "explanation": "媒体报道增加不等于实际发生率增加——可能只是关注度提高。这在心理学上称为'可得性启发':因为不断看到所以认为更常见。"
    },
    {
        "id": "cert025",
        "text": "99%的人都不知道这个秘密。医生不会告诉你,X光检查实际上对身体有害。",
        "options": ["虚假共识+阴谋暗示", "诉诸权威", "以偏概全", "统计滥用"],
        "correct": "虚假共识+阴谋暗示",
        "explanation": "'99%的人都不知道'是捏造的统计数字。'医生不会告诉你'暗示医疗系统在掩盖,但没有证据。实际上X光的风险是公开信息,医生会评估获益。"
    },
    {
        "id": "cert026",
        "text": "我朋友吃了这个保健品后,偏头痛完全消失了。所以这个产品一定有效。",
        "options": ["轶事证据谬误", "诉诸权威", "虚假因果", "以偏概全"],
        "correct": "轶事证据谬误",
        "explanation": "单个案例(轶事)不能作为有效性证据。可能是安慰剂效应、自然痊愈或同时发生的其他因素。需要随机双盲对照试验。"
    },
    {
        "id": "cert027",
        "text": "连NASA的科学家都在研究这个,说明这个理论很可能是真的。",
        "options": ["权威光环谬误", "诉诸情感", "滑坡论证", "虚假二分"],
        "correct": "权威光环谬误",
        "explanation": "权威机构研究某个话题不等于认可某个特定结论。NASA研究不明飞行物不等于承认外星人存在。需要看具体的研究结论而非'谁在研究'。"
    },
    {
        "id": "cert028",
        "text": "每年有成千上万人死于医疗事故,所以医院是最危险的地方,尽量别去医院。",
        "options": ["选择性风险呈现", "滑坡论证", "虚假因果", "诉诸情感"],
        "correct": "选择性风险呈现",
        "explanation": "只提医疗事故致死的人数,却不提每年因医疗救治而存活的人数(数百倍于事故致死)。这种'只报风险不报收益'的呈现方式是典型的信息操纵。"
    },
    {
        "id": "cert029",
        "text": "这个地区最近几年地震频发。肯定是因为附近建了大坝/开发了矿产。",
        "options": ["虚假因果(将自然事件归因于人为)", "以偏概全", "诉诸权威", "统计滥用"],
        "correct": "虚假因果(将自然事件归因于人为)",
        "explanation": "地震是地质构造活动的结果。虽然某些人类活动可能诱发微震,但将地震频发简单归因于某个工程需要地震学研究证据,不能仅凭时间先后推断。"
    },
    {
        "id": "cert030",
        "text": "现在的小孩体质越来越差,动不动就生病。我们小时候在泥地里打滚也不生病。",
        "options": ["辉煌过去叙事+确认偏误", "虚假因果", "以偏概全", "诉诸情感"],
        "correct": "辉煌过去叙事+确认偏误",
        "explanation": "童年的记忆经过选择性过滤。过去儿童死亡率远高于现在,很多'不生病'的儿童可能没活下来。现代卫生条件和医疗进步大幅提高了儿童健康水平。"
    },
    {
        "id": "cert031",
        "text": "这个研究发表在XX期刊上。XX期刊是顶级期刊,所以这个研究结论是可信的。",
        "options": ["诉诸权威(期刊光环)", "以偏概全", "诉诸传统", "滑坡论证"],
        "correct": "诉诸权威(期刊光环)",
        "explanation": "即使是顶级期刊,也可能发表错误结论(如柳叶刀撤回Wakefield疫苗论文)。科学研究需要看方法学而非发表期刊。顶级期刊也有被撤回的论文。"
    },
    {
        "id": "cert032",
        "text": "只要每天喝一杯这个果汁,就能排毒养颜、延年益寿。隔壁王阿姨喝了三个月年轻了十岁。",
        "options": ["多重谬误(排毒伪科学+轶事证据)", "诉诸权威", "滑坡论证", "以偏概全"],
        "correct": "多重谬误(排毒伪科学+轶事证据)",
        "explanation": "'排毒'是伪科学概念——肝脏和肾脏是身体自带的排毒系统,不需要果汁。'年轻了十岁'是轶事证据,没有科学测量支撑。"
    },
    {
        "id": "cert033",
        "text": "这场暴雨是百年不遇的!以前从来没下过这么大的雨。这证明气候在恶化。",
        "options": ["混淆天气与气候+近因效应", "虚假因果", "滑坡论证", "以偏概全"],
        "correct": "混淆天气与气候+近因效应",
        "explanation": "单次天气事件(暴雨)不等于气候趋势(气候变化需要几十年数据分析)。'从来没见过这么大'受近因效应影响——人们对最近事件的记忆最深刻。"
    },
    {
        "id": "cert034",
        "text": "这个药通过了三期临床试验所以是安全有效的。",
        "options": ["忽略条件语境(部分正确但有误导)", "诉诸权威", "以偏概全", "虚假二分"],
        "correct": "忽略条件语境(部分正确但有误导)",
        "explanation": "三期临床试验确实提供了有效性和安全性证据,但这不是绝对的。药品上市后仍有四期临床(上市后监测),有些罕见副作用只有在大规模使用后才发现。"
    },
    {
        "id": "cert035",
        "text": "网络上有一种说法:人体有酸性体质和碱性体质。酸性体质容易生病,碱性食物能让身体变碱。",
        "options": ["伪科学包装(酸碱体质理论)", "诉诸传统", "概念偷换", "滑坡论证"],
        "correct": "伪科学包装(酸碱体质理论)",
        "explanation": "人体血液的pH值被严格维持在7.35-7.45之间,与摄入的食物无关。酸碱体质理论没有科学依据,其提出者已被美国法院判定欺诈。"
    },
]


# =============================================================================
# 内存存储
# =============================================================================

_challenge_attempts: dict[str, dict] = {}  # user_id -> {score, attempts, history}
_certification_records: dict[str, dict] = {}  # user_id -> {passed, score, badge_earned, completed_at}
_weekly_scores: list[dict] = []  # [{user_id, username, score, week}]
_streaks: dict[str, dict] = {}  # user_id -> {current_streak, longest_streak, last_date}
_daily_tips = [
    "信息的可信度与转发量无关——热门不等于真实。",
    "看到'速看''马上被删'等字眼时，先停下来思考：为什么需要催促我？",
    "'天然'不等于'安全'。毒蘑菇也是天然的。",
    "任何研究结论都需要看原始论文，而不是看媒体的二次解读。",
    "'据研究表明'后面没有给研究链接的，多半是模糊引用。",
    "相关不等于因果。冰淇淋销量和溺水人数正相关，但冰淇淋不导致溺水。",
    "检查信息的发布时间——很多'新闻'其实是旧闻翻新。",
    "说谎者常用'不吹不黑''客观地说'来包装主观判断。",
    "'那XX又怎么说'是转移话题的经典手法，不代表论点成立。",
    "科学共识的权重应该远高于少数异议——不要把两边等权呈现。",
    "看到统计数据先问：样本量多少？来源是谁？方法是什么？",
    "'排毒'是个伪科学概念——你的肝脏和肾脏就是身体自带的排毒系统。",
    "来源可信度与内容的可信度高度相关——优先看原始来源而非转发。",
    "情感是信息操纵者最常用的武器——当你感到愤怒或恐惧时，先暂停转发。",
    "科学是一个不断修正的过程，昨天的'定论'今天可能被更新——这不等于'科学不可信'。",
    "所有人都忽略了一个关键问题：剂量决定毒性。水喝太多也会中毒。",
    "逆向思维：如果这条信息明天被证明是假的，会有什么后果？",
    "好的信息会告诉你它的局限性——声称100%确定的信息反而值得怀疑。",
    "AI生成的假信息越来越逼真。检查来源、交叉验证、保持怀疑——这三步永不过时。",
    "批判性思维不是否定一切，而是对信息保持开放但审慎的态度。",
]


def _generate_challenge_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    seed = f"challenge_{today}"
    return f"ch-{hashlib.md5(seed.encode()).hexdigest()[:8]}"


def _get_daily_challenge() -> list[dict]:
    """基于日期种子生成每日挑战(保证同一天题目一致)"""
    today = datetime.now(timezone.utc)
    seed = int(today.strftime("%Y%m%d"))
    rng = random.Random(seed)
    pool = list(CHALLENGE_POOL)
    rng.shuffle(pool)
    return pool[:5]


# =============================================================================
# 端点: 挑战赛
# =============================================================================

@router.get("/literacy/challenges")
async def get_challenges(
    current_user: User | None = Depends(get_current_user),
):
    """获取今日挑战题（5题）"""
    questions_data = _get_daily_challenge()
    challenge_id = _generate_challenge_id()

    questions = []
    for q in questions_data:
        questions.append(PublicChallengeQuestion(
            id=q["id"],
            text=q["text"],
            options=q["options"],
        ))
    # Store the full question data (with answers) in memory for validation during submit

    return ChallengeResponse(
        challenge_id=challenge_id,
        title="今日信息素养挑战",
        description="阅读以下5段文本,识别每段文本中隐藏的信息操纵手法。每道题选择一个答案。",
        questions=questions,
        difficulty="intermediate",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/literacy/challenges/submit")
async def submit_challenge(
    req: ChallengeSubmitRequest,
    current_user: User = Depends(get_current_active_user),
):
    """提交挑战答案"""
    questions_data = _get_daily_challenge()
    questions_map = {q["id"]: q for q in questions_data}

    if len(req.answers) != len(questions_data):
        raise HTTPException(400, f"需要回答全部{len(questions_data)}道题")

    correct_count = 0
    results = []

    for answer in req.answers:
        q = questions_map.get(answer.question_id)
        if not q:
            continue
        is_correct = answer.selected_type == q["correct"]
        if is_correct:
            correct_count += 1
        results.append({
            "question_id": answer.question_id,
            "correct": is_correct,
            "your_answer": answer.selected_type,
            "correct_type": q["correct"],
            "explanation": q["explanation"],
        })

    total = len(questions_data)
    percentage = round(correct_count / total * 100, 1)
    xp = correct_count * 20  # 每题20经验值

    # 记录尝试
    user_id = str(current_user.id)
    if user_id not in _challenge_attempts:
        _challenge_attempts[user_id] = {"score": 0, "attempts": 0, "history": []}
    record = _challenge_attempts[user_id]
    record["attempts"] += 1
    record["history"].append({
        "challenge_id": req.challenge_id,
        "score": correct_count,
        "total": total,
        "at": datetime.now(timezone.utc).isoformat(),
    })

    # 更新周榜 (定期清理旧数据防止内存泄漏)
    _weekly_scores.append({
        "user_id": user_id,
        "username": current_user.username,
        "score": correct_count,
        "week": datetime.now(timezone.utc).strftime("%Y-W%W"),
    })
    # 保留最近 10000 条记录防止内存泄漏
    if len(_weekly_scores) > 10000:
        _weekly_scores[:] = _weekly_scores[-8000:]

    # 更新连击天数
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user_id not in _streaks:
        _streaks[user_id] = {"current_streak": 0, "longest_streak": 0, "last_date": None}
    streak = _streaks[user_id]
    last = streak["last_date"]
    if last == today_date:
        pass  # 今天已完成, 不重复计算
    elif last == (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d"):
        streak["current_streak"] += 1
        streak["last_date"] = today_date
        if streak["current_streak"] > streak["longest_streak"]:
            streak["longest_streak"] = streak["current_streak"]
    else:
        streak["current_streak"] = 1
        streak["last_date"] = today_date

    # 消息
    if percentage == 100:
        msg = "满分! 你是信息素养大师! 🏆"
    elif percentage >= 80:
        msg = "非常好! 你对信息操纵有敏锐的洞察力! ⭐"
    elif percentage >= 60:
        msg = "不错! 继续学习,你正在成为批判性思维者。📚"
    else:
        msg = "别灰心! 识别信息操纵需要练习。查看解释了解每种模式。💪"

    return ChallengeResult(
        challenge_id=req.challenge_id,
        score=correct_count,
        total=total,
        percentage=percentage,
        results=results,
        earned_xp=xp,
        message=msg,
    )


@router.get("/literacy/challenges/leaderboard")
async def challenge_leaderboard(period: str = Query("weekly")):
    """挑战赛排行榜"""
    now = datetime.now(timezone.utc)
    current_week = now.strftime("%Y-W%W")

    if period == "weekly":
        scores = [s for s in _weekly_scores if s["week"] == current_week]
    else:
        scores = list(_weekly_scores)

    # 按用户聚合
    user_scores: dict[str, dict] = {}
    for s in scores:
        uid = s["user_id"]
        if uid not in user_scores:
            user_scores[uid] = {"username": s["username"], "total_score": 0, "attempts": 0}
        user_scores[uid]["total_score"] += s["score"]
        user_scores[uid]["attempts"] += 1

    ranked = sorted(
        [{"user_id": k, **v} for k, v in user_scores.items()],
        key=lambda x: x["total_score"],
        reverse=True,
    )[:20]

    return {
        "period": period,
        "leaderboard": [
            {"rank": i + 1, **entry}
            for i, entry in enumerate(ranked)
        ],
        "updated_at": now.isoformat(),
    }


# =============================================================================
# 端点: 案例图书馆
# =============================================================================

@router.get("/literacy/cases")
async def list_cases(
    category: str | None = Query(None, description="distortion/fallacy/narrative/statistical"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """分页获取精选案例"""
    cases = CASE_LIBRARY
    if category:
        cases = [c for c in cases if c["category"] == category]

    page = cases[offset:offset + limit]

    return {
        "total": len(cases),
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": c["id"],
                "title": c["title"],
                "summary": c["summary"],
                "category": c["category"],
                "sub_type": c["sub_type"],
                "credibility_score": c["credibility_score"],
                "created_at": c["created_at"],
            }
            for c in page
        ],
    }


@router.get("/literacy/cases/stats")
async def case_stats():
    """案例统计"""
    categories = {}
    for c in CASE_LIBRARY:
        cat = c["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    subtypes = {}
    for c in CASE_LIBRARY:
        st = c["sub_type"]
        if st not in subtypes:
            subtypes[st] = 0
        subtypes[st] += 1

    return {
        "total_cases": len(CASE_LIBRARY),
        "by_category": categories,
        "by_subtype": subtypes,
        "avg_credibility_score": round(
            sum(c["credibility_score"] for c in CASE_LIBRARY) / len(CASE_LIBRARY), 1
        ),
    }


@router.get("/literacy/cases/{case_id}")
async def get_case(case_id: str):
    """案例详情(含引擎分析标注)"""
    for c in CASE_LIBRARY:
        if c["id"] == case_id:
            return {
                **c,
                "learning_points": [
                    "识别信息操纵的核心手法",
                    "了解为什么这种手法有效(心理学基础)",
                    "学会在自己的信息消费中识别类似模式",
                ],
                "related_cases": [
                    r["id"] for r in CASE_LIBRARY
                    if r["id"] != case_id and r["category"] == c["category"]
                ][:3],
                "discussion_questions": [
                    "在生活中你是否遇到过类似的信息操纵？",
                    "如果你是辟谣者,你会如何反驳这条信息？",
                    "为什么这种操纵手法特别容易让人相信？",
                ],
            }

    raise HTTPException(404, "案例不存在")


# =============================================================================
# 端点: 认证系统
# =============================================================================

@router.get("/literacy/certification/status")
async def certification_status(
    current_user: User = Depends(get_current_active_user),
):
    """用户认证进度"""
    user_id = str(current_user.id)
    record = _certification_records.get(user_id, {})

    attempts = _challenge_attempts.get(user_id, {})
    challenges_completed = len(attempts.get("history", []))

    # 认证要求: 完成至少5次每日挑战 + 平均正确率 >= 70%
    avg_score = 0
    if attempts.get("history"):
        scores = [h["score"] for h in attempts["history"]]
        avg_score = sum(scores) / len(scores)

    eligible = challenges_completed >= 3 and avg_score >= 3.5  # 3.5/5 = 70%

    return {
        "challenges_completed": challenges_completed,
        "average_score": round(avg_score, 1),
        "max_score": 5.0,
        "eligible_for_exam": eligible,
        "certification_passed": record.get("passed", False),
        "badge": record.get("badge_earned"),
        "completed_at": record.get("completed_at"),
        "requirement": {
            "challenges_needed": 3,
            "min_avg_score": 3.5,
            "exam_pass_threshold": 16,  # 20题中正确16题 = 80%
        },
    }


@router.post("/literacy/certification/exam")
async def take_certification_exam(
    req: CertificationExamRequest,
    current_user: User = Depends(get_current_active_user),
):
    """提交认证考试(20题高级测试)"""
    if len(req.answers) != len(CERTIFICATION_POOL):
        raise HTTPException(400, f"需要回答全部{len(CERTIFICATION_POOL)}道题")

    exam_map = {q["id"]: q for q in CERTIFICATION_POOL}
    correct_count = 0
    results = []

    for answer in req.answers:
        q = exam_map.get(answer.question_id)
        if not q:
            continue
        is_correct = answer.selected_type == q["correct"]
        if is_correct:
            correct_count += 1
        results.append({
            "question_id": answer.question_id,
            "correct": is_correct,
            "explanation": q["explanation"],
        })

    passed = correct_count >= 16  # 80% 通过线
    user_id = str(current_user.id)

    if passed:
        badge = "critical-thinker-gold"
        _certification_records[user_id] = {
            "passed": True,
            "score": correct_count,
            "total": len(CERTIFICATION_POOL),
            "badge_earned": badge,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        _certification_records[user_id] = {
            "passed": False,
            "score": correct_count,
            "total": len(CERTIFICATION_POOL),
            "badge_earned": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "passed": passed,
        "score": correct_count,
        "total": len(CERTIFICATION_POOL),
        "percentage": round(correct_count / len(CERTIFICATION_POOL) * 100, 1),
        "badge_earned": "critical-thinker-gold" if passed else None,
        "badge_name": "批判思维大师" if passed else None,
        "results": results,
        "message": (
            "恭喜! 你已获得'批判思维大师'认证! 🎓" if passed
            else f"差一点! 需要至少16/20正确(80%)。你得了{correct_count}分。复习案例后可以重试。"
        ),
    }


@router.get("/literacy/certification/badge")
async def get_badge(
    current_user: User = Depends(get_current_active_user),
):
    """获取用户徽章"""
    user_id = str(current_user.id)
    record = _certification_records.get(user_id)

    if not record or not record.get("passed"):
        raise HTTPException(404, "尚未获得认证。请先通过认证考试。")

    return {
        "badge_id": record["badge_earned"],
        "badge_name": "批判思维大师",
        "badge_description": "已完成信息素养学院全部课程并通过认证考试。具备识别7种信息失真、12种逻辑谬误和8种叙事框架的能力。",
        "earned_at": record["completed_at"],
        "user": current_user.username,
        "share_url": f"https://truthtrace.app/badge/{user_id}",
    }


# =============================================================================
# 端点: 连击系统
# =============================================================================

@router.get("/literacy/challenges/streak")
async def get_streak(
    current_user: User | None = Depends(get_current_user),
):
    """获取挑战连击数据"""
    if not current_user:
        return {"current_streak": 0, "longest_streak": 0, "last_date": None, "streak_bonus_xp": 0, "message": "登录后可追踪连击记录"}

    user_id = str(current_user.id)
    streak = _streaks.get(user_id, {"current_streak": 0, "longest_streak": 0, "last_date": None})
    bonus = streak["current_streak"] * 5

    return {
        "current_streak": streak["current_streak"],
        "longest_streak": streak["longest_streak"],
        "last_completed_date": streak["last_date"],
        "streak_bonus_xp": bonus,
        "message": (
            f"连续{streak['current_streak']}天! 每次挑战额外获得+{bonus}经验值"
            if streak["current_streak"] >= 2
            else "连续完成每日挑战获得连击奖励!"
        ),
        "milestones": [
            {"days": 3, "reward": "解锁认证考试资格", "achieved": streak["current_streak"] >= 3},
            {"days": 7, "reward": "周冠军徽章", "achieved": streak["current_streak"] >= 7},
            {"days": 30, "reward": "月冠军徽章", "achieved": streak["current_streak"] >= 30},
        ],
    }


# =============================================================================
# 端点: 每日提示
# =============================================================================

@router.get("/literacy/challenges/daily-tip")
async def get_daily_tip():
    """获取每日信息素养提示"""
    today = datetime.now(timezone.utc)
    seed = int(today.strftime("%Y%m%d"))
    rng = random.Random(seed)
    tip = rng.choice(_daily_tips)
    return {
        "tip": tip,
        "date": today.strftime("%Y-%m-%d"),
        "source": "TruthTrace 信息素养学院",
    }
