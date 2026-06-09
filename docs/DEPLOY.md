# TruthTrace 部署指南

## 前置条件

- Docker 24+ & Docker Compose v2
- 至少 4GB 可用内存（ES 需要 1GB+）
- Python 3.12+ (本地开发)

## 快速启动

```bash
cd truthtrace
docker-compose up -d
```

7 个容器启动顺序：
```
postgres → redis → elasticsearch → backend → worker → frontend
```

## 访问

| 服务 | URL |
|------|-----|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/api/health |
| Elasticsearch | http://localhost:9200 |
| Redis | localhost:6379 |

## 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Celery Worker (另开终端)
celery -A app.tasks.worker worker --loglevel=info --concurrency=4

# 前端 (另开终端)
cd frontend
npm install
npm run dev
```

## 运行测试

```bash
cd backend
pip install pytest pytest-asyncio aiosqlite
python -m pytest tests/ -v
```

测试使用 SQLite 内存数据库，无需 PostgreSQL。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| DATABASE_URL | postgresql+asyncpg://... | 数据库连接串 |
| REDIS_URL | redis://localhost:6379/0 | Redis 缓存 |
| ELASTICSEARCH_URL | http://localhost:9200 | ES 搜索 |
| CELERY_BROKER_URL | redis://localhost:6379/1 | 消息队列 |
| CELERY_RESULT_BACKEND | redis://localhost:6379/2 | 任务结果 |

## 生产环境注意事项

1. 修改 `docker-compose.yml` 中的默认密码
2. 启用 ES 安全认证 (`xpack.security.enabled=true`)
3. 后端去掉 `--reload` 热重载
4. 添加 Nginx 反向代理
5. 配置 HTTPS 证书
