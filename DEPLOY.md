# TruthTrace 部署指南

## 架构

```
[Vercel] 前端 (React SPA)  ←───→  [Render/Railway] 后端 (FastAPI)
      ↑                                    ↑
      │  VITE_API_BASE_URL                 │  PostgreSQL + Redis + ES
      │  指向后端 URL                       │  Docker 或直接部署
```

## 一、前端部署到 Vercel（5 分钟）

### 1. 在 Vercel 中导入项目

```bash
# 安装 Vercel CLI
npm i -g vercel

# 进入 frontend 目录
cd frontend

# 登录并部署
vercel login
vercel --prod
```

### 2. 设置环境变量

在 Vercel Dashboard → Settings → Environment Variables 中添加：

| 变量名 | 值 | 说明 |
|---|---|---|
| `VITE_API_BASE_URL` | `https://你的后端域名` | 后端 API 地址 |

> ⚠️ **重要**: 前端不能和 API 放在同一个 Vercel 项目。Vercel 不支持 Python/FastAPI 服务端。后端需要单独托管。

### 3. 触发部署

```bash
git push  # 或 vercel --prod
```

Vercel 自动检测 Vite 框架，使用 `vercel.json` 中的配置。

---

## 二、后端部署（三选一）

### 方案 A: Render（推荐，免费额度足够开发用）

[render.com](https://render.com) — 支持 Docker 或 Python 原生部署

**使用 Docker**:
```bash
# 1. 在 Render 创建 "Web Service"
# 2. 连接 GitHub 仓库
# 3. 设置:
#    Runtime: Docker
#    Dockerfile Path: deploy/Dockerfile.backend
#    Port: 8000
# 4. 添加环境变量 (见下方)
```

**或使用 Python 原生**:
```bash
# Build Command: pip install -r requirements.txt
# Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 方案 B: Railway

[railway.app](https://railway.app) — 支持 Docker Compose 全栈

```bash
# 1. 安装 Railway CLI
# 2. railway login
# 3. railway init
# 4. railway up
```

### 方案 C: Fly.io

[fly.io](https://fly.io) — 全球边缘部署

```bash
fly launch
fly deploy
```

---

## 三、必需环境变量

### 后端最小环境变量

```bash
# 安全（必须设置，否则拒绝启动）
JWT_SECRET_KEY=<用 python -c "import secrets; print(secrets.token_urlsafe(64))" 生成>

# 数据库（使用 Render/Railway 提供的托管 PostgreSQL 或自带）
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/truthtrace

# Redis（Celery 需要，可选）
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/1
CELERY_RESULT_BACKEND=redis://host:6379/2

# CORS（必须设置为前端 Vercel 域名）
CORS_ORIGINS=https://你的项目.vercel.app

# 可选
SENTRY_DSN=https://xxx@sentry.io/xxx  # 错误追踪
ANTHROPIC_API_KEY=sk-ant-xxx           # LLM 增强分析
SMTP_HOST=smtp.example.com             # 邮件通知
```

---

## 四、CORS 配置

部署前在 `backend/app/main.py` 中更新 CORS origins 为你的前端域名：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://你的项目.vercel.app",  # Vercel 前端
        "http://localhost:5173",         # 本地开发
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 五、域名配置

1. 在 Vercel Dashboard 中添加自定义域名
2. DNS 添加 CNAME 记录指向 `cname.vercel-dns.com`
3. Vercel 自动申请和管理 SSL 证书

---

## 六、验证清单

- [ ] 前端 https://你的域名 正常加载
- [ ] API https://后端域名/api/health 返回 `{"status":"ok"}`
- [ ] 搜索功能正常：输入关键词 → 有结果返回
- [ ] 溯源功能正常：粘贴URL → 返回分析结果
- [ ] WebSocket 连接正常（TaskTracker 实时进度）
- [ ] 登录/注册正常
- [ ] 管理后台 `/admin` 可访问
- [ ] 移动端响应式正常

---

## 七、数据库

Render 提供免费 PostgreSQL（90天后过期需升级）:
1. Render Dashboard → New → PostgreSQL
2. 复制 Connection String
3. 在后端环境变量中设置 `DATABASE_URL`

```bash
# 初始化数据库表
cd backend
DATABASE_URL_SYNC="postgresql://..." python -m alembic upgrade head
```
