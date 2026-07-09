# Quant Paper Trading

一个面向未来港股、美股与期权扩展的 Python 量化交易 MVP。当前版本只提供本地模拟盘和日线回测，不连接任何实盘券商。

## 功能

- 均线交叉示例策略与可扩展策略接口
- CSV 日线回测、权益曲线、收益率、最大回撤和夏普比率
- 模拟券商适配器、下一日开盘撮合、限价触达撮合
- 下单前现金、卖空、订单金额、集中度和总敞口风控
- SQLite 账户、订单、成交与持仓持久化
- FastAPI 接口与自动生成的 OpenAPI 文档
- pytest 单元与端到端测试

期权只保留领域类型与适配边界，MVP 会拒绝期权订单。账户以 USD 记账，暂不换算 HKD。

## 快速启动

需要 Python 3.12 和 uv：

```bash
cp .env.example .env
uv sync
uv run uvicorn quant_trader.api:app --reload
```

打开 `http://127.0.0.1:8000/` 使用中文回测操作台，或访问 `/docs` 使用 API 文档。

## 部署到 Render

仓库根目录包含 `render.yaml`，可在 Render 创建 Blueprint 并连接该仓库。免费实例使用临时 SQLite，服务重启后账户会重置。
