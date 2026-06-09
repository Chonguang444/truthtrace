# 贡献指南

感谢你对 TruthTrace 的关注！以下是参与贡献的方式。

## 行为准则

- **尊重科学共识** — 提交的知识条目需引用可验证的权威来源
- **可溯源** — 任何声称需附带证据链接
- **不确定就说** — 不编造不基于事实的内容
- **善意推定** — 假设其他贡献者是善意地在改进产品

## 如何贡献

### 报告 Bug

在 Issues 中描述：
- 重现步骤
- 期望行为 vs 实际行为
- 环境信息（Python 版本、操作系统）

### 提交代码

1. Fork 仓库
2. 创建分支：`git checkout -b feature/your-feature`
3. 确保测试通过：`cd backend && pytest tests/ -v`
4. 提交前检查 TypeScript：`cd frontend && npx tsc --noEmit`
5. 提交 PR 到 `master` 分支

### 引擎规则优化

引擎规则主要在以下文件中：
- `backend/app/engine/distortion.py` — 失真检测模式
- `backend/app/engine/fallacy.py` — 逻辑谬误模式
- `backend/app/engine/statistical.py` — 统计滥用模式
- `backend/app/engine/narrative.py` — 叙事框架模式

修改规则后运行回归测试：
```bash
cd backend && python -m pytest tests/test_engine.py tests/test_engine_v2.py -v
```

### 新增知识条目

知识条目在 `backend/app/engine/authoritative_kb.py` 和 `backend/app/engine/expert_kb.py` 中。

每条知识需包含：
- 完整的引用格式
- 来源 URL
- 证据等级
- 适用范围/局限性

### 平台爬虫

新增平台支持需实现：
- URL 识别函数
- 异步爬取方法（含错误处理）
- Cookie 随机化

## 开发环境

```bash
# 后端
cd backend && pip install -r requirements.txt

# 前端
cd frontend && npm install

# 运行测试
cd backend && pytest tests/ -v
```

## Code Review 检查点

- [ ] 测试通过
- [ ] TypeScript 零错误
- [ ] 引擎规则不引入退化（回归测试通过）
- [ ] 新的知识条目附带可引用的来源 URL
