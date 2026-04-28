"""
SVACS Ingestion Server — mock_server.py
========================================
Endpoint : POST /ingest/signal
Health   : GET  /health
Logs     : api/ingestion_server/ingestion_log.jsonl 

Every request (success OR failure) is appended to the log file.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import json
import os
import time
import re

app = FastAPI()

#  In-memory store 
received   = []   # list of trace_ids for health counter
error_log  = []   # list of rejection reasons

#  Log file (sits next to this script) 
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingestion_log.jsonl")

UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)

VALID_VESSEL_TYPES = {"cargo", "speedboat", "submarine", "low_confidence", "anomaly", "unknown"}


def write_log(entry: dict):
    """Append one JSON line to the log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def validate_chunk(chunk: dict):
    """
    Returns (True, None) if valid.
    Returns (False, reason_string) if invalid.
    """
    required = ["trace_id", "timestamp", "samples", "sample_rate", "vessel_type"]
    for field in required:
        if field not in chunk:
            return False, f"Missing required field: '{field}'"

    trace_id = chunk["trace_id"]
    if not isinstance(trace_id, str) or not trace_id:
        return False, "trace_id must be a non-empty string"
    if not UUID_RE.match(trace_id):
        return False, f"trace_id is not a valid UUID4: '{trace_id}'"

    samples = chunk["samples"]
    if not isinstance(samples, list):
        return False, "samples must be an array"
    if len(samples) == 0:
        return False, "samples array is empty"

    if not isinstance(chunk["sample_rate"], (int, float)) or chunk["sample_rate"] <= 0:
        return False, "sample_rate must be a positive number"

    if not isinstance(chunk["timestamp"], (int, float)):
        return False, "timestamp must be a number"

    vessel = chunk["vessel_type"]
    if vessel not in VALID_VESSEL_TYPES:
        return False, f"vessel_type '{vessel}' is not valid. Must be one of: {VALID_VESSEL_TYPES}"

    return True, None


#  Routes 

@app.post("/ingest/signal")
async def ingest(request: Request):
    log_entry = {
        "event":     "ingest_attempt",
        "server_ts": round(time.time(), 4),
        "client_ip": request.client.host,
    }

    #  Step 1: Parse JSON 
    try:
        chunk = await request.json()
    except Exception:
        log_entry.update({
            "status":  "REJECTED",
            "reason":  "Body is not valid JSON",
            "trace_id": None,
        })
        write_log(log_entry)
        print(f"[REJECTED] Bad JSON from {request.client.host}")
        return JSONResponse(
            status_code=400,
            content={"status": "error", "reason": "Body is not valid JSON"}
        )

    #  Step 2: Validate schema 
    ok, reason = validate_chunk(chunk)
    if not ok:
        log_entry.update({
            "status":     "REJECTED",
            "reason":     reason,
            "trace_id":   chunk.get("trace_id", None),
            "vessel_type": chunk.get("vessel_type", None),
        })
        write_log(log_entry)
        error_log.append(reason)
        print(f"[REJECTED] {reason}")
        return JSONResponse(
            status_code=422,
            content={"status": "error", "reason": reason}
        )

    #  Step 3: Accept 
    trace_id = chunk["trace_id"]
    vessel   = chunk["vessel_type"]
    n        = len(chunk["samples"])
    anomaly  = chunk.get("expected_label", {}).get("anomaly_flag", False)
    snr      = chunk.get("snr_db", "N/A")

    log_entry.update({
        "status":      "ACCEPTED",
        "trace_id":    trace_id,
        "vessel_type": vessel,
        "samples":     n,
        "anomaly_flag": anomaly,
        "snr_db":      snr,
        "chunk_ts":    chunk.get("timestamp"),
    })
    write_log(log_entry)
    received.append(trace_id)

    TRACE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trace_log.jsonl")
    with open(TRACE_LOG, "a", encoding="utf-8") as tf:
        json.dump({
            "stage":       "signal_ingest",
            "trace_id":    trace_id,
            "vessel_type": vessel,
            "chunk_ts":    chunk.get("timestamp"),
            "server_ts":   round(time.time(), 4)
        }, tf)
        tf.write("\n")

    print(
        f"[INGEST/SIGNAL] trace={trace_id[:8]}...  "
        f"vessel={vessel:<16}  samples={n}  "
        f"anomaly={anomaly}  snr={snr}"
    )

    return {"status": "ok", "trace_id": trace_id}


@app.get("/health")
def health():
    return {
        "status":          "alive",
        "chunks_received": len(received),
        "chunks_rejected": len(error_log),
        "log_file":        LOG_FILE,
        "trace_log":       TRACE_LOG,
    }


if __name__ == "__main__":
    print(f"[SERVER] Logging to: {LOG_FILE}")
    print(f"[SERVER] Starting on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)