const form = document.querySelector("#video-form");
const videoUrlInput = document.querySelector("#video-url");
const analysisModeInput = document.querySelector("#analysis-mode");
const apiEndpointInput = document.querySelector("#api-endpoint");
const reportTitleInput = document.querySelector("#report-title-input");
const resetButton = document.querySelector("#reset-button");
const statusText = document.querySelector("#status-text");
const progressBar = document.querySelector("#progress-bar");
const videoFrame = document.querySelector("#video-frame");
const openBilibili = document.querySelector("#open-bilibili");
const metaVideoId = document.querySelector("#meta-video-id");
const metaPage = document.querySelector("#meta-page");
const metaSegments = document.querySelector("#meta-segments");
const sourceBadge = document.querySelector("#source-badge");
const reportTitle = document.querySelector("#report-title");
const reportSummary = document.querySelector("#report-summary");
const keywordList = document.querySelector("#keyword-list");
const timelineList = document.querySelector("#timeline-list");
const printButton = document.querySelector("#print-button");
const copyReportButton = document.querySelector("#copy-report-button");
const printTitle = document.querySelector("#print-title");
const printSummary = document.querySelector("#print-summary");
const printKeywords = document.querySelector("#print-keywords");
const printTimeline = document.querySelector("#print-timeline");
const steps = [...document.querySelectorAll(".pipeline-step")];

let currentReport = null;

const demoSegments = [
  {
    start: "00:00",
    end: "01:18",
    title: "开场与主题定位",
    summary: "视频先交代本期主题、适用对象和观看背景，把后面要解决的问题铺出来。",
    highlights: ["说明视频讨论范围", "提示观众可以重点关注后续案例"]
  },
  {
    start: "01:18",
    end: "04:36",
    title: "核心概念拆解",
    summary: "这一段把主题拆成几个基础概念，用更容易理解的表达解释每个概念之间的关系。",
    highlights: ["定义关键术语", "指出常见误区", "建立后续分析框架"]
  },
  {
    start: "04:36",
    end: "08:52",
    title: "案例与细节展开",
    summary: "视频进入具体例子，围绕案例背景、过程变化和结果差异进行说明。",
    highlights: ["用案例验证前面的概念", "强调时间线变化", "对比不同选择的影响"]
  },
  {
    start: "08:52",
    end: "12:40",
    title: "方法论总结",
    summary: "讲解者把前面的内容收束成可复用的方法，给出判断顺序和执行步骤。",
    highlights: ["整理判断标准", "给出操作步骤", "说明适用边界"]
  },
  {
    start: "12:40",
    end: "15:26",
    title: "结论与延伸",
    summary: "最后回到视频主线，总结关键结论，并补充后续可以继续关注的问题。",
    highlights: ["提炼最终观点", "留下延伸问题", "提醒观众复盘重点章节"]
  }
];

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = videoUrlInput.value.trim();
  const parsed = parseBilibiliUrl(url);

  if (!parsed) {
    setStatus("没有识别到 BV 或 av 编号，请提交完整 B 站视频链接", 0);
    markStep("parse");
    videoUrlInput.focus();
    return;
  }

  embedVideo(parsed, url);
  markStep("watch");
  setStatus("播放器已载入，正在生成内容报告", 36);

  try {
    const report = await analyzeWithApi(parsed, url);
    renderReport(report);
    currentReport = report;
    setStatus(report.source === "demo" ? "演示报告已生成" : "识别报告已生成", 100);
    markStep("export");
  } catch (error) {
    setStatus(error.message || "识别接口返回异常", 48);
    markStep("analyze");
  }
});

resetButton.addEventListener("click", () => {
  form.reset();
  apiEndpointInput.value = "/api/analyze";
  currentReport = null;
  videoFrame.innerHTML = `
    <div class="empty-player">
      <span class="play-mark">▶</span>
      <strong>提交 BV 或 av 链接后显示播放器</strong>
    </div>
  `;
  openBilibili.href = "#";
  openBilibili.setAttribute("aria-disabled", "true");
  metaVideoId.textContent = "-";
  metaPage.textContent = "-";
  metaSegments.textContent = "0";
  sourceBadge.textContent = "未生成";
  reportTitle.textContent = "等待分析";
  reportSummary.textContent = "报告生成后会在这里显示视频主题摘要。";
  keywordList.innerHTML = "";
  timelineList.innerHTML = `
    <article class="timeline-empty">
      <span>00:00</span>
      <div>
        <strong>还没有时间轴内容</strong>
        <p>提交视频链接后会生成按时间段整理的讲解内容。</p>
      </div>
    </article>
  `;
  syncPrintReport(null);
  markStep("parse");
  setStatus("等待提交视频链接", 0);
});

printButton.addEventListener("click", () => {
  if (!currentReport) {
    setStatus("先生成报告，再下载 PDF", 0);
    return;
  }
  downloadPdf(currentReport);
});

copyReportButton.addEventListener("click", async () => {
  if (!currentReport) {
    setStatus("先生成报告，再复制 Markdown", 0);
    return;
  }

  const markdown = reportToMarkdown(currentReport);
  try {
    await navigator.clipboard.writeText(markdown);
    setStatus("Markdown 已复制到剪贴板", 100);
  } catch {
    setStatus("当前浏览器不允许写入剪贴板", 100);
  }
});

function parseBilibiliUrl(url) {
  const bvidMatch = url.match(/BV[0-9A-Za-z]{10}/);
  const avidMatch = url.match(/(?:\/video\/av|[?&]aid=|^av)(\d+)/i);
  const pageMatch = url.match(/[?&]p=(\d+)/i);

  if (bvidMatch) {
    return {
      type: "bvid",
      id: bvidMatch[0],
      page: pageMatch ? Number(pageMatch[1]) : 1
    };
  }

  if (avidMatch) {
    return {
      type: "aid",
      id: avidMatch[1],
      page: pageMatch ? Number(pageMatch[1]) : 1
    };
  }

  return null;
}

function embedVideo(parsed, originalUrl) {
  const query =
    parsed.type === "bvid"
      ? `bvid=${encodeURIComponent(parsed.id)}`
      : `aid=${encodeURIComponent(parsed.id)}`;
  const src = `https://player.bilibili.com/player.html?${query}&page=${parsed.page}&autoplay=0&danmaku=0&high_quality=1`;

  videoFrame.innerHTML = `<iframe src="${src}" title="Bilibili 视频播放器" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>`;
  openBilibili.href = originalUrl;
  openBilibili.setAttribute("aria-disabled", "false");
  metaVideoId.textContent = parsed.type === "bvid" ? parsed.id : `av${parsed.id}`;
  metaPage.textContent = String(parsed.page);
  metaSegments.textContent = "0";
  markStep("watch");
}

async function analyzeWithApi(parsed, url) {
  const endpoint = apiEndpointInput.value.trim() || "/api/analyze";
  setStatus("正在请求 Python 后端识别接口", 58);
  markStep("analyze");

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      url,
      videoId: parsed.id,
      idType: parsed.type,
      page: parsed.page,
      mode: analysisModeInput.value,
      reportTitle: reportTitleInput.value.trim()
    })
  });

  if (!response.ok) {
    let message = `识别接口返回 ${response.status}`;
    try {
      const errorPayload = await response.json();
      message = errorPayload.error || message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  const data = await response.json();
  const normalized = normalizeReport(data, parsed, "api");
  if (!normalized.segments.length) {
    throw new Error("识别接口没有返回时间段内容");
  }
  return normalized;
}

async function analyzeWithDemo(parsed) {
  setStatus("正在整理演示时间轴", 70);
  markStep("analyze");
  await wait(520);

  const title = reportTitleInput.value.trim() || `${parsed.type === "bvid" ? parsed.id : `av${parsed.id}`} 视频内容笔记`;
  return normalizeReport(
    {
      title,
      duration: "15:26",
      summary:
        "这是一份前端演示报告，用于展示视频被识别后应呈现的播客式时间轴结构。接入真实 ASR 后端后，这里会显示从视频音频和字幕中提取出的真实摘要。",
      keywords: ["主题摘要", "时间轴", "关键观点", "PDF 笔记"],
      segments: demoSegments
    },
    parsed,
    "demo"
  );
}

function normalizeReport(data, parsed, source) {
  const title =
    reportTitleInput.value.trim() ||
    data.title ||
    `${parsed.type === "bvid" ? parsed.id : `av${parsed.id}`} 视频内容笔记`;

  return {
    source,
    title,
    videoId: parsed.type === "bvid" ? parsed.id : `av${parsed.id}`,
    page: parsed.page,
    duration: data.duration || "",
    summary: data.summary || "暂无摘要。",
    keywords: Array.isArray(data.keywords) ? data.keywords.slice(0, 8) : [],
    segments: Array.isArray(data.segments)
      ? data.segments.map((segment, index) => ({
          start: segment.start || "00:00",
          end: segment.end || "",
          title: segment.title || `片段 ${index + 1}`,
          summary: segment.summary || "",
          highlights: Array.isArray(segment.highlights) ? segment.highlights : []
        }))
      : []
  };
}

function renderReport(report) {
  const sourceNames = {
    "bilibili-subtitle": "B站字幕",
    "local-asr": "本地ASR",
    demo: "演示模式",
    api: "真实识别"
  };
  sourceBadge.textContent = sourceNames[report.source] || "识别报告";
  reportTitle.textContent = report.title;
  reportSummary.textContent = report.summary;
  metaSegments.textContent = String(report.segments.length);

  keywordList.innerHTML = report.keywords.map((keyword) => `<span>${escapeHtml(keyword)}</span>`).join("");

  timelineList.innerHTML = report.segments
    .map(
      (segment) => `
        <article class="timeline-item">
          <time>${escapeHtml(segment.start)}${segment.end ? ` - ${escapeHtml(segment.end)}` : ""}</time>
          <div>
            <strong>${escapeHtml(segment.title)}</strong>
            <p>${escapeHtml(segment.summary)}</p>
            ${
              segment.highlights.length
                ? `<ul>${segment.highlights.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
                : ""
            }
          </div>
        </article>
      `
    )
    .join("");

  syncPrintReport(report);
}

async function downloadPdf(report) {
  setStatus("正在生成 PDF 文件", 100);
  try {
    const response = await fetch("/api/report.pdf", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ report })
    });

    if (!response.ok) {
      let message = `PDF 接口返回 ${response.status}`;
      try {
        const errorPayload = await response.json();
        message = errorPayload.error || message;
      } catch {
        // Keep the status-based message.
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${sanitizeFilename(report.title || "bilicast-report")}.pdf`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setStatus("PDF 已生成并开始下载", 100);
  } catch (error) {
    setStatus(error.message || "PDF 生成失败", 100);
  }
}

function syncPrintReport(report) {
  if (!report) {
    printTitle.textContent = "BiliCast Studio Report";
    printSummary.textContent = "";
    printKeywords.textContent = "";
    printTimeline.innerHTML = "";
    return;
  }

  printTitle.textContent = report.title;
  printSummary.textContent = report.summary;
  printKeywords.textContent = report.keywords.length ? `关键词：${report.keywords.join("、")}` : "";
  printTimeline.innerHTML = report.segments
    .map(
      (segment) => `
        <article class="print-segment">
          <h2>${escapeHtml(segment.start)}${segment.end ? ` - ${escapeHtml(segment.end)}` : ""} ${escapeHtml(segment.title)}</h2>
          <p>${escapeHtml(segment.summary)}</p>
          ${
            segment.highlights.length
              ? `<ul>${segment.highlights.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
              : ""
          }
        </article>
      `
    )
    .join("");
}

function reportToMarkdown(report) {
  const lines = [`# ${report.title}`, "", report.summary, ""];
  if (report.keywords.length) {
    lines.push(`关键词：${report.keywords.join("、")}`, "");
  }

  for (const segment of report.segments) {
    lines.push(`## ${segment.start}${segment.end ? ` - ${segment.end}` : ""} ${segment.title}`);
    lines.push(segment.summary);
    for (const item of segment.highlights) {
      lines.push(`- ${item}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}

function markStep(activeName) {
  const order = ["parse", "watch", "analyze", "export"];
  const activeIndex = order.indexOf(activeName);

  steps.forEach((step) => {
    const stepName = step.dataset.step;
    const stepIndex = order.indexOf(stepName);
    step.classList.toggle("is-active", stepName === activeName);
    step.classList.toggle("is-done", activeIndex > stepIndex);
  });
}

function setStatus(message, progress) {
  statusText.textContent = message;
  progressBar.style.width = `${Math.max(0, Math.min(100, progress))}%`;
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sanitizeFilename(value) {
  return String(value)
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
}
