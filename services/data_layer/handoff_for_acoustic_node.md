## Signal Layer Handoff — Acoustic Node

**Endpoint:** POST http://localhost:8000/ingest/signal
**Schema:** shared/schemas/signal_chunk_schema.json
**Sample payloads:** services/data_layer/example_outputs/example_signal_chunks.json

Key fields your parser must read:
- samples: array of 4000 floats (raw acoustic data)
- sample_rate: 4000 (always)
- trace_id: UUID4 string — COPY THIS to your output, do not generate a new one
- vessel_type: cargo / speedboat / submarine / low_confidence / anomaly
- expected_label.anomaly_flag: true ONLY for scenario 5
- snr_db: signal-to-noise ratio