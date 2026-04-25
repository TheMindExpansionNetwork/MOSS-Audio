# Jimsky Modal Endpoint

This fork includes a serverless Modal API wrapper for MOSS-Audio.

See:

```text
docs/jimsky/MODAL_ENDPOINT.md
modal/moss_audio_modal_app.py
scripts/smoke_modal_endpoint.py
```

The API is designed for Jimsky/agent audio commands:

```text
record audio → send payload → MOSS-Audio understands/transcribes/summarizes → Jimsky executes safe tasks
```

Safety default: GPU inference requires bearer auth via Modal secret `moss-audio-api-token`, and GPU containers scale to zero after idle timeout.
