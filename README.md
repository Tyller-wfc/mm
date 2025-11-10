✅ MiniChat (FastAPI + WebSocket + 文件上传)

一个无需数据库、零依赖前端框架、可直接 Docker 部署的简易在线群聊系统，包含以下特性：

✅ WebSocket 实时聊天
✅ 首次进入弹窗设置昵称（自动记忆）
✅ 在线用户列表 / 入场离场提示
✅ 消息只保留最近 20 条（自动裁剪）
✅ 图片 + 任意类型文件上传/共享（自动区分图片预览 / 文件下载）
✅ 拖拽上传 / 粘贴上传（图片）
✅ Emoji 面板 + 贴纸支持
✅ 移动端适配（iOS/Android 浏览器）
✅ Docker 一键部署
✅ 无数据库、纯内存运行

📦 项目结构
app.py
Dockerfile
requirements.txt
static/
  ├── index.html      # 前端 UI（纯原生 JS）
  ├── stickers/       # 内置贴纸
  └── uploads/        # 文件上传目录（自动生成）

🚀 本地运行
1) 安装依赖
pip install -r requirements.txt


依赖非常精简：

fastapi

uvicorn[standard]

python-multipart（处理文件上传）

2) 启动服务
uvicorn app:app --reload --host 0.0.0.0 --port 8000

3) 打开浏览器访问
http://localhost:8000


首次进入会弹框要求设置昵称。
之后聊天界面会包括：

文本消息

图片消息

表情/贴纸

任意文件上传（带下载链接）

在线用户列表

✅ 功能说明
✅ 1. 昵称逻辑（自动记忆）

首次进入弹出昵称输入弹窗

存入浏览器 localStorage（mc_name）

下一次访问自动加入聊天室

“昵称输入 + 加入按钮”在加入后隐藏，移动端界面更简洁

✅ 2. 文件上传功能

后端 /upload 接口支持：

✅ 任意格式文件（默认 <10MB，可在 app.py 中调整）
✅ 自动保存至 static/uploads
✅ 中文文件名 ✅
✅ 图片自动预览
✅ 非图片显示为下载链接

支持以下方式上传：

点击“文件”按钮选择文件

拖拽文件到聊天窗口上方提示区

直接粘贴图片（剪切板图片）

✅ 3. WebSocket 实时聊天功能

入场/离场系统消息

在线用户实时更新

最近 20 条消息自动保留

图片 / 文件 / 文本都通过 WebSocket 广播

✅ 4. 移动端适配

适配 iOS Safari / Android Chrome

表情面板自动浮动

输入框随软键盘自动上推

输入区采用 sticky 底部定位

🐳 Docker 部署
构建镜像
docker build -t minichat:latest .

运行容器（含上传目录持久化）

Linux/Mac：

docker run -d --name minichat \
  -p 8000:8000 \
  -v "$(pwd)/static/uploads:/app/static/uploads" \
  --restart=unless-stopped \
  minichat:latest


Windows PowerShell：

docker run -d --name minichat `
  -p 8000:8000 `
  -v "${PWD}\static\uploads:/app/static/uploads" `
  --restart=unless-stopped `
  minichat:latest


启动后访问：

http://localhost:8000

🌐 生产部署建议

用 Nginx 反向代理 + WebSocket (upgrade 头)

使用 HTTPS → WebSocket 自动切换成 wss://

上传大小限制可在 Nginx + app.py 中同时调整

如需多房间 / 消息持久化 → 引入 Redis