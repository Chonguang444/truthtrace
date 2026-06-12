# 🛡️ TruthTrace — 平浪散暴

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-332%20passed-brightgreen.svg)](backend/tests/)
[![TypeScript](https://img.shields.io/badge/TypeScript-0%20errors-blue.svg)](frontend/)
[![Pipeline](https://img.shields.io/badge/pipeline-34%20steps-purple.svg)](backend/app/engine/)
[![Engines](https://img.shields.io/badge/engines-27-orange.svg)](backend/app/engine/)
[![Languages](https://img.shields.io/badge/languages-8-yellow.svg)](backend/app/engine/cross_lang_trace.py)
[![Lines](https://img.shields.io/badge/code-~68,000%20lines-lightgrey.svg)]()

**追溯每一条信息的源头。分析传播链路。识别谣言。还原真相。**

TruthTrace 是全球最完整的开源信息溯源与事实核查平台。输入任何网络链接，系统自动追溯信息源头，通过 **34 步推理管线（27 引擎）** 进行深度分析，生成学术风格的完整溯源报告 + 叙事替代辟谣 + 多平台一键分享。

> "剂量决定毒性。证据决定可信度。不确定就说不知道。"

---

## 📖 目录

- [核心能力](#-核心能力-v30)
- [理论基础](#-理论基础)
- [快速启动](#-快速启动)
- [Docker 一键部署](#-docker-一键部署)
- [架构](#-架构)
- [推理引擎矩阵](#-推理引擎矩阵)
- [API 文档](#-api-文档)
- [浏览器扩展](#-浏览器扩展)
- [安全](#-安全)
- [测试](#-测试)
- [开源协议](#-开源协议)

---

## 🎯 核心能力 (v3.0)

### 27 引擎推理管线 (34 步)

#### 核心检测引擎 (9)

| # | 引擎 | 检测范围 |
|---|------|---------|
| 1 | **失真检测** | 7 种模式：源头伪造/内容篡改/错误引用/忽略语境/情感操纵/权威绑架/语境剥离 (51条英文补充) |
| 2 | **逻辑谬误** | 12 种：因果倒置→滑坡论证→虚假二分→偷换概念→诉诸情感→选择性证据 (中英文双语) |
| 3 | **统计滥用** | 8 种：相对/绝对风险混淆/样本量忽略/混杂因素/基线率/选择性报告 |
| 4 | **拼接造谣** | 5 种：逻辑跳跃/因果缝合/时间线操控/类比滥用/意义突变 |
| 5 | **五层溯源** | L1表面→L2内容→L3来源→L4叙事→L5利益 |
| 6 | **领域知识** | 6 领域 + 权威来源引用 |
| 7 | **叙事框架** | 12 种：阴谋论→对立叙事→恐惧营销→道德恐慌→净化叙事→技术恐惧 |
| 8 | **模态漂移** | 5 种：推测→确定/意见→事实/条件→绝对/责任稀释 |
| 9 | **严格逻辑综合** | 7 级证据金字塔 + 乘法风险评分 + 因果链分析 + 假设检验 |

#### AI检测引擎 (5)

| # | 引擎 | 检测范围 |
|---|------|---------|
| 10 | **lmscan 统计指纹** | 12 维统计特征：词重复率/滑动窗口熵/Burstiness/TTR/句法模板/过渡词密度/组合指纹 |
| 11 | **smellcheck 静态指纹** | 8 类字符级检测：Unicode同形字/零宽字符/AI热词密度/RTL覆盖 |
| 12 | **AI 内容鉴伪** | AI文本检测/AI图片/深度伪造/机器人发帖/跨模态一致性 |
| 13 | **RAG 权威验证** | 实时检索WHO/国标/学术论文与主张交叉比对 |
| 14 | **多模态深度伪造检测** | 文本AI指纹+元数据异常+图像取证(ELA/克隆/光照/噪声)+音频频谱 |

#### 溯源与传播引擎 (5)

| # | 引擎 | 检测范围 |
|---|------|---------|
| 15 | **SatyaLens 引用评分** | 引用完整性/可验证来源链/5维加权评分/8类红旗检测 |
| 16 | **溯源可信度指数** | 三维度(来源权威/内容完整/引用质量) × 传播链衰减模型 → 节点-边权重可视化 |
| 17 | **Google Fact Check API** | 全球核查数据库交叉验证 + 40+裁决标准化映射 |
| 18 | **发布者画像** | 账号年龄/历史准确率/领域专注度/行为规律 |
| 19 | **传播风险** | 传播速度/变异系数/引爆节点/跨平台追踪 |

#### 辟谣与矫正引擎 (5)

| # | 引擎 | 检测范围 |
|---|------|---------|
| 20 | **因果图谱** | 6类因果谬误检测 + 因果主张提取 + 可信度传导 |
| 21 | **叙事替代** | 5语气策略(中立/权威/共情/教育/简洁) + 事实楔子 + 真相三明治 + 认知桥梁 |
| 22 | **个性化辟谣 (MURSE)** | 基于用户画像(认知风格/情感倾向/信任特征)的自适应辟谣文本生成 |
| 23 | **造谣过程演示** | 造谣者如何逐步建构虚假叙事的时间线动画 |
| 24 | **Sift Critic Agent** | 引擎间一致性计算 + 矛盾发现 + 误报风险标记 + 置信度校准 |

#### 免疫与教育引擎 (5)

| # | 引擎 | 检测范围 |
|---|------|---------|
| 25 | **预揭露接种** | 8种操纵手法识别 → 命名→解释→检测线索。基于33项实验(N=37,075)元分析验证的Inoculation Theory |
| 26 | **社区众包验证** | Community Notes式桥接共识算法 + 声誉系统 + AI辅助注记 |
| 27 | **AI核查教学助手** | 5维度验证矩阵(来源/事实/语境/意图/图像) + 引导式/教练式/自主式三级教学 |

#### 生态与可视化引擎 (4)

| 模块 | 功能 |
|------|------|
| **回音壁检测** | 多源引用链追踪—检测媒体互引形成的信息闭环 |
| **多语言溯源** | 8语言(zh/en/ja/ko/fr/de/es/ar/ru)自动翻译+跨国权威来源交叉验证 |
| **技术事实楔子** | 基于物理/化学/生物原理的不可辩驳事实 + 成本逻辑推演 |
| **英文虚假信息评分** | 51条英文正则 + 6类叙事框架补充检测 |
| **专家知识库** | 10大领域(心理学/社会学/犯罪学/管理学/数学/化学/物理/生物/政治/传播)权威知识 |
| **信息污染指数** | AQI式公共产品 — 实时量化各平台/话题的信息污染程度 |
| **谣言生命追踪** | 谣言完整生命周期(诞生→潜伏→放大→高峰→辟谣→衰退) + 年度报告 |
| **叙事战场可视化** | 展示同一事件的多竞争叙事 + 证据/逻辑/伦理三维评判 |
| **区块链溯源存证** | SHA-256哈希链防篡改 + 分级责任归因 |
| **IFCN 标准导出** | Schema.org ClaimReview JSON-LD + Google Fact Check + IFCN 2.0 Feed |
| **DetectZoo 跨库桥接** | 6个外部谣言库(Snopes/PolitiFact/FullFact/JapanFCC等)双向数据交换 |

---

## 📚 理论基础

TruthTrace v3.0 的每个引擎都建立在坚实的学术研究基础上：

| 理论 | 核心论文/来源 | 对应引擎 |
|------|-------------|---------|
| **Inoculation Theory** | Simchon et al. (2026) 33实验元分析 N=37,075; 12国视频接种 Nature Comms Psych (2026) | 预揭露引擎 |
| **结构指纹框架** | Germani, Spitale et al. (2026) Ethics & Information Technology | 逻辑谬误标注器 |
| **多层次信息操纵** | Lenk (2026) Humanities & Social Sciences Comms | 预揭露 + 深度伪造 |
| **GraphCheck KG** | Liu et al. (2025) — 击败DeepSeek-V3和OpenAI-o1 | 知识图谱推理 |
| **MURSE 个性化辟谣** | Pang et al. (2026) EACL Industry — 2x用户偏好 | 个性化辟谣 |
| **Community Notes** | PNAS (2025) / Nature Comms (2026) — 标注减少61%转发 | 社区验证 |
| **ISDR-M/SPIDR 传播模型** | 系统科学与数学 (2026) / 复杂系统与复杂性科学 (2025) | 谣言生命追踪 |
| **阐释实在论叙事伦理** | Sadler (2025) Communication Theory | 叙事战场 |
| **沟通适应理论+信息操纵** | Whitty & Doherty (2026) Behaviour & IT | 失真+谬误检测 |
| **多层次系统框架** | Hébert-Dufresne et al. (2025) npj Complexity | 信息污染指数 |
| **7级证据金字塔** | 循证医学 + 法学证据标准 | 严格逻辑综合 |
| **双阈值溯源** | 西安康奈专利 CN120075074A | 溯源可信度指数 |

完整理论基础详见 [研究文档](docs/RESEARCH.md)。

---

## 🚀 快速启动

### 方式 1: SQLite 零依赖模式（立即可用）

```bash
git clone https://github.com/Chonguang444/truthtrace.git
cd truthtrace

# 后端
cd backend
pip install -r requirements.txt
DATABASE_URL="sqlite+aiosqlite:///../truthtrace_local.db" uvicorn app.main:app --port 8000

# 前端 (新终端)
cd frontend
npm install
npm run dev
```

访问 **http://localhost:5173** · API 文档 **http://localhost:8000/api/docs**

### 方式 2: Docker 生产部署

```bash
git clone https://github.com/Chonguang444/truthtrace.git
cd truthtrace
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d
```

**8 个容器**：PostgreSQL 16 + Redis 7 + Elasticsearch 8 + FastAPI + Celery Worker + Celery Beat + Nginx(前端) + Nginx(反向代理)

---

## 🏗 架构

```
浏览器扩展 ─┐
Web 前端 ───┤
            ├── Nginx (HTTPS/反向代理)
            │
            ├── FastAPI (26 API 模块) ──┬── 27 引擎推理管线 (34步)
            │                         ├── 5 层安全防线
            │                         ├── 质量监控 + 进化校准
            │                         ├── 多平台爬虫集群 (8平台)
            │                         ├── WebSocket 实时推送
            │                         └── 视频内容分析 (OCR+语音)
            │
            ├── PostgreSQL 16 ──── 全文搜索 (tsvector + jieba)
            ├── Redis 7 ────────── 缓存 + Celery 队列
            ├── Celery ─────────── 异步任务 + 定时调度
            └── Elasticsearch ──── 可选搜索引擎
```

**后端：** Python 3.12+ · FastAPI · SQLAlchemy async · Celery · Alembic  
**前端：** React 18 · TypeScript · Vite · Tailwind CSS · Cytoscape.js · D3.js  
**NLP：** jieba · faster-whisper · SimHash · 情感分析  
**视频：** ffmpeg · EasyOCR · Whisper 语音转文字  
**规模：** ~68,000 行 · 34 文件引擎 · 26 API 模块 · 34 前端组件

---

## 📡 API 文档

启动后端后访问 **http://localhost:8000/api/docs**

### 核心端点 (共 150+ 路由)

| 端点 | 说明 |
|------|------|
| `POST /api/trace` | 提交 URL 溯源任务 |
| `GET /api/events/{id}` | 事件详情 (含引擎摘要) |
| `GET /api/events/{id}/report` | 完整溯源报告 |
| `POST /api/quick-check/text` | 快速检测 (<500ms, 无需登录) |
| `POST /api/video/analyze` | 视频 URL 分析 (B站/抖音/快手) |
| `POST /api/prebunking/check` | 预揭露操纵手法检测 |
| `GET /api/credibility-index/{id}` | 溯源可信度指数 |
| `POST /api/kg-reasoning` | 知识图谱增强推理 |
| `POST /api/personalized-debunking` | 个性化辟谣生成 |
| `POST /api/community/notes` | 提交社区证据注记 |
| `GET /api/community/verification/{id}` | 社区验证结果 |
| `POST /api/deepfake/check` | 多模态深度伪造检测 |
| `GET /api/pollution-index` | 信息污染指数 (AQI式) |
| `POST /api/teach/lesson` | AI事实核查教学 |
| `GET /api/narrative-battlefield/{id}` | 叙事战场分析 |
| `POST /api/blockchain/verify` | 区块链溯源存证 |
| `POST /api/detectzoo/export/{id}` | 导出到外部谣言库 |
| `GET /api/export/ifcn-feed` | IFCN Feed 导出 |
| `WS /api/ws` | WebSocket 实时推送 |

---

## 🔌 浏览器扩展

**Truth Lens** — Chrome/Edge 扩展位于 `browser-extension/`

**v2 功能：**
- 🔍 右键一键分析 — 任何网页划词检测
- ⚠️ **逻辑谬误实时标注** — 页面内12种谬误彩色标注+浮窗解释
- 📊 页面浮窗 — 社交媒体上显示可信度评分
- 🔗 传播链可视化 — 在浏览网页时查看信息传播路径

**安装：** 打开 `chrome://extensions` → 开发者模式 → 加载 `browser-extension/`

---

## 🛡️ 安全 (审计评分 20/25)

### 五层防线

| 层 | 防护 | 实现 |
|----|------|------|
| L1 | 输入净化 | SQL注入/XSS/命令注入/路径穿越/空字节检测 |
| L2 | 爬虫沙箱 | SSRF防护 + DNS重绑定 + 10MB限制 + 5跳重定向 |
| L3 | 内容过滤 | 恶意脚本/隐藏iframe/phishing检测 |
| L4 | 安全头 | CSP(无unsafe-inline)/HSTS/X-Frame-Deny/XSS保护 |
| L5 | 速率限制 | 200次/分钟/IP + CSRF原子操作 + 蜜罐端点 + 自动封禁 |

### 认证

- 密码：bcrypt (cost=12) — 抗GPU加速攻击
- JWT：HS256 · 30分钟访问令牌 + 7天刷新令牌
- Cookie：httpOnly + SameSite=Lax + secure(生产自动)
- Token 存储：仅内存 (无localStorage — 防XSS窃取)
- CSRF：单次使用 + GETDEL原子操作 + dict.pop原子回退

---

## 🧪 测试

```bash
cd backend
pytest tests/ -v

# 332 passed, 0 failed
```

---

## 📊 项目数据

| 维度 | 数据 |
|------|------|
| 代码行数 | ~68,000 (后端~54,000 + 前端~14,000) |
| 推理管线 | 34 步 |
| 引擎总数 | 27 个 |
| API 模块 | 26 个 (150+ 路由) |
| 前端页面 | 14 页 |
| 前端组件 | 34 个 |
| 支持语言 | 8 种 (zh/en/ja/ko/fr/de/es/ar/ru) |
| 测试数量 | 332 个 |
| Docker 容器 | 8 个 |
| 浏览器扩展 | Chrome/Edge (v2) |

---

## 🤝 贡献

欢迎通过 Issue 和 PR 参与贡献。

**贡献方向：**
- 引擎规则优化（正则模式微调/新语言支持）
- 新增领域知识条目
- 平台爬虫适配
- 前端 UI/UX 改进
- 文档翻译 (8种语言)

---

## 📄 开源协议

MIT License — 详见 [LICENSE](LICENSE)

## 👤 作者

**[Chonguang444](https://github.com/Chonguang444)** — 产品设计与全栈开发

TruthTrace 由 Chonguang444 设计和开发，Claude (Anthropic) 辅助编码实现。全部代码在 MIT 协议下开源。

---

<h4 align="center">
  TruthTrace — 平浪散暴，追溯真相，破除谣言
</h4>

<p align="center">
  <sub>
    v3.0 · 34步管线 · 27引擎 · 8语言 · 332测试 · ~68,000行代码<br>
    基于50+篇2025-2026最新学术研究的产品理论基础<br>
    全球最完整的开源信息溯源与事实核查平台
  </sub>
</p>
