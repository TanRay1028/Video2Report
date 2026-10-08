# 重要设计决策

## 2026-10-08：当前 Agent 直接执行 Skill

决定：Python 只执行视频下载、音频提取、ASR 和转写规范化；调用 `video-report` Skill 的当前 Coding Agent 直接读取 `transcript.md` 并生成 `report.html`。不再包含或启动额外的 Agent RPC/runtime。

原因：Skill 本身已经定义了理解、编辑、模板选择和交付规则；嵌套 Agent 会引入第二套模型配置、会话、重试和日志语义，与直接打包给 Agent 的目标重复。

代价：Python CLI 的成功终态仅为 `TRANSCRIBED`；HTML 是当前 Agent 的交付，不由 Python 状态机标记为渲染完成。旧的嵌套 Agent 执行、日志、费用估算和专用测试已删除。

## 2026-10-02：抖音下载使用独立播放端点

`ingest` 统一校验 Bilibili/抖音 URL。抖音路径优先从页面提取 `play_addr` 并请求 `iesdouyin.com/aweme/v1/play`；遇到 JS 挑战时使用 Playwright 渲染。该路径依赖抖音页面结构，平台改版后需要跟进。

## 2026-09-17：长音频按静音边界分两段

至少 60 分钟的云端 ASR 音频在中点附近寻找合适静音，命中时并行转写两个连续不重叠片段，并恢复原时间轴；未命中时保持整段请求。

## 2026-09-18：Standard 与 Brief 使用独立规则和模板

两种模式都读完整转写，只加载选定模式的规则与模板。Standard 服务理解与查阅，Brief 服务快速判断；不先生成 Standard 再压缩。

## 2026-09-19～23：报告设计保持模式边界

具体选择和用户理由维护在 [报告设计偏好](report-design-preferences.md)。关系图必须由转写支持，无法核实的精确连接应简化或改用文字。
