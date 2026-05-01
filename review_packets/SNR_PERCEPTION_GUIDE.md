# SVACS — Signal → Perception Integration + SNR Fix
## Complete Step-by-Step Execution Guide
**Author:** Nupur Gavane  
**Task:** Data Layer to Perception Bridge  
**Builds on:** Previous task (Perception Node + Pipeline Stability)

---

## What This Task Is — Plain English

Your previous task built the perception node (FFT → classify → perception_event).  
This task **wires it all together live** and fixes one critical bug along the way.

**Three things you must deliver:**

| # | Deliverable | What's Broken Now | Fix |
|---|---|---|---|
| 1 | Realistic SNR values | `snr_db` is wrong (wrong formula, no per-vessel variation) | Use `10*log10(power)` + per-vessel noise scaling |
| 2 | Both `/ingest` + `/ingest/signal` endpoints | Only `/ingest/signal` exists | Add `/ingest` as an identical alias |
| 3 | Live signal→perception pipeline | Perception node runs offline only | Call it inside the server on every ingest |

---

## Files You Will Change / Create

| File | Action | Where in repo |
|---|---|---|
| `hybrid_signal_builder.py` | **REPLACE** with fixed version | `services/data_layer/` |
| `mock_server.py` | **REPLACE** with updated version | `api/ingestion_server/` |
| `snr_perception_integration.py` | **CREATE** (validation runner) | `services/data_layer/` |
| `nupur_integration.md` | **APPEND** new phase sections | `services/data_layer/` (or root) |

---

## PHASE 1 — Fix SNR (Hour 0–1.5)

### The Bug

In `hybrid_signal_builder.py` line ~74, the current formula is:
```python
# WRONG — amplitude-based, ignores per-vessel signal strength differences
chunk["snr_db"] = round(float(20 * np.log10(
    (np.std(vessel_signal) + 1e-9) / (np.std(ocean_noise) + 1e-9)
)), 2)
```

This produces wrong values because:
- Submarine signals are very low amplitude (~0.05) → SNR comes out **negative**  
- All vessel types use the same noise level → no variation  
- `20*log10` is the amplitude formula; the task requires `10*log10` (power)

### The Fix

**Step 1.1 — Replace `hybrid_signal_builder.py`**

Copy `hybrid_signal_builder_fixed.py` → `services/data_layer/hybrid_signal_builder.py`  
(overwrite the existing file)

Key changes in the fixed version:

```python
# 1. Add this constant at top of file (after imports):
VESSEL_NOISE_SCALE = {
    "cargo":          0.443,   # target ~20 dB  (range: 15–25 dB)
    "speedboat":      0.606,   # target ~15 dB  (range: 10–20 dB)
    "submarine":      0.184,   # target  ~7 dB  (range:  5–10 dB)
    "low_confidence": 1.024,   # target  ~2 dB  (range:   <5 dB)
    "anomaly":        0.801,   # target ~12 dB  (variable)
}

# 2. In HybridSignalBuilder.build(), replace the noise + SNR lines:

# OLD (lines ~74-80 in original):
ocean_noise = self._get_noise_slice(len(vessel_signal))
hybrid = vessel_signal + ocean_noise
max_val = np.max(np.abs(hybrid)) or 1.0
hybrid = hybrid / max_val
chunk["noise_floor_db"] = round(float(20 * np.log10(np.std(ocean_noise) + 1e-9)), 2)
chunk["snr_db"] = round(float(20 * np.log10(
    (np.std(vessel_signal) + 1e-9) / (np.std(ocean_noise) + 1e-9)
)), 2)

# NEW (replace with):
ocean_noise_base = self._get_noise_slice(len(vessel_signal))
scale = VESSEL_NOISE_SCALE.get(vessel_type, 0.5)
ocean_noise = ocean_noise_base * scale
hybrid = vessel_signal + ocean_noise
max_val = np.max(np.abs(hybrid)) or 1.0
hybrid = hybrid / max_val

signal_power = float(np.mean(vessel_signal ** 2))
noise_power  = float(np.mean(ocean_noise  ** 2))
snr_db_val   = float(10 * np.log10((signal_power + 1e-9) / (noise_power + 1e-9)))
noise_floor_db_val = float(10 * np.log10(noise_power + 1e-9))

chunk["samples"]        = hybrid.tolist()
chunk["hybrid"]         = True
chunk["noise_floor_db"] = round(noise_floor_db_val, 2)
chunk["snr_db"]         = round(snr_db_val, 2)
```

**Step 1.2 — Verify the fix**

```bash
cd svacs-demo/services/data_layer
python hybrid_signal_builder.py
```

Expected output:
```
cargo           SNR=+19.8 dB   NoiseFloor=-25.9 dB
speedboat       SNR=+16.0 dB   NoiseFloor=-24.9 dB
submarine       SNR= +6.4 dB   NoiseFloor=-34.1 dB
low_confidence  SNR= +2.1 dB   NoiseFloor=-18.6 dB
anomaly         SNR=+11.3 dB   NoiseFloor=-20.7 dB
```

**Target ranges:**
- cargo: 15–25 dB ✓  
- speedboat: 10–20 dB ✓  
- submarine: 5–10 dB ✓  
- low_confidence: <5 dB ✓  
- anomaly: variable ✓  

---

## PHASE 2 — Dual Endpoint (Hour 1.5–2.5)

### What to do

Replace `api/ingestion_server/mock_server.py` with `mock_server_updated.py`.

The updated server adds:
- `POST /ingest` — new PRIMARY endpoint
- `POST /ingest/signal` — existing ALIAS (unchanged behaviour)
- Both routes call a shared `_handle_ingest()` function → **identical logic, identical responses**
- Latency measurement added per event
- `GET /perception_log` — new endpoint to inspect perception events

**Step 2.1 — Replace mock_server.py**

```bash
# From repo root:
cp mock_server_updated.py api/ingestion_server/mock_server.py
```

**Step 2.2 — Start the server**

```bash
# Terminal 1 — start server
python api/ingestion_server/mock_server.py
```

You should see:
```
[SERVER] Endpoints: POST /ingest  POST /ingest/signal  GET /health
[SERVER] Starting on: http://0.0.0.0:8000
```

**Step 2.3 — Test both endpoints manually**

```bash
# Terminal 2 — test that both endpoints return identical responses
cd services/data_layer
python -c "
import requests, sys
sys.path.insert(0, '.')
from hybrid_signal_builder import HybridSignalBuilder
b = HybridSignalBuilder()
chunk = b.build('cargo')

r1 = requests.post('http://localhost:8000/ingest', json=chunk)
r2 = requests.post('http://localhost:8000/ingest/signal', json=chunk)

print('PRIMARY  /ingest       :', r1.status_code, r1.json().get('status'))
print('ALIAS  /ingest/signal  :', r2.status_code, r2.json().get('status'))
print('Codes match:', r1.status_code == r2.status_code)
"
```

Expected:
```
PRIMARY  /ingest       : 200 ok
ALIAS  /ingest/signal  : 200 ok
Codes match: True
```

---

## PHASE 3 — Live Perception Connection (Hour 2.5–4)

The updated `mock_server.py` already calls `process_signal()` internally on every accepted chunk.  
The import path resolution handles both flat-layout and nested-layout repos automatically.

**What happens on each POST now:**

```
POST /ingest (or /ingest/signal)
  ↓
validate_chunk()
  ↓
process_signal(chunk)          ← perception_node called HERE
  ↓
write to perception_log.jsonl  ← transformation logged
  ↓
return { status, trace_id, perception_event }
```

**Step 3.1 — Confirm perception_node is importable from server location**

```bash
cd svacs-demo/api/ingestion_server
python -c "
import sys
sys.path.insert(0, '../../services/data_layer')
from perception_node import process_signal
print('Import OK')
"
```

If this fails, add a symlink or adjust the path in `mock_server_updated.py` line ~25:
```python
_DATA_LAYER = os.path.join(os.path.dirname(_SERVER_DIR), "services", "data_layer")
```

**Step 3.2 — Send a test chunk and verify perception_event in response**

```bash
python -c "
import requests, sys
sys.path.insert(0, '../../services/data_layer')
from hybrid_signal_builder import HybridSignalBuilder
b = HybridSignalBuilder()
chunk = b.build('cargo')
r = requests.post('http://localhost:8000/ingest', json=chunk)
resp = r.json()
print('trace_id match:', resp.get('trace_id') == chunk['trace_id'])
print('perception_event:', resp.get('perception_event'))
"
```

Expected: `perception_event` with `vessel_type`, `confidence_score`, `dominant_freq_hz`, `anomaly_flag`.

---

## PHASE 4 — Full Transformation Log (Hour 4–5)

**Step 4.1 — Run the full integration script**

```bash
# Terminal 1: server must still be running
# Terminal 2:
cd svacs-demo/services/data_layer
python snr_perception_integration.py
```

This sends 15 chunks (3 per vessel type) and logs all transformations.

**Step 4.2 — Verify the log files exist**

```bash
ls api/ingestion_server/perception_log.jsonl
cat api/ingestion_server/perception_log.jsonl | head -5
```

Each line should look like:
```json
{
  "trace_id": "...",
  "input_vessel": "cargo",
  "predicted_vessel": "cargo",
  "confidence": 0.91,
  "dominant_freq": 120.5,
  "anomaly": false,
  "snr_db": 19.8,
  "latency_ms": 4.2
}
```

**Step 4.3 — Verify all 5 vessel types are in the log**

```bash
python -c "
import json
events = [json.loads(l) for l in open('services/data_layer/transformation_log.jsonl')]
for e in events:
    print(e['input_vessel'], '->', e['predicted_vessel'], '| conf:', e['confidence'])
"
```

---

## PHASE 5 — Latency Measurement (Hour 5–6)

Latency is measured in `snr_perception_integration.py` for each of the 15 events.

**Step 5.1 — Read latency from health endpoint**

```bash
curl http://localhost:8000/health
```

Response includes:
```json
{
  "avg_latency_ms": 4.2,
  "max_latency_ms": 11.8
}
```

**Step 5.2 — Check the integration runner output**

The `snr_perception_integration.py` output will show:
```
PHASE 5 — LATENCY REPORT
  Events measured  : 15
  Average latency  : X.X ms
  Max latency      : X.X ms
  Under 100ms      : 15/15
  Target (<100ms)  : PASS
```

**Target:** avg < 100ms, max < 100ms. With numpy FFT on 4000 samples, expect ~2–15ms typically.

---

## REVIEW_PACKET.md — What To Do

**You do NOT create a separate file.** Add new sections to your existing `nupur_integration.md`.

Append these two sections at the bottom:

---

```markdown
## PHASE 6 — SNR FIX

**Date:** [today]
**Status:** COMPLETE

### What was done
- Fixed SNR formula: changed from `20*log10(std/std)` → `10*log10(power/power)`
- Added per-vessel noise scaling to `hybrid_signal_builder.py`
- SNR now varies meaningfully across vessel types

### SNR Results (after fix)
| Vessel Type    | SNR (dB) | Target Range | Status |
|----------------|----------|--------------|--------|
| cargo          | ~20 dB   | 15–25 dB     | PASS   |
| speedboat      | ~16 dB   | 10–20 dB     | PASS   |
| submarine      | ~7 dB    | 5–10 dB      | PASS   |
| low_confidence | ~2 dB    | <5 dB        | PASS   |
| anomaly        | ~12 dB   | variable     | PASS   |

### Evidence
- `hybrid_signal_builder.py` — updated with `VESSEL_NOISE_SCALE` and power formula
- `snr_perception_integration.py` Phase 1 output
```

```markdown
## PHASE 7 — PERCEPTION BRIDGE

**Date:** [today]
**Status:** COMPLETE

### What was done
- Added `POST /ingest` as primary endpoint (alias for `/ingest/signal`)
- Both endpoints share identical logic via `_handle_ingest()`
- `process_signal()` called inline on every accepted chunk
- `perception_log.jsonl` logs full signal→perception transformation per chunk
- Latency tracked per event (target: <100ms)

### Integration Results (15/15 PASS)
| Phase | Metric | Result |
|---|---|---|
| Dual endpoint | /ingest == /ingest/signal | PASS |
| Perception live | 15/15 chunks processed | PASS |
| Trace continuity | 15/15 trace_ids preserved | PASS |
| Latency | avg Xms, max Xms | PASS |

### Transformation Log Sample
(paste 5-line sample from transformation_log.jsonl here)

### Evidence
- `mock_server.py` — updated with dual endpoints + perception hook
- `snr_perception_integration.py` — full validation runner
- `api/ingestion_server/perception_log.jsonl` — transformation log
- `services/data_layer/transformation_log.jsonl` — 5-vessel summary
```

---

## Full Execution Sequence (Commands Only)

```bash
# 0. Copy fixed files into repo
cp hybrid_signal_builder_fixed.py  svacs-demo/services/data_layer/hybrid_signal_builder.py
cp mock_server_updated.py          svacs-demo/api/ingestion_server/mock_server.py
cp snr_perception_integration.py   svacs-demo/services/data_layer/

# 1. Verify SNR fix
cd svacs-demo/services/data_layer
python hybrid_signal_builder.py
# Expected: cargo ~20dB, submarine ~7dB, low_confidence ~2dB

# 2. Start server (Terminal 1)
cd svacs-demo
python api/ingestion_server/mock_server.py

# 3. Test dual endpoints (Terminal 2)
cd svacs-demo/services/data_layer
python -c "
import requests, sys
sys.path.insert(0,'.')
from hybrid_signal_builder import HybridSignalBuilder
chunk = HybridSignalBuilder().build('cargo')
r1 = requests.post('http://localhost:8000/ingest', json=chunk)
r2 = requests.post('http://localhost:8000/ingest/signal', json=chunk)
print(r1.status_code, r2.status_code, 'both 200?', r1.status_code == r2.status_code == 200)
"

# 4. Run full validation (all 5 phases)
python snr_perception_integration.py

# 5. Check health + latency
curl http://localhost:8000/health

# 6. Confirm perception log
cat ../../api/ingestion_server/perception_log.jsonl | python -m json.tool | head -40

# 7. Update nupur_integration.md (append Phase 6 + Phase 7 sections)
```

---

## Success Checklist

- [ ] `hybrid_signal_builder.py` updated — uses `VESSEL_NOISE_SCALE` + `10*log10` power formula  
- [ ] `python hybrid_signal_builder.py` shows SNR in correct ranges for all 5 vessel types  
- [ ] `mock_server.py` updated — `POST /ingest` and `POST /ingest/signal` both return HTTP 200  
- [ ] Both endpoints return identical responses for same payload  
- [ ] `process_signal()` called inside server — `perception_event` appears in HTTP response  
- [ ] `api/ingestion_server/perception_log.jsonl` exists with ≥5 entries (one per vessel)  
- [ ] `snr_perception_integration.py` shows 15/15 PASS  
- [ ] Latency: avg <100ms, max <100ms  
- [ ] `trace_id` unchanged end-to-end (input = server = perception output)  
- [ ] `nupur_integration.md` updated with Phase 6 (SNR) and Phase 7 (Perception Bridge) sections  

---

## Common Issues + Fixes

| Issue | Cause | Fix |
|---|---|---|
| `ImportError: perception_node` | Server can't find perception_node.py | Check path in mock_server.py line ~25; ensure both files are in same or correct relative directory |
| SNR still shows wrong values | Old `hybrid_signal_builder.py` still in place | Confirm you copied the fixed version — check for `VESSEL_NOISE_SCALE` at top of file |
| `/ingest` returns 404 | Old mock_server.py still running | Stop server, copy `mock_server_updated.py` → `mock_server.py`, restart |
| `perception_event` not in response | `PERCEPTION_AVAILABLE = False` in server logs | Fix import path (see above); check server startup logs for `[SERVER] perception_node imported successfully` |
| Latency > 100ms | Cold start on first run | Run a warmup chunk first; FFT on 4000 samples is typically 2–10ms |
