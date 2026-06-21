# BiliCast Studio

> 把 B 站视频整理成带时间轴的 PDF 笔记

提交 Bilibili 视频链接，网站自动嵌入播放器、读取字幕（或用本地语音识别生成字幕）、按时间段整理内容，并导出为 PDF 文档。

## 功能

- **站内播放** — 页面直接嵌入 Bilibili 播放器，边看视频边看报告
- **字幕读取** — 自动读取 Bilibili 公开字幕或 AI 字幕
- **本地 ASR** — 没有字幕的视频，下载音频后用 faster-whisper 语音识别
- **时间轴报告** — 按时间段整理内容，显示标题、摘要、要点
- **PDF 导出** — 一键下载带时间轴的播客式 PDF 笔记

## 快速开始（本地开发）

### 安装依赖

```bash
pip install reportlab

# 可选 - 给没有字幕的视频使用：
pip install yt-dlp faster-whisper

# FFmpeg（本地 ASR 需要）
# Windows: winget install ffmpeg
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg
```

### 启动

```bash
python server.py --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000

---

## Ubuntu 服务器部署

### 一键安装

```bash
# 1. 上传到服务器后解压
unzip bilicast-studio-ubuntu.zip -d bilicast-studio
cd bilicast-studio

# 2. 运行一键安装脚本
chmod +x install.sh
./install.sh
```

脚本会自动安装 ffmpeg、创建 Python 虚拟环境、安装 reportlab / yt-dlp / faster-whisper，并可选择配置 systemd 开机自启。

### 手动安装

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg

python3 -m venv venv
source venv/bin/activate
pip install reportlab yt-dlp faster-whisper

python server.py --host 0.0.0.0 --port 8000
```

### systemd 服务（开机自启）

```ini
sudo tee /etc/systemd/system/bilicast.service << 'EOF'
[Unit]
Description=BiliCast Studio
After=network.target

[Service]
Type=simple
User=你的用户名
WorkingDirectory=/path/to/bilicast-studio
ExecStart=/path/to/bilicast-studio/venv/bin/python server.py --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
Environment=WHISPER_MODEL=small
Environment=WHISPER_DEVICE=cpu

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable bilicast
sudo systemctl start bilicast
```

### Nginx 反代 + HTTPS（Certbot）

```bash
# 1. 安装 Nginx 和 Certbot
sudo apt install nginx certbot python3-certbot-nginx

# 2. 配置 Nginx 反代（参考项目中的 nginx.conf）
sudo cp nginx.conf /etc/nginx/sites-available/bilicast
sudo ln -s /etc/nginx/sites-available/bilicast /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 3. 申请 SSL 证书（自动配置 HTTPS）
sudo certbot --nginx -d 你的域名.com

# 4. 验证证书自动续期（certbot 内置定时任务）
sudo certbot renew --dry-run
```

> 建议用 Nginx 反代到本地 127.0.0.1:8000，由 Nginx 处理 HTTPS 和域名。不要直接用 0.0.0.0 暴露端口。

## 文件结构

```
bilicast-studio/
  server.py              # Python 后端（纯标准库）
  index.html             # 前端页面
  styles.css             # 响应式样式
  app.js                 # 前端交互
  requirements.txt       # Python 依赖
  install.sh             # Ubuntu 一键安装脚本
  nginx.conf             # Nginx 反代配置
  run_bilicast_server.bat # Windows 启动脚本
  README.md
```

## 识别模式

| 模式 | 说明 | 依赖 |
|---|---|---|
| 读取B站字幕 | 通过 Bilibili API 读取公开字幕或 AI 字幕 | 无 |
| 本地 ASR 识别 | 下载音频后用 faster-whisper 语音识别 | yt-dlp, faster-whisper, ffmpeg |
| 本地演示 | 不联网，生成示例报告用于测试流程 | 无 |

## API

### POST /api/analyze

请求：
```json
{"url":"https://www.bilibili.com/video/BV...","mode":"subtitle","page":1,"reportTitle":"可选标题"}
```

mode 可选值：subtitle（B站字幕）、asr（本地识别）、demo（演示）

返回：
```json
{"source":"bilibili-subtitle","title":"视频标题","duration":"18:42","summary":"整体摘要","keywords":["关键词"],"segments":[{"start":"00:00","end":"02:15","title":"段落标题","summary":"内容摘要","highlights":["要点一","要点二"]}]}
```

### POST /api/report.pdf

传入上面的 report JSON，返回 PDF 文件。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| WHISPER_MODEL | small | faster-whisper 模型大小（tiny/base/small/medium/large） |
| WHISPER_DEVICE | cpu | 运行设备（cpu / cuda） |

## 技术栈

- **后端** — Python 标准库（http.server），零框架依赖
- **前端** — 纯 HTML / CSS / JavaScript
- **PDF** — reportlab
- **ASR** — faster-whisper
- **视频信息** — Bilibili 开放 API
