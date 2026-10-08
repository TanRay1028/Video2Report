"""Public core command-line entry points."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import create_run


def main():
    load_dotenv(Path.cwd() / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("runs"))
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("url")
    prep.add_argument("--report-mode", choices=["standard", "brief"], default="standard")
    prep.add_argument("--transcript-mode", choices=["asr-only", "fused"], default="asr-only")
    prep.add_argument("--subtitle-file", type=Path)
    prep.add_argument("--asr-backend", choices=["mlx", "paraformer", "faster-whisper"])
    prep.add_argument("--asr-model")
    prep.add_argument(
        "--cookies-from-browser",
        help="browser for yt-dlp cookies (e.g. chrome, edge); Douyin downloads need it",
    )
    prep.add_argument(
        "--cookies",
        type=Path,
        help="Netscape cookies.txt for sites that reject anonymous downloads",
    )
    compare = sub.add_parser("compare-asr")
    compare.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "compare-asr":
        from .compare_asr import compare_asr

        output = compare_asr(args.manifest, args.runs)
        print(output)
        state = json.loads((output / "status.json").read_text(encoding="utf-8"))["state"]
        return 0 if state == "COMPLETE" else 1
    if args.command == "prepare":
        from .prepare import prepare

        status = prepare(
            create_run(
                args.runs,
                args.url,
                report_mode=args.report_mode,
                transcript_mode=args.transcript_mode,
                subtitle_file=args.subtitle_file,
                asr_backend=args.asr_backend,
                asr_model=args.asr_model,
                cookies_from_browser=args.cookies_from_browser,
                cookies_file=args.cookies,
            )
        )
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status["state"] == "TRANSCRIBED" else 1
