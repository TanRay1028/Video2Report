# Video2Report 当前架构

> 核对日期：2026-10-08。

## 执行流程

```text
当前 Coding Agent
  → 读取 video-report/SKILL.md
  → 调用 video-report prepare <URL>
  → Python: 链接校验/下载 → FFmpeg → ASR → transcript.md
  → 当前 Agent: 完整阅读 transcript → 选择 Profile/模式 → 编辑 HTML
  → report.html
```

Hermes Linux 入口保持同一业务流程：`skills/video-report/scripts/setup-linux.sh` 准备用户目录运行时，`prepare-video.sh` 从任意工作目录调用同一个 `video-report prepare` CLI；报告仍由当前 Hermes 会话生成，不启动嵌套 Agent。

不存在第二个 Agent 进程。Python 层不持有报告模型凭证，也不负责生成 HTML。

## 模块职责

| 模块 | 职责 |
|---|---|
| `cli.py` / `prepare.py` | CLI 参数、run 创建、终态与错误落盘 |
| `pipeline.py` | 顺序组织下载、音频提取、ASR 和转写构建 |
| `ingest.py` / `douyin_download.py` / `audio.py` | Bilibili/抖音校验与下载、16 kHz 单声道音频 |
| `asr.py` / `paraformer.py` / `faster_whisper_asr.py` | 本地或云端 ASR，输出统一 `AsrRun` |
| `transcript.py` / `transcript_foundation.py` | 来源事件、规范单元、可选字幕/OCR 融合 |
| `reuse.py` / `retention.py` | 兼容产物复用与媒体保留策略 |
| `trace.py` | 确定性媒体阶段的 `run.trace.jsonl` |
| `src/video_report_agent/skills/video-report/` | Codex/通用版本的内容组织、来源约束、阅读模式和 HTML 模板 |
| 仓库根目录 `skills/video-report/` | Hermes Linux 可安装包；携带同版报告规则、模板和运行时包装脚本 |
| `inspect_report.py` / `report_image.py` | 可选的确定性页面检查和长图导出，不调用模型 |

## 任务数据

`create_run` 保存规范来源 URL、视频 ID、ASR 配置、转写模式和报告模式。`prepare(run)` 产生 `source.info.json`、`asr.json`、`canonical-transcript.jsonl`、`transcript-manifest.json` 和 `transcript.md`，成功时写入 `TRANSCRIBED`。

当前 Agent 使用 `input.json` 中的来源信息和 `report_mode`，并以 `transcript.md` 为报告正文的唯一内容证据。`data-source-units` 用于回查来源，不是自动质量证明。

## 完成边界

Python 成功标准是 `status.json.state == "TRANSCRIBED"` 且 `transcript.md` 存在。报告完成由当前 Agent 确认 `report.html` 存在、自包含、无未解析占位符，并按可用工具完成静态或浏览器检查。
