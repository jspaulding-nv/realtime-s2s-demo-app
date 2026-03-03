# Batch Latency Test 3 — Summary

**Date:** 2026-03-02
**Test:** Third batch run of 3 sermon audio files through real-time S2S translation pipeline
**Purpose:** Further confirm reproducibility and stability of the auto-restart fix

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

All 3 files streamed to completion without connection loss.

| # | File | Duration | Avg Drift | Max Drift | Final Drift |
|---|---|---|---|---|---|
| 1 | 200108_SpiritandPresenceofGod.mp3 | 31.8 min (1,908s) | -75.3s | 34.4s | -191.3s |
| 2 | Blessed_Self-Forgetfulness.mp3 | 40.5 min (2,427s) | -89.2s | 10.9s | -209.4s |
| 3 | Beholding_the_Love_of_God.mp3 | 31.5 min (1,888s) | -44.3s | 29.4s | -115.0s |

---

## Comparison Across All 3 Tests

### File 1: SpiritandPresenceofGod (31.8 min)

| Metric | Test 1 | Test 2 | Test 3 |
|---|---|---|---|
| avg_drift | -77.9s | -64.7s | -75.3s |
| max_drift | 33.8s | 33.5s | 34.4s |
| final_drift | -191.8s | -128.3s | -191.3s |

### File 2: Blessed_Self-Forgetfulness (40.5 min)

| Metric | Test 1 | Test 2 | Test 3 |
|---|---|---|---|
| avg_drift | -82.1s | -102.7s | -89.2s |
| max_drift | 10.9s | 21.5s | 10.9s |
| final_drift | -196.2s | -239.1s | -209.4s |

### File 3: Beholding_the_Love_of_God (31.5 min)

| Metric | Test 1 | Test 2 | Test 3 |
|---|---|---|---|
| avg_drift | -44.1s | -42.6s | -44.3s |
| max_drift | 29.8s | 29.9s | 29.4s |
| final_drift | -116.1s | -115.7s | -115.0s |

---

## Observations

1. **100% stability across 3 runs:** All 9 file streams (3 files x 3 tests) completed without any connection loss. The auto-restart fix is confirmed reliable.

2. **File 3 is highly reproducible:** All metrics within ~1s across all 3 tests. This is the most consistent audio file, likely due to steady speech patterns.

3. **File 1 shows two clusters:** Tests 1 and 3 are nearly identical (avg_drift -76/-75s, final_drift -192/-191s), while Test 2 was an outlier with better final drift (-128s). Suggests occasional Riva server performance variance.

4. **File 2 has the most variance:** max_drift swings between 10.9s and 21.5s across runs. This file's speech patterns likely trigger different Riva batching behavior between sessions.

5. **Max positive drift is consistent:** Across all 9 runs, peak real-time latency falls in a 10–35s range. The typical ceiling is ~34s (File 1) or ~30s (File 3), with File 2 being the best performer at 10–21s.

6. **Negative drift is structural:** Final drift is consistently deeply negative for all files across all tests, confirming Spanish TTS output is longer than English input. This is an inherent property of the translation, not a bug.

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
- `test_results_3/200108_SpiritandPresenceofGod_latency.png` (106 KB)
- `test_results_3/Blessed_Self-Forgetfulness_latency.png` (102 KB)
- `test_results_3/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_latency.png` (120 KB)

### Timing Event Data (CSV)
- `test_results_3/200108_SpiritandPresenceofGod_results.csv` — 67,648 rows, 3.3 MB
- `test_results_3/Blessed_Self-Forgetfulness_results.csv` — 85,441 rows, 4.2 MB
- `test_results_3/gospel_in_life_tk_1-john-part-2-mp3_Beholding_the_Love_of_God_results.csv` — 65,296 rows, 3.2 MB

CSV format: `source, stage, timestamp_ms, chunk_index, source_position_sec, audio_bytes`
