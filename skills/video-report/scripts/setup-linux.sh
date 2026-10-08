#!/bin/sh
set -eu

missing=""
for command_name in git uv ffmpeg ffprobe; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    missing="$missing $command_name"
  fi
done

if [ -n "$missing" ]; then
  printf 'Missing required commands:%s\n' "$missing" >&2
  printf 'Install them with your Linux package manager, then rerun this script.\n' >&2
  exit 2
fi

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
runtime_dir="${VIDEO2REPORT_HOME:-$data_home/video2report}"
repo_url="${VIDEO2REPORT_REPO_URL:-https://github.com/TanRay1028/Video2Report.git}"
repo_ref="${VIDEO2REPORT_REF:-main}"

if [ -e "$runtime_dir" ] && [ ! -d "$runtime_dir/.git" ]; then
  printf 'VIDEO2REPORT_HOME exists but is not a Git checkout: %s\n' "$runtime_dir" >&2
  exit 2
fi

if [ ! -d "$runtime_dir/.git" ]; then
  mkdir -p "$(dirname "$runtime_dir")"
  git clone --depth 1 --branch "$repo_ref" "$repo_url" "$runtime_dir"
elif [ "${VIDEO2REPORT_UPDATE:-0}" = "1" ]; then
  if [ -n "$(git -C "$runtime_dir" status --porcelain)" ]; then
    printf 'Runtime checkout has local changes; refusing to update: %s\n' "$runtime_dir" >&2
    exit 2
  fi
  git -C "$runtime_dir" fetch origin "$repo_ref"
  git -C "$runtime_dir" checkout "$repo_ref"
  git -C "$runtime_dir" merge --ff-only "origin/$repo_ref"
fi

(
  cd "$runtime_dir"
  uv sync --extra faster-whisper
  uv run playwright install chromium
)

printf 'VIDEO2REPORT_HOME=%s\n' "$runtime_dir"
printf 'Runtime ready. If Chromium reports missing shared libraries, run:\n'
printf '  cd "%s" && uv run playwright install-deps chromium\n' "$runtime_dir"
