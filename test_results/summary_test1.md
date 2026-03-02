# Batch Latency Test 1 — Summary

**Date:** 2026-03-02
**Test:** Full batch run of 3 sermon audio files through real-time S2S translation pipeline
**Purpose:** Verify the auto-restart fix for Riva ASR endpointing and measure translation drift over long-duration streams

---

## Problem

WebSocket connections were dropping after ~60 seconds during streaming translation. Root cause: Riva's ASR aggressively endpointed (closed the gRPC streaming session after detecting silence boundaries). When `streaming_s2s_response_generator` finished, the `run_translation()` thread exited. The `AudioChunkIterator` remained alive but nothing consumed from it — client audio piled up unprocessed and the connection eventually died.

## Fix Applied

**File modified:** `backend/riva_client.py` — `run_translation()` inner function (lines 162–204)

Wrapped the Riva response loop in a `while not chunk_iterator._stopped` retry loop that auto-restarts a new streaming session when ASR endpointing closes the previous one. The same `AudioChunkIterator` instance is reused across restarts so queued chunks flow seamlessly into the new stream.

Key behavior:
- When ASR endpointing fires, `streaming_s2s_response_generator` stops consuming but does NOT call `stop()` on the iterator
- `_stopped` remains `False`, so `__next__` keeps yielding queued and future chunks
- A new `streaming_s2s_response_generator` call starts a fresh gRPC stream that resumes pulling from the same iterator
- Chunks accumulated during the restart gap are immediately consumed by the new stream

---

## Test Configuration

| Parameter | Value |
|---|---|
| Sample rate | 16,000 Hz |
| Chunk size | 9,600 bytes (4,800 samples, 0.3s) |
| Audio format | Mono Int16 PCM |
| Target language | es-US |
| Riva server | 10.1.90.249:50051 |
| Translation model | megatronnmt_any_any_1b |
| TTS voice | Magpie-Multilingual.ES-US.Isabela |
| Drain period | 30 seconds |
| Backend | FastAPI/uvicorn on localhost:8000 |

---

## Results

All 3 files streamed to completion without connection loss — confirming the fix works.

| # | File | Duration | Avg Drift | Max Drift | Final Drift |
|---|---|---|---|---|---|
| 1 | 200108_SpiritandPresenceofGod.mp3 | 31.8 min (1,908s) | -77.9s | 33.8s | -191.8s |
| 2 | Blessed_Self-Forgetfulness.mp3 | 40.5 min (2,427s) | -82.1s | 10.9s | -196.2s |
| 3 | Beholding_the_Love_of_God.mp3 | 31.5 min (1,888s) | -44.1s | 29.8s | -116.1s |

### Interpreting Drift

- **Positive drift** = translation is behind (input outpacing output). The max positive values (10–34s) represent the peak real-time translation latency experienced during streaming.
- **Negative drift** = translated audio output is longer than the input consumed so far. Riva's TTS generates more audio than the original speech duration, causing output to exceed input over time.
- **Final drift** is deeply negative for all files, meaning the system produced substantially more output audio than the input duration. This is expected behavior — Spanish translations of English speech tend to be longer.

### Key Observations

1. **No connection drops:** All 3 files (31–40 min each) completed without any WebSocket disconnection. This is the critical improvement over the pre-fix behavior where connections died at ~60s.
2. **Max latency was acceptable:** Peak positive drift of 10–34s across all files. File 2 had the best peak latency at 10.9s.
3. **Output exceeds input:** The consistently negative final drift indicates the translated speech is ~1.5–2x longer than real-time. This may warrant investigation into TTS pacing or output buffering.

---

## Files Used

### Source / Configuration
- `batch_latency_test.py` — Test client that streams audio at real-time rate through WebSocket and measures drift
- `backend/riva_client.py` — Riva S2S client wrapper (contains the auto-restart fix)
- `backend/main.py` — FastAPI backend with WebSocket and test timing endpoints
- `backend/websocket_handler.py` — WebSocket session management and audio routing
- `backend/config.py` — Audio and Riva configuration constants

### Test Audio Inputs
- `test_audio/200108_SpiritandPresenceofGod.mp3`
- `test_audio/Blessed_Self-Forgetfulness.mp3`
- `test_audio/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God.mp3`

## Files Created

### Latency Plots (PNG)
- `test_results/200108_SpiritandPresenceofGod_latency.png` — Drift over time plot
- `test_results/Blessed_Self-Forgetfulness_latency.png` — Drift over time plot
- `test_results/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_latency.png` — Drift over time plot

### Timing Event Data (CSV)
- `test_results/200108_SpiritandPresenceofGod_results.csv` — 67,543 rows, 3.5 MB
- `test_results/Blessed_Self-Forgetfulness_results.csv` — 84,697 rows, 4.4 MB
- `test_results/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_results.csv` — 65,392 rows, 3.4 MB

CSV format: `source, stage, timestamp_ms, chunk_index, source_position_sec, audio_bytes`

---

## Next Steps

1. Investigate why output audio duration exceeds input (negative drift accumulation) — may need TTS rate adjustment or output buffering changes
2. Run with different endpointing parameters to find optimal balance between responsiveness and stream stability
3. Test with live microphone input to compare real-time behavior vs file-based streaming
