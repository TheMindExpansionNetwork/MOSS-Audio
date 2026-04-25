# Jimsky MOSS-Audio Model Bakeoff: March on Washington Sample

Date: 2026-04-25 UTC

A locked 30-second public-domain archival audio clip was extracted from National Archives / Internet Archive item `gov.archives.arc.49737` (*THE MARCH ON WASHINGTON*, 1963). The same clip and prompt were run against four MOSS-Audio variants.

## Locked sample

```text
/opt/data/workspace/audio_tests/march_on_washington/model_bakeoff_actual_20260425_221627/locked_sample_march_30s.wav
```

## Results

| Variant | GPU | Load seconds | Inference seconds | Client wall seconds | Output hygiene | Grade | Verdict |
|---|---:|---:|---:|---:|---|---:|---|
| `OpenMOSS-Team/MOSS-Audio-4B-Instruct` | L4 | 12.181 | 5.887 | 39.569 | clean | 75.0 | Fast, clean, affordable baseline; too shallow for rich archival analysis. |
| `OpenMOSS-Team/MOSS-Audio-4B-Thinking` | L4 | 8.707 | 15.902 | 39.956 | needs think-strip | 65.0 | Understands context, but leaks `<think>` and is not production-clean without filtering. |
| `OpenMOSS-Team/MOSS-Audio-8B-Instruct` | L40S | 87.117 | 10.395 | 112.826 | clean | 90.0 | Best practical winner: detailed, accurate, clean output, strong audio-quality and lyric observations. |
| `OpenMOSS-Team/MOSS-Audio-8B-Thinking` | L40S | 88.323 | 10.631 | 120.554 | needs think-strip | 81.0 | Strong reasoning/details but leaks `<think>`; useful only with a cleanup/structured-output wrapper. |

## Ranking

1. `OpenMOSS-Team/MOSS-Audio-8B-Instruct` — best overall for user-facing analysis.
2. `OpenMOSS-Team/MOSS-Audio-8B-Thinking` — strong but requires `<think>` stripping.
3. `OpenMOSS-Team/MOSS-Audio-4B-Instruct` — best cheap/fast baseline.
4. `OpenMOSS-Team/MOSS-Audio-4B-Thinking` — acceptable but less clean than 4B Instruct for this task.

## Key observations

- The 8B models loaded successfully on `L40S`; model downloads are now warmed into the Modal Hugging Face cache.
- The 4B models worked on `L4`.
- Thinking variants produced visible `<think>` blocks despite prompt instructions. Add a response cleanup layer before production use.
- The endpoint was restored after the bakeoff to safer default `OpenMOSS-Team/MOSS-Audio-4B-Thinking` on `L4`.
- After the idle wait, Modal showed `Tasks: 0`.

## Best answer excerpt: 8B Instruct

```text
Audible Content: A large mixed-gender choir sings a cappella with a full, resonant sound. The performance is slow, deliberate, and emotionally charged, featuring sustained harmonies and a powerful, unified delivery. The lyrics are partially intelligible, with phrases such as "We are not afraid today," "Oh, we believe in our hearts," and "We shall overcome" clearly audible. The final word, "come," is cut off abruptly. Speech/Singing: The choir sings in a formal, reverent style, with no spoken words or announcements. The vocal delivery is smooth, blended, and dynamically controlled, emphasizing emotional intensity over individual expression. Crowd/Event Atmosphere: The recording captures a large, reverberant space with a sense of collective presence. The acoustics suggest a vast outdoor or hall-like environment, with the choir's sound filling the space. There is no audible crowd noise, applause, or ambient chatter, indicating a focused, solemn atmosphere. Historical Context Cues: The content, style, and context strongly align with the 1963 March on Washington for Jobs and Freedom. The song "We Shall Overcome" is a central anthem of the Civil Rights Movement, and the performance reflects the movement's themes of unity, resilience, and hope. The recording's archival quality and lack of modern elements further support its historical authenticity. Audio Quality: The recording is monophonic, with a narrow frequency range and a constant background hiss. The sound is muffled, lacking high-frequency clarity, and exhibits limited dynamic range. The abrupt ending suggests the clip is an excerpt from a longer recording. Clip Structure: The clip begins mid-phrase and ends abruptly, with no introduction or conclusion. It captures a continuous segment of the choir's performance
```

## Cost snapshot

After the bakeoff, Modal billing for `jimsky-moss-audio` showed approximately `$0.72238639` for the active app row plus `$0.00531202` for an older stopped row that day.
