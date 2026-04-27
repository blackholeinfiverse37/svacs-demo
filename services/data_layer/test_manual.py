import requests
from hybrid_signal_builder import HybridSignalBuilder

builder = HybridSignalBuilder(4000, 1.0)
for vtype in ["cargo", "speedboat", "submarine", "low_confidence", "anomaly"]:
    chunk = builder.build(vtype)
    r = requests.post("http://localhost:8000/ingest/signal", json=chunk)
    print(f"[{vtype}] HTTP {r.status_code} | trace={chunk['trace_id'][:8]} | resp={r.json()}")