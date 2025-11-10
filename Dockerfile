FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PORT=8000 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY app.py ./app.py
COPY static ./static

# 上传目录与权限
RUN mkdir -p static/uploads && chmod -R 777 static

# 安装 curl 用于 HEALTHCHECK（也可以删除这段及下面的 HEALTHCHECK）
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

EXPOSE ${PORT}

# 健康检查（用 curl，避免 Python one-liner 转义问题）
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# 启动
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
