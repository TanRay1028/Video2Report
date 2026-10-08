#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  printf 'Usage: %s <video-url-or-share-text> [standard|brief] [prepare options...]\n' "$0" >&2
  exit 2
fi

source_value="$1"
report_mode="${2:-standard}"
if [ "$report_mode" != "standard" ] && [ "$report_mode" != "brief" ]; then
  printf 'Report mode must be standard or brief, got: %s\n' "$report_mode" >&2
  exit 2
fi
if [ "$#" -ge 2 ]; then
  shift 2
else
  shift 1
fi

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
runtime_dir="${VIDEO2REPORT_HOME:-$data_home/video2report}"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"
runs_dir="${VIDEO2REPORT_RUNS:-$hermes_home/artifacts/video-report/runs}"

if [ ! -f "$runtime_dir/pyproject.toml" ]; then
  printf 'Video2Report runtime is not installed at %s\n' "$runtime_dir" >&2
  printf "Run this skill's scripts/setup-linux.sh first.\n" >&2
  exit 2
fi

mkdir -p "$runs_dir"
set +e
output="$({
  cd "$runtime_dir"
  uv run video-report --runs "$runs_dir" prepare "$source_value" \
    --asr-backend faster-whisper --report-mode "$report_mode" "$@"
} 2>&1)"
exit_code=$?
set -e
printf '%s\n' "$output"

run_id="$(printf '%s\n' "$output" | sed -n 's/^[[:space:]]*"run_id":[[:space:]]*"\([^"]*\)".*/\1/p' | tail -n 1)"
if [ -n "$run_id" ]; then
  printf 'RUN_DIR=%s/%s\n' "$runs_dir" "$run_id"
fi
exit "$exit_code"
