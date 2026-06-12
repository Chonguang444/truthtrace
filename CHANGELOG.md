# Changelog

All notable changes to TruthTrace will be documented in this file.

---

## [3.0.0] — 2026-06-12

### 🚀 P0: 预揭露 + 可信度 + 谬误标注 (Inoculation Theory)

- **AI预揭露引擎** (`engine/prebunking.py`) — 8种操纵手法检测 + 接种提示。基于33项实验(N=37,075)元分析验证的Inoculation Theory
- **溯源可信度指数** (`engine/credibility_index.py`) — 三维度(来源权威/内容完整/引用质量) × 传播链衰减模型 → 节点-边权重可视化
- **逻辑谬误实时标注器** (`browser-extension/content/fallacy-annotator.js`) — 12种谬误彩色标注 + 浮窗解释
- **预揭露卡片组件** (`components/PrebunkingCard.tsx`) — 操纵手法命名→解释→检测线索

### 🧠 P1: KG推理 + 个性化 + 社区 + 深度伪造

- **知识图谱增强推理** (`engine/kg_reasoning.py`) — 跨领域知识图谱多跳推理 (GraphCheck-style)
- **个性化辟谣引擎** (`engine/personalized_debunking.py`) — 基于认知画像的自适应辟谣 (MURSE-style, 2x用户偏好)
- **社区众包验证** (`engine/community_verify.py`) — 桥接共识算法 + 声誉系统 (Community Notes PNAS/Nature)
- **多模态深度伪造检测** (`engine/deepfake_detector.py`) — 文本+图像+元数据多模态检测
- **可信度传播图** (`components/CredibilityIndexGraph.tsx`) — 节点可信度渐变色条 + 三维度迷你图
- **5合1引擎面板** (`components/NewEnginePanels.tsx`) — KG推理/个性化/深度伪造/污染指数/教学

### 🌐 P2: 生态产品

- **谣言生命追踪** (`engine/rumor_lifecycle.py`) — 6阶段(诞生→潜伏→放大→高峰→辟谣→衰退) + 年度报告
- **信息污染指数** (`engine/pollution_index.py`) — AQI式公共产品，实时量化各平台/话题污染程度
- **AI核查教学助手** (`engine/teach_assistant.py`) — 5维度验证矩阵 + 三级教学(引导/教练/自主)
- **叙事战场可视化** (`engine/narrative_battlefield.py`) — 展示竞争叙事 + 证据/逻辑/伦理三维评判
- **区块链溯源存证** (`engine/blockchain_verify.py`) — SHA-256哈希链防篡改 + 分级责任归因
- **谣言生命周期时间线** (`components/RumorLifecycleTimeline.tsx`) — 6阶段可视化 + 峰值触达
- **叙事战场图** (`components/NarrativeBattlefieldViz.tsx`) — 多叙事空间布局 + 冲突标注

### 🔒 安全加固 (审计问题修复)

- PBKDF2 → **bcrypt** (cost=12) 直接使用，移除已停止维护的 passlib
- CSRF: **GETDEL原子操作**(Redis) + dict.pop原子操作(内存) — 修复TOCTOU竞态
- JWT: 24h → **30min** | Refresh: 30天 → **7天**
- Cookie: **secure动态**(`not settings.debug`) | httpOnly + SameSite=Lax
- DB密码: 移除硬编码默认值 → 强制环境变量
- debug: True → **False** 默认
- propagation_edges: **FK索引**(`index=True`)
- 默认数据库密码移除
- 加密库评估: passlib→bcrypt直接

### 🌍 多语言扩展

- 3→**8语言** (zh/en/ja/ko/fr/de/es/ar/ru)
- 术语映射: 12→**200+**
- 国际实体检测: 19→**50+**
- 新增 `detect_english_claim()` 英文反向检测
- 英文虚假信息评分集成 (51条模式 + 6类叙事)

### 📈 管线扩展

- 推理步骤: 21→**39步**
- 引擎总数: 12→**27个**
- API模块: 25→**26个** (new_engines.py: 13端点)
- 前端组件: 14→**36个**
- 测试: 313→**419个** (+87新引擎测试)

### 🛠 修复

- `rigorous_logic.py`: statMatches未定义变量 — 统计滥用信号现正确计入
- `reasoning.py`: hasattr逻辑错误 — 置信度现正确反映严谨分析结果
- `community.py`: 缺失 `_generate_hotspot_events` 导入
- `LiteracyAcademy.tsx`: 绕过AuthContext的localStorage读token — 已移除
- `rumor_lifecycle.py`: 缺失 hashlib 导入
- prebunking regex 模式放宽 (中文匹配)
- kg_reasoning 中文实体映射 (阿斯巴甜→aspartame等)
- expert_kb API适配 (list vs dict)
- debuff→debunk typo 修复

### 🎨 前端与部署

- **PWA**: manifest.json + service worker + icons(192/512/32) + favicon SVG
- **SEO**: Open Graph + Twitter Card + JSON-LD结构化数据 + Canonical URL
- **代码分割**: 7个懒加载页面 + 4个vendor chunk (首屏~50KB gzip)
- **生产Docker**: Celery time-limit + graceful shutdown
- `.env.example`: 3步部署指南 + v3.0.0版本更新
- **ErrorBoundary**: 全局错误边界 + Suspense回退
- Admin面板: 7→**11标签** (新增IFCN合规 + DetectZoo + 跨库桥接)

---

## [2.1.0] — 2026-06-11

### P2

- GraphRAG-Causal 因果图谱引擎 #20
- Correction Agent 叙事替代 #22 (5语气策略)
- ClaimReview 导出 (Schema.org JSON-LD)

### 安全

- JWT弱密钥守卫强化
- CSRF一次性使用
- 全局URL安全验证
- CSP移除unsafe-inline
- Evolution模块48测试
- 注册限流 (3次/小时/IP)

### 前端

- CausalGraphCard, CorrectionPanel, ShareDebunk
- RealTimeMonitor, AnalyticsDashboard
- Truth Lens 浏览器插件

---

## [2.0.0] — 2026-06-10

### P0-P1 全工具集成

- SatyaLens 引用完整性评分 #16
- Google Fact Check API #17
- lmscan AI统计检测 #18 (12特征)
- smellcheck AI指纹检测 #19 (8类)
- Sift Critic Agent #21
- MediaCrawler 5平台
- 前端: Cytoscape传播图V2, FactCheckBadge, AIDetectionConsensus, CytoscapeTimeline
- 深度内容采集 (三层L1/L2/L3)

---

## [1.0.0] — 2026-06-09

### Initial Release

- 15引擎推理管线 (21步)
- React 18 + FastAPI + PostgreSQL + Redis + Elasticsearch
- 7级证据金字塔 + 因果链分析 + 假设检验
- B站视频音频转录 (Whisper)
- 多平台爬虫 (微博/知乎/百度/B站/抖音/快手/微信/小红书)
- Docker Compose 一键部署
- 206测试通过
