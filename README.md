
# MiniChat (FastAPI + WebSocket)

一个超简易、零数据库、单房间的网页聊天程序，支持：
- 在线用户列表
- 入场/离场系统消息
- 最近消息记录（内存保留 100 条，首屏下发 50 条）
- 纯前端原生 JS，无第三方前端依赖

## 运行步骤

```bash
# 1) 安装依赖（建议在虚拟环境中）
pip install -r requirements.txt

# 2) 启动服务（默认 8000 端口）
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 3) 浏览器打开
http://localhost:8000
```

## 结构
```
app.py
static/
  └── index.html
requirements.txt
```

## 部署小贴士
- 生产环境可用 `uvicorn app:app --host 0.0.0.0 --port 80`，或配合 nginx 反向代理。
- 若使用 HTTPS，请确保前端使用 `wss://`（本页面会自动根据 `https:` 切换到 `wss:`）。
- 该示例仅演示最基本功能：单房间、内存广播。如需多房间、持久化、鉴权、消息存储等，可在后端引入 Redis、数据库、JWT 等自行拓展。
