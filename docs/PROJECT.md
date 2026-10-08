# Video2Report 当前状态

> 2026-10-08 按当前代码核对。

## 目标与边界

将公开 Bilibili 或抖音视频转成带时间戳的完整转写，再由调用 `video-report` Skill 的当前 Coding Agent 生成自包含 HTML 阅读报告。

仓库只维护媒体下载、音频提取、ASR、规范转写、复用/清理、Skill、模板和可选页面检查工具。模型对转写的理解、报告写作与 HTML 编辑都由当前 Agent 完成，不启动嵌套 Agent。

## 当前能力

- `video-report prepare <URL>` 完成下载、FFmpeg 提音频、ASR 和 `transcript.md`，终态为 `TRANSCRIBED`。
- 支持 Bilibili 与抖音公开链接，包含抖音 `modal_id` 页面和短链解析后的标准视频页。
- ASR 后端包括 Apple Silicon MLX Whisper、百炼 Paraformer/Fun-ASR 和 Windows/Linux 本地 `faster-whisper`。
- Standard 用于精读，Brief 用于速览；两者都读完整转写，使用独立规则和模板。
- 可按兼容条件复用下载、ASR 或完整转写；运行工件统一使用 UTF-8。
- 已有转写时可跳过脚本，直接向 Skill 提供 Markdown、TXT、SRT 或 JSONL。

## 已知限制

- Python 只保证到 `TRANSCRIBED`；`report.html` 是当前 Agent 的交付物，其质量取决于转写、模型和可用工具。
- 流水线不支持任意网站、私密视频或无音频图集。
- 云端 ASR 可能在本地停止后继续执行并产生费用。
- 来源 ID、时间戳和页面可渲染都不能单独证明语义忠实，仍需按转写核对关键数字、条件和归属。

## 文档入口

[使用与安装](../README.zh-CN.md) · [架构](ARCHITECTURE.md) · [当前计划](PLAN.md) · [设计决策](DECISIONS.md) · [报告设计偏好](report-design-preferences.md)
