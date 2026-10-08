# Video2Report Skill

[简体中文](README.zh-CN.md) | English

Turn a public Bilibili or Douyin video into a self-contained HTML reading report with traceable source timestamps.

This repository is a Skill plus deterministic helper code. Python downloads media, extracts audio, and writes `transcript.md`. The Coding Agent that invoked the Skill reads the transcript and templates and writes `report.html` directly. No second Agent runtime is started.

## Workflow

```text
video URL
  -> media download
  -> FFmpeg 16 kHz mono audio
  -> timestamped transcript.md
  -> current Coding Agent + video-report Skill
  -> self-contained report.html
```

The Python command ends at `TRANSCRIBED`. HTML generation belongs to the current Agent.

## Install

Install Python 3.12, [uv](https://docs.astral.sh/uv/), and `ffmpeg` / `ffprobe`. For Windows or Linux:

```sh
git clone https://github.com/TanRay1028/Video2Report.git
cd Video2Report
uv sync --extra faster-whisper
```

For Apple Silicon, use `uv sync --extra mlx`. If Douyin requires browser rendering, also run `uv run playwright install chromium`.

## Use

Keep the repository available to the Agent, including the complete `src/video_report_agent/skills/video-report/` directory. For a video link, the Skill directs the current Agent to run:

```sh
uv run video-report prepare "<URL>" --asr-backend faster-whisper --report-mode standard
```

Use `--report-mode brief` for a concise report. The command creates `runs/<run-id>/transcript.md`; the current Agent then follows `SKILL.md` and the selected template to write `report.html` in that run directory.

An existing Markdown, TXT, or SRT transcript can be supplied directly without running the Python preparation step.

Available ASR backends are local `faster-whisper`, Apple Silicon `mlx`, and DashScope `paraformer`. The cloud backend requires `DASHSCOPE_API_KEY`; local backends do not require a report-model API key.

## Checks

```sh
uv run pytest -q
uv run ruff check src tests
uv lock --check
```

See the [Skill instructions](src/video_report_agent/skills/video-report/SKILL.md) and [project documentation](docs/README.md).
