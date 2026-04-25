#!/usr/bin/env python3
"""Smoke-test the deployed Jimsky MOSS-Audio endpoint.

Usage:
    python scripts/smoke_modal_endpoint.py https://your-modal-url

This default smoke test uses /health and dry_run so it does not start a GPU.
Use --audio-file to run real inference.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from urllib.request import Request, urlopen


def request_json(url: str, payload: dict | None = None, token: str | None = None, timeout: int = 60):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method="GET" if payload is None else "POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--audio-file")
    parser.add_argument("--token", default=os.environ.get("MOSS_AUDIO_API_TOKEN"))
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print(json.dumps(request_json(f"{base}/health"), indent=2))

    payload = {"prompt": "Describe this audio.", "dry_run": True}
    print(json.dumps(request_json(f"{base}/v1/audio/understand", payload), indent=2))

    if args.audio_file:
        if not args.token:
            raise SystemExit("--token or MOSS_AUDIO_API_TOKEN required for real inference")
        with open(args.audio_file, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        payload = {
            "prompt": "Transcribe this audio and summarize what the user wants Jimsky to do.",
            "audio_b64": audio_b64,
            "filename": args.audio_file,
            "max_new_tokens": 512,
            "temperature": 0.2,
        }
        print(json.dumps(request_json(f"{base}/v1/audio/understand", payload, args.token, timeout=900), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
