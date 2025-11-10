import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ----------------------------
# 基础路径与目录
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
STICKER_DIR = STATIC_DIR / "stickers"

STATIC_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STICKER_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# FastAPI 初始化
# ----------------------------
app = FastAPI(title="MiniChat")

# 如需跨域，放开这里（按需添加你的前端域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改成你的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态目录挂载
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")

# ----------------------------
# 工具：文件名清理（保留中文）
# ----------------------------
# 允许：中文字符、英文字母、数字、点、下划线、短横、空格
# 移除：路径分隔符、控制字符、其它危险字符
FNAME_ALLOWED = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff._\- ]+")

def sanitize_filename(name: str) -> str:
    # 仅取 basename，避免 ../
    name = os.path.basename(name)
    # 去除控制字符
    name = "".join(ch for ch in name if ch.isprintable())
    # 过滤危险字符但保留中文
    name = FNAME_ALLOWED.sub("", name)
    # 空名则给默认名
    if not name or name in {".", ".."}:
        name = "file"
    # 压缩多余空格
    name = re.sub(r"\s+", " ", name).strip()
    return name

def unique_path(dir_path: Path, filename: str) -> Path:
    """同名则追加时间戳避免覆盖"""
    candidate = dir_path / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return dir_path / f"{stem}_{ts}{suffix}"

# ----------------------------
# WebSocket 连接与消息管理
# ----------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.usernames: Dict[WebSocket, str] = {}
        self.history: List[Dict] = []  # 保存最近 N 条消息
        self.max_history = 20

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.usernames[websocket] = username
        # 加入欢迎
        await self.broadcast_system(f"{username} 加入了聊天室")
        # 发送参与者列表
        await self.broadcast_participants()
        # 发送历史
        await websocket.send_json({"type": "history", "data": self.history})

    def disconnect(self, websocket: WebSocket):
        username = self.usernames.get(websocket, "访客")
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.usernames.pop(websocket, None)
        # 断开时不立即广播；由上层调用
        return username

    async def send_personal(self, websocket: WebSocket, message: Dict):
        await websocket.send_json(message)

    async def broadcast(self, message: Dict):
        # 裁剪历史
        if message.get("type") in {"chat", "image", "file", "system"}:
            self.history.append(message)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
        # 广播
        for conn in list(self.active_connections):
            try:
                await conn.send_json(message)
            except Exception:
                # 某些连接可能已断，忽略
                pass

    async def broadcast_system(self, text: str):
        await self.broadcast({
            "type": "system",
            "data": text,
            "ts": datetime.now().strftime("%H:%M:%S")
        })

    async def broadcast_participants(self):
        users = [self.usernames.get(ws, "访客") for ws in self.active_connections]
        for conn in list(self.active_connections):
            try:
                await conn.send_json({"type": "participants", "data": users})
            except Exception:
                pass

manager = ConnectionManager()

# ----------------------------
# 路由：健康检查、首页
# ----------------------------
@app.get("/health")
def health():
    return {"ok": True, "time": int(time.time())}

@app.get("/", response_class=HTMLResponse)
def index():
    # 仅便捷：重定向到 /static/index.html
    return HTMLResponse(
        '<meta http-equiv="refresh" content="0; url=/static/index.html" />',
        status_code=200
    )

# ----------------------------
# 路由：上传任意文件
# ----------------------------
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB，按需调整

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # 尺寸限制（FastAPI 若未启服务端 limit，可在此读取检测）
    # 这里直接保存到磁盘；如需严格尺寸校验，可先读取到内存/临时文件判断大小
    raw_name = file.filename or "file"
    safe_name = sanitize_filename(raw_name)
    # 如果清掉后没有后缀，可以保留原后缀
    orig_suffix = Path(raw_name).suffix
    if orig_suffix and not safe_name.endswith(orig_suffix):
        safe_name = f"{safe_name}{orig_suffix}"

    dest_path = unique_path(UPLOAD_DIR, safe_name)

    # 将内容流式写入磁盘，避免一次性读入内存
    size = 0
    with dest_path.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                try: dest_path.unlink(missing_ok=True)
                except Exception: pass
                raise HTTPException(status_code=413, detail="文件过大（>10MB）")
            f.write(chunk)

    # 返回可访问 URL（相对路径即可）
    url = f"/static/uploads/{dest_path.name}"
    return {"url": url, "name": dest_path.name}

# ----------------------------
# WebSocket：聊天
# ----------------------------
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # 取用户名（缺省为访客+随机）
    username = websocket.query_params.get("username") or f"访客{int(time.time())%1000}"
    try:
        await manager.connect(websocket, username)
        while True:
            data_text = await websocket.receive_text()
            # 简单 JSON 解析
            try:
                import json
                payload = json.loads(data_text)
            except Exception:
                await manager.send_personal(websocket, {"type": "system", "data": "消息格式错误"})
                continue

            msg_type = payload.get("type")
            msg_data = payload.get("data")
            msg_name = payload.get("name")  # 文件/图片名

            # 附上时间戳与发送者
            envelope = {
                "type": msg_type,
                "user": manager.usernames.get(websocket, "访客"),
                "data": msg_data,
                "name": msg_name,
                "ts": datetime.now().strftime("%H:%M:%S"),
            }

            # 基础校验与白名单
            if msg_type == "chat":
                if not isinstance(msg_data, str) or not msg_data.strip():
                    await manager.send_personal(websocket, {"type": "system", "data": "空消息无法发送"})
                    continue
                await manager.broadcast(envelope)

            elif msg_type in {"image", "file"}:
                # 仅允许本站上传的静态资源/贴纸
                if not isinstance(msg_data, str):
                    await manager.send_personal(websocket, {"type": "system", "data": "文件地址非法"})
                    continue
                if not (
                    msg_data.startswith("/static/uploads/") or
                    msg_data.startswith("/static/stickers/")
                ):
                    await manager.send_personal(websocket, {"type": "system", "data": "非法资源地址"})
                    continue
                # 服务器不再限制类型：任意文件都走 'file'，图片走 'image'
                await manager.broadcast(envelope)

            elif msg_type == "participants":
                # 可选：前端主动拉取
                await manager.broadcast_participants()

            else:
                await manager.send_personal(websocket, {"type": "system", "data": f"未知消息类型：{msg_type}"})

    except WebSocketDisconnect:
        user = manager.disconnect(websocket)
        await manager.broadcast_system(f"{user} 离开了聊天室")
        await manager.broadcast_participants()
    except Exception as e:
        # 兜底异常
        try:
            await manager.send_personal(websocket, {"type": "system", "data": f"服务器错误：{e}"})
        except Exception:
            pass
        finally:
            user = manager.disconnect(websocket)
            await manager.broadcast_system(f"{user} 离开了聊天室")
            await manager.broadcast_participants()
