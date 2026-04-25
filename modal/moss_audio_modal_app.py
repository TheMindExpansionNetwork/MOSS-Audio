"""Modal serverless endpoint for MOSS-Audio.

Deploy:
    modal deploy modal/moss_audio_modal_app.py

Endpoints:
    GET  /health
    POST /v1/audio/understand

The inference GPU only starts when /v1/audio/understand is called without
`dry_run: true`. Containers scale to zero after the idle timeout.
"""

import base64
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.request import Request as UrlRequest, urlopen

import modal

APP_NAME = "jimsky-moss-audio"
DEFAULT_MODEL_ID = os.environ.get("MOSS_AUDIO_MODEL_ID", "OpenMOSS-Team/MOSS-Audio-4B-Instruct")
DEFAULT_MAX_NEW_TOKENS = int(os.environ.get("MOSS_AUDIO_MAX_NEW_TOKENS", "512"))
MAX_AUDIO_BYTES = int(os.environ.get("MOSS_AUDIO_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))
REQUIRE_AUTH = os.environ.get("MOSS_AUDIO_REQUIRE_AUTH", "true").lower() not in {"0", "false", "no"}

app = modal.App(APP_NAME)

# Persistent HF/model cache so cold starts after the first download are much cheaper.
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
outputs = modal.Volume.from_name("outputs", create_if_missing=True)

# Small CPU-only API image for fast /health and dry-run checks.
api_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi[standard]",
    "pydantic",
)

# Build GPU image without starting any GPU. GPU is only requested by MossAudioRunner.
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install(
        "torch==2.9.1+cu128",
        "torchaudio==2.9.1+cu128",
        "torchcodec",
        "accelerate",
        "transformers==4.57.1",
        "safetensors>=0.4.0",
        "numpy>=2.0",
        "soundfile>=0.12.0",
        "tiktoken>=0.12.0",
        "einops>=0.8.0",
        "scipy>=1.12.0",
        "tqdm>=4.60.0",
        "packaging",
        "requests",
        "fastapi[standard]",
        "pydantic",
        "python-multipart",
        "huggingface_hub>=0.34.0",
        "hf_transfer>=0.1.8",
        extra_options="--extra-index-url https://download.pytorch.org/whl/cu128",
    )
    .env(
        {
            "HF_HOME": "/cache/huggingface",
            "HUGGINGFACE_HUB_CACHE": "/cache/huggingface/hub",
            # Keep disabled for now: Modal/PyTorch image builds can cache without it,
            # and disabling avoids cold-start failures if hf_transfer is missing in
            # any reused layer/container.
            "HF_HUB_ENABLE_HF_TRANSFER": "0",
        }
    )
    .add_local_dir(".", remote_path="/opt/MOSS-Audio", copy=True)
    .run_commands("cd /opt/MOSS-Audio && pip install -e . --no-deps")
)


def _safe_filename(suffix: str) -> str:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"input{suffix[:16]}"


def _write_audio_payload(payload: dict, workdir: str) -> Optional[str]:
    """Accept base64 audio or URL and write a local file for MOSS-Audio."""
    audio_b64 = payload.get("audio_b64")
    audio_url = payload.get("audio_url")
    filename = payload.get("filename") or "input.wav"
    suffix = Path(filename).suffix or ".wav"
    out_path = str(Path(workdir) / _safe_filename(suffix))

    if audio_b64:
        # Support data URL style payloads too.
        if isinstance(audio_b64, str) and "," in audio_b64[:128] and "base64" in audio_b64[:128]:
            audio_b64 = audio_b64.split(",", 1)[1]
        data = base64.b64decode(audio_b64)
        if len(data) > MAX_AUDIO_BYTES:
            raise ValueError(f"audio_b64 too large: {len(data)} bytes > {MAX_AUDIO_BYTES}")
        Path(out_path).write_bytes(data)
        return out_path

    if audio_url:
        req = UrlRequest(audio_url, headers={"User-Agent": "jimsky-moss-audio/0.1"})
        with urlopen(req, timeout=30) as response:
            data = response.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise ValueError(f"audio_url payload too large: > {MAX_AUDIO_BYTES} bytes")
        Path(out_path).write_bytes(data)
        return out_path

    return None


def _check_auth(headers: dict) -> None:
    if not REQUIRE_AUTH:
        return
    expected = os.environ.get("MOSS_AUDIO_API_TOKEN")
    if not expected:
        raise PermissionError("MOSS_AUDIO_API_TOKEN is not configured; endpoint is locked")
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ").strip() != expected:
        raise PermissionError("missing or invalid bearer token")


@app.cls(
    image=image,
    gpu=os.environ.get("MOSS_AUDIO_GPU", "L4"),
    cpu=4.0,
    memory=32768,
    timeout=900,
    scaledown_window=60,
    max_containers=2,
    volumes={"/cache": hf_cache, "/outputs": outputs},
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("moss-audio-api-token"),
    ],
)
class MossAudioRunner:
    @modal.enter()
    def load(self):
        import torch
        from src.hf_inference import MossAudioHFInference

        started = time.perf_counter()
        self.model_id = os.environ.get("MOSS_AUDIO_MODEL_ID", DEFAULT_MODEL_ID)
        self.inference = MossAudioHFInference(
            model_name_or_path=self.model_id,
            device="cuda:0" if torch.cuda.is_available() else "cpu",
            torch_dtype="auto",
            enable_time_marker=True,
        )
        self.load_seconds = round(time.perf_counter() - started, 3)

    @modal.method()
    def understand(self, payload: dict) -> dict:
        started = time.perf_counter()
        prompt = (payload.get("prompt") or payload.get("question") or "Describe this audio.").strip()
        max_new_tokens = int(payload.get("max_new_tokens") or DEFAULT_MAX_NEW_TOKENS)
        temperature = float(payload.get("temperature", 0.2))
        top_p = float(payload.get("top_p", 1.0))
        top_k = int(payload.get("top_k", 50))

        with tempfile.TemporaryDirectory(prefix="moss-audio-") as td:
            audio_path = _write_audio_payload(payload, td)
            answer = self.inference.generate(
                question=prompt,
                audio_path=audio_path,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )

        return {
            "ok": True,
            "model": self.model_id,
            "answer": answer,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "load_seconds": getattr(self, "load_seconds", None),
            "serverless_note": "GPU container scales to zero after idle timeout.",
        }


@app.function(
    image=api_image,
    cpu=0.25,
    memory=512,
    timeout=900,
    secrets=[modal.Secret.from_name("moss-audio-api-token")],
)
@modal.asgi_app()
def api():
    from fastapi import Body, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field

    web = FastAPI(
        title="Jimsky MOSS-Audio API",
        version="0.1.0",
        description="Serverless Modal API for MOSS-Audio audio understanding.",
    )

    class AudioRequest(BaseModel):
        prompt: str = Field(default="Describe this audio.")
        audio_b64: Optional[str] = None
        audio_url: Optional[str] = None
        filename: Optional[str] = "input.wav"
        max_new_tokens: int = 512
        temperature: float = 0.2
        top_p: float = 1.0
        top_k: int = 50
        dry_run: bool = False

    @web.get("/health")
    async def health():
        return {
            "ok": True,
            "app": APP_NAME,
            "model_default": DEFAULT_MODEL_ID,
            "auth_required": REQUIRE_AUTH,
            "gpu_starts_only_on_inference": True,
        }

    @web.post("/v1/audio/understand")
    async def understand(body: AudioRequest = Body(...), authorization: Optional[str] = Header(default=None)):
        headers = {"authorization": authorization or ""}
        if body.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "received_prompt": body.prompt,
                "has_audio_b64": bool(body.audio_b64),
                "has_audio_url": bool(body.audio_url),
                "would_start_gpu": False,
            }
        try:
            _check_auth(headers)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        try:
            payload = body.model_dump()
            return MossAudioRunner().understand.remote(payload)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"MOSS-Audio inference failed: {exc}") from exc

    return web


@app.local_entrypoint()
def main():
    print(
        json.dumps(
            {
                "app": APP_NAME,
                "default_model": DEFAULT_MODEL_ID,
                "message": "Deploy with: modal deploy modal/moss_audio_modal_app.py",
            },
            indent=2,
        )
    )
