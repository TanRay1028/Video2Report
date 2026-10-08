# Hermes Agent（Linux）

仓库在 `skills/video-report/` 提供可由 Hermes Agent 加载的 Linux Skill。它复用本仓库的 Python 运行时，不另建报告生成服务或嵌套 Agent。

## 安装 Skill

Hermes 支持 GitHub 多文件 Skill 时，可直接安装：

```sh
hermes skills install TanRay1028/Video2Report/skills/video-report
```

也可以把 `skills/video-report/` 复制到 `${HERMES_HOME:-$HOME/.hermes}/skills/video-report/`。

## 准备 Linux 运行时

系统需要 `git`、`uv`、`ffmpeg` 和 `ffprobe`。首次使用前运行：

```sh
sh "${HERMES_HOME:-$HOME/.hermes}/skills/video-report/scripts/setup-linux.sh"
```

脚本会把仓库克隆到 `${VIDEO2REPORT_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/video2report}`，创建项目虚拟环境，安装 `faster-whisper`，并下载 Playwright Chromium。脚本不调用 `sudo`；系统包仍由管理员安装。Chromium 缺少 Linux 共享库时，按脚本给出的 `playwright install-deps chromium` 提示处理。

## 运行与产物

在 Hermes 中使用 `/video-report <链接>`。Skill 会调用：

```sh
sh "$SKILL_ROOT/scripts/prepare-video.sh" "<URL>" standard
```

下载、音频提取和转写产物默认写入 `${HERMES_HOME:-$HOME/.hermes}/artifacts/video-report/runs/<run-id>/`。Hermes 当前会话读取 `transcript.md`，生成 `report.html`，并把 HTML 作为文档交付。

可用环境变量：

- `VIDEO2REPORT_HOME`：运行时仓库位置。
- `VIDEO2REPORT_RUNS`：任务输出根目录。
- `VIDEO2REPORT_REPO_URL`：运行时仓库来源。
- `VIDEO2REPORT_REF`：首次克隆的分支或标签，默认 `main`。
- `VIDEO2REPORT_UPDATE=1`：允许安装脚本对干净的现有运行时执行 fast-forward 更新。
