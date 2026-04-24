# Nupur — Integration Review Packet

## Status: COMPLETE

## What I Own
- `services/data_layer/` — signal generation + streaming
- `api/ingestion_server/mock_server.py` — ingestion endpoint (mock)
- `shared/schemas/signal_chunk_schema.json` — output contract

---

## Repo Layout (svacs-demo/)

All files are placed under the unified `svacs-demo/` repo. Do **not** run anything outside this root.

```
svacs-demo/
├── api/
│   └── ingestion_server/
│       └── mock_server.py
├── services/
│   └── data_layer/
│       ├── hybrid_signal_builder.py
│       ├── signal_generator.py
│       ├── streaming_simulator.py
│       ├── scenario_builder.py
│       ├── run_tests.py
│       ├── utils/
│       │   └── signal_utils.py
│       ├── scenarios/           ← generated at runtime by scenario_builder.py
│       └── example_outputs/     ← sample pre-generated chunks for reference (see below)
├── shared/
│   └── schemas/
│       └── signal_chunk_schema.json
└── streaming/                   ← streaming_simulator.py is the canonical entry point
                                    run it from services/data_layer/ (see How to Run)
```

> **`streaming/` folder note:** This folder exists as a placeholder for a future
> standalone streaming service. For now, `streaming_simulator.py` lives in
> `services/data_layer/` and is the active entry point. Do not move it.

> **`example_outputs/` note:** Contains pre-generated signal chunk JSONs for each
> vessel type. Acoustic Node and Ankita can use these for offline testing without
> running the live stream. Format is identical to live `/ingest` POST body.

---

## How to Run

>  All commands below must be run from the **repo root** (`svacs-demo/`).

### 1. Start ingestion server
```bash
python api/ingestion_server/mock_server.py
# Listens on http://localhost:8000/ingest
```

### 2. Start streaming
```bash
# Single vessel, 30 seconds
python services/data_layer/streaming_simulator.py --vessel cargo --duration 30 --endpoint http://localhost:8000/ingest

# Full demo (all 5 scenarios back-to-back)
python services/data_layer/streaming_simulator.py --demo --endpoint http://localhost:8000/ingest
```

> **Note on imports:** `streaming_simulator.py` imports `HybridSignalBuilder` using a
> relative path. If you run it from repo root and hit an import error, use:
> ```bash
> cd services/data_layer && python streaming_simulator.py --demo --endpoint http://localhost:8000/ingest
> ```

---

## Output Schema
See: `shared/schemas/signal_chunk_schema.json`

Key fields for Acoustic Node consumption:
- `samples` — array of 4000 floats (the raw acoustic signal)
- `sample_rate` — 4000 Hz, fixed
- `trace_id` — UUID4, generated fresh per chunk, present on every emission
- `vessel_type` — one of: cargo / speedboat / submarine / low_confidence / anomaly
- `expected_label.anomaly_flag` — true only for scenario 5 (anomaly)
- `snr_db` — signal-to-noise ratio in decibels

---

## Acoustic Node — Handoff

**What to consume:**
- Listen on `POST http://localhost:8000/ingest`
- Each POST body is a `signal_chunk` — full schema at `shared/schemas/signal_chunk_schema.json`

**Where to import from (if building in Python):**
```python
# From svacs-demo/services/data_layer/
from hybrid_signal_builder import HybridSignalBuilder

builder = HybridSignalBuilder(sample_rate=4000, duration=1.0)
chunk = builder.build("cargo")   # returns a pipeline-ready dict
```

**What to output** (`perception_event`):
- Must include the same `trace_id` from the incoming `signal_chunk` — do NOT generate a new one
- Must include: `vessel_type`, `confidence`, `dominant_freq_hz`, `anomaly_flag`

**FFT classification bands :**

| Vessel Type    | Frequency Range | Confidence Expected |
|----------------|-----------------|---------------------|
| cargo          | 50 – 200 Hz     | high                |
| speedboat      | 500 – 1500 Hz   | medium_high         |
| submarine      | 20 – 100 Hz     | medium (low energy) |
| low_confidence | any             | low (noise-buried)  |
| anomaly        | multi-peak      | unknown → flag it   |

**For offline testing (no live stream needed):**
Use pre-generated chunks in `services/data_layer/example_outputs/` — same schema, ready to parse.

---

## Trace ID Continuity Contract

Every chunk carries a `trace_id` (UUID4). This is the **primary identifier** for end-to-end tracing across the full pipeline.

**My guarantee (Signal Layer):**
- `trace_id` is generated fresh per chunk via `uuid.uuid4()`
- It is present on every HTTP POST to `/ingest`
- It is never null, never missing

**Downstream teams must:**
- Copy `trace_id` from input event to output event — **do NOT generate a new one**
- Never rename or drop the field
- The same `trace_id` must appear in: `perception_event` → `intelligence_event` → `state_event` → UI dashboard

**Quick verification (run after connecting to any downstream endpoint):**
```bash
cd services/data_layer && python -c "
import requests
from hybrid_signal_builder import HybridSignalBuilder
chunk = HybridSignalBuilder(4000, 1.0).build('cargo')
r = requests.post('http://localhost:8000/ingest', json=chunk)
resp = r.json()
assert resp['trace_id'] == chunk['trace_id'], 'TRACE ID MISMATCH — downstream is not preserving trace_id'
print('TRACE CONTINUITY CONFIRMED:', chunk['trace_id'][:8])
"
```

---

## Confirmed
-  `trace_id` present on every chunk (UUID4)
-  HTTP POST working to `/ingest` (HTTP 200)
-  All 5 vessel scenarios streaming
-  `anomaly_flag` set correctly on scenario 5
-  20–50ms delay between chunks (real-time simulation)
-  All files placed under `svacs-demo/` unified repo structure
-  `example_outputs/` available for offline testing by downstream teams
-  Run instructions verified from repo root
-  Acoustic Node handoff documented (import path, output contract, FFT bands)