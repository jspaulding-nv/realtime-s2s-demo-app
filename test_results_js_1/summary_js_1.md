# Batch Latency Test JS 1 — Summary

**Date:** 2026-03-20
**Test:** First batch run of 3 sermon audio files on the jeff test machine
**Purpose:** Validate ASR endpointing fix (`start_history=300ms`, `start_threshold=0.5`) to prevent Chinese character ASR hallucination that crashes the TTS TRT-LLM encoder

---

## Test System

| Component | Details |
|---|---|
| OS | Ubuntu 22.04.5 LTS |
| GPU 0 | NVIDIA L40S (49,140 MiB) |
| GPU 1 | NVIDIA L40S (49,140 MiB) |
| NVIDIA Driver | 550.127.05 |
| CUDA Version | 12.4 |

### GPU Assignment (docker-compose.yaml)

| Container | GPU |
|---|---|
| Riva ASR (parakeet-1.1B) | GPU 0 |
| Riva NMT (megatronnmt 1.6B) | GPU 0 |
| Riva TTS (Magpie-Multilingual) | GPU 1 |

---

## Test Configuration

| Parameter | Value |
|---|---|
| Sample rate | 16,000 Hz |
| Chunk size | 9,600 bytes (4,800 samples, 0.3s) |
| Audio format | Mono Int16 PCM |
| Target language | es-US |
| Riva server | localhost:50051 |
| Translation model | megatronnmt_any_any_1b |
| TTS voice | Magpie-Multilingual.ES-US.Isabela |
| Drain period | 30 seconds |
| Backend | FastAPI/uvicorn on localhost:8000 |
| ASR `start_history` | 300ms (raised from 100ms) |
| ASR `start_threshold` | 0.5 (raised from 0.3) |

---

## Results

| # | File | Duration | Avg Drift | Max Drift | Final Drift | Events | Status |
|---|---|---|---|---|---|---|---|
| 1 | 200108_SpiritandPresenceofGod.mp3 | 31.8 min (1,909s) | -71.5s | 29.4s | -195.2s | 11,258 | Complete |
| 2 | Blessed_Self-Forgetfulness.mp3 | 40.5 min (2,427s) | -109.1s | 11.4s | -245.8s | 14,462 | Complete |
| 3 | Beholding_the_Love_of_God.mp3 | 31.5 min (1,888s) | -15.1s | 31.2s | -61.9s* | 8,973 | Partial |

\* TTS crash at ~28m 9s — `令人难以置信。` (Chinese: "Unbelievable.") hallucinated by ASR, triggering TRT-LLM assertion failure. Audio output stopped for remainder of file.

---

## Observations

1. **Files 1 and 2 completed cleanly:** Both streamed to completion with negative final drift, matching reference baseline (-191s for the Spirit file). No TTS crashes, no Chinese character errors in TTS logs.

2. **File 3 had one TTS crash:** At ~28m 9s into the 31.5 min file, the ASR hallucinated a 6-character Chinese phrase (`令人难以置信。`) from English speech. This crashed the TTS TRT-LLM encoder. The container entered zombie state (confirmed by `Condition variable wait timed out` 60s later). The watchdog was not present in this build; audio stopped for the remainder of the file.

3. **Endpointing fix reduced but did not eliminate hallucinations:** Single Chinese filler characters (`呃`) that caused rapid crash loops in earlier tests appear to be suppressed. However, the ASR can still hallucinate multi-character Chinese phrases from sustained English speech patterns, which also trigger the same crash.

4. **Peak drift is excellent for completed files:** Max positive drift of 11–31s across all three files is well within acceptable range and consistent with reference baseline behavior (10–35s ceiling).

5. **Negative drift is structural:** Final drift deeply negative for Files 1 and 2 confirms Spanish TTS output is longer than English input (~6.4% expansion). This is an inherent property of the translation, not a bug.

6. **Watchdog needed as backstop:** The endpointing fix alone is not sufficient. The zombie state from file 3's crash confirms the watchdog (auto-restart of TTS container + NMT gRPC channel reset) should be reintroduced.

---

## Files Used

### Source / Configuration
- `batch_latency_test.py` — Test client
- `backend/riva_client.py` — Riva S2S client (ASR endpointing fix, no watchdog)
- `backend/main.py` — FastAPI backend
- `backend/websocket_handler.py` — WebSocket session management

### Test Audio Inputs
- `test_audio/200108_SpiritandPresenceofGod.mp3`
- `test_audio/Blessed_Self-Forgetfulness.mp3`
- `test_audio/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God.mp3`

## Files Created

### Latency Plots (PNG)
- `test_results_js_1/200108_SpiritandPresenceofGod_latency.png`
- `test_results_js_1/Blessed_Self-Forgetfulness_latency.png`
- `test_results_js_1/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_latency.png`

### Timing Event Data (CSV)
- `test_results_js_1/200108_SpiritandPresenceofGod_results.csv` — 52,860 rows
- `test_results_js_1/Blessed_Self-Forgetfulness_results.csv` — 67,659 rows
- `test_results_js_1/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_results.csv` — 45,801 rows

CSV format: `source, stage, timestamp_ms, chunk_index, source_position_sec, audio_bytes`
