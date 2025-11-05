from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Set, List
import json
import datetime
import os
import uuid
import imghdr

app = FastAPI(title="MiniChat")

# 静态目录（index.html、uploads）
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

# ---- 图片上传 ----
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = {"png", "jpeg", "gif", "webp"}

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="图片过大，最大 5MB")
    kind = imghdr.what(None, h=data)
    if kind == "jpg":
        kind = "jpeg"
    if kind not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 png/jpeg/gif/webp")
    filename = f"{uuid.uuid4().hex}.{kind}"
    save_dir = os.path.join("static", "uploads")
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    url = f"/static/uploads/{filename}"
    return JSONResponse({"url": url, "type": kind, "size": len(data), "name": file.filename})

# ---- WebSocket 聊天 ----
HISTORY_LIMIT = 20  # 新加入时仅下发最近 20 条

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.usernames: Dict[WebSocket, str] = {}
        self.history: List[dict] = []  # 仅存储 chat/image

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.usernames[websocket] = username
        # 下发最近 20 条历史
        await websocket.send_text(json.dumps({"type": "history", "data": self.history[-HISTORY_LIMIT:]}))
        # 广播入场（system 不计入 history）
        await self.broadcast({"type": "system", "data": f"{username} 加入了聊天室"})
        await self.send_participants()

    def disconnect(self, websocket: WebSocket):
        username = self.usernames.get(websocket, "某位用户")
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.usernames:
            del self.usernames[websocket]
        return username

    async def send_personal(self, websocket: WebSocket, message: dict):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        # 统一加时间戳
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        enriched = {"ts": timestamp, **message}

        # 仅存 chat/image 到历史
        if message.get("type") in ("chat", "image"):
            self.history.append(enriched)
            self.history[:] = self.history[-HISTORY_LIMIT:]

        # 广播
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(enriched))
            except Exception:
                try:
                    self.active_connections.remove(connection)
                    if connection in self.usernames:
                        del self.usernames[connection]
                except Exception:
                    pass

    async def send_participants(self):
        users = sorted([name for _, name in self.usernames.items()])
        payload = {"type": "participants", "data": users}
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(payload))
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    username = websocket.query_params.get("username") or "匿名用户"
    try:
        await manager.connect(websocket, username)
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {"type": "chat", "data": data}

            msg_type = payload.get("type", "chat")
            if msg_type == "chat":
                text = str(payload.get("data", "")).strip()
                if not text:
                    continue
                await manager.broadcast({
                    "type": "chat",
                    "user": username,
                    "data": text
                })
            elif msg_type == "image":
                url = str(payload.get("data", "")).strip()
                name = payload.get("name") or ""
                if not (url.startswith("/static/uploads/") or url.startswith("/static/stickers/")):
                    await manager.send_personal(websocket, {"type": "error", "data": "非法图片地址"})
                    continue
                await manager.broadcast({
                    "type": "image",
                    "user": username,
                    "data": url,
                    "name": name
                })
            else:
                pass  # ignore
    except WebSocketDisconnect:
        left_user = manager.disconnect(websocket)
        await manager.broadcast({"type": "system", "data": f"{left_user} 离开了聊天室"})
        await manager.send_participants()
    except Exception as e:
        try:
            await manager.send_personal(websocket, {"type": "error", "data": str(e)})
        except Exception:
            pass
        left_user = manager.disconnect(websocket)
        await manager.broadcast({"type": "system", "data": f"{left_user} 连接异常，已断开"})
        await manager.send_participants()
