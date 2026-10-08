# Video2Report Skill

[English](README.md) | 简体中文

把公开 Bilibili 或抖音视频整理成可回查原文位置的自包含 HTML 阅读报告。

本仓库是一个“Skill + 确定性处理脚本”工具包：Python 只处理视频下载、音频提取和转写；调用 Skill 的当前 Coding Agent 负责完整阅读 `transcript.md`，并按报告规则直接生成 `report.html`。不会再启动第二个 Agent。

## 工作流

```text
视频链接
  → 下载视频/音频
  → FFmpeg 提取 16 kHz 单声道音频
  → ASR 生成带时间戳 transcript.md
  → 当前 Agent 读取 Skill、模板和 transcript
  → 生成自包含 report.html
```

Python 命令的终态是 `TRANSCRIBED`。HTML 是当前 Agent 的交付物，不是 Python 再次调用模型生成的产物。

## 安装

需要 Python 3.12、[uv](https://docs.astral.sh/uv/)、`ffmpeg` / `ffprobe`。Windows/Linux 推荐本地 `faster-whisper`：

```powershell
git clone https://github.com/TanRay1028/Video2Report.git
cd Video2Report
uv sync --extra faster-whisper
```

Apple Silicon 可改用：

```sh
uv sync --extra mlx
```

抖音页面在纯 HTTP 请求发生挑战时会回退到 Playwright，需要时执行：

```sh
uv run playwright install chromium
```

## 使用

将整个仓库放入 Agent 可读取的 Skill 目录，保留以下目录的相对结构：

```text
src/video_report_agent/skills/video-report/
├── SKILL.md
├── modes/
├── references/
└── assets/
```

用户提供链接后，Skill 会让当前 Agent 在仓库根目录运行：

```sh
uv run video-report prepare "<URL>" --asr-backend faster-whisper --report-mode standard
```

支持的报告模式：

- `standard`：精读，默认。
- `brief`：速览，保留核心结论、条件与依据。

成功后命令会输出 run 目录信息。当前 Agent 继续在该目录读取 `input.json`、`transcript.md` 和选定模式的模板，最终写入 `report.html`。

已有完整转写时，可跳过 Python 流水线，直接把 TXT、Markdown 或 SRT 交给 Skill。

## ASR 选项

- `faster-whisper`：Windows/Linux 本地运行，默认模型 `small`。
- `mlx`：Apple Silicon 本地运行。
- `paraformer`：百炼云端转写，需 `DASHSCOPE_API_KEY`。

可在 `.env` 中设置 `ASR_BACKEND`、`ASR_MODEL`、`DASHSCOPE_API_KEY`。云端 ASR 会上传音频；本地后端不需要报告模型密钥。

## 产物与边界

`runs/<run-id>/` 会保存来源元数据、`asr.json`、规范转写、`transcript.md` 和阶段日志。公开 Bilibili 和抖音链接可用；私密视频、需登录内容和图集不保证支持。报告内容只以 transcript 为证据，没有可靠时间戳时不编造定位。

## 开发检查

```sh
uv run pytest -q
uv run ruff check src tests
uv lock --check
```

报告规则见 [`SKILL.md`](src/video_report_agent/skills/video-report/SKILL.md)，工程文档见 [docs/README.md](docs/README.md)。
