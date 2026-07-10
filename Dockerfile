FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV DATABASE_URL=sqlite:////tmp/paper_trading.db

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

EXPOSE 7860

CMD ["uv", "run", "uvicorn", "quant_trader.api:app", "--host", "0.0.0.0", "--port", "7860"]
