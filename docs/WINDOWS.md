# Windows 本地使用说明（prepare + faster-whisper）

本文说明在 Windows 上不使用 Pi Agent、不调用付费 ASR API，完成
`Bilibili 链接 → 下载 → 本地 ASR → transcript.md` 的最小路径，
以及如何把转写交给 Coding Agent（如 DeepSeek Harness）生成 HTML 精读报告。

`generate`（Pi 流程）在 Windows 上仍视为未验证能力；`prepare` 是已验证路径。

## 1. 环境要求

- Python 3.12（`uv` 可自动安装：`uv python install 3.12`）
- [uv](https://docs.astral.sh/uv/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) 在 `PATH` 中，例如 `uv tool install yt-dlp`
- [ffmpeg](https://ffmpeg.org/) 在 `PATH` 中（`ffmpeg` 与 `ffprobe`），例如
  `winget install Gyan.FFmpeg`

## 2. 安装

```sh
uv sync --extra faster-whisper
```

`faster-whisper` 本地转写，无需 `DASHSCOPE_API_KEY`、`PI_API_KEY` 或 Node.js/Pi。

## 3. 运行 prepare

```sh
uv run video-report prepare 'https://www.bilibili.com/video/BV...' --asr-backend faster-whisper
```

`prepare` 依次完成：链接验证 → yt-dlp 下载（audio-only）→ ffmpeg 提取
16 kHz 单声道 WAV → faster-whisper 中文转写 → 生成 `asr.json` 与
`transcript.md`。成功时退出码为 0，`status.json` 的 `state` 为
`TRANSCRIBED`。全程不启动 Pi、不生成 `report.html`、不截图。

产物在 `runs/<run-id>/`：

- `input.json` / `status.json`：任务快照与状态
- `asr.json`：带毫秒时间戳的原始转写（faster-whisper 原始结果保留在 `raw_result`）
- `transcript.md`：`[unit-XXXXXX | 开始–结束s] 文本` 形式的规范转写

同一视频再次 `prepare` 会自动复用已有下载与转写，不会重复请求。

### 支持的平台与抖音说明

- **Bilibili**：yt-dlp 直接下载，匿名即可，无需登录。
- **抖音（douyin.com）**：yt-dlp 的抖音网页接口被平台封锁（HTTP 403），`prepare`
  对抖音来源自动改用内置的 iesdouyin 播放端点下载器（思路同开源项目 DouyinGo）：
  安卓 UA 抓页面里的 `play_addr` uri，再从无签名的
  `iesdouyin.com/aweme/v1/play` 端点拉流。若页面返回 JS 反爬挑战壳，自动
  回退到本机 Playwright 无头 Chromium 渲染后再提取（Chromium 由项目自带
  playwright 依赖提供）。支持 `/video/<id>` 和带 `modal_id` 的分享页（精选、
  收藏页等）；图集作品会明确报错（无音频）。通常不需要 Cookie；可选
  `--cookies cookies.txt` 或 `--cookies-from-browser chrome|edge` 透传给
  yt-dlp（B 站一般用不到）。

```sh
uv run video-report prepare 'https://www.douyin.com/video/<id>' --asr-backend faster-whisper
```

## 4. 模型选择

`--asr-model` 可指定 faster-whisper 模型（默认 `small`）：

| 模型 | 磁盘 | 中文效果 | 适用 |
|---|---|---|---|
| `small`（默认） | ~460 MB | 良好 | 日常视频、CPU 可接受 |
| `medium` | ~1.5 GB | 更好 | 对准确度要求高 |
| `large-v3-turbo` | ~1.6 GB | 最好 | 质量优先 |

也可传 `Systran/faster-whisper-*` 仓库名或本地模型目录。首次运行会从 Hugging Face
下载所选模型（`small` 约 460 MB）。默认使用 CPU + `int8` 量化，保证无 GPU 环境
可用；如要在 NVIDIA GPU 上运行，可修改 `FasterWhisperBackend(device="cuda",
compute_type="float16")`。依赖中固定 `av>=12,<14`，因为 PyAV 14+ 移除了
faster-whisper 1.2.x 依赖的 `metadata_errors` 参数。

## 5. 交给 Coding Agent 生成报告

把项目中的 `src/video_report_agent/skills/video-report/` 目录放入 Agent 的
skill 目录（DeepSeek Harness：会话工作区的 `.dsh/skills/video-report/`，保留
`SKILL.md`、`modes/`、`references/`、`assets/` 的相对结构），然后向 Agent
提供 Bilibili 链接即可。Agent 会先运行 `prepare`，确认 `TRANSCRIBED` 后读取
`transcript.md` 并按 Skill 规则生成自包含的 `report.html`；也可以直接手动
运行 `prepare` 后，把 `transcript.md` 交给 Agent 并指明使用 video-report Skill。

## 6. 与原有路径的关系

- `generate`、`compare-asr` 命令与 `mlx`（Apple Silicon）、`paraformer`
  （DashScope 云端）后端保持不变；`prepare` 复用同一套下载、音频处理、
  转写规范化与复用逻辑，只是停在 `TRANSCRIBED`，不进入 Pi 阶段。
- Windows 默认区域编码不是 UTF-8；本项目的运行工件（`transcript.md`、
  `asr.json` 等）统一以 UTF-8 读写，请勿用非 UTF-8 编辑器改动后放回。
