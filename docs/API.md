# TruthTrace API 文档

Base URL: `http://localhost:8000/api`

## 搜索

### GET /api/search
搜索事件（全文搜索 + JSONB + ILIKE 三级回退）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | ✅ | 关键词或 URL |
| status | string | | emerging/active/resolved |
| limit | int | | 1-100, 默认 20 |
| offset | int | | 默认 0 |

### GET /api/search/url
通过 URL 搜索（精确→模糊→建议提交）

| 参数 | 类型 | 必填 |
|------|------|------|
| url | string | ✅ |

## 追踪任务

### POST /api/trace
提交异步溯源任务

```json
{
  "url": "https://weibo.com/...",
  "title": "可选标题",
  "description": "可选描述",
  "deep_trace": false
}
```

### GET /api/tasks/{task_id}
查询任务状态（SUCCESS/FAILURE/STARTED）

### GET /api/trace/url-chain?url=...
解析 URL 跳转链

## 事件

### GET /api/events/{event_id}
事件详情（含来源统计、平台分布、原始来源）

### GET /api/events/{event_id}/timeline
事件时间线

### GET /api/events/{event_id}/graph
传播图数据 (nodes + edges, 用于 D3.js)

### GET /api/events/{event_id}/sources?sort_by=published_at&order=desc
来源列表，支持排序

### GET /api/events/{event_id}/report
完整溯源报告（传播链 + 时间线 + 辟谣分析）

### GET /api/events/{event_id}/verify
触发真实性验证（CrossReferencer + RumorDetector）

## 辟谣

### GET /api/rumors?verdict=false&limit=20
辟谣广场列表

### GET /api/rumors/{rumor_id}
辟谣报告详情

## 系统

### GET /api/health
健康检查

```json
{
  "status": "ok",
  "app": "TruthTrace",
  "version": "0.1.0"
}
```
