from __future__ import annotations

import argparse
import http.server
import html
import json
import mimetypes
import os
import re
import socketserver
import sys
import tempfile
import traceback
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json,text/plain,*/*",
}


class UserFacingError(RuntimeError):
    pass


@dataclass
class ParsedVideo:
    id_type: str
    video_id: str
    page: int = 1

    @property
    def display_id(self) -> str:
        return self.video_id if self.id_type == "bvid" else f"av{self.video_id}"


DEMO_SEGMENTS = [
    {
        "start": "00:00",
        "end": "01:18",
        "title": "开场与主题定位",
        "summary": "视频先交代本期主题、适用对象和观看背景，把后面要解决的问题铺出来。",
        "highlights": ["说明视频讨论范围", "提示观众可以重点关注后续案例"],
    },
    {
        "start": "01:18",
        "end": "04:36",
        "title": "核心概念拆解",
        "summary": "这一段把主题拆成几个基础概念，用更容易理解的表达解释每个概念之间的关系。",
        "highlights": ["定义关键术语", "指出常见误区", "建立后续分析框架"],
    },
    {
        "start": "04:36",
        "end": "08:52",
        "title": "案例与细节展开",
        "summary": "视频进入具体例子，围绕案例背景、过程变化和结果差异进行说明。",
        "highlights": ["用案例验证前面的概念", "强调时间线变化", "对比不同选择的影响"],
    },
    {
        "start": "08:52",
        "end": "12:40",
        "title": "方法论总结",
        "summary": "讲解者把前面的内容收束成可复用的方法，给出判断顺序和执行步骤。",
        "highlights": ["整理判断标准", "给出操作步骤", "说明适用边界"],
    },
    {
        "start": "12:40",
        "end": "15:26",
        "title": "结论与延伸",
        "summary": "最后回到视频主线，总结关键结论，并补充后续可以继续关注的问题。",
        "highlights": ["提炼最终观点", "留下延伸问题", "提醒观众复盘重点章节"],
    },
]


def parse_bilibili_url(url: str, page: int | None = None) -> ParsedVideo:
    bvid_match = re.search(r"BV[0-9A-Za-z]{10}", url)
    avid_match = re.search(r"(?:/video/av|[?&]aid=|^av)(\d+)", url, re.I)
    page_match = re.search(r"[?&]p=(\d+)", url, re.I)
    resolved_page = page or (int(page_match.group(1)) if page_match else 1)

    if bvid_match:
        return ParsedVideo("bvid", bvid_match.group(0), max(1, resolved_page))
    if avid_match:
        return ParsedVideo("aid", avid_match.group(1), max(1, resolved_page))
    raise UserFacingError("没有识别到 BV 或 av 编号，请提交完整 Bilibili 视频链接。")


def http_json(url: str, timeout: int = 16) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def fetch_view_info(parsed: ParsedVideo) -> dict[str, Any]:
    params = (
        {"bvid": parsed.video_id}
        if parsed.id_type == "bvid"
        else {"aid": parsed.video_id}
    )
    url = "https://api.bilibili.com/x/web-interface/view?" + urllib.parse.urlencode(params)
    payload = http_json(url)
    if payload.get("code") != 0:
        raise UserFacingError(payload.get("message") or "Bilibili 视频信息接口返回异常。")
    return payload.get("data") or {}


def fetch_subtitle_items(parsed: ParsedVideo, cid: int) -> list[dict[str, Any]]:
    params = (
        {"bvid": parsed.video_id, "cid": cid}
        if parsed.id_type == "bvid"
        else {"aid": parsed.video_id, "cid": cid}
    )
    player_url = "https://api.bilibili.com/x/player/v2?" + urllib.parse.urlencode(params)
    player_payload = http_json(player_url)
    subtitles = (
        (player_payload.get("data") or {})
        .get("subtitle", {})
        .get("subtitles", [])
    )
    if not subtitles:
        raise UserFacingError(
            "这个视频没有公开字幕或 AI 字幕。可以安装 yt-dlp + faster-whisper 后启用本地 ASR，"
            "或换一个带字幕的视频测试。"
        )

    preferred = choose_subtitle(subtitles)
    subtitle_url = preferred.get("subtitle_url") or ""
    if subtitle_url.startswith("//"):
        subtitle_url = f"https:{subtitle_url}"
    if subtitle_url.startswith("/"):
        subtitle_url = f"https://www.bilibili.com{subtitle_url}"
    if not subtitle_url:
        raise UserFacingError("字幕接口没有返回可下载的字幕地址。")

    subtitle_payload = http_json(subtitle_url)
    body = subtitle_payload.get("body") or []
    items = []
    for item in body:
        content = clean_text(str(item.get("content", "")))
        if not content:
            continue
        items.append(
            {
                "from": float(item.get("from", 0)),
                "to": float(item.get("to", item.get("from", 0))),
                "content": content,
            }
        )
    if not items:
        raise UserFacingError("字幕为空，无法生成时间轴报告。")
    return items


def choose_subtitle(subtitles: list[dict[str, Any]]) -> dict[str, Any]:
    for subtitle in subtitles:
        language = f"{subtitle.get('lan', '')} {subtitle.get('lan_doc', '')}".lower()
        if "zh" in language or "中文" in language or "自动" in language:
            return subtitle
    return subtitles[0]


def analyze_with_bilibili_subtitle(parsed: ParsedVideo, requested_title: str | None = None) -> dict[str, Any]:
    view = fetch_view_info(parsed)
    pages = view.get("pages") or []
    if not pages:
        raise UserFacingError("没有从 Bilibili 获取到视频分 P 信息。")

    page_index = min(max(parsed.page - 1, 0), len(pages) - 1)
    selected_page = pages[page_index]
    cid = selected_page.get("cid")
    if not cid:
        raise UserFacingError("没有从 Bilibili 获取到当前分 P 的 cid。")

    subtitle_items = fetch_subtitle_items(parsed, int(cid))
    title = requested_title or view.get("title") or f"{parsed.display_id} 视频内容笔记"
    segments = build_segments_from_subtitles(subtitle_items)
    transcript = "。".join(item["content"] for item in subtitle_items[:120])

    return {
        "source": "bilibili-subtitle",
        "title": title,
        "duration": format_time(int(view.get("duration") or selected_page.get("duration") or 0)),
        "summary": summarize_text(transcript, 220)
        or "已从 Bilibili 字幕生成时间轴报告。",
        "keywords": extract_keywords(title, transcript),
        "segments": segments,
        "videoId": parsed.display_id,
        "page": parsed.page,
    }


def analyze_with_optional_local_asr(parsed: ParsedVideo, url: str, requested_title: str | None = None) -> dict[str, Any]:
    try:
        import yt_dlp  # type: ignore
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        raise UserFacingError(
            "当前环境没有安装本地语音识别依赖。需要安装 yt-dlp、faster-whisper 和 ffmpeg，"
            "或者使用带公开字幕的视频。"
        ) from exc

    model_size = os.environ.get("WHISPER_MODEL", "small")
    with tempfile.TemporaryDirectory(prefix="bilicast-") as tmpdir:
        audio_path = None
        info = {}

        # Strategy 1: yt-dlp (works for most sites)
        try:
            output = str(Path(tmpdir) / "%(id)s.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output,
                "quiet": True,
                "noplaylist": True,
                "http_headers": HEADERS,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                    }
                ],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            audio_files = list(Path(tmpdir).glob("*.m4a")) or list(Path(tmpdir).iterdir())
            if audio_files:
                audio_path = str(audio_files[0])
        except Exception:
            pass

        # Strategy 2: Bilibili playurl API directly (bypass yt-dlp)
        if not audio_path and "bilibili" in url.lower():
            try:
                view = fetch_view_info(parsed)
                cid = None
                pages = view.get("pages") or []
                if pages:
                    page_index = min(max(parsed.page - 1, 0), len(pages) - 1)
                    cid = pages[page_index].get("cid")
                if not cid:
                    cid = view.get("cid")
                if cid:
                    p = urllib.parse.urlencode({
                        "bvid": parsed.video_id if parsed.id_type == "bvid" else "",
                        "aid": parsed.video_id if parsed.id_type == "aid" else "",
                        "cid": cid, "qn": 0, "fnval": 16, "fnver": 0, "fourk": 1,
                    })
                    play_data = http_json("https://api.bilibili.com/x/player/playurl?" + p)
                    audio_list = (play_data.get("data") or {}).get("dash", {}).get("audio", [])
                    if audio_list:
                        audio_url = audio_list[0].get("baseUrl") or audio_list[0].get("base_url", "")
                        if audio_url:
                            raw_path = Path(tmpdir) / "audio_raw.m4s"
                            audio_req = urllib.request.Request(audio_url, headers=HEADERS)
                            with urllib.request.urlopen(audio_req, timeout=120) as ar:
                                with open(raw_path, "wb") as f:
                                    while True:
                                        chunk = ar.read(65536)
                                        if not chunk:
                                            break
                                        f.write(chunk)
                            if raw_path.stat().st_size > 0:
                                import subprocess
                                converted_path = Path(tmpdir) / "audio.m4a"
                                subprocess.run(
                                    ["ffmpeg", "-i", str(raw_path), "-c", "copy", "-y", str(converted_path)],
                                    capture_output=True, text=True, timeout=120,
                                )
                                if converted_path.exists() and converted_path.stat().st_size > 0:
                                    audio_path = str(converted_path)
                                    info = {"title": view.get("title", ""), "duration": view.get("duration", 0)}
            except Exception:
                import traceback
                traceback.print_exc()

        if not audio_path:
            raise UserFacingError("音频下载失败，无法进行本地 ASR。")

        model = WhisperModel(model_size, device=os.environ.get("WHISPER_DEVICE", "cpu"))
        raw_segments, info_obj = model.transcribe(audio_path, language="zh", vad_filter=True)
        subtitle_items = [
            {"from": float(seg.start), "to": float(seg.end), "content": clean_text(seg.text)}
            for seg in raw_segments
            if clean_text(seg.text)
        ]

    if not subtitle_items:
        raise UserFacingError("ASR 没有识别到有效文本。")

    transcript = "。".join(item["content"] for item in subtitle_items[:120])
    title = requested_title or info.get("title") or f"{parsed.display_id} 视频内容笔记"
    return {
        "source": "local-asr",
        "title": title,
        "duration": format_time(int(getattr(info_obj, "duration", 0) or info.get("duration") or 0)),
        "summary": summarize_text(transcript, 220) or "已通过本地 ASR 生成时间轴报告。",
        "keywords": extract_keywords(title, transcript),
        "segments": build_segments_from_subtitles(subtitle_items),
        "videoId": parsed.display_id,
        "page": parsed.page,
    }


def demo_report(parsed: ParsedVideo, requested_title: str | None = None) -> dict[str, Any]:
    title = requested_title or f"{parsed.display_id} 视频内容笔记"
    return {
        "source": "demo",
        "title": title,
        "duration": "15:26",
        "summary": (
            "这是一份演示报告，用来展示真实识别完成后的时间轴与播客笔记形态。"
            "切换到真实识别时，后端会优先读取 Bilibili 字幕；如果视频无字幕，可以安装本地 ASR 依赖。"
        ),
        "keywords": ["主题摘要", "时间轴", "关键观点", "PDF 笔记"],
        "segments": DEMO_SEGMENTS,
        "videoId": parsed.display_id,
        "page": parsed.page,
    }


def build_segments_from_subtitles(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    start_time = 0.0
    last_to = 0.0
    char_count = 0

    for item in items:
        if not current:
            current = [item]
            start_time = item["from"]
            last_to = item["to"]
            char_count = len(item["content"])
            continue

        gap = item["from"] - last_to
        span = item["to"] - start_time
        if gap > 7 or span > 150 or char_count > 520:
            groups.append(current)
            current = [item]
            start_time = item["from"]
            char_count = len(item["content"])
        else:
            current.append(item)
            char_count += len(item["content"])
        last_to = item["to"]

    if current:
        groups.append(current)

    segments = []
    for index, group in enumerate(groups, start=1):
        text = clean_text("。".join(part["content"] for part in group))
        title = make_segment_title(text, index)
        segments.append(
            {
                "start": format_time(group[0]["from"]),
                "end": format_time(group[-1]["to"]),
                "title": title,
                "summary": summarize_text(text, 180) or "这一段主要围绕当前主题继续展开。",
                "highlights": make_highlights(text),
            }
        )
    return segments


def make_segment_title(text: str, index: int) -> str:
    chunks = re.split(r"[。！？!?；;，,\s]+", text)
    for chunk in chunks:
        chunk = clean_text(chunk)
        if len(chunk) >= 6:
            return truncate(chunk, 18)
    return f"片段 {index}"


def make_highlights(text: str) -> list[str]:
    parts = [clean_text(part) for part in re.split(r"[。！？!?；;]", text)]
    highlights = []
    for part in parts:
        if 8 <= len(part) <= 80 and part not in highlights:
            highlights.append(part)
        if len(highlights) == 3:
            break
    if highlights:
        return highlights
    compact = truncate(text, 60)
    return [compact] if compact else []


def summarize_text(text: str, limit: int) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    sentences = [clean_text(item) for item in re.split(r"[。！？!?]", text) if clean_text(item)]
    summary = ""
    for sentence in sentences:
        next_text = f"{summary}{sentence}。"
        if len(next_text) > limit:
            break
        summary = next_text
    return summary or truncate(text, limit)


def extract_keywords(title: str, transcript: str) -> list[str]:
    candidates = []
    for text in [title, transcript[:600]]:
        for item in re.split(r"[\s，。！？、,.!?:：；;（）()【】\[\]《》<>\"']+", text):
            item = clean_text(item)
            if 2 <= len(item) <= 10 and item not in candidates:
                candidates.append(item)
            if len(candidates) >= 6:
                break
        if len(candidates) >= 6:
            break
    fallback = ["字幕识别", "时间轴", "视频摘要"]
    for item in fallback:
        if item not in candidates:
            candidates.append(item)
    return candidates[:8]


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def truncate(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def format_time(seconds: float | int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def generate_pdf(report: dict[str, Any]) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise UserFacingError("缺少 PDF 依赖 reportlab，请先安装 requirements.txt。") from exc

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    except Exception:
        pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=report.get("title") or "BiliCast Report",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=22,
        leading=30,
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "ChineseH2",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=20,
        textColor=colors.HexColor("#0A4A40"),
        spaceBefore=8,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=18,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "ChineseSmall",
        parent=body_style,
        fontSize=9.5,
        leading=16,
        textColor=colors.HexColor("#475467"),
    )

    story: list[Any] = [
        Paragraph(escape_pdf_text(report.get("title") or "BiliCast Studio Report"), title_style),
        Paragraph(escape_pdf_text(report.get("summary") or ""), body_style),
    ]
    keywords = report.get("keywords") or []
    if keywords:
        story.append(Paragraph("关键词：" + escape_pdf_text("、".join(map(str, keywords))), small_style))
    story.append(Spacer(1, 8))

    for segment in report.get("segments") or []:
        time_label = f"{segment.get('start', '')} - {segment.get('end', '')}".strip(" -")
        heading = f"{time_label}  {segment.get('title', '')}"
        story.append(Paragraph(escape_pdf_text(heading), h2_style))
        story.append(Paragraph(escape_pdf_text(segment.get("summary") or ""), body_style))
        rows = []
        for item in segment.get("highlights") or []:
            rows.append([Paragraph("• " + escape_pdf_text(str(item)), small_style)])
        if rows:
            table = Table(rows, colWidths=[170 * mm])
            table.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            story.append(table)
        story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


def escape_pdf_text(value: Any) -> str:
    return html.escape(str(value), quote=False).replace("\n", "<br/>")


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="BiliCast Studio Python website")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    os.chdir(ROOT)
    class Handler(http.server.SimpleHTTPRequestHandler):
        server_version = "BiliCastPython/1.0"

        def translate_path(self, path: str) -> str:
            parsed = urllib.parse.urlparse(path)
            clean_path = parsed.path.strip("/")
            if not clean_path:
                clean_path = "index.html"
            target = (ROOT / clean_path).resolve()
            if ROOT not in target.parents and target != ROOT:
                return str(ROOT / "index.html")
            return str(target)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self.send_json({"error": "接口只支持 POST。"}, status=405)
                return
            return super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            try:
                parsed_path = urllib.parse.urlparse(self.path).path
                if parsed_path == "/api/analyze":
                    self.handle_analyze()
                elif parsed_path == "/api/report.pdf":
                    self.handle_report_pdf()
                else:
                    self.send_json({"error": "接口不存在。"}, status=404)
            except UserFacingError as exc:
                self.send_json({"error": str(exc)}, status=400)
            except Exception:
                traceback.print_exc()
                self.send_json({"error": "服务器内部错误，请查看终端日志。"}, status=500)

        def handle_analyze(self) -> None:
            payload = self.read_json()
            url = str(payload.get("url") or "").strip()
            page = payload.get("page")
            requested_title = str(payload.get("reportTitle") or "").strip() or None
            mode = str(payload.get("mode") or "subtitle").lower()
            if not url:
                raise UserFacingError("请先提交 Bilibili 视频链接。")

            parsed = parse_bilibili_url(url, int(page) if page else None)
            if mode == "demo":
                report = demo_report(parsed, requested_title)
            elif mode == "asr":
                report = analyze_with_optional_local_asr(parsed, url, requested_title)
            else:
                report = analyze_with_bilibili_subtitle(parsed, requested_title)
            self.send_json(report)

        def handle_report_pdf(self) -> None:
            payload = self.read_json(max_bytes=2_000_000)
            report = payload.get("report") or payload
            if not isinstance(report, dict):
                raise UserFacingError("PDF 接口需要 report JSON。")
            pdf_bytes = generate_pdf(report)
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Content-Disposition", 'attachment; filename="bilicast-report.pdf"')
            self.end_headers()
            self.wfile.write(pdf_bytes)

        def read_json(self, max_bytes: int = 200_000) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                return {}
            if length > max_bytes:
                raise UserFacingError("请求体太大。")
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise UserFacingError("请求 JSON 格式不正确。") from exc
            if not isinstance(data, dict):
                raise UserFacingError("请求 JSON 必须是对象。")
            return data

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def guess_type(self, path: str) -> str:
            if path.endswith(".js"):
                return "application/javascript; charset=utf-8"
            if path.endswith(".css"):
                return "text/css; charset=utf-8"
            if path.endswith(".html"):
                return "text/html; charset=utf-8"
            return mimetypes.guess_type(path)[0] or "application/octet-stream"

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"BiliCast Studio running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
