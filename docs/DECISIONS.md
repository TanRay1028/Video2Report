# Core 重要设计决策

> 2026-09-24 从本仓库 Git、现有规则和源码回填。日期为相关提交或已有记录日期，不冒充原始会议日期。明确记录的理由按原意保留；“工程解释”是本次依据实现的分析，不声称为当时动机。以下均为已实现或已采纳，验证边界另述。

## 2026-09-14：公开核心与托管服务分离

决定：Core 只维护媒体、转写、Pi、Skill、渲染与 CLI，托管能力由调用方负责；产品 Skill 只有一个维护来源。依据：`124b715`、[AGENTS.md](../AGENTS.md)。边界目的在规则中明确：避免私有逻辑进入公开包及核心规则重复维护。代价：集成方需匹配核心版本，不能把某一仓库提交视为整个产品已发布。

## 已有基线，2026-09-24 确认：顺序 Python 管线与 Pi 单 Agent

决定：确定性前后处理由 Python 完成，Pi 拥有模型/工具循环；不另加 planner、critic 或多 Agent 层。依据：[AGENTS.md](../AGENTS.md)、[pi.py](../src/video_report_agent/pi.py)、[pipeline.py](../src/video_report_agent/pipeline.py)。工程解释：任务输入与交付目标明确，复用现有 Runtime 可避免重复实现循环；代价是依赖 Pi 协议及生命周期。原始决策日期未单独确认。

完成以 `agent_settled`、最终正常停止及 HTML 交付条件为准。源码明确指出 `agent_end` 后仍可能重试或压缩。程序检查与语义质量分开，默认不开额外 review；并未承诺自动修复或自动验收。

## 2026-09-27：调用方可显式启用同会话的有限模型恢复

决定：只有任务输入提供 `model_recovery` 时，PiRunner 才在任务级配置中关闭 Pi 的 Agent/Provider 自动重试，并在同一 Pi 进程与 session 中按策略续试或切模型；逐次请求写入 `model-attempts.jsonl`，不保存新请求正文，也不改共享 Pi 配置。未提供策略的 CLI/Local 路径维持原行为。恢复不改变 `agent_settled`、最终 `stopReason == "stop"` 与完整 HTML 检查等完成条件，总时限沿用调用方 deadline。依据：[pi.py](../src/video_report_agent/pi.py)、[execution.py](../src/video_report_agent/execution.py)。代价：调用方需提供精确备用 provider/model 与恢复预算；进程重启恢复仍由 Service 生命周期策略决定。

## 2026-09-15：阶段日志与 Agent 事件分层

决定：`run.trace.jsonl` 记录管线，`pi.events.jsonl` 保存模型与工具细节。依据：`f8274ec` 与现行 AGENTS。工程解释：阶段耗时和 Agent 行为需要不同粒度；代价是分析时需要关联两份日志，客户端时间不能证明供应商内部排队或推理时间。

## 2026-09-27：DeepSeek V4.1 Flash 费用窗口沿用供应商时钟边界

决定：QwenAI DeepSeek V4.1 Flash 的人民币估算使用北京时间 08:00–22:00 忙时、其余时间闲时；不再把工作日、法定节假日和既有本地费率时段混入计算。依据：[usage.py](../src/video_report_agent/usage.py) 与[百炼价目表](https://help.aliyun.com/zh/model-studio/model-pricing)，页面给出忙闲时钟窗口但没有列日历例外。Service 的 Public 路由复用同一时段函数。代价：金额仍是 token 用量估算，不代表账号账单；价目或供应商规则变化后需重新核对并同步路由与估算。

## 2026-09-17：长音频按静音边界分两段

决定：至少 60 分钟的云端 ASR 音频，在中点前后 30 秒内寻找至少 250 ms 静音，合适时切成连续、不重叠两段并行识别，合并时恢复句/词时间；否则整段请求。依据：`da588e8`、[README](../README.md)。工程解释：控制并发为两路并利用停顿切分；代价是一个报告任务可能同时占用两个云请求，不能据实现宣称固定提速倍数。

## 2026-09-18：Standard 与 Brief 各有规则和模板

决定：任务保存模式，两种模式都读完整转写，只提供所选模式资产；不同报告可复用转写，不先生成 Standard 再压缩。依据：`690e95a`、[CONTEXT](../CONTEXT.md)。已有定义明确区分理解/查阅与快速判断的阅读用途。代价：两套模板需分别验证，不能把一个模式的局部设计无条件推广到另一个。

## 2026-09-19～23：报告设计按已选方案落地，保持模式边界

决定与明确用户理由保留在 [设计偏好](report-design-preferences.md)，本页只作索引，避免双份细则：

- `d337515`、`41a7df8`：Brief 短标签优先完整展示；Standard 采用浅蓝表头与白底正文。长说明会增高，窄屏可能需局部横向滚动。
- `28dca51` → `6ec2135`：Standard 左侧页外导航后改为书签卡片，替代旧轻量外观；仍保留纸面空间与正常长图宽度，窄屏和长图隐藏导航，不显示进度条。
- `892f275`：精确图示关系先计算，无法核实则简化或换表达；用户要求改善弱模型稳定性，不逐学科新增绘图框架或默认视觉反馈循环。规则落地不证明真实生成效果提升。

这些规则只影响后续相应模式生成，不自动重写历史报告。用户已明确选定方案即授权采纳，但不包含提交、推送或部署。

## 2026-09-21～23：费用估算可缓存，不能替代账单

决定：完成的 assistant 消息去重聚合，人民币估算与 Pi 美元估算分列；LLM 聚合持久缓存，ASR 元数据有界缓存但金额按当前费率重算。依据：`993ffc4`、`428f4fe`、[usage.py](../src/video_report_agent/usage.py) 的注释与实现。代码明确不改写 Pi 原生美元值；缓存用于减少重复日志/ASR 文件读取。代价：费率需维护、未知调用不能当免费、历史估算可随配置变化；独立 ASR 复用的计费缺口保留在 [PLAN](PLAN.md)。

## 2026-09-25：默认精简 Agent 事件并保留请求延迟

为降低流式碎片与重复快照造成的磁盘占用，默认保存调用级完成记录、工具详情和费用字段，完整 RPC 流改为显式调试选项并保留 7 天。代价是默认无法逐 token 回放或查看被中断调用的全部中间内容。请求首响由 Pi 请求前钩子和首个非空内容片段计时，不能用 message_start 补算旧记录。历史日志不迁移、不删除；保持原有完成判定和费用统计来源。

## 2026-11-24：prepare 停在 TRANSCRIBED，faster-whisper 作为 Windows 本地后端

决定：`generate` 的前半段（下载 → 音频 → ASR → 规范转写）提取为 `_prepare_transcript` 供 `generate` 与新命令 `prepare` 共用；`prepare` 在同一 `runs/<run-id>/` 产物下以 `TRANSCRIBED` 结束，不启动 Pi、不渲染报告、不需要 Pi/云端凭证。新增本地 `faster-whisper` ASR 后端（默认模型 `small`），与 `mlx`、`paraformer` 并列，输出沿用同一 `AsrRun`/`asr.json` 契约。依据：[pipeline.py](../src/video_report_agent/pipeline.py)、[prepare.py](../src/video_report_agent/prepare.py)、[faster_whisper_asr.py](../src/video_report_agent/faster_whisper_asr.py)、[WINDOWS.md](WINDOWS.md)。原因：Windows 上完整 Pi 流水线未验证，而 Coding Agent 自行生成报告只需要可靠转写；代价：模型从 Hugging Face 首次下载，CPU 速度受硬件限制，报告质量取决于接管的 Coding Agent。运行工件读写统一为 UTF-8，修正了 Windows 非 UTF-8 区域编码下的转写复用失败。`prepare` 的终态 `TRANSCRIBED` 同时纳入媒体保留（`MEDIA_KEEP_LAST` / `MEDIA_MAX_AGE_DAYS`）的终态集合，转写文本与 `asr.json` 不受影响。

## 2026-10-02：链接入口扩展到抖音，抖音下载绕过 yt-dlp

决定：`ingest` 新增 `validate_source_url` 统一校验 Bilibili / 抖音（`/video/<id>` 与 `modal_id` 分享页，归一化为 `douyin-<id>` 的 `video_id`）；抖音来源不调用 yt-dlp——其网页详情接口已被平台全面封锁（匿名、登录 Cookie、TLS 指纹模拟均返回 HTTP 403），改由 [douyin_download.py](../src/video_report_agent/douyin_download.py) 用安卓 UA 抓取页面内嵌的 `play_addr` uri，从无需签名的 `iesdouyin.com/aweme/v1/play` 端点拉流（方法参考开源项目 DouyinGo）；页面为 JS 反爬挑战壳时自动回退 Playwright 无头 Chromium 渲染。`--cookies` / `--cookies-from-browser` 参数作为可选透传保留。原因：抖音风控只封网页 API、不封播放端点，且页面对纯 HTTP 客户端返回 JS 挑战；代价：抖音路径依赖移动端页面结构（抖音改版需跟进），Playwright 回退首次启动较慢，图集作品无法处理。
