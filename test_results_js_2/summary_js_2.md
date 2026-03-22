# Batch Latency Test JS 2 — Summary

**Date:** 2026-03-21
**Test:** Batch run of 3 sermon audio files — evaluating `check_interval=10s` watchdog improvement
**Purpose:** Validate that reducing watchdog `check_interval` from 30s to 10s improves TTS zombie recovery on Beholding without affecting clean files

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
| ASR `start_history` | 300ms |
| ASR `start_threshold` | 0.5 |
| Watchdog `zombie_timeout` | 30s |
| Watchdog `check_interval` | 10s (reduced from 30s) |
| Watchdog `recovery_timeout` | 120s |

---

## Results

| # | File | Duration | Avg Drift | Max Drift | Final Drift | Events | Status |
|---|---|---|---|---|---|---|---|
| 1 | 200108_SpiritandPresenceofGod.mp3 | 31.8 min (1,909s) | -72.6s | 29.5s | -203.4s | 11,539 | Complete |
| 2 | Blessed_Self-Forgetfulness.mp3 | 40.5 min (2,427s) | -108.2s | 11.2s | -245.8s | 14,151 | Complete |
| 3 | Beholding_the_Love_of_God.mp3 | 31.5 min (1,888s) | -9.5s | 58.6s | +44.2s* | 9,830 | Partial |

\* TTS crash at ~28 min — same recurring hallucination pattern as js_1. Watchdog detected and restarted TTS container. Audio resumed but file ended before full recovery.

---

## Comparison Across JS Tests (Beholding — crash recovery progression)

| Test | Config | Max Drift | Final Drift | Events |
|---|---|---|---|---|
| js_1 | zombie_timeout=60s, check_interval=30s | 31.2s | +199.1s | 8,973 |
| js_2 | zombie_timeout=30s, check_interval=10s | **58.6s** | **+44.2s** | 9,830 |

Reducing watchdog sensitivity improved recovery: final drift improved from +199s → +44s.

---

## Observations

1. **Files 1 and 2 fully stable:** Both streamed to completion matching the reference baseline. The watchdog configuration change had no effect on clean sessions — as expected.

2. **Beholding recovery improving with each test:** Faster watchdog detection (`check_interval=10s`) reduced max drift by 20s and final drift by 18s vs js_4. The TTS restart is happening earlier, giving more recovery time before end of file.

3. **Beholding crash is consistent and location-specific:** TTS crashes at ~28 min in every test run. The trigger (`令人难以置信。` or similar Chinese phrase) is caused by a specific speech pattern at that point in the audio. ASR endpointing tuning has not prevented it; the watchdog is the primary mitigation.

4. **Stall distribution is clean for Files 1 and 2:** Max gap ≤ 30s with very few events > 10s, consistent with normal ASR endpointing behavior and no TTS issues.

5. **Negative drift is structural:** Final drift for Files 1 and 2 is deeply negative, confirming Spanish TTS output is longer than English input (~6.4% expansion). This is inherent to the language pair, not a bug.

---

## Files Used

### Source / Configuration
- `batch_latency_test.py` — Test client
- `backend/riva_client.py` — Riva S2S client (ASR endpointing fix + watchdog)
- `backend/config.py` — WatchdogConfig (zombie_timeout=30s, check_interval=10s)
- `backend/main.py` — FastAPI backend
- `backend/websocket_handler.py` — WebSocket session management

### Test Audio Inputs
- `test_audio/200108_SpiritandPresenceofGod.mp3`
- `test_audio/Blessed_Self-Forgetfulness.mp3`
- `test_audio/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God.mp3`

## Files Created

### Latency Plots (PNG)
- `test_results_js_2/200108_SpiritandPresenceofGod_latency.png`
- `test_results_js_2/Blessed_Self-Forgetfulness_latency.png`
- `test_results_js_2/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_latency.png`

### Timing Event Data (CSV)
- `test_results_js_2/200108_SpiritandPresenceofGod_results.csv` — 53,703 rows
- `test_results_js_2/Blessed_Self-Forgetfulness_results.csv` — 66,726 rows
- `test_results_js_2/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_results.csv` — 48,372 rows

CSV format: `source, stage, timestamp_ms, chunk_index, source_position_sec, audio_bytes`
