# TruthTrace 架构文档

## 概述

TruthTrace 是一个全网事件溯源 + 辟谣平台。输入 URL 或关键词，自动追溯到最早发布者，展示传播链路，评估可信度。

## 系统架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React 前端     │────▶│   FastAPI 后端    │────▶│  PostgreSQL 16  │
│   :5173         │     │   :8000           │     │  事件+来源+图谱  │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  Redis 7 │ │  Celery  │ │  ES 8    │
              │  缓存+MQ │ │  Worker  │ │  搜索索引 │
              │  :6379   │ │  async   │ │  :9200   │
              └──────────┘ └──────────┘ └──────────┘
```

## 数据模型

```
Event (事件)
  ├── id, title, summary, keywords
  ├── status: emerging → active → resolved
  ├── credibility_score: 0-100
  └── 关系
       ├── Source[] (信息来源)
       │    └── PropagationEdge[] (传播关系)
       ├── TimelineNode[] (时间线)
       └── RumorReport (辟谣报告, 1:1)
```

## 核心 Pipeline (9 步)

```
POST /api/trace { url }
  │
  ├─ Step 1: URLResolver — 短链接展开 → 跳转链
  ├─ Step 2: GeneralCrawler — 爬取页面 → CrawlResult
  ├─ Step 3: EventExtractor — NLP事件提取 → 5W1H
  ├─ Step 4: EntityRecognizer — 命名实体识别
  ├─ Step 5: ContentFingerprinter — SimHash指纹
  ├─ Step 6: PropagationGraphBuilder — 构建传播图
  ├─ Step 7: OriginalFinder — 识别原始来源
  ├─ Step 8: _persist_trace_result — 写入PostgreSQL
  └─ Step 9: _generate_rumor_report — 生成辟谣报告
```

## 模块划分

| 模块 | 路径 | 职责 |
|------|------|------|
| crawler | backend/app/crawler/ | 爬虫：Base→General/Weibo/Zhihu |
| analyzer | backend/app/analyzer/ | NLP：分词→实体→事件→聚类→情感 |
| tracer | backend/app/tracer/ | 溯源：PageRank→权威评分→原始来源 |
| verifier | backend/app/verifier/ | 辟谣：交叉验证→事实核查→谣言检测 |
| api | backend/app/api/ | REST API: search/events/trace/rumors |
| tasks | backend/app/tasks/ | Celery Worker: 异步9步Pipeline |

## 前端路由

| 路由 | 页面 | 关键组件 |
|------|------|---------|
| `/` | Home | 搜索入口 |
| `/search?q=` | Search | 筛选器 + TaskTracker |
| `/events/:id` | EventDetail | 传播图 + 时间线 + 来源卡片 |
| `/events/:id/report` | TraceReport | 完整溯源报告 |
| `/rumors` | RumorSquare | 辟谣广场 |
