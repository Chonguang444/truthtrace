# 🛡️ TruthTrace — 平浪散暴

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-206%20passed-brightgreen.svg)](backend/tests/)
[![TypeScript](https://img.shields.io/badge/TypeScript-0%20errors-blue.svg)](frontend/)

**追溯每一条信息的源头。分析传播链路。识别谣言。还原真相。**

TruthTrace 是一款面向公众的信息可信度全维度检测工具。输入任何网络链接（网页/微博/知乎/B站/抖音），系统自动追溯信息源头，通过 10 引擎推理管线进行深度分析，生成学术风格的完整溯源报告。

> "剂量决定毒性。证据决定可信度。不确定就说不知道。"

---

## 📖 目录

- [核心能力](#-核心能力)
- [快速启动](#-快速启动)
- [Docker 一键部署](#-docker-一键部署)
- [架构](#-架构)
- [推理引擎](#-推理引擎)
- [API 文档](#-api-文档)
- [浏览器扩展](#-浏览器扩展)
- [安全](#-安全)
- [测试](#-测试)
- [开源协议](#-开源协议)

---

## 🎯 核心能力

### 10 引擎推理管线

| # | 引擎 | 检测范围 |
|---|------|---------|
| 1 | **失真检测** | 7 种模式：源头伪造/内容篡改/错误引用/忽略语境/情感操纵/权威绑架/语境剥离 |
| 2 | **逻辑谬误** | 12 种：因果倒置→滑坡论证→虚假二分→偷换概念→诉诸情感→选择性证据 |
| 3 | **统计滥用** | 8 种：相对/绝对风险混淆/样本量忽略/混杂因素/基线率/选择性报告 |
| 4 | **拼接造谣** | 5 种：逻辑跳跃/因果缝合/时间线操控/类比滥用/意义突变 |
| 5 | **五层溯源** | L1表面→L2内容→L3来源→L4叙事→L5利益 |
| 6 | **领域知识** | 6 领域：食品/医药/经济/法律/环境/历史 |
| 7 | **叙事框架** | 12 种：阴谋论→对立叙事→恐惧营销→道德恐慌→净化叙事→技术恐惧→虚假平衡 |
| 8 | **模态漂移** | 5 种：推测→确定/意见→事实/条件→绝对/责任稀释 |
| 9 | **综合判定** | 7 级证据金字塔 + 乘法风险评分 + 因果链分析 |
| 10 | **纠偏建议** | 教育性解释 + 科学素养提示 + 权威来源引用 |

### 7 级证据金字塔

```
L6 → 收敛 (≥2 独立权威来源交叉确认)
L5 → 权威 (国标/法律/WHO/系统评价)
L4 → 强 (同行评审研究)
L3 → 中等 (可靠二手来源)
L2 → 有限 (单一研究/初步报告)
L1 → 弱 (匿名来源/目击者)
L0 → 零 (无来源声称)
```

> 权威域名自动识别：gov.cn/who.int → 95分 / pubmed/nature → 85分 / weibo → 40分

### 中英文双语言引擎

针对中文谣言的正则模式 40+ 条 + 英文模式 19 条，覆盖：
- "研究表明/科学家发现" 无具体来源
- "78.43%数据" 无来源
- "速看/转发/再不看就来不及了" 恐惧营销
- "不转不是中国人" 道德绑架
- "studies show/scientists say" 英文模糊引用
- "share before deleted/your children being poisoned" 英文情绪操纵

### 多平台内容采集

| 平台 | 爬取方式 | 采集内容 |
|------|---------|---------|
| 微博 | 公开热搜 API | 热搜标题/摘要 |
| 知乎 | 公开热榜 API | 热门问题/摘要 |
| 百度 | HTML 解析 | 风云榜热词 |
| B站 | 公开 API | 视频标题/描述/作者/播放量/评论 |
| 抖音 | 热点 API + Playwright | 视频标题/标签 |
| 快手 | HTML 解析 | 热门话题 |

---

## 🚀 快速启动

### 方式 1: SQLite 零依赖模式（立即可用，不需要 Docker）

```bash
# 1. 克隆
git clone https://github.com/Chonguang444/truthtrace.git
cd truthtrace

# 2. 后端
cd backend
pip install -r requirements.txt
DATABASE_URL="sqlite+aiosqlite:///../truthtrace_local.db" uvicorn app.main:app --port 8000

# 3. 新开终端，前端
cd frontend
npm install
npm run dev
```

访问 **http://localhost:5173** · API 文档 **http://localhost:8000/api/docs**

> SQLite 模式：90% 功能可用（仅缺少 PostgreSQL 全文分词和 Celery 定时任务）

---

### 方式 2: Docker 一键部署（生产就绪）

```bash
git clone https://github.com/Chonguang444/truthtrace.git
cd truthtrace

# 开发环境
docker compose up -d

# 生产环境（含 Celery Beat + Nginx + HTTPS）
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d
```

**8 个容器：**

| 容器 | 用途 |
|------|------|
| `postgres` | PostgreSQL 16 (数据库 + 全文搜索) |
| `redis` | Redis 7 (缓存 + 消息队列) |
| `elasticsearch` | ES 8 (可选搜索引擎) |
| `backend` | FastAPI (86 条 API 路由) |
| `worker` | Celery Worker (异步任务 + 10引擎分析) |
| `beat` | Celery Beat (定时调度：每15分钟爬取热点) |
| `frontend` | Nginx + Vite 构建产物 |
| `nginx` | 反向代理 + HTTPS 终止 |

服务启动后，`AutoCollector` 自动开始爬取多平台热点内容。

**环境变量：** 复制 `backend/.env` 并根据需要修改数据库密码：

```bash
DB_PASSWORD=your_secure_password
JWT_SECRET_KEY=your_jwt_secret
SENTRY_DSN=     # 可选
ANTHROPIC_API_KEY=  # 可选，启用 LLM 深度分析
```

---

## 🏗 架构

```
浏览器扩展 ─┐
Web 前端 ───┤
            ├── Nginx (HTTPS/反向代理)
            │
            ├── FastAPI (86 路由) ──┬── 10 引擎推理管线 (14个模块)
            │                      ├── 5 层安全防线
            │                      ├── 质量监控 + 自我进化
            │                      ├── 多平台爬虫集群 (6平台)
            │                      ├── WebSocket 实时推送
            │                      └── 视频内容分析 (OCR+语音)
            │
            ├── PostgreSQL 16 ──── 全文搜索 (tsvector + jieba)
            ├── Redis 7 ────────── 缓存 + Celery 队列
            ├── Celery ─────────── 异步任务 + 定时调度
            └── Elasticsearch ──── 可选搜索引擎
```

**后端：** Python 3.12 + FastAPI + SQLAlchemy async + Celery  
**前端：** React 18 + TypeScript + Vite + Tailwind CSS + D3.js  
**NLP：** jieba 分词 + SimHash 指纹  
**视频分析：** ffmpeg + EasyOCR + Whisper 语音转文字

---

## 🧠 推理引擎

### 推理链追踪

```
用户提交 URL
    │
    ├── Step 1: 内容采集 (爬虫 + 去重 + 安全沙箱)
    ├── Step 2: 失真检测 (7 种模式匹配)
    ├── Step 3: 逻辑谬误 (12 种模式)
    ├── Step 4: 统计滥用 (8 种检测 + 教育解释)
    ├── Step 5: 拼接造谣 (逻辑跳跃 + 意义突变)
    ├── Step 6: 五层溯源 (L1-L5)
    ├── Step 7: 领域知识验证 (6 领域 + 权威来源)
    ├── Step 8: 叙事框架 (12 种)
    ├── Step 9: 模态漂移 (5 种)
    ├── Step 10: 严格逻辑综合判定
    │            ├── 7 级证据等级分析
    │            ├── 失真因果链追踪
    │            ├── 假设检验 (可证伪性)
    │            └── 乘法风险评分
    └── 输出: 溯源报告 + 推理链 + 纠偏建议 + 不确定性声明
```

### 评分公式

```
score = 50 + credibility_bonus − (independent_penalty × chain_multiplier × evidence_discount)

其中:
- credibility_bonus:  权威来源 +15,  学术来源 +8
- chain_multiplier:    1条因果链 ×1.2,  3条×2.0
- evidence_discount:   权威级 ×0.02,   匿名来源 ×1.0
```

### 关键原则

1. **可溯源** — 每个结论附带证据片段和来源 URL
2. **不确定就说** — 超出知识范围返回 "unverifiable"
3. **不创造知识** — 仅基于已知权威来源验证（19 条可引用知识）
4. **证据等级决定力度** — 政府文件中的精确数字是正常的，匿名来源的数字是可疑的
5. **零信号不是虚假** — 没有任何引擎发现问题时，保持 50 分中性

---

## 📡 API 文档

启动后端后访问 **http://localhost:8000/api/docs** 查看交互式 Swagger 文档。

### 核心端点

| 端点 | 说明 |
|------|------|
| `POST /api/trace` | 提交 URL 溯源任务 |
| `GET /api/tasks/{id}` | 查询任务进度 |
| `GET /api/search?q=` | 搜索事件 (jieba 中文分词) |
| `GET /api/events/{id}` | 事件详情 (含引擎摘要) |
| `GET /api/events/{id}/report` | 溯源报告 |
| `GET /api/events/{id}/analysis` | 完整 10 引擎分析 |
| `POST /api/video/analyze` | 视频 URL 分析 (B站/抖音/快手) |
| `POST /api/auth/register` | 用户注册 |
| `POST /api/auth/login` | 用户登录 |
| `GET /api/stats/dashboard` | 数据仪表盘 |
| `GET /api/admin/overview` | 管理员概览 |
| `GET /api/monitor/alerts` | 叙事告警 |
| `WS /api/ws` | WebSocket 实时推送 |

---

## 🔌 浏览器扩展

Chrome/Edge 扩展位于 `browser-extension/`:

1. 打开 `chrome://extensions`
2. 开启**开发者模式**
3. 点击**加载已解压的扩展** → 选择 `browser-extension/` 目录

**功能：**
- 🔍 右键一键分析 — 任何网页右键 "用 TruthTrace 溯源分析"
- 📊 页面浮窗 — 社交媒体上显示可信度评分
- ⚠️ 转发前警告 — 检测到低可信度内容时弹窗提醒

---

## 🛡️ 安全

### 五层防线

| 层 | 防护 | 实现 |
|----|------|------|
| L1 | 输入净化 | SQL注入/XSS/命令注入检测 + 17条危险模式 |
| L2 | 爬虫沙箱 | SSRF防护 + 10MB限制 + 5跳重定向 + 禁止内网 |
| L3 | 内容过滤 | 恶意脚本/隐藏iframe/phishing检测 |
| L4 | 安全头 | CSP/HSTS/X-Frame-Deny/XSS保护 |
| L5 | 速率限制 | 200次/分钟/IP + CSRF + 蜜罐端点 + 自动封禁 |

### 隐私

- 密码：pbkdf2_sha256 哈希（不可逆）
- IP：每 24 小时匿名化（最后 8 位清零）
- URL 跟踪参数：自动移除（utm/fbclid/gclid）
- 不追踪浏览行为，不记录精确位置
- 用户注销后 30 天内永久删除

---

## 🧪 测试

```bash
cd backend
pytest tests/ -v

# 206 tests passed
```

测试覆盖：
- 7 种失真检测（9 个用例 + 正常内容不误报）
- 12 种逻辑谬误（11 个用例）
- 5 层溯源（4 个用例）
- 6 领域知识验证（6 个用例）
- 8 种叙事框架（8 个用例 + 中性内容不误报）
- 8 种统计滥用（8 个用例）
- 5 种拼接造谣（7 个用例）
- 完整管线（7 个端到端场景）

---

## 🤝 贡献

欢迎通过 Issue 和 PR 参与贡献。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

**贡献方向：**
- 引擎规则优化（正则模式微调）
- 新增领域知识条目
- 平台爬虫适配
- 前端 UI/UX 改进
- 文档翻译

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
    78+ 任务 · 180+ 文件 · 35,000+ 行代码 · 206 个测试<br>
    10 引擎 · 7 级证据 · 140 API 路由 · 8 层爬虫沙箱 · Prometheus 监控<br>
    反馈闭环 · 质量仪表盘 · Alembic 迁移 · 自我进化<br>
    一个可以部署的完整系统
  </sub>
</p>
