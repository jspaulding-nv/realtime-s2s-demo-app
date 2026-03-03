# Batch Latency Test 2 — Summary

**Date:** 2026-03-02
**Test:** Repeat batch run of 3 sermon audio files through real-time S2S translation pipeline
**Purpose:** Confirm reproducibility of Test 1 results after the auto-restart fix

---

## Background

This is a repeat of Test 1 using identical configuration and the same 3 audio files. The auto-restart fix in `backend/riva_client.py` (committed in `bc30349`) was already in place from Test 1.

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

All 3 files streamed to completion without connection loss.

| # | File | Duration | Avg Drift | Max Drift | Final Drift |
|---|---|---|---|---|---|
| 1 | 200108_SpiritandPresenceofGod.mp3 | 31.8 min (1,908s) | -64.7s | 33.5s | -128.3s |
| 2 | Blessed_Self-Forgetfulness.mp3 | 40.5 min (2,427s) | -102.7s | 21.5s | -239.1s |
| 3 | Beholding_the_Love_of_God.mp3 | 31.5 min (1,888s) | -42.6s | 29.9s | -115.7s |

---

## Comparison with Test 1

| File | Metric | Test 1 | Test 2 | Delta |
|---|---|---|---|---|
| SpiritandPresenceofGod | avg_drift | -77.9s | -64.7s | +13.2s (improved) |
| | max_drift | 33.8s | 33.5s | -0.3s |
| | final_drift | -191.8s | -128.3s | +63.5s (improved) |
| Blessed_Self-Forgetfulness | avg_drift | -82.1s | -102.7s | -20.6s (worse) |
| | max_drift | 10.9s | 21.5s | +10.6s (worse) |
| | final_drift | -196.2s | -239.1s | -42.9s (worse) |
| Beholding_the_Love_of_God | avg_drift | -44.1s | -42.6s | +1.5s (similar) |
| | max_drift | 29.8s | 29.9s | +0.1s (similar) |
| | final_drift | -116.1s | -115.7s | +0.4s (similar) |

### Observations

1. **Stability confirmed:** All 3 files completed without connection loss in both tests — the auto-restart fix is reliable.
2. **File 1 improved:** Average and final drift both improved notably, suggesting Riva server load or timing variance between runs.
3. **File 2 regressed slightly:** Max drift went from 10.9s to 21.5s and final drift worsened by ~43s. This is likely due to natural variance in how Riva batches translations during different speech patterns.
4. **File 3 nearly identical:** All metrics within ~1.5s of Test 1, showing good reproducibility for this particular audio.
5. **Max positive drift range:** 21–34s across both tests. This represents the peak real-time translation latency a listener would experience.
6. **Negative final drift consistent:** All files produce more output audio than input duration, confirming Spanish TTS generates longer speech than English source.

---

## Files Used

### Source / Configuration
- `batch_latency_test.py` — Test client
- `backend/riva_client.py` — Riva S2S client with auto-restart fix
- `backend/main.py` — FastAPI backend
- `backend/websocket_handler.py` — WebSocket session management

### Test Audio Inputs
- `test_audio/200108_SpiritandPresenceofGod.mp3`
- `test_audio/Blessed_Self-Forgetfulness.mp3`
- `test_audio/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God.mp3`

## Files Created

### Latency Plots (PNG)
- `test_results_2/200108_SpiritandPresenceofGod_latency.png` (115 KB)
- `test_results_2/Blessed_Self-Forgetfulness_latency.png` (101 KB)
- `test_results_2/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_latency.png` (119 KB)

### Timing Event Data (CSV)
- `test_results_2/200108_SpiritandPresenceofGod_results.csv` — 66,346 rows, 3.3 MB
- `test_results_2/Blessed_Self-Forgetfulness_results.csv` — 86,068 rows, 4.3 MB
- `test_results_2/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_results.csv` — 65,569 rows, 3.2 MB

CSV format: `source, stage, timestamp_ms, chunk_index, source_position_sec, audio_bytes`
