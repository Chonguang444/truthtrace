# TruthTrace 理论基础

TruthTrace 的每个引擎都建立在坚实的学术研究基础上。本文档汇总了核心理论基础。

---

## 心理免疫理论 (Inoculation Theory)

**核心发现**: 预先暴露于"弱化版"的操纵手法可以增强人们对虚假信息的抵抗力——就像疫苗一样。

| 研究 | 来源 | 年份 | 关键发现 |
|------|------|------|---------|
| 信号检测论元分析 | *Current Opinion in Psychology* | 2026 | 33实验(N=37,075): 接种干预确实提高真伪辨识力，无反应偏倚 |
| 12国视频接种 | *Communications Psychology* (Nature) | 2026 | 3个预揭露视频覆盖1.2亿+ YouTube用户，12国验证有效 |
| 逻辑基础型接种 | *JESP* | 2025 | 基于主动开放思维的接种比技巧型更持久 |
| 真实世界局限 | *IJHCS* | 2026 | 单技巧预揭露对多技巧组合的虚假信息转移效果差 |

**对应引擎**: `prebunking.py` — 预揭露接种引擎

> Simchon, Zipori, Teitelbaum, Lewandowsky & van der Linden. (2026). A Signal Detection Theory Meta-Analysis of Psychological Inoculation Against Misinformation. *Current Opinion in Psychology*.

---

## 结构指纹框架 (Structural Fingerprints)

**核心发现**: 虚假信息具有跨主题的重复模式——"抗原"可用于设计下一代"接种"干预。

四大指纹类型:
1. **语言指纹** — 重复的词汇/语法特征
2. **叙事指纹** — 重复的故事结构
3. **逻辑指纹** — 重复的谬误和推理错误
4. **批判思维指纹** — 利用认知偏差的模式

**对应引擎**: `prebunking.py`, `fallacy.py`, `distortion.py`

> Germani, Spitale, et al. (2026). The structural fingerprints of disinformation: a content-agnostic framework. *Ethics and Information Technology*.

---

## 多层次信息操纵框架

**核心发现**: 信息操纵可分为技术层(个体技术)和程序层(协调活动)。

- **技术层**: 废话(bullshit)、虚假信息、阴谋论
- **程序层**: 协同不真实行为(CIB)、外国信息操纵(FIMI)、系统性谎言

**对应引擎**: `prebunking.py`, `deepfake_detector.py`

> Lenk. (2026). Towards a deeper understanding of information manipulation. *Humanities and Social Sciences Communications* (Nature).

---

## 知识图谱增强事实核查 (GraphCheck)

**核心发现**: 知识图谱驱动的多跳推理在长文本核查中击败了DeepSeek-V3和OpenAI o1。

**对应引擎**: `kg_reasoning.py`

> Liu et al. (2025). GraphCheck: Breaking Long-Term Text Barriers with Extracted Knowledge Graph-Powered Fact-Checking.

---

## 个性化辟谣 (MURSE)

**核心发现**: LLM驱动的个性化中文谣言辟谣使**用户偏好提升2倍**。根据读者的知识背景、情感倾向生成定制化辟谣文本。

**对应引擎**: `personalized_debunking.py`

> Pang et al. (2026). Tailoring Rumor Debunking to You: Diversifying Chinese Rumor-Debunking Passages. *EACL Industry*.

---

## 社区笔记 (Community Notes)

**核心发现**: X(Twitter)的Community Notes:

| 指标 | 效果 | 来源 |
|------|------|------|
| 标注后转发减少 | 46-61% | PNAS (2025) |
| 系统级总减少 | ~15% | (因标注太慢) |
| 平均标注展示时间 | 62.9h | (远落后于传播峰值) |
| 有用笔记达成率 | <10% | (90%提案未达"有帮助") |

**结论**: Community Notes 有效但不充分。最优方案 = 众包 + 专业核查 + AI辅助。

**对应引擎**: `community_verify.py`

> Community notes reduce engagement with and diffusion of false information online. *PNAS* (2025).

> Community-based fact-checking reduces the spread of misleading posts. *Nature Communications* (2026).

---

## 传播模型 (ISDR-M / SPIDR)

**核心发现**: 社交媒体正向强化机制显著**扩大谣言传播规模**，并削弱传统接触传播路径的主导作用。控制促谣者数量可降低扩散风险。

**对应引擎**: `rumor_lifecycle.py`, `propagation_risk.py`

> 媒体激活与正强化机制驱动的谣言传播模型. *系统科学与数学* (2026).

> 促谣及辟谣的在线社交网络谣言传播模型. *复杂系统与复杂性科学* (2025).

---

## 传播链可信度传导 (双阈值溯源)

**核心发现**: 多源数据融合 + 双阈值动态调节 + 溯源可信度指数 = 增强信息完整性和溯源精度。

**对应引擎**: `credibility_index.py`

> 西安康奈网络科技. (2025). 多源数据融合的网络信息溯源分析系统. CN120075074A.

---

## 阐释实在论叙事伦理

**核心发现**: 超越真/假二元判定。内容可以"指称上不假但伦理上可争议"。

**对应引擎**: `narrative_battlefield.py`

> Sadler. (2025/2026). Suspicious stories: taking narrative seriously in disinformation research. *Communication Theory*.

---

## 多层次系统框架

**核心发现**: 虚假信息传播需从四层理解: 微观(个体)→中观I(社会群体)→中观II(平台)→宏观(法律)。

**对应引擎**: `pollution_index.py`

> Hébert-Dufresne et al. (2025). The complexity of misinformation extends beyond virus and warfare analogies. *npj Complexity*.

---

## 沟通适应理论 + 信息操纵理论

**核心发现**: 虚假新闻含有更多道德化语言、人际冲突、因果词、未来焦点和确定性词。虚假新闻定位为"对抗他人"而非"认同群体"。

**对应引擎**: `distortion.py`, `fallacy.py`

> Whitty & Doherty. (2026). Enhancing mis- and disinformation detection. *Behaviour & Information Technology*.

---

## 动机推理与纠正接受度

**核心发现**: 当纠正来源可信度模糊时，人们策略性利用模糊性来维持态度一致的信念。即使是AI事实核查也经过态度滤镜——即使告知AI准确率97%，偏误仍存在。

**对应引擎**: `personalized_debunking.py`, `correction_agent.py`

> Amaddio. (2025). Reactions to Misinformation Corrections Made by Ambiguous Human and AI Sources. Ohio State University Dissertation.

---

## 7级证据金字塔

基于循证医学和法学证据标准的原创框架:

```
L6 → 收敛 (≥2 独立权威来源交叉确认)
L5 → 权威 (国标/法律/WHO/系统评价)
L4 → 强 (同行评审研究)
L3 → 中等 (可靠二手来源)
L2 → 有限 (单一研究/初步报告)
L1 → 弱 (匿名来源/目击者)
L0 → 零 (无来源声称)
```

---

## 关键原则

1. **可溯源** — 每个结论附带证据片段和来源URL
2. **不确定就说** — 超出知识范围返回"unverifiable"
3. **不创造知识** — 仅基于已知权威来源验证
4. **证据等级决定惩罚力度** — 权威来源的数字不是操纵信号
5. **零信号不是"虚假"** — 没有证据证明问题时保持中性
6. **乘法而非加法** — 因果链中的失真风险远超各自相加
