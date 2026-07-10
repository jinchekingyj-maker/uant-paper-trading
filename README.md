---
title: Quant Paper Trading
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

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

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)：

```bash
cp .env.example .env
uv sync
uv run uvicorn quant_trader.api:app --reload
```

打开 `http://127.0.0.1:8000/docs` 使用交互式 API 文档。
打开 `http://127.0.0.1:8000/` 可使用中文回测操作台，直接输入股票代码并获取公开历史日线。

运行测试：

```bash
uv run pytest
```

## 模拟交易示例

先注入一根行情，让系统获得参考价格：

```bash
curl -X POST http://127.0.0.1:8000/market-data/bars \
  -H 'content-type: application/json' \
  -d '{"market":"US","symbol":"AAPL","trading_date":"2024-01-02","open":185,"high":188,"low":184,"close":187,"volume":1000000}'
```

提交市价单：

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H 'content-type: application/json' \
  -d '{"account_id":"paper","market":"US","symbol":"AAPL","security_type":"STOCK","side":"BUY","order_type":"MARKET","quantity":"10"}'
```

再注入下一交易日行情，订单将在其开盘价成交：

```bash
curl -X POST http://127.0.0.1:8000/market-data/bars \
  -H 'content-type: application/json' \
  -d '{"market":"US","symbol":"AAPL","trading_date":"2024-01-03","open":188,"high":190,"low":187,"close":189,"volume":1200000}'
```

## 回测

`POST /backtests` 默认使用内置样例 CSV，也可传入本机 CSV 路径。CSV 必须包含：

```text
date,open,high,low,close,volume
```

策略在当日收盘后产生信号，订单最早在下一根日线成交，避免未来数据泄漏。

港股代码可输入 `0700`，系统会自动转换为行情源使用的 `0700.HK`。

## 部署到 Render

仓库根目录已包含 `render.yaml`。将项目推送至 GitHub 后，在 Render 创建 Blueprint 并连接该仓库即可。免费实例的 SQLite 位于临时磁盘，服务重启后模拟账户会重置；正式长期使用时应升级持久磁盘或 PostgreSQL。

## 部署到 Hugging Face Spaces

如果 Render 卡在银行卡验证，可以改用 Hugging Face Spaces。仓库根目录已包含 `Dockerfile`，README 顶部也声明了 Spaces 配置。

创建方式：

1. 打开 Hugging Face 并创建一个新的 Space。
2. Space SDK 选择 `Docker`。
3. 可见性建议先选 `Public`，硬件选免费 CPU 即可。
4. 创建后选择从 GitHub 导入，使用本仓库地址。

启动成功后，打开 Space 页面即可看到中文操作台；输入 `AAPL`、`MSFT` 或港股 `0700` 可以直接运行公开日线回测。

注意：免费 Space 默认没有持久化磁盘，服务重启后模拟账户和订单记录可能重置。回测不受影响，因为会重新拉取公开历史日线。

## 项目结构

```text
src/quant_trader/
├── api.py          # FastAPI
├── backtest.py     # 回测引擎与指标
├── broker.py       # 券商接口和模拟券商
├── db.py           # SQLAlchemy 持久化
├── domain.py       # 统一领域模型
├── portfolio.py    # 持仓、现金与盈亏
├── risk.py         # 下单前风控
├── schemas.py      # API 数据契约
└── strategy.py     # 策略接口与均线策略
```
