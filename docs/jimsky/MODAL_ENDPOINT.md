# Jimsky MOSS-Audio Modal Endpoint

This fork adds a serverless Modal API wrapper around MOSS-Audio so Jimsky/agents can send audio plus an instruction payload and receive an audio-understanding response.

## Design Goals

- **Serverless first:** no always-on GPU server.
- **Scale to zero:** the GPU runner uses Modal `scaledown_window=60`.
- **Agent-friendly payloads:** JSON with `audio_b64` or `audio_url` plus a `prompt`.
- **Safe by default:** inference requires a bearer token stored in Modal secret `moss-audio-api-token`.
- **Cache-aware:** Hugging Face/model files use the existing Modal volume `huggingface-cache`.

## Modal App

```text
jimsky-moss-audio
```

Main file:

```text
modal/moss_audio_modal_app.py
```

## Default Model

```text
OpenMOSS-Team/MOSS-Audio-4B-Thinking
```

Override with env:

```text
MOSS_AUDIO_MODEL_ID=OpenMOSS-Team/MOSS-Audio-4B-Thinking
```

The 4B model is the intended first deployment target. The 8B variants may need a larger GPU such as `L40S` or `A100-40GB`.

## Endpoints

After deployment, Modal will provide a URL for the ASGI app.

### Health

```bash
curl https://YOUR-MODAL-ENDPOINT/health
```

This does **not** start a GPU.

### Dry Run

```bash
curl -X POST https://YOUR-MODAL-ENDPOINT/v1/audio/understand \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Describe this audio.","dry_run":true}'
```

This does **not** start a GPU.

### Audio Understanding

```bash
AUDIO_B64=$(base64 -w0 test/test_en.mp3)

curl -X POST https://YOUR-MODAL-ENDPOINT/v1/audio/understand \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $MOSS_AUDIO_API_TOKEN" \
  -d "{\"prompt\":\"Transcribe this and summarize what the speaker wants Jimsky to do.\",\"audio_b64\":\"$AUDIO_B64\",\"filename\":\"test_en.mp3\",\"max_new_tokens\":512,\"temperature\":0.2}"
```

## Payload Schema

```json
{
  "prompt": "Describe this audio.",
  "audio_b64": "base64 audio bytes, optional",
  "audio_url": "https://example.com/audio.mp3, optional",
  "filename": "input.wav",
  "max_new_tokens": 512,
  "temperature": 0.2,
  "top_p": 1.0,
  "top_k": 50,
  "dry_run": false
}
```

Provide either `audio_b64` or `audio_url`. If neither is provided, the model receives a text-only prompt.

## Secret Setup

Do not commit or print token values.

Required Modal secret:

```text
moss-audio-api-token
```

Expected key inside secret:

```text
MOSS_AUDIO_API_TOKEN=[REDACTED]
```

Optional existing secret:

```text
huggingface-secret
```

Expected key if used:

```text
HF_TOKEN=[REDACTED]
```

## Deploy

From repo root with Hermes venv active and Modal credentials loaded:

```bash
cd /opt/data/hermes-agent
source venv/bin/activate
set -a; source /opt/data/.env; set +a
cd /opt/data/workspace/projects/MOSS-Audio
modal deploy modal/moss_audio_modal_app.py
```

## Cost/Safety Notes

- `/health` and dry-run requests are CPU-only.
- Real inference starts one GPU container.
- The default GPU is `L4`.
- The GPU container idles for only 60 seconds before scaling down.
- Do not run open public inference without an auth token; a public unauthenticated GPU endpoint can burn credits.
- Check billing after tests:

```bash
modal billing report --for today --json
```

## Verified Smoke Test

A bounded real inference smoke test was run against the deployed Modal app using a 0.5-second generated WAV tone, `max_new_tokens=40`, and bearer-token auth from environment only. Result:

```json
{
  "ok": true,
  "model": "OpenMOSS-Team/MOSS-Audio-4B-Instruct",
  "elapsed_seconds": 2.357,
  "load_seconds": 8.061,
  "answer": "A single, clear, and high-pitched electronic beep sounds in a quiet indoor space, with no background noise or reverberation."
}
```

After the test, Modal was checked again after the idle window and `jimsky-moss-audio` showed `Tasks: 0`, confirming the GPU scaled down. The same billing check showed roughly `$0.16` for the active deployed app row that day.

Implementation note: `src/audio_io.py` uses SoundFile + SciPy resampling instead of `torchaudio.load` to avoid TorchCodec/FFmpeg shared-library compatibility failures in the Modal CUDA image.

## Jimsky Agent Use

Intended agent flow:

1. User records voice/audio.
2. Telegram/Discord/Hermes stores or base64-encodes the audio.
3. Jimsky sends payload to `/v1/audio/understand` with prompt like:

```text
Transcribe this audio, extract the user's intent, list actions, and identify anything that needs approval.
```

4. Jimsky receives structured natural-language output.
5. Jimsky executes safe tasks and asks for approvals where needed.
